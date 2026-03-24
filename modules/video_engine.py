"""
PaperBrief — Video Assembly Module
Assembles narration audio, background images, subtitles, and overlays
into a vertical (1080×1920) YouTube Short using MoviePy.

Content Structure:
  Hook (0-10s) → Insight (10-40s) → Impact (40-60s)
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ImageClip,
    TextClip,
    VideoClip,
    concatenate_videoclips,
)

import config

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
W = config.VIDEO_WIDTH
H = config.VIDEO_HEIGHT
FPS = config.VIDEO_FPS


# ═════════════════════════════════════════════════════════════════════════════
#  SUBTITLE ENGINE — Dynamic word-by-word subtitles
# ═════════════════════════════════════════════════════════════════════════════

def _create_subtitle_clips(text: str, start_time: float, duration: float,
                           font_size: int = 110, words_per_group: int = 2,
                           y_position: float = 0.5) -> list:
    """
    Create dynamic word-group subtitle clips that appear sequentially
    over the given duration, simulating karaoke-style subtitles.

    Args:
        text: Full narration text for this segment
        start_time: When this segment starts in the video (seconds)
        duration: Duration of this segment (seconds)
        font_size: Font size for subtitles (massively increased for Shorts)
        words_per_group: How many words to show at a time
        y_position: Vertical position (0.0=top, 1.0=bottom, 0.5=center)

    Returns:
        List of MoviePy TextClip-like ImageClip objects with zoom animations
    """
    words = text.split()
    if not words:
        return []

    # Split into groups (kinetic pacing)
    groups = []
    for i in range(0, len(words), words_per_group):
        groups.append(" ".join(words[i:i + words_per_group]))

    time_per_group = duration / len(groups)
    clips = []

    for i, group_text in enumerate(groups):
        group_start = start_time + (i * time_per_group)

        # Create localized stylized sub
        text_clip = _create_styled_text_clip(
            group_text,
            font_size=font_size,
            duration=time_per_group,
            start=group_start,
            y_position=y_position,
        )
        if text_clip:
            clips.append(text_clip)

    return clips


def _create_styled_text_clip(text: str, font_size: int, duration: float,
                              start: float, y_position: float) -> Optional[ImageClip]:
    """
    Create a styled subtitle clip with bold black text, thick white stroke,
    and a short pop-out zoom animation, utilizing Pillow for native rendering depth.
    """
    # Create temporary image to measure text size
    # Thick strokes need more padding!
    stroke_w = int(font_size * 0.12)
    padding_x, padding_y = 60 + stroke_w, 40 + stroke_w
    max_text_width = W - 160  # Leave large horizontal margins

    # Try to load a nice font, fallback to default
    font = _get_font(font_size)

    # Measure and wrap text
    dummy_img = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    # Word wrap
    lines = _word_wrap(text, font, max_text_width, dummy_draw)

    # Measure actual text block size
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    if not line_heights:
        return None

    line_spacing = 15  # Positive spacing to prevent overlap with large thick strokes
    total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)
    max_line_width = max(line_widths)

    # Create image with fully transparent background (no basic rectangles!)
    img_w = max_line_width + padding_x * 2
    img_h = max(0, total_text_height + padding_y * 2)

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw text lines (horizontally centered)
    y_offset = padding_y
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (img_w - lw) // 2
        
        # Modern Content Creator Style: Dark Text, Thick Bright Stroke
        draw.text((x, y_offset), line, fill=(15, 15, 15, 255), font=font,
                  stroke_width=stroke_w, stroke_fill=(255, 255, 255, 255))
        
        y_offset += line_heights[i] + line_spacing

    img_array = np.array(img)

    clip = (
        ImageClip(img_array, transparent=True)
        .with_duration(duration)
        .with_start(start)
    )

    # Apply Quadratic Pop-Zoom-Out animation
    zoom_effect = lambda t: 1.35 - 0.35 * min(t / 0.15, 1.0)
    try:
        if hasattr(clip, "resized"):
            clip = clip.resized(zoom_effect)
        elif hasattr(clip, "resize"):
            clip = clip.resize(zoom_effect)
    except Exception as e:
        logger.warning(f"Could not apply zoom effect on subtitles: {e}")

    # Position: center horizontally, at specified vertical position
    y_px = int(H * y_position) - img_h // 2
    y_px = max(font_size, min(y_px, H - img_h - font_size))
    clip = clip.with_position(("center", y_px))

    return clip


def _word_wrap(text: str, font, max_width: int, draw) -> list[str]:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def _draw_rounded_rect(draw, coords, radius, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = coords
    draw.rounded_rectangle(coords, radius=radius, fill=fill)


def _get_font(size: int):
    """Try to load a good font, with fallbacks."""
    font_candidates = [
        "arial.ttf",
        "Arial.ttf",
        "DejaVuSans-Bold.ttf",
        "FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    # Check custom fonts directory
    if config.FONTS_DIR.exists():
        for f in config.FONTS_DIR.glob("*.ttf"):
            font_candidates.insert(0, str(f))

    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue

    logger.warning("No TrueType font found. Using default bitmap font.")
    return ImageFont.load_default()


# ═════════════════════════════════════════════════════════════════════════════
#  BACKGROUND IMAGES — Ken Burns effect (slow zoom/pan)
# ═════════════════════════════════════════════════════════════════════════════

def _create_ken_burns_clip(image_path: Path, duration: float,
                            zoom_start: float = 1.0,
                            zoom_end: float = 1.15) -> VideoClip:
    """
    Create a clip from a still image with slow zoom (Ken Burns effect).
    """
    img = Image.open(str(image_path)).convert("RGB")
    img = img.resize((W, H), Image.Resampling.LANCZOS)
    img_array = np.array(img)

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        zoom = zoom_start + (zoom_end - zoom_start) * progress

        # Calculate crop region for zoom
        new_w = int(W / zoom)
        new_h = int(H / zoom)
        x_offset = (W - new_w) // 2
        y_offset = (H - new_h) // 2

        cropped = img_array[y_offset:y_offset + new_h, x_offset:x_offset + new_w]

        # Resize back to full resolution
        from PIL import Image as PILImage
        frame = PILImage.fromarray(cropped).resize((W, H), PILImage.Resampling.LANCZOS)
        return np.array(frame)

    return VideoClip(make_frame, duration=duration).with_fps(FPS)


# ═════════════════════════════════════════════════════════════════════════════
#  WATERMARK & OVERLAYS
# ═════════════════════════════════════════════════════════════════════════════

def _create_watermark_clip(arxiv_id: str, duration: float) -> ImageClip:
    """Create a 'Source: arXiv:xxxx' watermark in the bottom-right corner."""
    text = f"Source: arXiv:{arxiv_id}"
    font = _get_font(config.WATERMARK_FONT_SIZE)

    # Measure text
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    padding = 16
    img = Image.new("RGBA", (tw + padding * 2, th + padding * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _draw_rounded_rect(draw, (0, 0, tw + padding * 2, th + padding * 2),
                        radius=8, fill=(0, 0, 0, 130))
    draw.text((padding, padding), text, fill=(255, 255, 255, 200), font=font)

    arr = np.array(img)
    clip = (
        ImageClip(arr, transparent=True)
        .with_duration(duration)
        .with_position((W - arr.shape[1] - 30, H - arr.shape[0] - 80))
    )
    return clip


def _create_progress_bar(duration: float) -> VideoClip:
    """Create an animated progress bar at the top of the video."""
    bar_height = 6

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        bar_width = int(W * progress)

        frame = np.zeros((bar_height, W, 4), dtype=np.uint8)
        # Gradient from cyan to purple
        if bar_width > 0:
            for x in range(bar_width):
                ratio = x / W
                r = int(0 + 150 * ratio)
                g = int(220 - 120 * ratio)
                b = int(255 - 55 * ratio)
                frame[0:bar_height, x] = [r, g, b, 220]

        return frame

    return (
        VideoClip(make_frame, duration=duration)
        .with_fps(FPS)
        .with_position(("center", 0))
    )


def _create_insight_overlay_clips(insight_points: list[str],
                                   start_time: float,
                                   duration: float) -> list:
    """
    Create large text overlay clips for the insight points.
    These appear one-by-one during the insight segment.
    """
    if not insight_points:
        return []

    time_per_point = duration / len(insight_points)
    clips = []

    for i, point in enumerate(insight_points):
        point_start = start_time + (i * time_per_point)

        text_clip = _create_styled_text_clip(
            point,
            font_size=48,
            duration=time_per_point - 0.3,  # Small gap between points
            start=point_start,
            y_position=0.35,  # Upper-center area
        )
        if text_clip:
            clips.append(text_clip)

    return clips


# ═════════════════════════════════════════════════════════════════════════════
#  FORMULA OVERLAY
# ═════════════════════════════════════════════════════════════════════════════

def _create_formula_clips(formula_paths: list[Path], start_time: float,
                           duration: float) -> list:
    """Overlay formula images during the insight segment."""
    if not formula_paths:
        return []

    time_per_formula = duration / len(formula_paths)
    clips = []

    for i, fpath in enumerate(formula_paths[:3]):  # Max 3 formulas
        try:
            img = Image.open(str(fpath)).convert("RGBA")

            # Scale to fit (max 60% of video width)
            max_w = int(W * 0.6)
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)),
                                  Image.Resampling.LANCZOS)

            arr = np.array(img)
            clip = (
                ImageClip(arr, transparent=True)
                .with_duration(time_per_formula - 0.5)
                .with_start(start_time + i * time_per_formula)
                .with_position(("center", int(H * 0.7)))
            )
            clips.append(clip)
        except Exception as e:
            logger.warning(f"Could not load formula image {fpath}: {e}")

    return clips


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN ASSEMBLY
# ═════════════════════════════════════════════════════════════════════════════

def assemble_video(
    script: dict,
    audio_data: dict,
    image_paths: dict,
    output_path: Path,
    arxiv_id: str = "",
    formula_paths: list[Path] = None,
    bg_music_path: Path = None,
) -> Path:
    """
    Assemble all elements into a final vertical video.

    Args:
        script: Dict with hook, insight, insight_points, impact
        audio_data: Dict from audio_engine with segment paths & durations
        image_paths: Dict mapping segment names to background image paths
        output_path: Where to save the final .mp4
        arxiv_id: Paper ID for watermark
        formula_paths: Optional list of formula PNG paths
        bg_music_path: Optional path to background music file

    Returns:
        Path to the final video file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("═══ Starting video assembly ═══")

    # ── Determine segment durations from audio ──
    hook_dur = audio_data.get("hook", {}).get("duration", 10)
    insight_dur = audio_data.get("insight", {}).get("duration", 30)
    impact_dur = audio_data.get("impact", {}).get("duration", 20)
    total_duration = hook_dur + insight_dur + impact_dur

    logger.info(f"Segment durations — Hook: {hook_dur:.1f}s, "
                f"Insight: {insight_dur:.1f}s, Impact: {impact_dur:.1f}s, "
                f"Total: {total_duration:.1f}s")

    # ── Segment timing ──
    hook_start = 0
    insight_start = hook_dur
    impact_start = hook_dur + insight_dur

    # ── Build background clips (Ken Burns effect) ──
    bg_clips = []

    for seg_name, start, dur in [
        ("hook", hook_start, hook_dur),
        ("insight", insight_start, insight_dur),
        ("impact", impact_start, impact_dur),
    ]:
        img_path = image_paths.get(seg_name)
        if img_path and Path(img_path).exists():
            clip = _create_ken_burns_clip(Path(img_path), dur)
            clip = clip.with_start(start)
            bg_clips.append(clip)
        else:
            # Solid color fallback
            color_map = {
                "hook": (20, 0, 40),
                "insight": (0, 20, 50),
                "impact": (10, 30, 20),
            }
            color = color_map.get(seg_name, (10, 10, 30))
            solid = np.full((H, W, 3), color, dtype=np.uint8)
            clip = ImageClip(solid).with_duration(dur).with_start(start)
            bg_clips.append(clip)

    # ── Subtitle clips ──
    subtitle_clips = []
    for seg_name, text_key, start, dur in [
        ("hook", "hook", hook_start, hook_dur),
        ("insight", "insight", insight_start, insight_dur),
        ("impact", "impact", impact_start, impact_dur),
    ]:
        text = script.get(text_key, "")
        if text:
            subs = _create_subtitle_clips(
                text, start, dur,
                font_size=58 if seg_name != "hook" else 64,
                words_per_group=4,
                y_position=0.55,
            )
            subtitle_clips.extend(subs)

    # ── Insight point overlays (big text) ──
    insight_overlays = _create_insight_overlay_clips(
        script.get("insight_points", []),
        insight_start,
        insight_dur,
    )

    # ── Formula overlays ──
    formula_clips = []
    if formula_paths:
        formula_clips = _create_formula_clips(
            formula_paths, insight_start, insight_dur
        )

    # ── Watermark ──
    watermark_clip = None
    if arxiv_id:
        watermark_clip = _create_watermark_clip(arxiv_id, total_duration)

    # ── Progress bar ──
    progress_bar = _create_progress_bar(total_duration)

    # ── Compose all layers ──
    all_clips = bg_clips + subtitle_clips + insight_overlays + formula_clips
    if watermark_clip:
        all_clips.append(watermark_clip)
    all_clips.append(progress_bar)

    video = CompositeVideoClip(all_clips, size=(W, H))

    # ── Audio: narration + background music ──
    audio_clips = []

    # Load narration audio per segment
    for seg_name, start in [("hook", hook_start), ("insight", insight_start), ("impact", impact_start)]:
        seg_audio = audio_data.get(seg_name, {})
        audio_path = seg_audio.get("path")
        if audio_path and Path(audio_path).exists():
            a_clip = AudioFileClip(str(audio_path)).with_start(start)
            audio_clips.append(a_clip)

    # Background music (looped, low volume)
    if bg_music_path and bg_music_path.exists():
        try:
            bg_music = AudioFileClip(str(bg_music_path))
            # Loop if shorter than total
            if bg_music.duration < total_duration:
                loops = int(total_duration / bg_music.duration) + 1
                bg_music = concatenate_videoclips(
                    [bg_music] * loops
                ).subclipped(0, total_duration)
            else:
                bg_music = bg_music.subclipped(0, total_duration)
            bg_music = bg_music.with_volume_scaled(config.BG_MUSIC_VOLUME)
            audio_clips.append(bg_music)
        except Exception as e:
            logger.warning(f"Could not load background music: {e}")

    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips)
        video = video.with_audio(final_audio)

    video = video.with_duration(total_duration)

    # ── Render ──
    logger.info(f"Rendering video to {output_path} (Codec: {config.VIDEO_CODEC})...")
    # RTX GPUs using h264_nvenc can process video blazing fast
    preset = "fast" if config.VIDEO_CODEC == "h264_nvenc" else "medium"
    
    video.write_videofile(
        str(output_path),
        fps=FPS,
        codec=config.VIDEO_CODEC,
        audio_codec=config.AUDIO_CODEC,
        threads=4,
        preset=preset,
        logger="bar",
    )

    # Cleanup
    video.close()
    for clip in audio_clips:
        try:
            clip.close()
        except Exception:
            pass

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"✅ Video saved: {output_path} ({file_size_mb:.1f} MB)")

    return output_path
