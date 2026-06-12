# 🎵 Lootbeats

A fast, multithreaded YouTube-to-MP3 downloader written in Python. `lootbeats` allows you to download music by single song name, YouTube URL, or batch lists from a text file, leveraging parallel workers for high performance.

---

## ✨ Features

- **Parallel Downloads:** Supports concurrent downloads using up to 10 workers (threads) to maximize download speed.
- **Smart Duplicate Prevention:** 
  - Automatically indexes downloaded YouTube video IDs in a `.songdl_index` file.
  - Performs keyword matching on target directories to skip files that have already been downloaded.
- **Robust Storage Management:** Checks available storage before download starts and halts automatically if space is critically low, avoiding corrupt/partial files.
- **High Quality Audio & Metadata:** 
  - Extracts the best audio formats and converts them to **320kbps MP3** via FFmpeg.
  - Automatically embeds ID3 metadata tags.
  - Embeds YouTube video thumbnail as MP3 cover art.
- **Flexible Inputs:** Accepts direct song search queries, YouTube URLs, or batch text files (e.g., `songs.txt`).

---

## 🛠️ Prerequisites

To run Lootbeats, you will need:

1. **Python 3.x**
2. **`yt-dlp`**: Python library for downloading. Install it via pip:
   ```bash
   pip install yt-dlp
   ```
3. **FFmpeg**: Required for audio extraction, MP3 conversion, and thumbnail embedding.
   - **Windows:** Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add its `bin` folder to your system PATH.
   - **macOS:** Install via Homebrew: `brew install ffmpeg`
   - **Linux:** Install via package manager: `sudo apt install ffmpeg`

---

## 🚀 Usage

### 1. Download a single song (by name search)
```bash
python lootbeats.py -s "Bohemian Rhapsody Queen" -d ./music
```

### 2. Download a specific YouTube URL
```bash
python lootbeats.py -s "https://www.youtube.com/watch?v=fJ9rUzIMcZQ" -d ./music
```

### 3. Bulk download from a text file
Create a text file (e.g., `songs.txt`) with one query or URL per line, then run:
```bash
python lootbeats.py -l songs.txt -d ./music
```

### 4. Adjust parallel download threads (workers)
Set the number of concurrent worker threads (default is 3, maximum is 10):
```bash
python lootbeats.py -l songs.txt -d ./music --workers 5
```

### 5. Force re-download existing songs
By default, the script skips already-downloaded songs. To force downloading everything:
```bash
python lootbeats.py -l songs.txt -d ./music --no-skip
```

---

## ⚙️ Options & Arguments

| Argument | Long Flag | Description | Default |
|---|---|---|---|
| `-s` | `--song` | Single song search query or YouTube URL | None |
| `-l` | `--list` | Path to a text file with one song search query/URL per line | None |
| `-d` | `--destination` | Folder to save the downloaded MP3 files | `./downloads` |
| | `--workers` | Number of parallel worker threads (1 to 10) | `3` |
| | `--retries` | Number of download retries on network error | `3` |
| | `--no-skip` | Force downloading even if the file exists in index/folder | False |

---

> [!NOTE]
> Ensure FFmpeg is fully installed and added to your system environment variables. If FFmpeg is missing, `yt-dlp` will download files but will fail to convert them to MP3 or embed metadata.
