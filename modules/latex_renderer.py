"""
PaperBrief — LaTeX Rendering Module
Extracts and renders LaTeX formulas from paper text into transparent PNG images.
"""

import logging
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

import config

logger = logging.getLogger(__name__)


def extract_formulas(text: str) -> list[str]:
    """
    Extract LaTeX formulas from text using regex patterns.

    Detects:
    - Display math: $$ ... $$, \\[ ... \\]
    - Inline math: $ ... $ (only substantial formulas, not single variables)
    - LaTeX environments: \\begin{equation} ... \\end{equation}

    Returns:
        List of unique LaTeX formula strings.
    """
    formulas = []

    # Display math: $$ ... $$
    display_double = re.findall(r'\$\$(.*?)\$\$', text, re.DOTALL)
    formulas.extend(display_double)

    # Display math: \[ ... \]
    display_bracket = re.findall(r'\\\[(.*?)\\\]', text, re.DOTALL)
    formulas.extend(display_bracket)

    # Equation environments
    equation_env = re.findall(
        r'\\begin\{(?:equation|align|gather)\*?\}(.*?)\\end\{(?:equation|align|gather)\*?\}',
        text, re.DOTALL
    )
    formulas.extend(equation_env)

    # Inline math: $ ... $ (filter out trivial single-char formulas)
    inline = re.findall(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', text)
    formulas.extend([f for f in inline if len(f.strip()) > 3])

    # Deduplicate and clean
    seen = set()
    unique_formulas = []
    for f in formulas:
        cleaned = f.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_formulas.append(cleaned)

    logger.info(f"Extracted {len(unique_formulas)} formula(s) from text.")
    return unique_formulas


def render_latex(latex_string: str, output_path: Path,
                 font_size: int = 36, dpi: int = 200,
                 text_color: str = "white") -> Path:
    """
    Render a LaTeX formula to a transparent PNG image using matplotlib.

    Args:
        latex_string: Raw LaTeX string (without $ delimiters)
        output_path: Where to save the PNG
        font_size: Font size for rendering
        dpi: DPI for output image
        text_color: Color of the formula text

    Returns:
        Path to the rendered PNG file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 2))
    ax.set_axis_off()
    fig.patch.set_alpha(0.0)  # Transparent background

    # Wrap in display math mode
    if not latex_string.startswith("$"):
        latex_string = f"${latex_string}$"

    try:
        ax.text(
            0.5, 0.5, latex_string,
            transform=ax.transAxes,
            fontsize=font_size,
            color=text_color,
            ha="center", va="center",
            math_fontfamily="dejavusans",
        )

        fig.savefig(
            str(output_path),
            dpi=dpi,
            transparent=True,
            bbox_inches="tight",
            pad_inches=0.1,
        )
        logger.info(f"Rendered LaTeX to {output_path}")

    except Exception as e:
        logger.error(f"Failed to render LaTeX: {e}\nFormula: {latex_string[:100]}")
        # Create a blank transparent image as fallback
        from PIL import Image
        img = Image.new("RGBA", (400, 100), (0, 0, 0, 0))
        img.save(str(output_path))
        logger.info(f"Saved blank fallback image to {output_path}")

    finally:
        plt.close(fig)

    return output_path


def render_all_formulas(text: str, output_dir: Path) -> list[Path]:
    """
    Extract all formulas from text and render them to PNG files.

    Args:
        text: Full paper text or conclusion text
        output_dir: Directory to save formula images

    Returns:
        List of Paths to rendered PNG files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    formulas = extract_formulas(text)

    if not formulas:
        logger.info("No formulas found in text.")
        return []

    # Render at most 5 formulas to keep video clean
    formulas = formulas[:5]

    paths = []
    for i, formula in enumerate(formulas):
        output_path = output_dir / f"formula_{i:02d}.png"
        rendered = render_latex(formula, output_path)
        paths.append(rendered)

    logger.info(f"Rendered {len(paths)} formula image(s).")
    return paths
