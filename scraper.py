"""Scrapes the daily WOD from crossfit.com."""

import logging
import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

REST_DAY_KEYWORDS = ["rest day", "rest", "active recovery"]


def fetch_wod(target_date: date | None = None) -> dict:
    """Fetch a WOD from crossfit.com for the given date.

    CrossFit typically posts tomorrow's WOD in the evening, so by default
    we fetch today's date (which was posted the night before).

    Args:
        target_date: The date to fetch. Defaults to today.

    Returns:
        dict with keys: date, title, raw_text, is_rest_day
    """
    if target_date is None:
        target_date = date.today()

    url = _build_url(target_date)
    logger.info("Fetching WOD from %s", url)

    resp = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        timeout=30,
    )
    resp.raise_for_status()

    wod_text = _extract_article_text(resp.text)

    if not wod_text:
        raise ValueError(f"Could not extract WOD text from {url}")

    # Extract title from page
    title_match = re.search(r"<title>(.*?)</title>", resp.text)
    title = title_match.group(1).strip() if title_match else ""
    # Clean up title
    title = re.sub(r"\s*\|\s*CrossFit.*$", "", title).strip()

    is_rest_day = _is_rest_day(wod_text)
    date_str = target_date.isoformat()

    logger.info("WOD fetched for %s (%d chars, rest_day=%s)", date_str, len(wod_text), is_rest_day)

    return {
        "date": date_str,
        "title": title or f"WOD - {date_str}",
        "raw_text": wod_text,
        "is_rest_day": is_rest_day,
    }


def _build_url(d: date) -> str:
    """Build the crossfit.com workout URL for a given date."""
    return f"https://www.crossfit.com/workout/{d.year}/{d.month:02d}/{d.day:02d}"


def _extract_article_text(html: str) -> str | None:
    """Extract the WOD text from the <article> tag."""
    soup = BeautifulSoup(html, "html.parser")

    article = soup.find("article")
    if article:
        text = article.get_text(separator="\n").strip()
        if len(text) > 20:
            # Clean up excessive whitespace while preserving structure
            lines = [line.strip() for line in text.splitlines()]
            # Remove consecutive blank lines (keep max 1)
            cleaned = []
            prev_blank = False
            for line in lines:
                if not line:
                    if not prev_blank:
                        cleaned.append("")
                    prev_blank = True
                else:
                    cleaned.append(line)
                    prev_blank = False
            result = "\n".join(cleaned).strip()
            # Strip trailing boilerplate
            for marker in ["Find a gym near you:", "View the CrossFit map"]:
                idx = result.find(marker)
                if idx != -1:
                    result = result[:idx].strip()
            return result

    return None


def _is_rest_day(text: str) -> bool:
    """Detect if the WOD is a rest day."""
    text_lower = text.lower().strip()
    # Short text with rest keyword
    if len(text_lower) < 100:
        return any(kw in text_lower for kw in REST_DAY_KEYWORDS)
    # First line is "Rest Day" (crossfit.com rest day pages start this way)
    first_line = text_lower.split("\n")[0].strip()
    if first_line in ("rest day", "rest"):
        return True
    return False
