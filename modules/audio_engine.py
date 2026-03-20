"""
PaperBrief — Audio Generation Module
Converts narration scripts to speech audio using ElevenLabs or Google TTS.
"""

import logging
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

import config

logger = logging.getLogger(__name__)


# ── ElevenLabs TTS ───────────────────────────────────────────────────────────

def _elevenlabs_tts(text: str, output_path: Path) -> Path:
    """Generate audio using ElevenLabs API."""
    if not config.ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY is not set.")

    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

    audio_generator = client.text_to_speech.convert(
        voice_id=config.ELEVENLABS_VOICE_ID,
        model_id=config.ELEVENLABS_MODEL_ID,
        text=text,
        output_format="mp3_44100_128",
    )

    # Write the generator output to file
    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)

    logger.info(f"ElevenLabs audio saved to {output_path}")
    return output_path


# ── Google TTS (Free Fallback) ───────────────────────────────────────────────

# Language code mapping for gTTS
GTTS_LANG_MAP = {
    "EN": "en",
    "ID": "id",
    "ES": "es",
    "FR": "fr",
    "DE": "de",
    "JA": "ja",
    "KO": "ko",
    "ZH": "zh-CN",
    "PT": "pt",
    "AR": "ar",
}


def _enhance_gtts_rhythm(text: str) -> str:
    """
    Hack to improve gTTS naturalness by manipulating punctuation.
    gTTS relies heavily on punctuation to dictate rhythm and pauses.
    """
    import re
    # 1. Force phrase boundaries (slight breath/pause) before conjunctions
    conjunctions = [
        " karena ", " tetapi ", " namun ", " sehingga ", 
        " bahwa ", " untuk ", " dengan ", " serta ",
        " because ", " however ", " therefore ", " so ", " which "
    ]
    for conj in conjunctions:
        # Add a comma before conjunctions if one doesn't exist already
        text = re.sub(rf"(?<!,){conj}", f", {conj.strip()} ", text, flags=re.IGNORECASE)

    # 2. Add dramatic/TikTok-style micro-pauses using ellipses
    text = text.replace(",", ", ... ")
    text = text.replace(".", ". ... ")
    text = text.replace("!", "! ... ")
    text = text.replace("?", "? ... ")
    
    # 3. Clean up any artifacts like double ellipses
    text = re.sub(r'(\s*\.\.\.\s*)+', ' ... ', text)
    
    return text.strip()


def _google_tts(text: str, output_path: Path, lang: str = "EN") -> Path:
    """Generate audio using Google TTS (gTTS) — free, no API key required."""
    from gtts import gTTS

    gtts_lang = GTTS_LANG_MAP.get(lang.upper(), "en")
    
    # Apply rhythm and pacing configurations
    rhythmic_text = _enhance_gtts_rhythm(text)
    
    tts = gTTS(text=rhythmic_text, lang=gtts_lang, slow=False)
    tts.save(str(output_path))

    logger.info(f"gTTS audio saved to {output_path} (lang: {gtts_lang})")
    return output_path


# ── Edge TTS (High Quality Free Fallback) ────────────────────────────────────

EDGE_VOICE_MAP = {
    # "EN": "en-US-ChristopherNeural",
    "EN": "en-US-AvaNeural",
    # "ID": "id-ID-ArdiNeural",  # Excellent Indonesian male voice, sounds like an educator
    "ID": "id-ID-GadisNeural-Female",  # Excellent Indonesian male voice, sounds like an educator
    "ES": "es-ES-AlvaroNeural",
    "FR": "fr-FR-HenriNeural",
    "DE": "de-DE-KillianNeural",
    "JA": "ja-JP-KeitaNeural",
    "KO": "ko-KR-InJoonNeural",
    "ZH": "zh-CN-YunxiNeural",
    "PT": "pt-BR-AntonioNeural",
    "AR": "ar-SA-HamedNeural",
}

def _edge_tts(text: str, output_path: Path, lang: str = "EN") -> Path:
    """Generate audio using Edge TTS (Microsoft Neural Voices). Free, no API key."""
    import asyncio
    import edge_tts

    voice = EDGE_VOICE_MAP.get(lang.upper(), "en-US-AvaNeural")
    
    # Custom educator intonation: +10% speed for better retention in Shorts
    rate = "+10%"
    
    async def _generate():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(output_path))

    asyncio.run(_generate())
    logger.info(f"Edge TTS audio saved to {output_path} (voice: {voice})")
    return output_path


# ── Audio Duration ───────────────────────────────────────────────────────────

def get_audio_duration(audio_path: Path) -> float:
    """Get duration of an audio file in seconds using moviepy."""
    from moviepy import AudioFileClip

    with AudioFileClip(str(audio_path)) as clip:
        duration = clip.duration

    return duration


# ── Segment Audio Generation ─────────────────────────────────────────────────

def generate_segment_audio(script: dict, output_dir: Path,
                           provider: str = "elevenlabs",
                           lang: str = "EN") -> dict:
    """
    Generate separate audio files for each segment (hook, insight, impact).

    Args:
        script: Dict with keys 'hook', 'insight', 'impact'
        output_dir: Directory to save audio files
        provider: "elevenlabs" or "gtts"
        lang: Language code ("EN", "ID", etc.) — used for gTTS

    Returns:
        Dict with segment audio paths and durations.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    tts_func = _get_tts_function(provider)
    segments = {}

    for segment_name in ["hook", "insight", "impact"]:
        text = script.get(segment_name, "")
        if not text:
            logger.warning(f"Empty text for segment '{segment_name}'. Skipping.")
            continue

        audio_path = output_dir / f"{segment_name}.mp3"
        try:
            # Pass lang formatting to the free providers (ElevenLabs auto-detects via multilingual model)
            fallback_enabled = (provider == "elevenlabs" and not config.ELEVENLABS_API_KEY)
            if provider == "edge-tts" or fallback_enabled:
                _edge_tts(text, audio_path, lang=lang)
            elif provider == "gtts":
                _google_tts(text, audio_path, lang=lang)
            else:
                tts_func(text, audio_path)
            duration = get_audio_duration(audio_path)
            segments[segment_name] = {"path": audio_path, "duration": duration}
            logger.info(f"Segment '{segment_name}': {duration:.1f}s")
        except Exception as e:
            logger.error(f"Failed to generate audio for '{segment_name}': {e}")
            raise

    # Also generate the full combined narration
    full_text = script.get("full_narration", "")
    if full_text:
        full_path = output_dir / "full_narration.mp3"
        fallback_enabled = (provider == "elevenlabs" and not config.ELEVENLABS_API_KEY)
        if provider == "edge-tts" or fallback_enabled:
            _edge_tts(full_text, full_path, lang=lang)
        elif provider == "gtts":
            _google_tts(full_text, full_path, lang=lang)
        else:
            tts_func(full_text, full_path)
        full_duration = get_audio_duration(full_path)
        segments["full"] = {"path": full_path, "duration": full_duration}
        logger.info(f"Full narration: {full_duration:.1f}s")

    return segments


# ── Main Entry Point ─────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(config.MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=15),
)
def generate_audio(script: dict, output_dir: Path,
                   provider: str = "elevenlabs",
                   lang: str = "EN") -> dict:
    """
    Generate all audio files for a video. Auto-fallback from ElevenLabs to gTTS.

    Returns:
        Dict with segment audio paths and durations.
    """
    try:
        return generate_segment_audio(script, output_dir, provider, lang=lang)
    except Exception as e:
        if provider == "elevenlabs":
            logger.warning(f"ElevenLabs failed ({e}). Falling back to Edge TTS...")
            return generate_segment_audio(script, output_dir, "edge-tts", lang=lang)
        raise


def _get_tts_function(provider: str):
    """Return the appropriate TTS function."""
    if provider == "elevenlabs":
        if not config.ELEVENLABS_API_KEY:
            logger.info("No ElevenLabs key. Using Edge TTS fallback.")
            return _edge_tts
        return _elevenlabs_tts
    elif provider == "edge-tts":
        return _edge_tts
    return _google_tts
