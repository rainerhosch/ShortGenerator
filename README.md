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

## 🐳 Server Deployment (Docker Compose)

Running this bot on an Ubuntu server is completely hassle-free with Docker. It bypasses complex `venv` setups (PEP 668 issues) and automatically packs `ffmpeg` and required fonts in one clean package.

### Step 1: Install Docker
If you haven't installed Docker on your server, do it first:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

### Step 2: Transfer Files
Ensure you've uploaded your project folder to the server. 
**Crucial Items:** Ensure `.env`, `client_secrets.json`, and the previously generated `.youtube_token.json` are present inside the folder.

### Step 3: Start the Bot
Run the Docker Compose detached daemon:
```bash
sudo docker compose up -d
```

### Checking Logs
Watch the scheduler working seamlessly in the background:
```bash
sudo docker compose logs -f
```

*(Note for NVENC/GPU users: If you want blazing fast encoding in Docker, make sure you've installed the `Nvidia Container Toolkit` on your server and uncommented the `deploy` block in `docker-compose.yml`.)*

---

*PaperBrief — Turning academic PDFs into endless streams.*
