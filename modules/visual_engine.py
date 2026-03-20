"""
PaperBrief — Visual Generation Module
Generates background images for video segments from PDF page screenshots.
Falls back to DALL-E 3 or gradient placeholders when PDF is unavailable.
"""

import logging
import math
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from tenacity import retry, stop_after_attempt, wait_exponential

import config

logger = logging.getLogger(__name__)

# Vertical video dimensions
TARGET_WIDTH = config.VIDEO_WIDTH
TARGET_HEIGHT = config.VIDEO_HEIGHT


# ═════════════════════════════════════════════════════════════════════════════
#  PDF PAGE SCREENSHOTS (Primary)
# ═════════════════════════════════════════════════════════════════════════════

def extract_pdf_pages(pdf_path: Path, output_dir: Path,
                      page_indices: list[int] = None,
                      dpi: int = 200) -> list[Path]:
    """
    Render specific pages of a PDF as high-resolution PNG images.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save the page images
        page_indices: List of 0-indexed page numbers to extract.
                      If None, auto-selects relevant pages for the 3 segments.
        dpi: Resolution for rendering (200 = good quality for 1080p)

    Returns:
        List of Paths to the generated PNG images.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    if page_indices is None:
        page_indices = _select_segment_pages(total_pages)

    # Render scale: fitz default is 72dpi, so scale = dpi / 72
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    paths = []
    for idx in page_indices:
        if idx < 0 or idx >= total_pages:
            logger.warning(f"Page index {idx} out of range (0-{total_pages-1}). Skipping.")
            continue

        page = doc[idx]
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        output_path = output_dir / f"page_{idx:03d}.png"
        pix.save(str(output_path))

        logger.info(f"Extracted PDF page {idx + 1}/{total_pages} → {output_path.name} "
                    f"({pix.width}x{pix.height})")
        paths.append(output_path)

    doc.close()
    return paths


def _select_segment_pages(total_pages: int) -> list[int]:
    """
    Auto-select 3 representative pages for hook/insight/impact segments.

    Strategy:
    - Hook:    Page 0 (title page — visually striking)
    - Insight: Middle page (likely has figures/tables/methodology)
    - Impact:  Second-to-last page (likely has results/conclusion)
    """
    hook_page = 0
    insight_page = max(1, total_pages // 2)  # Middle
    impact_page = max(2, total_pages - 2)     # Near the end

    # Avoid duplicates
    pages = list(dict.fromkeys([hook_page, insight_page, impact_page]))

    # Ensure we have exactly 3 pages
    while len(pages) < 3 and pages[-1] + 1 < total_pages:
        pages.append(pages[-1] + 1)
    # If still not enough (very short paper), repeat last
    while len(pages) < 3:
        pages.append(pages[-1])

    return pages[:3]


def _prepare_pdf_image_for_video(image_path: Path, output_path: Path,
                                  darken: float = 0.55) -> Path:
    """
    Process a PDF page screenshot for use as video background:
    1. Resize/crop to 1080x1920 (vertical)
    2. Apply slight darkening so overlaid text is readable
    3. Apply subtle blur to reduce visual noise

    Args:
        image_path: Path to the raw PDF page image
        output_path: Where to save the processed image
        darken: Brightness multiplier (0.0 = black, 1.0 = original)
    """
    img = Image.open(str(image_path)).convert("RGB")

    # ── Resize to cover 1080x1920 ──
    img_ratio = img.width / img.height
    target_ratio = TARGET_WIDTH / TARGET_HEIGHT

    if img_ratio > target_ratio:
        new_height = TARGET_HEIGHT
        new_width = int(new_height * img_ratio)
    else:
        new_width = TARGET_WIDTH
        new_height = int(new_width / img_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Center crop
    left = (new_width - TARGET_WIDTH) // 2
    top = (new_height - TARGET_HEIGHT) // 2
    img = img.crop((left, top, left + TARGET_WIDTH, top + TARGET_HEIGHT))

    # ── Darken for text readability ──
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(darken)

    # ── Light blur to reduce PDF text noise ──
    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))

    img.save(str(output_path), quality=95)
    return output_path


# ═════════════════════════════════════════════════════════════════════════════
#  DALL-E 3 (Optional — only if user explicitly wants generated images)
# ═════════════════════════════════════════════════════════════════════════════

def _dalle3_generate(prompt: str, output_path: Path) -> Path:
    """Generate an image using OpenAI DALL-E 3."""
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set.")

    import openai

    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

    enhanced_prompt = (
        f"Cinematic, high-quality vertical background image (9:16 aspect ratio) for a science video. "
        f"Style: modern, futuristic, dark tones with vibrant accent colors. "
        f"Subject: {prompt}. "
        f"No text, no watermarks, no logos. Ultra-detailed, 4K quality."
    )

    response = client.images.generate(
        model="dall-e-3",
        prompt=enhanced_prompt,
        size="1024x1792",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url

    import httpx
    img_response = httpx.get(image_url, timeout=30)
    with open(output_path, "wb") as f:
        f.write(img_response.content)

    logger.info(f"DALL-E 3 image saved to {output_path}")
    return output_path


# ═════════════════════════════════════════════════════════════════════════════
#  PLACEHOLDER FALLBACK (gradient)
# ═════════════════════════════════════════════════════════════════════════════

SEGMENT_COLORS = {
    "hook": [(20, 0, 40), (80, 0, 120)],
    "insight": [(0, 20, 50), (0, 80, 140)],
    "impact": [(10, 30, 20), (20, 120, 60)],
}


def _placeholder_image(prompt: str, output_path: Path,
                        segment_type: str = "insight") -> Path:
    """Generate a gradient placeholder image."""
    img = Image.new("RGB", (TARGET_WIDTH, TARGET_HEIGHT))
    draw = ImageDraw.Draw(img)

    colors = SEGMENT_COLORS.get(segment_type, SEGMENT_COLORS["insight"])
    top_color, bottom_color = colors

    for y in range(TARGET_HEIGHT):
        ratio = y / TARGET_HEIGHT
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
        draw.line([(0, y), (TARGET_WIDTH, y)], fill=(r, g, b))

    img.save(str(output_path), quality=95)
    logger.info(f"Placeholder image saved to {output_path} (segment: {segment_type})")
    return output_path


# ═════════════════════════════════════════════════════════════════════════════
#  RESIZE UTILITY
# ═════════════════════════════════════════════════════════════════════════════

def resize_for_vertical(image_path: Path, output_path: Path = None) -> Path:
    """Resize and center-crop an image to 1080x1920 (9:16 vertical)."""
    if output_path is None:
        output_path = image_path

    img = Image.open(str(image_path))

    if img.size == (TARGET_WIDTH, TARGET_HEIGHT):
        return image_path

    img_ratio = img.width / img.height
    target_ratio = TARGET_WIDTH / TARGET_HEIGHT

    if img_ratio > target_ratio:
        new_height = TARGET_HEIGHT
        new_width = int(new_height * img_ratio)
    else:
        new_width = TARGET_WIDTH
        new_height = int(new_width / img_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    left = (new_width - TARGET_WIDTH) // 2
    top = (new_height - TARGET_HEIGHT) // 2
    img = img.crop((left, top, left + TARGET_WIDTH, top + TARGET_HEIGHT))

    img.save(str(output_path), quality=95)
    return output_path


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINTS
# ═════════════════════════════════════════════════════════════════════════════

def generate_images_from_pdf(pdf_path: Path, output_dir: Path) -> dict:
    """
    Generate video background images from PDF page screenshots.

    This is the PRIMARY method — uses actual paper pages as backgrounds.
    Pages are auto-selected: title page (hook), middle page (insight),
    near-end page (impact).

    Args:
        pdf_path: Path to the paper PDF file
        output_dir: Directory to save processed images

    Returns:
        Dict mapping segment names to image file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract raw PDF page images
    raw_pages = extract_pdf_pages(pdf_path, output_dir)

    if len(raw_pages) < 3:
        logger.warning(f"Only extracted {len(raw_pages)} pages. Padding with duplicates.")
        while len(raw_pages) < 3:
            raw_pages.append(raw_pages[-1])

    # Map segments to pages and process for video
    segments = ["hook", "insight", "impact"]
    image_paths = {}

    for seg_name, raw_path in zip(segments, raw_pages[:3]):
        processed_path = output_dir / f"bg_{seg_name}.png"
        _prepare_pdf_image_for_video(raw_path, processed_path)
        image_paths[seg_name] = processed_path

    logger.info(f"Generated {len(image_paths)} background images from PDF pages.")
    return image_paths


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def generate_images(visual_prompts: dict, output_dir: Path,
                    use_dalle: bool = True) -> dict:
    """
    Generate background images using DALL-E 3 or placeholder fallback.
    This is the SECONDARY method — used only when PDF is unavailable
    or when user explicitly wants AI-generated images.

    Args:
        visual_prompts: Dict with keys "hook", "insight", "impact" → prompt strings
        output_dir: Directory to save images
        use_dalle: Whether to attempt DALL-E 3 (falls back to placeholder on failure)

    Returns:
        Dict mapping segment names to image file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths = {}

    for segment_name, prompt in visual_prompts.items():
        output_path = output_dir / f"bg_{segment_name}.png"

        if use_dalle and config.OPENAI_API_KEY:
            try:
                _dalle3_generate(prompt, output_path)
                resize_for_vertical(output_path)
                image_paths[segment_name] = output_path
                continue
            except Exception as e:
                logger.warning(f"DALL-E 3 failed for '{segment_name}': {e}. Using placeholder.")

        _placeholder_image(prompt, output_path, segment_type=segment_name)
        image_paths[segment_name] = output_path

    logger.info(f"Generated {len(image_paths)} background images.")
    return image_paths
