# 📄 PaperBrief — Generator Video Edukasi Otomatis (arXiv to Shorts)

**PaperBrief** adalah *pipeline* otomatis berbasis Python yang terus-menerus mengubah publikasi riset terbaru dari arXiv menjadi video vertikal (Shorts/Reels/TikTok) berdurasi 60 detik yang sangat menarik.

Tanpa perlu campur tangan manusia, PaperBrief rutin mengambil paper akademik terbaru, menulis ulang naskah yang memikat menggunakan LLM tingkat lanjut (via OpenRouter/Gemini), menarasikannya dengan model *Text-to-Speech* Neural yang sangat realistis (Edge-TTS sekelas ElevenLabs), lalu merakit keseluruhan video secara dinamis (lengkap dengan efek *Ken Burns*, *subtitle karaoke*, serta ekstraksi rumus LaTeX), dan mengunggahnya secara mandiri ke kanal media sosial Anda.

---

## ✨ Fitur Utama

- **End-to-End Automation**: Dari file mentah PDF penelitian hingga publikasi YouTube Shorts dalam hitungan menit.
- **Smart Paper Selection**: Otomatisasi pengambilan paper terbaru anti-duplikat. Mendukung fitur acak kategori dari puluhan ruang lingkup arXiv.
- **Suara AI Kelas Premium**: Pilihan integrasi berbayar **ElevenLabs** atau menggunakan alternatif gratis tak terbatas **Edge-TTS** (Microsoft Azure Neural Voices) dengan irama *edukator*.
- **Hardware Acceleration**: Dukungan *rendering* menggunakan Nvidia GPU (`--device cuda` / `h264_nvenc`) untuk proses kompilasi video super cepat tanpa membebani CPU.
- **Dynamic Video Assembly**: Sistem pembuatan *Subtitle* berirama/gaya *karaoke*, bilah kemajuan (*progress bar*), sorotan teks besar, serta otomatisasi ekstrak rumus LaTeX (Matematika).
- **Headless Auto-Uploader**: Pendekatan integrasi OAuth 2.0 asli (*Refresh Token*) untuk memastikan video sukses tertayang di YouTube API secara _headless_ (tanpa perlu klik izin browser berulang kali di server).
- **Built-in Daemon/Scheduler**: Modul `scheduler.py` yang kuat untuk di-deploy di sistem 24/7.
- **Auto-Cleanup Storage**: Terhindar dari memori penuh dengan fitur penghapusan pintar *storage server* pasca proses unggah selesai.

---

## 🚀 Panduan Memulai Cepat (Local / PC Pribadi)

### 1. Prasyarat Sistem
- Python 3.10+
- `ffmpeg` telah terinstal di sistem dan masuk dalam lintasan (PATH) terminal.
- *(Opsional)* VGA Nvidia untuk menjalankan opsi rendering paralel `cuda`.

### 2. Instalasi
Kloning repositori dan instal ketergantungannya:
```bash
git clone https://github.com/yourusername/PaperBrief.git
cd PaperBrief
pip install -r requirements.txt
```

### 3. Konfigurasi
Gandakan file pancingan `.env.example` ke file baru bernama `.env` lalu isikan konfigurasi Anda:
```ini
OPENROUTER_API_KEY="kunci_api_anda"
ELEVENLABS_API_KEY="" # Kosongkan agar otomatis menggunakan suara narator gratis dari Edge-TTS
UPLOAD_YOUTUBE=true
SCHEDULE_LANG=ID
CLEANUP_AFTER_UPLOAD=true
```

### 4. Otentikasi Saluran YouTube (Cukup Lakukan 1x Seumur Hidup)
Bila ingin fitur publikasi otomatis beroperasi layaknya bot sungguhan:
1. Dapatkan token mentah `client_secrets.json` dari [Google Cloud Console](https://console.cloud.google.com/) (Pilih tipe *OAuth Application*: **Desktop App**).
2. Taruh persis di folder utama proyek ini.
3. Eksekusi skrip komando pembuka izin:
```bash
python youtube_auth.py
```
*(Browser akan otomatis terbuka. Login dan setujui izin pada saluran YouTube Anda. Sebuah file `.youtube_token.json` akan tercipta secara ajaib dan menjadi tiket paspor mutlak untuk otomasi masa depan bot).*

---

## 💻 Cara Penggunaan

### Mode Interaktif
Jalankan menu pemilih interaktif (Wizard):
```bash
python main.py
```

### Mode Command Line (Via Terminal Langsung)
Memproses secara paksa untuk 1 ID paper spesifik:
```bash
python main.py --arxiv-id 2401.12345 --device cuda --lang ID
```

Menarik 3 abstrak sekaligus untuk kategori kecerdasan buatan:
```bash
python main.py --category cs.AI --max-papers 3 --device cuda
```

Memanggil Modul Penjadwalan 1x putaran seketika tanpa perlu menunggu dering alarm waktu:
```bash
python scheduler.py --run-once --device cuda --lang ID
```

---

## 🐳 Server Deployment (Lingkungan Production)

Aplikasi ini sudah disegel dengan Docker. Menjalankan sistem ini selama 24 jam nonstop di atas OS Server (seperti Ubuntu/Debian/Centos) kini sangat direkomendasikan memakai **Docker Container**. Hal ini wajib menimbang ketegasan sistem proteksi penulisan kode Python ala Linux modern (`PEP 668`), serta untuk membebaskan Anda dari belitan rumit mengurai paket `ffmpeg`.

### Tahap 1: Transfer File ke Server Baru Anda
Bawa pindahkan seluruh kode proyek (folder ini) ke Sever VPS Anda. 
**PENTING MUTLAK:** Sangat diwajibkan untuk menstansfer seluruh file inti Anda termasuk `.env`, `client_secrets.json`, dan hasil ekstraksi lokal **`.youtube_token.json`** . Langkah ini akan membuahkan hasil agar di server tidak terjadi hambatan pop-up browser apapun.

### Tahap 2: Menyalakan Mesin (*Build & Up*)
Jalankan komando ini saat masuk ke folder sistem di Server Ubuntu penampung Anda:
```bash
sudo docker compose up -d --build
```

### Tahap 3: Pembersihan dan Pembangunan Ulang Sempurna (Optional)
Apabila sebelumnya image Anda membengkak bergiga-giga byte memori dan Anda baru saja mensetting file pencegah `.dockerignore`, lakukan pembangunan ulang kontainer tanpa cache lama dengan komando keras ini:
```bash
sudo docker compose build --no-cache
sudo docker compose up -d
```

### Cek Terminal Latar Belakang (Logs)
Berhentilah merasa cemas. Simak seluruh aktivitas *daemon scheduler* bekerja mandiri dari mengolah abstrak matematika hingga mengirimkannya di YouTube melalui log dari cermin Docker:
```bash
sudo docker compose logs -f
```

*(Catatan khusus bagi sultan server GPU NVENC: Agar fitur rekayasa Docker ini berjalan super kencang dalam perakitan videonya, pastikan injeksi komponen resmi `Nvidia Container Toolkit` sudah terestrak rapi di komputer Linux host mesin Anda, dan perbolehkan izin `deploy --> driver: nvidia` di berkas `docker-compose.yml` berinteraksi).*

---
*PaperBrief — Mengubah tumpukan PDF karya tulis membosankan menjadi luapan hiburan pengetahuan tiada henti.*
