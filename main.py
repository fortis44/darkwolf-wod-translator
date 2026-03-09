"""DarkWolf WOD Translator — main entry point.

Orchestrates the full pipeline:
1. Check if today's WOD is already processed
2. Scrape crossfit.com
3. Generate both modifications via Claude API
4. Build HTML pages
5. Publish to GitHub Pages
6. Log results
"""

import json
import logging
import sys
import time
from datetime import date
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config
from scraper import fetch_wod
from modifier import modify_wod
from generator import generate_wod_page, generate_index_page
from publisher import publish


def setup_logging():
    """Configure rotating file + console logging."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # File handler (rotating, 5 MB max, keep 3 backups)
    fh = RotatingFileHandler(
        config.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)


def load_wod_log() -> list:
    """Load the WOD processing log."""
    if config.WOD_LOG.exists():
        return json.loads(config.WOD_LOG.read_text(encoding="utf-8"))
    return []


def save_wod_log(log: list):
    """Save the WOD processing log."""
    config.WOD_LOG.write_text(
        json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def is_already_processed(today: str, log: list) -> bool:
    """Check if today's WOD has already been processed successfully."""
    return any(
        entry.get("date", "")[:10] == today and entry.get("status") == "success"
        for entry in log
    )


def run():
    """Execute the full WOD translation pipeline."""
    setup_logging()
    logger = logging.getLogger(__name__)

    today = date.today().isoformat()
    logger.info("=== DarkWolf WOD Translator — %s ===", today)

    # Load processing log
    wod_log = load_wod_log()

    # Check if already processed
    if is_already_processed(today, wod_log):
        logger.info("Today's WOD already processed. Exiting.")
        return

    log_entry = {"date": today, "status": "pending", "errors": []}

    try:
        # Step 1: Scrape
        logger.info("Step 1: Scraping crossfit.com...")
        wod_data = _retry(fetch_wod, "scrape")
        log_entry["title"] = wod_data.get("title", "")
        log_entry["is_rest_day"] = wod_data.get("is_rest_day", False)

        # Step 2: Modify via Claude API
        logger.info("Step 2: Generating modifications via Claude API...")
        modifications = _retry(lambda: modify_wod(wod_data), "modify")

        # Step 3: Generate HTML
        logger.info("Step 3: Generating HTML pages...")
        wod_page_path = generate_wod_page(wod_data, modifications)

        # Save log entry before generating index so today's WOD appears in sitemap
        log_entry["status"] = "success"
        wod_log.append(log_entry)
        save_wod_log(wod_log)

        index_page_path = generate_index_page()

        # Step 4: Publish to GitHub Pages
        logger.info("Step 4: Publishing to GitHub Pages...")
        seo_files = [
            str(config.OUTPUT_DIR / "sitemap.xml"),
            str(config.OUTPUT_DIR / "robots.txt"),
        ]
        published = publish([wod_page_path, index_page_path] + seo_files)
        if not published:
            log_entry["errors"].append("Publish to GitHub Pages failed")
            logger.warning("Publish failed — files saved locally only")

        logger.info("Pipeline complete! WOD page: %s", wod_page_path)

    except Exception as e:
        log_entry["status"] = "error"
        log_entry["errors"].append(str(e))
        logger.exception("Pipeline failed: %s", e)
        # Only save on error (success was already saved before index generation)
        wod_log.append(log_entry)
        save_wod_log(wod_log)


def _retry(func, label: str, max_retries: int = config.MAX_RETRIES):
    """Retry a function with exponential backoff."""
    logger = logging.getLogger(__name__)
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as e:
            logger.warning(
                "%s attempt %d/%d failed: %s", label, attempt, max_retries, e
            )
            if attempt == max_retries:
                raise
            time.sleep(config.RETRY_DELAY * attempt)


if __name__ == "__main__":
    run()
