"""
PaperBrief — Scheduler Engine
Runs automatically 2x daily or interactively with --run-once.
"""

import argparse
import random
import time
import logging
import schedule

import config
from main import run_batch
from modules import uploader, history_db

logger = logging.getLogger("Scheduler")

def job(lang_override=None):
    logger.info("⏰ Scheduler job started.")
    
    # Pick a random category
    category = random.choice(config.ARXIV_CATEGORIES)
    logger.info(f"🎲 Selected random category: {category}")
    
    lang = lang_override or config.SCHEDULE_LANG
    
    # Run batch processing for 1 paper (or based on config)
    # The scraper already filters out processed papers based on history_db
    results = run_batch(
        category=category,
        max_results=config.SCHEDULE_PAPERS_PER_RUN,
        dry_run=False,
        llm_provider=config.SCHEDULE_LLM_PROVIDER,
        llm_model=config.SCHEDULE_LLM_MODEL,
        tts_provider=config.SCHEDULE_TTS_PROVIDER,
        lang=lang,
    )
    
    for res in results:
        if res["status"] == "success":
            arxiv_id = res["arxiv_id"]
            video_path = res["output_path"]
            logger.info(f"🎥 Successfully generated video for {arxiv_id} at {video_path}")
            
            # Auto-upload phase (controls inside uploader.py will respect .env)
            uploader.upload_to_all_platforms(
                video_path=video_path,
                title=res["title"],
                arxiv_id=arxiv_id
            )
            
            # Storage cleanup: Erase the huge video resources automatically
            if getattr(config, "CLEANUP_AFTER_UPLOAD", True):
                import shutil
                paper_dir = config.OUTPUT_DIR / arxiv_id
                if paper_dir.exists():
                    logger.info(f"🧹 Clean up: permanently deleting '{paper_dir}' to free up storage")
                    try:
                        shutil.rmtree(paper_dir)
                    except Exception as e:
                        logger.error(f"⚠ Failed to clean up {paper_dir}: {e}")
        else:
            logger.warning(f"⚠ Generation failed for {res.get('arxiv_id', 'unknown')}")
            
    logger.info("✅ Scheduler job finished.")

def main():
    parser = argparse.ArgumentParser(description="PaperBrief Auto-Upload Scheduler")
    parser.add_argument("--run-once", action="store_true", help="Run the job once immediately without scheduling")
    parser.add_argument("--status", action="store_true", help="Print history statistics and exit")
    parser.add_argument("--lang", type=str, default=None, help="Override output language (e.g. EN, ID)")
    args = parser.parse_args()
    
    # Set up basic logging if not already done
    logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-7s │ %(name)-10s │ %(message)s")
    
    if args.status:
        stats = history_db.get_stats()
        print("\n📊 PaperBrief History Statistics:")
        print(f"  Total Processed : {stats['total_processed']}")
        print(f"  Successful      : {stats['success']}")
        print(f"  YouTube Uploads : {stats['uploaded_youtube']}\n")
        return
        
    if args.run_once:
        logger.info("🚀 Running single job (--run-once)...")
        job(lang_override=args.lang)
        return
        
    logger.info("📅 Starting Scheduler Daemon...")
    for t in config.SCHEDULE_TIMES:
        schedule.every().day.at(t).do(job, lang_override=args.lang)
        logger.info(f"   ↳ Scheduled daily job at {t}")
        
    logger.info("   ↳ Waiting for scheduled time. Leave this script running.")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
