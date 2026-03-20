"""
PaperBrief — Main Pipeline Orchestrator
End-to-end: arXiv paper → 60-second YouTube Short.

Usage:
    python main.py                          # Interactive mode
    python main.py --category cs.AI --max-papers 3
    python main.py --category cs.AI --max-papers 1 --dry-run
    python main.py --arxiv-id 2401.12345
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import config
from modules import scraper, ai_logic, audio_engine, visual_engine, latex_renderer, video_engine, history_db

# ── Logging Setup ────────────────────────────────────────────────────────────

def setup_logging(verbose: bool = False):
    """Configure structured logging."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s │ %(levelname)-7s │ %(name)-20s │ %(message)s"
    date_fmt = "%H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=date_fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.OUTPUT_DIR / "paperbrief.log", encoding="utf-8"),
        ],
    )

logger = logging.getLogger("PaperBrief")


# ═════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE MENU SYSTEM
# ═════════════════════════════════════════════════════════════════════════════

def _print_banner():
    """Print the PaperBrief ASCII banner."""
    print()
    print("  ╔═══════════════════════════════════════════════════════╗")
    print("  ║          📄 PaperBrief — Short Video Generator       ║")
    print("  ║       Research Papers → 60s YouTube Shorts           ║")
    print("  ╚═══════════════════════════════════════════════════════╝")
    print()


def _select_llm_provider() -> tuple[str, str]:
    """
    Interactive menu to select LLM provider and model.

    Returns:
        (provider, model) — e.g. ("openrouter", "xiaomi/mimo-v2-flash")
    """
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │  🤖 Select LLM Provider for Script Generation   │")
    print("  ├─────────────────────────────────────────────────┤")
    print("  │  1. Gemini      (Google)                        │")
    print("  │  2. OpenAI      (GPT models)                    │")
    print("  │  3. OpenRouter  (Any model — 100+ providers)    │")
    print("  └─────────────────────────────────────────────────┘")
    print()

    providers = {
        "1": "gemini",
        "2": "openai",
        "3": "openrouter",
    }

    while True:
        choice = input("  Enter choice [1/2/3] (default: 1): ").strip()
        if choice == "":
            choice = "1"
        if choice in providers:
            break
        print("  ⚠ Invalid choice. Please enter 1, 2, or 3.")

    provider = providers[choice]

    # Default models per provider
    default_models = ai_logic.DEFAULT_MODELS.copy()

    # Example models to show the user
    model_examples = {
        "gemini": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-pro-preview-05-06",
        ],
        "openai": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-nano",
        ],
        "openrouter": [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "minimax/minimax-m2.5:free",
            "stepfun/step-3.5-flash:free",
            "openai/gpt-oss-120b:free",
            "google/gemma-3n-e4b-it:free",
            # "google/gemini-2.0-flash-001",
            # "xiaomi/mimo-v2-flash",
            # "deepseek/deepseek-chat-v3-0324",
            # "meta-llama/llama-4-maverick",
            # "anthropic/claude-sonnet-4",
        ],
    }

    default_model = default_models[provider]
    examples = model_examples.get(provider, [])

    print()
    print(f"  ┌─────────────────────────────────────────────────┐")
    print(f"  │  📋 Select Model for {provider.upper():10s}                  │")
    print(f"  ├─────────────────────────────────────────────────┤")
    for i, ex in enumerate(examples, 1):
        marker = " ← default" if ex == default_model else ""
        print(f"  │  {i}. {ex:<40s}{marker:>4s} │")
    print(f"  │                                                 │")
    print(f"  │  Or type any model name manually                │")
    print(f"  └─────────────────────────────────────────────────┘")
    print()

    model_input = input(f"  Enter model name or # (default: {default_model}): ").strip()

    if model_input == "" or model_input is None:
        model = default_model
    elif model_input.isdigit() and 1 <= int(model_input) <= len(examples):
        model = examples[int(model_input) - 1]
    else:
        model = model_input  # User typed a custom model name

    print(f"\n  ✅ Using: {provider} / {model}\n")
    return provider, model


def _select_tts_provider() -> str:
    """Interactive menu to select TTS provider."""
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │  🔊 Select TTS Provider for Audio Narration     │")
    print("  ├─────────────────────────────────────────────────┤")
    print("  │  1. ElevenLabs  (High quality, requires API key)│")
    print("  │  2. Google TTS  (Free, no API key needed)       │")
    print("  └─────────────────────────────────────────────────┘")
    print()

    while True:
        choice = input("  Enter choice [1/2] (default: 1): ").strip()
        if choice == "":
            choice = "1"
        if choice in ("1", "2"):
            break
        print("  ⚠ Invalid choice. Please enter 1 or 2.")

    tts = "elevenlabs" if choice == "1" else "gtts"
    print(f"\n  ✅ TTS: {tts}\n")
    return tts


def _select_source() -> dict:
    """Interactive menu to select paper source/input."""
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │  📥 Select Paper Source                          │")
    print("  ├─────────────────────────────────────────────────┤")
    print("  │  1. Fetch from arXiv by category                │")
    print("  │  2. Fetch specific paper by arXiv ID            │")
    print("  └─────────────────────────────────────────────────┘")
    print()

    while True:
        choice = input("  Enter choice [1/2] (default: 1): ").strip()
        if choice == "":
            choice = "1"
        if choice in ("1", "2"):
            break
        print("  ⚠ Invalid choice. Please enter 1 or 2.")

    if choice == "1":
        category = input(f"  arXiv category (default: {config.DEFAULT_CATEGORY}): ").strip()
        if not category:
            category = config.DEFAULT_CATEGORY

        max_papers_str = input(f"  Max papers to process (default: {config.DEFAULT_MAX_RESULTS}): ").strip()
        try:
            max_papers = int(max_papers_str) if max_papers_str else config.DEFAULT_MAX_RESULTS
        except ValueError:
            max_papers = config.DEFAULT_MAX_RESULTS

        print(f"\n  ✅ Source: arXiv/{category} — up to {max_papers} paper(s)\n")
        return {"mode": "batch", "category": category, "max_papers": max_papers}

    else:
        arxiv_id = input("  Enter arXiv paper ID (e.g. 2401.12345): ").strip()
        if not arxiv_id:
            print("  ⚠ No arXiv ID provided. Using category mode instead.")
            print(f"\n  ✅ Source: arXiv/{config.DEFAULT_CATEGORY} — up to 1 paper\n")
            return {"mode": "batch", "category": config.DEFAULT_CATEGORY, "max_papers": 1}

        print(f"\n  ✅ Source: arXiv paper {arxiv_id}\n")
        return {"mode": "single", "arxiv_id": arxiv_id}


def _select_language() -> str:
    """Interactive menu to select output language."""
    from modules.ai_logic import LANGUAGE_CONFIGS

    print("  ┌─────────────────────────────────────────────────┐")
    print("  │  🌐 Select Output Language                      │")
    print("  ├─────────────────────────────────────────────────┤")

    lang_list = list(LANGUAGE_CONFIGS.keys())
    for i, code in enumerate(lang_list, 1):
        name = LANGUAGE_CONFIGS[code]["name"]
        print(f"  │  {i}. {code}  — {name:<39s}│")

    print(f"  │                                                 │")
    print(f"  │  Or type any ISO code (e.g. DE, JA, KO)        │")
    print("  └─────────────────────────────────────────────────┘")
    print()

    lang_input = input("  Enter language [1-4 or code] (default: EN): ").strip()

    if lang_input == "":
        lang = "EN"
    elif lang_input.isdigit() and 1 <= int(lang_input) <= len(lang_list):
        lang = lang_list[int(lang_input) - 1]
    else:
        lang = lang_input.upper()

    lang_name = LANGUAGE_CONFIGS.get(lang, {}).get("name", lang)
    print(f"\n  ✅ Language: {lang} ({lang_name})\n")
    return lang


def _confirm_and_run() -> dict:
    """
    Run the full interactive setup flow.

    Returns:
        Dict with all user selections.
    """
    _print_banner()

    # Step 1: LLM Provider + Model
    provider, model = _select_llm_provider()

    # Step 2: TTS Provider
    tts = _select_tts_provider()

    # Step 3: Language
    lang = _select_language()

    # Step 4: Paper Source
    source = _select_source()

    # Step 5: Dry run?
    dry_run_input = input("  Dry run mode? (skip paid API calls) [y/N]: ").strip().lower()
    dry_run = dry_run_input in ("y", "yes")

    # Summary
    print()
    print("  ╔═══════════════════════════════════════════════════════╗")
    print("  ║  📋 CONFIGURATION SUMMARY                            ║")
    print("  ╠═══════════════════════════════════════════════════════╣")
    print(f"  ║  LLM Provider : {provider:<38s}║")
    print(f"  ║  LLM Model    : {model:<38s}║")
    print(f"  ║  TTS Provider : {tts:<38s}║")
    print(f"  ║  Language     : {lang:<38s}║")
    if source["mode"] == "batch":
        print(f"  ║  Source        : arXiv/{source['category']:<31s}║")
        print(f"  ║  Max Papers   : {str(source['max_papers']):<38s}║")
    else:
        print(f"  ║  Source        : arXiv paper {source['arxiv_id']:<23s}║")
    print(f"  ║  Dry Run      : {'Yes' if dry_run else 'No':<38s}║")
    print("  ╚═══════════════════════════════════════════════════════╝")
    print()

    confirm = input("  Start processing? [Y/n]: ").strip().lower()
    if confirm in ("n", "no"):
        print("  Cancelled.")
        sys.exit(0)

    return {
        "provider": provider,
        "model": model,
        "tts": tts,
        "lang": lang,
        "dry_run": dry_run,
        **source,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  PIPELINE
# ═════════════════════════════════════════════════════════════════════════════

def process_paper(paper_data: dict, dry_run: bool = False,
                  llm_provider: str = "gemini",
                  llm_model: str = None,
                  tts_provider: str = "elevenlabs",
                  lang: str = "EN") -> dict:
    """
    Full pipeline for a single paper.

    Steps:
        1. Generate script via LLM
        2. Generate audio via TTS
        3. Generate background images
        4. Extract & render LaTeX formulas
        5. Assemble video

    Args:
        paper_data: Dict with title, authors, abstract, conclusion, arxiv_id
        dry_run: If True, skip API calls and use mock data
        llm_provider: "gemini", "openai", or "openrouter"
        llm_model: Specific model name (None = use provider default)
        tts_provider: "elevenlabs" or "gtts"
        lang: Language code ("EN", "ID", "ES", etc.)

    Returns:
        Dict with status, output_path, and metadata.
    """
    arxiv_id = paper_data.get("arxiv_id", "unknown")
    paper_dir = config.OUTPUT_DIR / arxiv_id
    paper_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "arxiv_id": arxiv_id,
        "title": paper_data.get("title", ""),
        "status": "pending",
        "output_path": None,
        "errors": [],
    }

    start_time = time.time()

    try:
        # ── Step 1: Generate Script ──────────────────────────────────────
        logger.info(f"{'─' * 60}")
        logger.info(f"📄 Processing: {paper_data['title'][:70]}...")
        logger.info(f"   arXiv ID: {arxiv_id}")
        logger.info(f"{'─' * 60}")

        if dry_run:
            script = _mock_script(paper_data)
            logger.info("[DRY RUN] Using mock script.")
        else:
            logger.info("🤖 Step 1/5: Generating narration script...")
            script = ai_logic.generate_script(
                paper_data, provider=llm_provider, model=llm_model, lang=lang
            )

        # Save script for debugging
        script_path = paper_dir / "script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)
        logger.info(f"Script saved to {script_path}")

        # ── Step 2: Generate Audio ───────────────────────────────────────
        if dry_run:
            audio_data = _mock_audio_data(paper_dir)
            logger.info("[DRY RUN] Using mock audio data.")
        else:
            logger.info("🔊 Step 2/5: Generating narration audio...")
            audio_dir = paper_dir / "audio"
            audio_data = audio_engine.generate_audio(
                script, audio_dir, provider=tts_provider, lang=lang
            )

        # ── Step 3: Generate Background Images from PDF ──────────────────
        logger.info("🎨 Step 3/5: Generating background images from PDF...")
        image_dir = paper_dir / "images"

        pdf_path = paper_data.get("pdf_path")
        if pdf_path and Path(pdf_path).exists():
            # Primary: use actual PDF page screenshots
            image_paths = visual_engine.generate_images_from_pdf(
                Path(pdf_path), image_dir
            )
        else:
            # Fallback: use AI-generated or placeholder images
            logger.info("No PDF available. Using fallback images.")
            visual_prompts = script.get("visual_prompts", {})
            if dry_run:
                image_paths = visual_engine.generate_images(
                    visual_prompts, image_dir, use_dalle=False
                )
            else:
                image_paths = visual_engine.generate_images(visual_prompts, image_dir)

        # ── Step 4: Extract & Render LaTeX Formulas ──────────────────────
        logger.info("📐 Step 4/5: Extracting LaTeX formulas...")
        formula_dir = paper_dir / "formulas"
        conclusion_text = paper_data.get("conclusion", "")
        formula_paths = latex_renderer.render_all_formulas(conclusion_text, formula_dir)

        # ── Step 5: Assemble Video ───────────────────────────────────────
        logger.info("🎬 Step 5/5: Assembling video...")
        output_path = paper_dir / "final_short.mp4"

        # Find background music (if any in assets)
        bg_music = _find_bg_music()

        if dry_run:
            logger.info("[DRY RUN] Skipping video assembly (no audio files).")
            logger.info(f"Would generate video at: {output_path}")
            result["status"] = "dry_run_complete"
            result["output_path"] = str(output_path)
        else:
            video_engine.assemble_video(
                script=script,
                audio_data=audio_data,
                image_paths=image_paths,
                output_path=output_path,
                arxiv_id=arxiv_id,
                formula_paths=formula_paths,
                bg_music_path=bg_music,
            )
            result["status"] = "success"
            result["output_path"] = str(output_path)

        elapsed = time.time() - start_time
        logger.info(f"✅ Completed in {elapsed:.1f}s: {arxiv_id}")

    except Exception as e:
        elapsed = time.time() - start_time
        result["status"] = "error"
        result["errors"].append(str(e))
        logger.error(f"❌ Failed after {elapsed:.1f}s: {arxiv_id} — {e}", exc_info=True)

    # Record to history database
    try:
        category = ""
        if paper_data.get("categories"):
            category = paper_data["categories"][0] if isinstance(paper_data["categories"], list) else paper_data["categories"]
        history_db.record_paper(
            arxiv_id=arxiv_id,
            title=paper_data.get("title", ""),
            category=category,
            status=result["status"],
            output_path=result.get("output_path", ""),
        )
    except Exception as he:
        logger.warning(f"Failed to record to history: {he}")

    return result


# ── Batch & Single Processing ────────────────────────────────────────────────

def run_batch(category: str = config.DEFAULT_CATEGORY,
              max_results: int = config.DEFAULT_MAX_RESULTS,
              dry_run: bool = False,
              llm_provider: str = "gemini",
              llm_model: str = None,
              tts_provider: str = "elevenlabs",
              lang: str = "EN") -> list[dict]:
    """
    Process multiple papers from a given arXiv category.

    Returns:
        List of result dicts with status for each paper.
    """
    import random
    if category.lower() == "random":
        category = random.choice(config.ARXIV_CATEGORIES)
        
    model_display = llm_model or ai_logic.DEFAULT_MODELS.get(llm_provider, "default")

    logger.info(f"═══════════════════════════════════════════════════════════")
    logger.info(f"  PaperBrief — Batch Processing")
    logger.info(f"  Category : {category} | Max papers: {max_results}")
    logger.info(f"  LLM      : {llm_provider} / {model_display}")
    logger.info(f"  TTS      : {tts_provider}")
    logger.info(f"  Language : {lang}")
    logger.info(f"  Dry run  : {dry_run}")
    logger.info(f"═══════════════════════════════════════════════════════════")

    # Validate config
    warnings = config.validate_config()
    for w in warnings:
        logger.warning(w)

    # Get already-processed IDs
    skip_ids = history_db.get_processed_ids()
    logger.info(f"📊 Papers in history: {len(skip_ids)}")

    # Fetch papers (skip already-processed)
    logger.info("📥 Fetching papers from arXiv...")
    papers = scraper.get_paper_data(category, max_results, skip_ids=skip_ids)

    if not papers:
        logger.warning("No papers found or all papers were filtered out.")
        return []

    logger.info(f"Processing {len(papers)} paper(s)...")

    results = []
    for i, paper in enumerate(papers, 1):
        logger.info(f"\n{'━' * 60}")
        logger.info(f"  Paper {i}/{len(papers)}")
        logger.info(f"{'━' * 60}")

        result = process_paper(
            paper, dry_run=dry_run,
            llm_provider=llm_provider,
            llm_model=llm_model,
            tts_provider=tts_provider,
            lang=lang,
        )
        results.append(result)

    # Summary
    _print_summary(results)
    return results


def run_single(arxiv_id: str, dry_run: bool = False,
               llm_provider: str = "gemini",
               llm_model: str = None,
               tts_provider: str = "elevenlabs",
               lang: str = "EN") -> dict:
    """Process a single paper by its arXiv ID."""
    logger.info(f"Fetching paper {arxiv_id}...")

    import arxiv as arxiv_lib
    client = arxiv_lib.Client()
    search = arxiv_lib.Search(id_list=[arxiv_id])

    results = list(client.results(search))
    if not results:
        logger.error(f"Paper {arxiv_id} not found on arXiv.")
        return {"status": "error", "errors": ["Paper not found"]}

    r = results[0]
    paper = {
        "title": r.title,
        "authors": [a.name for a in r.authors],
        "abstract": r.summary,
        "pdf_url": r.pdf_url,
        "arxiv_id": r.entry_id.split("/")[-1],
        "published": r.published.isoformat(),
    }

    # Download and extract conclusion
    paper_dir = config.OUTPUT_DIR / paper["arxiv_id"]
    pdf_path = scraper.download_pdf(paper["pdf_url"], paper_dir)
    conclusion = scraper.extract_conclusion(pdf_path)
    paper["conclusion"] = conclusion or paper["abstract"]
    paper["pdf_path"] = str(pdf_path)

    return process_paper(
        paper, dry_run=dry_run,
        llm_provider=llm_provider,
        llm_model=llm_model,
        tts_provider=tts_provider,
        lang=lang,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_script(paper_data: dict) -> dict:
    """Generate a mock script for dry-run testing."""
    return {
        "hook": f"Scientists just made a groundbreaking discovery about {paper_data['title'][:50]}.",
        "insight": (
            "Using a novel approach, researchers analyzed massive datasets "
            "and found surprising patterns. Think of it like finding a needle "
            "in a haystack, except the needle was hiding in plain sight all along. "
            "Their method outperformed previous approaches by a significant margin."
        ),
        "insight_points": [
            "Novel methodology with 40% improvement",
            "Tested across 10,000+ data points",
            "Outperforms all existing baselines",
        ],
        "impact": (
            "This means in the future, we could see dramatically better AI systems "
            "that understand and interact with the world more naturally. "
            "The implications for technology are enormous."
        ),
        "visual_prompts": {
            "hook": "Futuristic laboratory with glowing neural networks and data streams",
            "insight": "Abstract scientific visualization with graphs and molecular structures",
            "impact": "Optimistic futuristic cityscape with advanced technology integration",
        },
        "full_narration": "",
        "title_short": f"Research Breakthrough: {paper_data['title'][:30]}",
        "hashtags": ["#science", "#research", "#AI"],
    }


def _mock_audio_data(paper_dir: Path) -> dict:
    """Generate mock audio metadata for dry-run testing."""
    return {
        "hook": {"path": paper_dir / "audio" / "hook.mp3", "duration": 8.0},
        "insight": {"path": paper_dir / "audio" / "insight.mp3", "duration": 30.0},
        "impact": {"path": paper_dir / "audio" / "impact.mp3", "duration": 18.0},
        "full": {"path": paper_dir / "audio" / "full.mp3", "duration": 56.0},
    }


def _find_bg_music() -> Path | None:
    """Find a background music file in the assets directory."""
    music_dir = config.MUSIC_DIR
    if not music_dir.exists():
        return None

    for ext in ["*.mp3", "*.wav", "*.m4a"]:
        files = list(music_dir.glob(ext))
        if files:
            logger.info(f"Using background music: {files[0].name}")
            return files[0]

    return None


def _print_summary(results: list[dict]):
    """Print a summary table of batch processing results."""
    logger.info(f"\n{'═' * 60}")
    logger.info("  BATCH SUMMARY")
    logger.info(f"{'═' * 60}")

    success = sum(1 for r in results if r["status"] in ("success", "dry_run_complete"))
    failed = sum(1 for r in results if r["status"] == "error")

    for r in results:
        icon = "✅" if r["status"] in ("success", "dry_run_complete") else "❌"
        logger.info(f"  {icon} {r['arxiv_id']}: {r['status']}")
        if r.get("errors"):
            for err in r["errors"]:
                logger.info(f"     └─ {err[:80]}")

    logger.info(f"\n  Total: {len(results)} | Success: {success} | Failed: {failed}")
    logger.info(f"{'═' * 60}")


# ═════════════════════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="PaperBrief — Convert research papers to YouTube Shorts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                          # Interactive mode
  python main.py --category cs.AI --max-papers 3          # CLI mode
  python main.py --arxiv-id 2401.12345 --dry-run          # Single paper dry-run
  python main.py --llm openrouter --model xiaomi/mimo-v2-flash
  python main.py --category cs.AI --lang ID               # Indonesian output
        """,
    )
    parser.add_argument("--category", "-c", default=None,
                        help=f"arXiv category (default: {config.DEFAULT_CATEGORY})")
    parser.add_argument("--max-papers", "-n", type=int, default=None,
                        help=f"Maximum papers to process (default: {config.DEFAULT_MAX_RESULTS})")
    parser.add_argument("--arxiv-id", "-id", type=str, default=None,
                        help="Process a single paper by arXiv ID")
    parser.add_argument("--dry-run", "-d", action="store_true",
                        help="Test pipeline without calling paid APIs")
    parser.add_argument("--llm", choices=["gemini", "openai", "openrouter"], default=None,
                        help="LLM provider for script generation")
    parser.add_argument("--model", "-m", type=str, default=None,
                        help="Specific LLM model name (e.g. gpt-4o-mini, xiaomi/mimo-v2-flash)")
    parser.add_argument("--tts", choices=["elevenlabs", "gtts"], default=None,
                        help="TTS provider for audio generation")
    parser.add_argument("--lang", "-l", type=str, default=None,
                        help="Output language code: EN, ID, ES, FR, etc. (default: EN)")
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None,
                        help="Hardware rendering device (e.g. cuda for NVENC)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    # Apply GPU override logic if requested via CLI
    if args.device:
        config.RENDER_DEVICE = args.device
        config.VIDEO_CODEC = "h264_nvenc" if args.device == "cuda" else "libx264"

    # Determine if we're in interactive or CLI mode
    has_cli_args = any([args.category, args.max_papers, args.arxiv_id, args.llm, args.tts, args.lang])

    if has_cli_args:
        # ── CLI Mode (backward compatible) ──
        setup_logging(args.verbose)

        llm_provider = args.llm or "gemini"
        llm_model = args.model  # None = use default
        tts_provider = args.tts or "elevenlabs"
        lang = (args.lang or "EN").upper()
        category = args.category or config.DEFAULT_CATEGORY
        max_papers = args.max_papers or config.DEFAULT_MAX_RESULTS

        if args.arxiv_id:
            result = run_single(
                args.arxiv_id, dry_run=args.dry_run,
                llm_provider=llm_provider, llm_model=llm_model,
                tts_provider=tts_provider, lang=lang,
            )
            icon = "✅" if result["status"] in ("success", "dry_run_complete") else "❌"
            logger.info(f"{icon} Result: {result['status']}")
        else:
            run_batch(
                category, max_papers, dry_run=args.dry_run,
                llm_provider=llm_provider, llm_model=llm_model,
                tts_provider=tts_provider, lang=lang,
            )
    else:
        # ── Interactive Mode ──
        setup_logging(args.verbose)
        selections = _confirm_and_run()

        if selections["mode"] == "single":
            result = run_single(
                selections["arxiv_id"],
                dry_run=selections["dry_run"],
                llm_provider=selections["provider"],
                llm_model=selections["model"],
                tts_provider=selections["tts"],
                lang=selections["lang"],
            )
            icon = "✅" if result["status"] in ("success", "dry_run_complete") else "❌"
            logger.info(f"{icon} Result: {result['status']}")
        else:
            run_batch(
                selections["category"],
                selections["max_papers"],
                dry_run=selections["dry_run"],
                llm_provider=selections["provider"],
                llm_model=selections["model"],
                tts_provider=selections["tts"],
                lang=selections["lang"],
            )


if __name__ == "__main__":
    main()
