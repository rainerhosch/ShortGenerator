# 📄 PaperBrief — Automated Research Short Video Generator

**PaperBrief** is a fully automated Python pipeline that continuously turns the latest arXiv research papers into highly engaging, 60-second vertical videos for YouTube Shorts, TikTok, and Instagram Reels. 

With zero human intervention, PaperBrief regularly fetches fresh academic papers, writes captivating scripts using advanced LLMs (via OpenRouter/Gemini), narrates them using hyper-realistic neural TTS, assembles a dynamic video with *Ken Burns* effects and LaTeX formula overlays, and autonomously uploads the final product to your social media channels.

---

## ✨ Features

- **End-to-end Automation**: From raw research PDF to a published YouTube Short in minutes.
- **Smart Paper Selection**: Automatically fetches the latest non-duplicate papers from randomized or specific arXiv categories.
- **High-Quality AI Narration**: Built-in support for **ElevenLabs** as well as a 100% free fallback to Microsoft Azure's **Edge-TTS** (Premium Neural voices).
- **Hardware Acceleration**: Supports Nvidia GPUs (`--device cuda` / `h264_nvenc`) to assemble and render videos blazingly fast.
- **Dynamic Video Assembly**: Generates Karaokee-style pop-up subtitles, progress bars, contextual insight overlays, watermarks, and LaTeX formula extraction.
- **Headless Uploading**: Real OAuth 2.0 integration for headless, permission-persistent automated uploads to YouTube.
- **Built-in Scheduler**: A robust `scheduler.py` daemon to run content generation routines 2x a day continuously.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- `ffmpeg` installed on your system and added to your OS PATH.
- (Optional) Nvidia GPU for `cuda` parallel encoding rendering.

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/yourusername/PaperBrief.git
cd PaperBrief
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` (or create one) and fill in your configuration:
```ini
OPENROUTER_API_KEY="your_api_key_here"
ELEVENLABS_API_KEY="" # Leave blank to use Edge-TTS for free
UPLOAD_YOUTUBE=true
SCHEDULE_LANG=ID
```

### 4. YouTube Authentication (One-time Setup)
If you want to use the auto-upload feature to YouTube:
1. Obtain `client_secrets.json` from [Google Cloud Console](https://console.cloud.google.com/) (Must be **Desktop App** OAuth 2.0 type).
2. Place the file in the project's root directory.
3. Run the authenticator:
```bash
python youtube_auth.py
```
*(Your browser will open. Log in and accept the permissions. A `.youtube_token.json` file will be generated and saved, granting the script perpetual headless access to upload videos).*

---

## 💻 Usage

### Interactive Mode
Launch the interactive wizard to guide you through generating a video step-by-step:
```bash
python main.py
```

### Command Line Mode
Process a single paper forcefully:
```bash
python main.py --arxiv-id 2401.12345 --device cuda --lang ID
```

Process a batch from a specific category:
```bash
python main.py --category cs.AI --max-papers 3 --device cuda
```

Run the scheduler exactly once immediately:
```bash
python scheduler.py --run-once --device cuda
```

---

## ☁️ Server Deployment (Ubuntu / Systemd)

To make `scheduler.py` run continuously in the background on an Ubuntu Server and start automatically when the server reboots, the industry-standard approach is to use `systemd`.

### Step 1: Transfer Files to the Server
Upload your entire project to the server. 
**Crucial:** Ensure you also upload the `.youtube_token.json` that you generated previously on your local computer so the server doesn't get blocked by browser verification.

### Step 2: Create a Systemd Service File
Open your server terminal and create a new service file:
```bash
sudo nano /etc/systemd/system/paperbrief.service
```

### Step 3: Configure the Service
Paste the following configuration into the file. **Make sure to change `User`, `WorkingDirectory`, and `ExecStart`** to match your server's actual setup:

```ini
[Unit]
Description=PaperBrief YouTube Auto-Uploader Daemon
After=network.target

[Service]
Type=simple
# Ubah dengan username server Anda (misal: ubuntu atau root)
User=ubuntu

# Ubah sesuai dengan path direktori project Anda disimpan di server
WorkingDirectory=/home/ubuntu/ShortGenerator

# Ubah path ke binary python Anda. Sangat disarankan merujuk ke venv jika ada.
ExecStart=/usr/bin/python3 scheduler.py

# Script akan otomatis restart dalam 10 detik jika mengalami crash
Restart=always
RestartSec=10

# Tambahkan logging environment Variables jika perlu
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```
*Save and exit (Ctrl+O, Enter, Ctrl+X).*

### Step 4: Enable and Start the Service
Reload the systemd daemon so it recognizes your new service:
```bash
sudo systemctl daemon-reload
```

Start the service running right now:
```bash
sudo systemctl start paperbrief.service
```

**Enable the service so it runs automatically every time the server boots:**
```bash
sudo systemctl enable paperbrief.service
```

### Step 5: Check Logs
You can monitor the bot running in the background live by checking the service logs at any time:
```bash
sudo journalctl -u paperbrief.service -f
```

---

*PaperBrief — Turning academic PDFs into endless streams.*
