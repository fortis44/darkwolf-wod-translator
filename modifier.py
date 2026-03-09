"""Claude API calls to generate TBI-modified and TBI+RC-modified WODs."""

import json
import logging
from pathlib import Path

import anthropic

import config

logger = logging.getLogger(__name__)


def load_prompt(filename: str) -> str:
    """Load a system prompt from the prompts directory."""
    path = config.PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8").strip()


def modify_wod(wod_data: dict) -> dict:
    """Generate both TBI-only and TBI+RC modifications for a WOD.

    Returns dict with keys: tbi, tbi_rc (each containing the structured modification).
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    raw_text = wod_data["raw_text"]
    is_rest_day = wod_data.get("is_rest_day", False)

    user_message = _build_user_message(raw_text, is_rest_day)

    # Call 1: TBI-only modification
    logger.info("Generating TBI-modified WOD...")
    tbi_system = load_prompt("tbi_system.txt")
    tbi_result = _call_claude(client, tbi_system, user_message)

    # Call 2: TBI + Rotator Cuff modification
    logger.info("Generating TBI+RC-modified WOD...")
    tbi_rc_system = load_prompt("tbi_rc_system.txt")
    tbi_rc_result = _call_claude(client, tbi_rc_system, user_message)

    return {
        "tbi": tbi_result,
        "tbi_rc": tbi_rc_result,
    }


def _build_user_message(raw_text: str, is_rest_day: bool) -> str:
    """Build the user message to send to Claude."""
    if is_rest_day:
        return (
            "Today is a REST DAY on crossfit.com. There is no programmed workout.\n\n"
            "Please generate a 20-minute recovery and mobility session instead. "
            "Include a brief warmup, the mobility/recovery flow, and a cooldown.\n\n"
            f"Original posting:\n{raw_text}"
        )
    return (
        "Here is today's CrossFit WOD. Please modify it according to your instructions "
        "and return the result as structured JSON.\n\n"
        f"ORIGINAL WOD:\n{raw_text}"
    )


def _call_claude(client: anthropic.Anthropic, system_prompt: str, user_message: str) -> dict:
    """Make a single Claude API call and parse the JSON response."""
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract text content
    text = response.content[0].text.strip()

    # Parse JSON from the response (may be wrapped in ```json blocks)
    json_str = _extract_json(text)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response as JSON. Raw response:\n%s", text)
        # Return the raw text wrapped in a fallback structure
        return {
            "warmup": {"duration": "See below", "movements": []},
            "workout": {
                "name": "Modified WOD",
                "type": "See below",
                "movements": [],
                "notes": text,
            },
            "cooldown": {"duration": "See below", "movements": []},
            "intensity_notes": "Could not parse structured response.",
            "_raw": text,
        }


def _extract_json(text: str) -> str:
    """Extract JSON from Claude's response, handling markdown code blocks."""
    # Try to find JSON in ```json ... ``` blocks
    import re

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find raw JSON (starts with {)
    start = text.find("{")
    if start != -1:
        # Find the matching closing brace
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

    # Return as-is and let the caller handle the error
    return text
