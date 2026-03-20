FROM python:3.11-slim

# Instalasi System Dependencies
# 1. ffmpeg = untuk kompilasi video dan ekstraksi audio oleh moviepy
# 2. fonts-dejavu-core = font default untuk teks di video/subtitles
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies terisolasi dari OS
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file ke dalam container
COPY . .

# Variabel Lingkungan
ENV PYTHONUNBUFFERED=1

# Perintah default ketika container di jalankan
CMD ["python", "scheduler.py"]
