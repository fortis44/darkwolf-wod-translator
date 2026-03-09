"""Generates branded HTML pages from WOD data using Jinja2 templates."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config

logger = logging.getLogger(__name__)


def get_jinja_env() -> Environment:
    """Create configured Jinja2 environment."""
    return Environment(
        loader=FileSystemLoader(str(config.TEMPLATES_DIR)),
        autoescape=True,
    )


def generate_wod_page(wod_data: dict, modifications: dict) -> str:
    """Generate an individual WOD HTML page.

    Args:
        wod_data: Original WOD info (date, title, raw_text, is_rest_day)
        modifications: Dict with 'tbi' and 'tbi_rc' modification results

    Returns:
        Path to the generated HTML file.
    """
    env = get_jinja_env()
    template = env.get_template("wod_page.html")

    wod_date = wod_data["date"]
    # Parse date for display and navigation
    if isinstance(wod_date, str):
        dt = datetime.strptime(wod_date[:10], "%Y-%m-%d")
    else:
        dt = wod_date

    date_display = dt.strftime("%A, %B %d, %Y")
    prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    filename = dt.strftime("%Y-%m-%d") + ".html"

    html = template.render(
        date_display=date_display,
        date_iso=dt.strftime("%Y-%m-%d"),
        title=wod_data.get("title", ""),
        original_wod=wod_data["raw_text"],
        is_rest_day=wod_data.get("is_rest_day", False),
        tbi=modifications["tbi"],
        tbi_rc=modifications["tbi_rc"],
        prev_date=prev_date,
        next_date=next_date,
        site_base_url=config.SITE_BASE_URL,
    )

    output_path = config.OUTPUT_DIR / filename
    output_path.write_text(html, encoding="utf-8")
    logger.info("Generated WOD page: %s", output_path)
    return str(output_path)


def generate_index_page() -> str:
    """Regenerate the index page listing all WODs (most recent first).

    Returns:
        Path to the generated index.html file.
    """
    env = get_jinja_env()
    template = env.get_template("index.html")

    # Read the WOD log to get all processed dates
    wods = []
    if config.WOD_LOG.exists():
        log_data = json.loads(config.WOD_LOG.read_text(encoding="utf-8"))
        for entry in log_data:
            if entry.get("status") == "success":
                dt = datetime.strptime(entry["date"][:10], "%Y-%m-%d")
                wods.append({
                    "date": entry["date"][:10],
                    "date_display": dt.strftime("%A, %B %d, %Y"),
                    "title": entry.get("title", ""),
                    "is_rest_day": entry.get("is_rest_day", False),
                })

    # Sort most recent first
    wods.sort(key=lambda w: w["date"], reverse=True)

    html = template.render(
        wods=wods,
        site_base_url=config.SITE_BASE_URL,
    )

    output_path = config.OUTPUT_DIR / "index.html"
    output_path.write_text(html, encoding="utf-8")
    logger.info("Generated index page with %d WODs", len(wods))
    return str(output_path)
