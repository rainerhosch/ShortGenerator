"""
PaperBrief — Centralized Configuration
Loads environment variables and defines project-wide constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────────────────
load_dotenv()

# ── Project Paths ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
MODULES_DIR = ROOT_DIR / "modules"
ASSETS_DIR = ROOT_DIR / "assets"
OUTPUT_DIR = ROOT_DIR / "output"
FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"
WATERMARK_DIR = ASSETS_DIR / "watermark"

# Create directories if they don't exist
for d in [ASSETS_DIR, OUTPUT_DIR, FONTS_DIR, MUSIC_DIR, WATERMARK_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Video Specifications ─────────────────────────────────────────────────────
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
RENDER_DEVICE = os.getenv("RENDER_DEVICE", "cpu").lower()
VIDEO_CODEC = "h264_nvenc" if RENDER_DEVICE == "cuda" else "libx264"
AUDIO_CODEC = "aac"
TARGET_DURATION_SECONDS = 60

# ── Content Structure Timing (seconds) ───────────────────────────────────────
# Hook (0-10s) → Insight (10-40s) → Impact (40-60s)
SEGMENT_HOOK = (0, 10)       # "Ilmuwan baru saja menemukan..."
SEGMENT_INSIGHT = (10, 40)   # Methodology & findings with text overlay
SEGMENT_IMPACT = (40, 60)    # Real-world connection

# ── Subtitle & Typography ────────────────────────────────────────────────────
SUBTITLE_FONT_SIZE = 60
SUBTITLE_FONT_COLOR = "white"
SUBTITLE_BG_COLOR = (0, 0, 0, 180)  # Semi-transparent black
SUBTITLE_POSITION = ("center", "center")
WATERMARK_FONT_SIZE = 28
WATERMARK_OPACITY = 0.7

# ── API Keys ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── API Settings ─────────────────────────────────────────────────────────────
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # Default
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_monolingual_v1")

FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY", "")

# ── arXiv Defaults ───────────────────────────────────────────────────────────
DEFAULT_CATEGORY = "random"
DEFAULT_MAX_RESULTS = 5
MAX_PAPER_PAGES = 50
MIN_PAPER_PAGES = 3

# ── Background Music ─────────────────────────────────────────────────────────
BG_MUSIC_VOLUME = 0.08  # 8% volume for ambient background

# ── Retry Settings ───────────────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 2

# ── Scheduler Settings ───────────────────────────────────────────────────────
SCHEDULE_TIMES = os.getenv("SCHEDULE_TIMES", "08:00,20:00").split(",")
SCHEDULE_PAPERS_PER_RUN = int(os.getenv("SCHEDULE_PAPERS_PER_RUN", "1"))
SCHEDULE_LLM_PROVIDER = os.getenv("SCHEDULE_LLM_PROVIDER", "openrouter")
SCHEDULE_LLM_MODEL = os.getenv("SCHEDULE_LLM_MODEL", "")
SCHEDULE_TTS_PROVIDER = os.getenv("SCHEDULE_TTS_PROVIDER", "edge-tts")
SCHEDULE_LANG = os.getenv("SCHEDULE_LANG", "EN")
CLEANUP_AFTER_UPLOAD = os.getenv("CLEANUP_AFTER_UPLOAD", "true").lower() == "true"

# ── arXiv Category Pool (random pick per scheduler run) ──────────────────────
ARXIV_CATEGORIES = [
    # Computer Science (all sub-categories)
    "cs.AI", "cs.AR", "cs.CC", "cs.CE", "cs.CG", "cs.CL",
    "cs.CR", "cs.CV", "cs.CY", "cs.DB", "cs.DC", "cs.DL",
    "cs.DM", "cs.DS", "cs.ET", "cs.FL", "cs.GL", "cs.GR",
    "cs.GT", "cs.HC", "cs.IR", "cs.IT", "cs.LG", "cs.LO",
    "cs.MA", "cs.MM", "cs.MS", "cs.NA", "cs.NE", "cs.NI",
    "cs.OH", "cs.OS", "cs.PF", "cs.PL", "cs.RO", "cs.SC",
    "cs.SD", "cs.SE", "cs.SI", "cs.SY",
    # Mathematics (all sub-categories)
    "math.AC", "math.AG", "math.AP", "math.AT", "math.CA",
    "cs.AI", "cs.AR", "cs.CC", "cs.CE", "cs.CG", "cs.CL",
    "math.CO", "math.CT", "math.CV", "math.DG", "math.DS",
    "cs.CR", "cs.CV", "cs.CY", "cs.DB", "cs.DC", "cs.DL",
    "math.FA", "math.GM", "math.GN", "math.GR", "math.GT",
    "cs.DM", "cs.DS", "cs.ET", "cs.FL", "cs.GL", "cs.GR",
    "math.HO", "math.IT", "math.KT", "math.LO", "math.MG",
    "cs.GT", "cs.HC", "cs.IR", "cs.IT", "cs.LG", "cs.LO",
    "math.MP", "math.NA", "math.NT", "math.OA", "math.OC",
    "cs.MA", "cs.MM", "cs.MS", "cs.NA", "cs.NE", "cs.NI",
    "math.PR", "math.QA", "math.RA", "math.RT", "math.SG",
    "cs.OH", "cs.OS", "cs.PF", "cs.PL", "cs.RO", "cs.SC",
    "math.SP", "math.ST",
]

# ── Upload Platform Toggles ──────────────────────────────────────────────────
UPLOAD_YOUTUBE_ENABLED = os.getenv("UPLOAD_YOUTUBE", "false").lower() == "true"
UPLOAD_FACEBOOK_ENABLED = os.getenv("UPLOAD_FACEBOOK", "false").lower() == "true"
UPLOAD_TIKTOK_ENABLED = os.getenv("UPLOAD_TIKTOK", "false").lower() == "true"

# ── YouTube API (OAuth 2.0) ──────────────────────────────────────────────────
def _find_youtube_client_secrets() -> Path:
    """Find the YouTube client secrets JSON file in the root directory."""
    # First check exact match
    exact_match = ROOT_DIR / "client_secrets.json"
    if exact_match.exists():
        return exact_match
    
    # Then check for any client_secret*.json file (Google default download name)
    try:
        secrets = list(ROOT_DIR.glob("client_secret*.json"))
        if secrets:
            return secrets[0]
    except Exception:
        pass
        
    return exact_match  # Return default path even if not found

YOUTUBE_CLIENT_SECRETS = _find_youtube_client_secrets()
YOUTUBE_TOKEN_PATH = OUTPUT_DIR / ".youtube_token.json"

# ── Facebook Reels API (Graph API) ───────────────────────────────────────────
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
FACEBOOK_PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_TOKEN", "")

# ── TikTok Content Posting API ───────────────────────────────────────────────
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")


def validate_config():
    """Check that at least minimum required API keys are set."""
    warnings = []
    if not GEMINI_API_KEY and not OPENROUTER_API_KEY:
        warnings.append("⚠ No LLM API key set (GEMINI_API_KEY or OPENROUTER_API_KEY). Script generation will fail.")
    if not ELEVENLABS_API_KEY:
        warnings.append("ℹ No ELEVENLABS_API_KEY set. Falling back to Google TTS (gTTS).")
    if not OPENAI_API_KEY:
        warnings.append("ℹ No OPENAI_API_KEY set. Falling back to placeholder images.")
    return warnings
