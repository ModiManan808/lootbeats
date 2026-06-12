#!/usr/bin/env python3
"""
songdl.py — Fast parallel YouTube → MP3 downloader

Usage:
  Single song:
    python songdl.py -s "Bohemian Rhapsody Queen" -d ./music

  YouTube URL:
    python songdl.py -s "https://www.youtube.com/watch?v=fJ9rUzIMcZQ" -d ./music

  List from file (one song per line, names or URLs):
    python songdl.py -l songs.txt -d ./music

  Parallel workers (default 3, max 10):
    python songdl.py -l songs.txt -d ./music --workers 4

  Force re-download already existing songs:
    python songdl.py -l songs.txt -d ./music --no-skip
"""

import argparse
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import yt_dlp
except ImportError:
    print("[ERROR] yt-dlp is not installed.  Run: pip install yt-dlp")
    sys.exit(1)

# Global lock — keeps parallel output from interleaving
_print_lock = threading.Lock()

def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


# ── URL / video-ID helpers ────────────────────────────────────────────────────

def is_url(query: str) -> bool:
    return query.startswith("http://") or query.startswith("https://")


def extract_video_id(url: str) -> str | None:
    """Pull the 11-char YouTube video ID from any YouTube URL format."""
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


# ── Download index (tracks video IDs so filenames stay clean) ────────────────

INDEX_FILE = ".songdl_index"   # hidden file inside the destination folder

def _index_path(dest: str) -> str:
    return os.path.join(dest, INDEX_FILE)

def load_index(dest: str) -> set:
    """Load the set of already-downloaded video IDs from the index file."""
    path = _index_path(dest)
    if not os.path.isfile(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}

def save_to_index(dest: str, video_id: str) -> None:
    """Append a video ID to the index file (thread-safe via lock)."""
    with _print_lock:
        with open(_index_path(dest), "a", encoding="utf-8") as f:
            f.write(video_id + "\n")

# Load index once at startup; shared across all threads
_downloaded_ids: set = set()
_index_lock = threading.Lock()

def mark_downloaded(dest: str, video_id: str) -> None:
    with _index_lock:
        _downloaded_ids.add(video_id)
        save_to_index(dest, video_id)

def is_in_index(video_id: str) -> bool:
    with _index_lock:
        return video_id in _downloaded_ids


# ── Already-downloaded check ──────────────────────────────────────────────────

def already_downloaded(dest: str, query: str) -> bool:
    """
    Returns True if the song was already downloaded.

    URL  → check video ID against the index file (.songdl_index)
    Text → match all significant words against existing .mp3 filenames
    """
    if is_url(query):
        vid_id = extract_video_id(query)
        return bool(vid_id and is_in_index(vid_id))
    else:
        if not os.path.isdir(dest):
            return False
        words = [w.lower() for w in query.split() if len(w) > 2]
        if not words:
            return False
        for fname in os.listdir(dest):
            if fname.endswith(".mp3") and all(w in fname.lower() for w in words):
                return True
        return False


# ── Storage check ─────────────────────────────────────────────────────────────

MIN_FREE_MB  = 100  # warn below this
ABORT_FREE_MB = 20  # hard stop below this
MB_PER_SONG  = 12   # ~8-10 MB typical 320kbps MP3, 12 MB to be safe

def free_space_mb(path: str) -> float:
    return shutil.disk_usage(path).free / (1024 * 1024)


def check_storage(dest: str, song_count: int) -> None:
    free_mb   = free_space_mb(dest)
    needed_mb = song_count * MB_PER_SONG

    if free_mb < ABORT_FREE_MB:
        print(f"\n[ERROR] Storage full! Only {free_mb:.1f} MB free.")
        print(f"        Free up space and try again.")
        sys.exit(1)

    if free_mb < MIN_FREE_MB:
        print(f"[WARN]  Very low disk space: {free_mb:.1f} MB free — "
              f"downloads may fail mid-way!")
    elif free_mb < needed_mb:
        print(f"[WARN]  Low space: {free_mb:.0f} MB free, "
              f"~{needed_mb} MB needed for {song_count} song(s). Continuing …")
    else:
        print(f"[INFO]  Disk space OK — {free_mb/1024:.1f} GB free.")


# ── yt-dlp options ────────────────────────────────────────────────────────────

def build_opts(dest: str, retries: int) -> dict:
    return {
        "default_search": "ytsearch1",

        # Audio-only streams — [vcodec=none] ensures no video track is picked.
        # YouTube's best native audio is opus/webm at up to 251kbps.
        "format": (
            "bestaudio[ext=webm][vcodec=none]/"
            "bestaudio[ext=m4a][vcodec=none]/"
            "bestaudio[vcodec=none]/"
            "bestaudio"
        ),

        # Always pick the highest bitrate, prefer opus, 48kHz sample rate
        "format_sort": ["abr:320", "asr:48000", "acodec:opus"],

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",   # highest MP3 quality
            },
            {"key": "FFmpegMetadata"},       # embed ID3 tags
            {"key": "EmbedThumbnail"},       # embed cover art
        ],

        "writethumbnail": True,

        # Original song title as filename — clean and readable
        "outtmpl": os.path.join(dest, "%(title)s.%(ext)s"),

        "noplaylist": True,
        "retries": retries,
        "fragment_retries": retries,
        "socket_timeout": 20,
        "youtube_include_dash_manifest": False,
        "quiet": True,
        "no_warnings": True,
        "noprogress": False,
        "ignoreerrors": False,
    }


# ── Single-song worker ────────────────────────────────────────────────────────

def download_one(query: str, dest: str, index: int, total: int,
                 retries: int, skip: bool) -> tuple[bool, str]:
    label = f"[{index}/{total}]"

    # Skip check
    if skip and already_downloaded(dest, query):
        tprint(f"{label} ⏭  Already downloaded, skipping: {query!r}")
        return True, query

    # For URLs, extract the video ID upfront so we can record it after download
    vid_id = extract_video_id(query) if is_url(query) else None

    def progress_hook(d):
        if d["status"] == "downloading":
            pct   = d.get("_percent_str", "?%").strip()
            speed = d.get("_speed_str",   "?").strip()
            eta   = d.get("_eta_str",     "?").strip()
            tprint(f"  {label} {pct}  {speed}  ETA {eta}    ", end="\r", flush=True)
        elif d["status"] == "finished":
            tprint(f"  {label} Download done, converting …        ")
        elif d["status"] == "error":
            # Capture video ID from yt-dlp info dict if we didn't get it from URL
            nonlocal vid_id
            if not vid_id and d.get("info_dict"):
                vid_id = d["info_dict"].get("id")

    # Use a post-processor hook to grab the video ID from search results
    # (when query is a song name, not a URL, we don't know the ID upfront)
    resolved_id = [None]

    class IDCapture(yt_dlp.postprocessor.common.PostProcessor):
        def run(self, info):
            resolved_id[0] = info.get("id")
            return [], info

    opts = build_opts(dest, retries)
    opts["progress_hooks"] = [progress_hook]

    tprint(f"\n{label} ↓  {query!r}\n" + "─" * 60)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.add_post_processor(IDCapture(), when="pre_process")
            ret = ydl.download([query])
        if ret == 0:
            # Record the video ID so future runs can skip this song
            final_id = vid_id or resolved_id[0]
            if final_id:
                mark_downloaded(dest, final_id)
            tprint(f"{label} ✓  Done: {query!r}")
            return True, query
        else:
            tprint(f"{label} ✗  Failed (exit {ret}): {query!r}")
            return False, query

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "No video formats" in msg or "Unsupported URL" in msg:
            tprint(f"{label} ✗  Not found / bad URL: {query!r}")
        elif "Unable to download" in msg:
            tprint(f"{label} ✗  Network error: {query!r}")
        else:
            tprint(f"{label} ✗  {query!r}: {msg.strip()}")
        return False, query

    except yt_dlp.utils.ExtractorError as e:
        tprint(f"{label} ✗  Extractor error: {query!r}: {e}")
        return False, query

    except OSError as e:
        # Catch disk-full errors that happen during write / ffmpeg conversion
        if e.errno in (28, 112):  # ENOSPC on Linux/Mac, ERROR_DISK_FULL on Windows
            tprint(f"{label} ✗  STORAGE FULL while downloading {query!r}!")
            tprint(f"        Free up disk space and re-run.")
            # Propagate so the main thread can abort remaining downloads
            raise
        tprint(f"{label} ✗  OS error for {query!r}: {e}")
        return False, query

    except KeyboardInterrupt:
        tprint(f"\n[ABORT] Interrupted: {query!r}")
        raise

    except Exception as e:
        tprint(f"{label} ✗  Unexpected ({type(e).__name__}): {query!r}: {e}")
        return False, query


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_list(path: str) -> list:
    if not os.path.isfile(path):
        print(f"[ERROR] List file not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        print(f"[ERROR] List file is empty: {path}")
        sys.exit(1)
    return lines


def ensure_dest(dest: str) -> str:
    dest = os.path.expanduser(dest)
    try:
        os.makedirs(dest, exist_ok=True)
    except OSError as e:
        print(f"[ERROR] Cannot create '{dest}': {e}")
        sys.exit(1)
    return dest


def dedup(songs: list) -> list:
    seen, out = set(), []
    for s in songs:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        prog="songdl",
        description="Fast parallel YouTube → MP3 downloader.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    inp = p.add_argument_group("Input (at least one required)")
    inp.add_argument("-s", "--song", metavar="QUERY", help="Song name or YouTube URL.")
    inp.add_argument("-l", "--list", metavar="FILE",  help=".txt file, one song per line.")

    p.add_argument("-d", "--destination", metavar="DIR", default="./downloads",
                   help="Save folder (default: ./downloads).")
    p.add_argument("--workers", metavar="N", type=int, default=3,
                   help="Parallel workers (default: 3, max: 10).")
    p.add_argument("--retries", metavar="N", type=int, default=3,
                   help="Retries per song on network error (default: 3).")
    p.add_argument("--no-skip", action="store_true",
                   help="Re-download even if song already exists.")

    args = p.parse_args()
    if not args.song and not args.list:
        p.error("Provide at least -s SONG or -l LIST (or both).")
    if not 1 <= args.workers <= 10:
        p.error("--workers must be between 1 and 10.")
    return args


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args    = parse_args()
    dest    = ensure_dest(args.destination)
    skip    = not args.no_skip

    songs = []
    if args.list:
        from_file = read_list(args.list)
        print(f"[INFO]  Loaded {len(from_file)} song(s) from {args.list!r}")
        songs.extend(from_file)
    if args.song:
        songs.append(args.song)

    songs   = dedup(songs)
    total   = len(songs)
    workers = min(args.workers, total)

    # Load already-downloaded index into memory
    global _downloaded_ids
    _downloaded_ids = load_index(dest)
    if _downloaded_ids:
        print(f"[INFO]  Index loaded — {len(_downloaded_ids)} previously downloaded video(s).")

    # Storage check before we start
    check_storage(dest, total)

    print(f"\n{'═' * 60}")
    print(f"  Songs      : {total}")
    print(f"  Workers    : {workers}  (parallel)")
    print(f"  Skip exist : {'yes' if skip else 'no'}")
    print(f"  Destination: {os.path.abspath(dest)}")
    print(f"{'═' * 60}")

    ok_list, fail_list = [], []
    start = time.time()
    storage_full = False

    if workers == 1:
        for i, song in enumerate(songs, 1):
            try:
                success, _ = download_one(song, dest, i, total, args.retries, skip)
                (ok_list if success else fail_list).append(song)
            except OSError:
                fail_list.append(song)
                storage_full = True
                break
    else:
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(download_one, song, dest, i, total, args.retries, skip): song
                    for i, song in enumerate(songs, 1)
                }
                for f in as_completed(futures):
                    try:
                        success, song = f.result()
                        (ok_list if success else fail_list).append(song)
                    except OSError:
                        song = futures[f]
                        fail_list.append(song)
                        storage_full = True
                        pool.shutdown(wait=False, cancel_futures=True)
                        break
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        song = futures[f]
                        tprint(f"[ERROR] Worker crashed for {song!r}: {e}")
                        fail_list.append(song)
        except KeyboardInterrupt:
            tprint("\n[ABORT] Cancelled — partial results below.")

    elapsed = time.time() - start

    print(f"\n{'═' * 60}")
    if storage_full:
        print(f"  ⚠  STOPPED EARLY — Disk is full!")
        print(f"     Free up space then re-run (already downloaded songs will be skipped).")
    print(f"  Finished in {elapsed:.1f}s")
    print(f"  ✓  Success : {len(ok_list)}")
    print(f"  ✗  Failed  : {len(fail_list)}")
    if fail_list:
        print(f"\n  Failed songs:")
        for s in fail_list:
            print(f"    • {s}")
    print(f"{'═' * 60}\n")

    sys.exit(0 if not fail_list else 1)


if __name__ == "__main__":
    main()
