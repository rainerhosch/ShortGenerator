"""
PaperBrief — Data Acquisition Module
Fetches research papers from arXiv and extracts key sections (Abstract, Conclusion).
"""

import logging
import re
import shutil
from pathlib import Path
from typing import Optional

import arxiv
import fitz  # PyMuPDF
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import config

logger = logging.getLogger(__name__)


# ── arXiv Fetching ───────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(config.MAX_RETRIES),
    wait=wait_exponential(multiplier=config.RETRY_WAIT_SECONDS, min=2, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=lambda retry_state: logger.warning(
        f"arXiv fetch retry #{retry_state.attempt_number}..."
    ),
)
def fetch_papers(category: str = config.DEFAULT_CATEGORY,
                 max_results: int = config.DEFAULT_MAX_RESULTS) -> list[dict]:
    """
    Fetch latest papers from arXiv by category.

    Returns:
        List of dicts with keys: title, authors, abstract, pdf_url, arxiv_id, published
    """
    logger.info(f"Fetching up to {max_results} papers from arXiv category: {category}")

    client = arxiv.Client(page_size=min(max_results, 10), delay_seconds=10.0, num_retries=3)
    search = arxiv.Search(
        query=f"cat:{category}",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    for result in client.results(search):
        paper = {
            "title": result.title,
            "authors": [a.name for a in result.authors],
            "abstract": result.summary,
            "pdf_url": result.pdf_url,
            "arxiv_id": result.entry_id.split("/")[-1],  # e.g., "2401.12345v1"
            "published": result.published.isoformat(),
            "categories": result.categories,
        }
        papers.append(paper)
        logger.info(f"  Found: {paper['title'][:80]}...")

    logger.info(f"Fetched {len(papers)} papers.")
    return papers


# ── PDF Download ─────────────────────────────────────────────────────────────

def download_pdf(pdf_url: str, save_dir: Path) -> Path:
    """
    Download a paper's PDF to the specified directory.

    Returns:
        Path to the downloaded PDF file.
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = pdf_url.split("/")[-1] + ".pdf"
    save_path = save_dir / filename

    if save_path.exists():
        logger.info(f"PDF already downloaded: {save_path}")
        return save_path

    logger.info(f"Downloading PDF from {pdf_url}...")

    import urllib.request
    urllib.request.urlretrieve(pdf_url, str(save_path))

    logger.info(f"Saved PDF to {save_path} ({save_path.stat().st_size / 1024:.0f} KB)")
    return save_path


# ── PDF Text Extraction ─────────────────────────────────────────────────────

def _extract_full_text(pdf_path: Path) -> tuple[str, int]:
    """Extract all text from a PDF. Returns (text, page_count)."""
    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    return full_text, page_count


def extract_conclusion(pdf_path: Path) -> Optional[str]:
    """
    Extract the Conclusion/Discussion section from a research paper PDF.

    Strategy:
    1. Look for sections titled 'Conclusion', 'Conclusions', 'Discussion',
       'Summary', 'Concluding Remarks' using regex.
    2. Extract text from that heading until the next section heading or 'References'.
    3. Fallback: if no conclusion section found, use text from the last 2 pages.

    Returns:
        Extracted conclusion text, or None if PDF is invalid / out of page bounds.
    """
    full_text, page_count = _extract_full_text(pdf_path)

    if page_count < config.MIN_PAPER_PAGES:
        logger.warning(f"Paper too short ({page_count} pages). Skipping.")
        return None

    if page_count > config.MAX_PAPER_PAGES:
        logger.warning(f"Paper too long ({page_count} pages). Skipping.")
        return None

    # ── Strategy 1: Regex for conclusion heading ──
    conclusion_pattern = re.compile(
        r'(?:^|\n)\s*'
        r'(?:\d+\.?\s*)?'  # Optional section number
        r'(Conclusion|Conclusions|Discussion|Summary|Concluding\s+Remarks)'
        r'\s*\n',
        re.IGNORECASE
    )

    match = conclusion_pattern.search(full_text)

    if match:
        start = match.start()
        # Find the next section heading or "References"
        next_section = re.search(
            r'\n\s*(?:\d+\.?\s*)?(?:References|Bibliography|Acknowledgment|Appendix)\s*\n',
            full_text[start + len(match.group()):],
            re.IGNORECASE,
        )
        if next_section:
            end = start + len(match.group()) + next_section.start()
        else:
            end = len(full_text)

        conclusion = full_text[start:end].strip()

        # Truncate if too long (> 3000 chars)
        if len(conclusion) > 3000:
            conclusion = conclusion[:3000] + "..."

        logger.info(f"Extracted conclusion ({len(conclusion)} chars) via heading match.")
        return conclusion

    # ── Strategy 2: Fallback — last 2 pages ──
    logger.info("No conclusion heading found. Using last 2 pages as fallback.")
    doc = fitz.open(str(pdf_path))
    fallback_text = ""
    for i in range(max(0, page_count - 2), page_count):
        fallback_text += doc[i].get_text()
    doc.close()

    if len(fallback_text) > 3000:
        fallback_text = fallback_text[:3000] + "..."

    return fallback_text.strip() if fallback_text.strip() else None


# ── Orchestrator ─────────────────────────────────────────────────────────────

def get_paper_data(category: str = config.DEFAULT_CATEGORY,
                   max_results: int = config.DEFAULT_MAX_RESULTS,
                   skip_ids: set = None) -> list[dict]:
    """
    Full pipeline: fetch papers → download PDFs → extract conclusions.

    Args:
        category: arXiv category to search
        max_results: Maximum number of papers to fetch
        skip_ids: Set of arXiv IDs to skip (already processed)

    Returns:
        List of paper dicts, each enriched with 'conclusion' and 'pdf_path' keys.
    """
    # Fetch a larger pool so we don't run out if many recent papers are already filtered out
    # Constrain to absolute max 10 to avoid ArXiv 429 rate limit errors
    fetch_limit = min(10, max(5, max_results * 2))
    papers = fetch_papers(category, fetch_limit)

    # Filter out already-processed papers
    if skip_ids:
        original_count = len(papers)
        papers = [p for p in papers if p["arxiv_id"] not in skip_ids]
        skipped = original_count - len(papers)
        if skipped > 0:
            logger.info(f"Skipped {skipped} already-processed paper(s).")
            
    # Trim down to the exact number of max_results requested by user
    papers = papers[:max_results]

    enriched = []

    for paper in papers:
        try:
            # Create output dir per paper
            paper_dir = config.OUTPUT_DIR / paper["arxiv_id"]
            paper_dir.mkdir(parents=True, exist_ok=True)

            # Download and extract
            pdf_path = download_pdf(paper["pdf_url"], paper_dir)
            conclusion = extract_conclusion(pdf_path)

            if conclusion is None:
                logger.warning(f"Skipping paper {paper['arxiv_id']}: could not extract conclusion.")
                # Garbage collector: Clean up orphaned PDF dir since it's skipped
                shutil.rmtree(paper_dir, ignore_errors=True)
                continue

            paper["conclusion"] = conclusion
            paper["pdf_path"] = str(pdf_path)
            enriched.append(paper)

        except Exception as e:
            logger.error(f"Error processing paper {paper.get('arxiv_id', 'unknown')}: {e}", exc_info=True)
            if 'paper_dir' in locals() and paper_dir.exists():
                shutil.rmtree(paper_dir, ignore_errors=True)
            continue

    logger.info(f"Successfully processed {len(enriched)}/{len(papers)} papers.")
    return enriched
