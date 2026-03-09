"""Scrapes the daily WOD from crossfit.com."""

import json
import re
import logging
import requests
from datetime import date

import config

logger = logging.getLogger(__name__)

# REST_DAY_KEYWORDS appear in WOD text when there's no workout
REST_DAY_KEYWORDS = ["rest day", "rest", "active recovery"]


def fetch_wod() -> dict:
    """Fetch today's WOD from crossfit.com.

    Returns dict with keys: date, title, raw_text, is_rest_day
    """
    logger.info("Fetching WOD from %s", config.CROSSFIT_WOD_URL)

    resp = requests.get(
        config.CROSSFIT_WOD_URL,
        headers={"User-Agent": "DarkWolf WOD Translator/1.0"},
        timeout=30,
    )
    resp.raise_for_status()

    wod_data = _parse_preloaded_state(resp.text)

    if wod_data is None:
        wod_data = _parse_html_fallback(resp.text)

    if wod_data is None:
        raise ValueError("Could not parse WOD from crossfit.com response")

    logger.info("WOD fetched for %s: %s", wod_data["date"], wod_data["title"])
    return wod_data


def _parse_preloaded_state(html: str) -> dict | None:
    """Try to extract WOD from window.__PRELOADED_STATE__ JSON."""
    match = re.search(
        r"window\.__PRELOADED_STATE__\s*=\s*({.*?});?\s*</script>",
        html,
        re.DOTALL,
    )
    if not match:
        logger.debug("No __PRELOADED_STATE__ found, trying fallback")
        return None

    try:
        state = json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.warning("Failed to parse __PRELOADED_STATE__ JSON")
        return None

    # Navigate the state object — structure may vary
    # Try common paths: state.wod, state.data, state.posts, etc.
    wod_text = None
    wod_title = None
    wod_date = None

    # Path 1: state -> wod or workout
    for key in ("wod", "workout", "data"):
        if key in state and isinstance(state[key], dict):
            obj = state[key]
            wod_text = obj.get("description") or obj.get("content") or obj.get("text")
            wod_title = obj.get("title", "")
            wod_date = obj.get("date", "")
            if wod_text:
                break

    # Path 2: nested in posts/items list
    if not wod_text:
        for key in ("posts", "items", "workouts"):
            items = state.get(key, [])
            if isinstance(items, list) and items:
                obj = items[0]
                if isinstance(obj, dict):
                    wod_text = (
                        obj.get("description")
                        or obj.get("content")
                        or obj.get("text")
                    )
                    wod_title = obj.get("title", "")
                    wod_date = obj.get("date", "")
                    if wod_text:
                        break

    # Path 3: deep search for any key containing 'wod' or 'workout'
    if not wod_text:
        wod_text = _deep_search_text(state)

    if not wod_text:
        return None

    if not wod_date:
        wod_date = date.today().isoformat()

    is_rest_day = _is_rest_day(wod_text)

    return {
        "date": wod_date,
        "title": wod_title or f"WOD - {wod_date}",
        "raw_text": wod_text.strip(),
        "is_rest_day": is_rest_day,
    }


def _deep_search_text(obj, depth=0) -> str | None:
    """Recursively search JSON for workout text content."""
    if depth > 5:
        return None
    if isinstance(obj, str) and len(obj) > 50:
        # Likely a workout description
        return obj
    if isinstance(obj, dict):
        for key in obj:
            if any(kw in key.lower() for kw in ("wod", "workout", "description", "content")):
                val = obj[key]
                if isinstance(val, str) and len(val) > 20:
                    return val
        for val in obj.values():
            result = _deep_search_text(val, depth + 1)
            if result:
                return result
    if isinstance(obj, list):
        for item in obj:
            result = _deep_search_text(item, depth + 1)
            if result:
                return result
    return None


def _parse_html_fallback(html: str) -> dict | None:
    """Fallback: parse WOD from HTML content directly."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Look for common WOD container patterns
    selectors = [
        ".wod-content",
        ".workout-content",
        "[class*='wod']",
        "[class*='workout']",
        "article",
        ".entry-content",
        ".post-content",
    ]

    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n").strip()
            if len(text) > 20:
                title_el = soup.select_one("h1, h2, .wod-title, .entry-title")
                title = title_el.get_text().strip() if title_el else ""
                return {
                    "date": date.today().isoformat(),
                    "title": title or f"WOD - {date.today().isoformat()}",
                    "raw_text": text,
                    "is_rest_day": _is_rest_day(text),
                }

    return None


def _is_rest_day(text: str) -> bool:
    """Detect if the WOD is a rest day."""
    text_lower = text.lower().strip()
    # If the entire text is very short and contains rest keywords
    if len(text_lower) < 100:
        return any(kw in text_lower for kw in REST_DAY_KEYWORDS)
    return False
