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
2. **Python Dependencies**: Install them using the provided `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
3. **FFmpeg**: Required for audio extraction, MP3 conversion, and thumbnail embedding.
   
   <details>
   <summary><b>Windows Setup Steps (Click to expand)</b></summary>

   1. Download the **ffmpeg-git-essentials.7z** or **zip** file from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/).
   2. Extract the folder using a tool like 7-Zip or WinRAR.
   3. Move the extracted folder to a permanent location (e.g., `C:\ffmpeg`).
   4. Copy the path to the `bin` folder inside it (e.g., `C:\ffmpeg\bin`).
   5. Open the Windows Start Menu, search for **"Edit the system environment variables"**, and open it.
   6. Click on the **Environment Variables...** button at the bottom right.
   7. Under *System variables*, locate and select the **`Path`** variable, then click **Edit...**.
   8. Click **New** on the right side, and paste the path to your bin folder (e.g., `C:\ffmpeg\bin`).
   9. Click **OK** on all windows to save the settings.
   10. Open a new Command Prompt or PowerShell and verify installation by running:
       ```cmd
       ffmpeg -version
       ```
   </details>

   <details>
   <summary><b>macOS Setup Steps (Click to expand)</b></summary>

   1. Open Terminal.
   2. Install Homebrew (if not already installed) by running:
      ```bash
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      ```
   3. Install FFmpeg:
      ```bash
      brew install ffmpeg
      ```
   </details>

   <details>
   <summary><b>Linux Setup Steps (Click to expand)</b></summary>

   - **Ubuntu/Debian:**
     ```bash
     sudo apt update && sudo apt install ffmpeg -y
     ```
   - **Fedora/CentOS:**
     ```bash
     sudo dnf install ffmpeg -y
     ```
   - **Arch Linux:**
     ```bash
     sudo pacman -S ffmpeg
     ```
   </details>

---

## 🚀 Usage

### 1. Download a single song (by name search)
```bash
python lootbeats.py -s "Billie Eilish - WILDFLOWER" -d ./music
```

### 2. Download a specific YouTube URL
```bash
python lootbeats.py -s "https://youtu.be/l08Zw-RY__Q" -d ./music
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
