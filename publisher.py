"""Publishes generated WOD pages to GitHub Pages via git push."""

import logging
import shutil
import subprocess
from pathlib import Path

import config

logger = logging.getLogger(__name__)

PAGES_DIR = config.BASE_DIR / "gh-pages"


def publish(file_paths: list[str]) -> bool:
    """Copy generated files into the gh-pages branch and push.

    Args:
        file_paths: List of absolute paths to files to publish.

    Returns:
        True if published successfully.
    """
    try:
        _ensure_pages_branch()

        # Copy CSS
        css_src = config.TEMPLATES_DIR / "style.css"
        if css_src.exists():
            shutil.copy2(str(css_src), str(PAGES_DIR / "style.css"))

        # Copy each generated file
        for local_path in file_paths:
            filename = Path(local_path).name
            dest = PAGES_DIR / filename
            shutil.copy2(local_path, str(dest))
            logger.info("Copied %s to gh-pages/", filename)

        # Git add, commit, push
        _run_git("add", "-A", cwd=PAGES_DIR)

        # Check if there's anything to commit
        result = _run_git("status", "--porcelain", cwd=PAGES_DIR)
        if not result.strip():
            logger.info("No changes to publish")
            return True

        _run_git("commit", "-m", "Update WOD pages", cwd=PAGES_DIR)
        _run_git("push", "origin", "gh-pages", cwd=PAGES_DIR)

        logger.info("Published to GitHub Pages successfully")
        return True

    except Exception:
        logger.exception("GitHub Pages publish failed")
        return False


def _ensure_pages_branch():
    """Clone or update the gh-pages worktree."""
    if PAGES_DIR.exists() and (PAGES_DIR / ".git").exists():
        # Already cloned, just pull
        _run_git("checkout", "gh-pages", cwd=PAGES_DIR)
        _run_git("pull", "--rebase", "origin", "gh-pages", cwd=PAGES_DIR)
        return

    if PAGES_DIR.exists():
        shutil.rmtree(str(PAGES_DIR))

    # Get the remote URL from the main repo
    remote_url = _run_git(
        "remote", "get-url", "origin", cwd=str(config.BASE_DIR)
    ).strip()

    # Check if gh-pages branch exists on remote
    result = _run_git(
        "ls-remote", "--heads", "origin", "gh-pages",
        cwd=str(config.BASE_DIR),
    )

    if "gh-pages" in result:
        # Clone just the gh-pages branch
        _run_git_raw(
            "git", "clone", "--branch", "gh-pages", "--single-branch",
            remote_url, str(PAGES_DIR),
        )
    else:
        # Create orphan gh-pages branch
        PAGES_DIR.mkdir(parents=True, exist_ok=True)
        _run_git("init", cwd=PAGES_DIR)
        _run_git("checkout", "--orphan", "gh-pages", cwd=PAGES_DIR)
        _run_git("remote", "add", "origin", remote_url, cwd=PAGES_DIR)

    # Set git identity for the pages repo
    _run_git("config", "user.name", "Kelly Ryan", cwd=PAGES_DIR)
    _run_git("config", "user.email", "kelly.ryan.a@protonmail.com", cwd=PAGES_DIR)


def _run_git(*args, cwd=None) -> str:
    """Run a git command and return stdout."""
    return _run_git_raw("git", *args, cwd=cwd)


def _run_git_raw(*args, cwd=None) -> str:
    """Run a command and return stdout."""
    result = subprocess.run(
        args,
        cwd=cwd or str(PAGES_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        logger.error("Command failed: %s\nstderr: %s", " ".join(args), result.stderr)
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{result.stderr}")
    return result.stdout
