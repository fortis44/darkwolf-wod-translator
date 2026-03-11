"""Publishes generated WOD pages to the main DarkWolf site repo."""

import logging
import shutil
import subprocess
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# Target directory: C:\DarkWolfSite\wod\
SITE_WOD_DIR = config.SITE_WOD_DIR
SITE_DIR = config.SITE_DIR


def publish(file_paths: list[str]) -> bool:
    """Copy generated files into the main site's wod/ directory and push.

    Args:
        file_paths: List of absolute paths to files to publish.

    Returns:
        True if published successfully.
    """
    try:
        SITE_WOD_DIR.mkdir(parents=True, exist_ok=True)

        # Pull latest from main site repo
        _run_git("pull", "--rebase", "origin", "master", cwd=SITE_DIR)

        # Copy the rethemed CSS from the site's wod dir (already there)
        # If not, copy from templates
        site_css = SITE_WOD_DIR / "style.css"
        if not site_css.exists():
            css_src = config.TEMPLATES_DIR / "style.css"
            if css_src.exists():
                shutil.copy2(str(css_src), str(site_css))

        # Copy each generated file
        for local_path in file_paths:
            filename = Path(local_path).name
            dest = SITE_WOD_DIR / filename
            shutil.copy2(local_path, str(dest))
            logger.info("Copied %s to DarkWolfSite/wod/", filename)

        # Git add, commit, push from the main site repo
        _run_git("add", "wod/", cwd=SITE_DIR)

        # Check if there's anything to commit
        result = _run_git("status", "--porcelain", cwd=SITE_DIR)
        if not result.strip():
            logger.info("No changes to publish")
            return True

        _run_git("commit", "-m", "Update daily WOD pages", cwd=SITE_DIR)
        _run_git("push", "origin", "master", cwd=SITE_DIR)

        logger.info("Published WOD pages to main site successfully")
        return True

    except Exception:
        logger.exception("WOD publish to main site failed")
        return False


def _run_git(*args, cwd=None) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd or str(SITE_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        logger.error("Command failed: git %s\nstderr: %s", " ".join(args), result.stderr)
        raise RuntimeError(f"Command failed: git {' '.join(args)}\n{result.stderr}")
    return result.stdout
