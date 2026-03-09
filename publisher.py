"""Uploads generated files to Hostinger via SFTP."""

import logging
import os
from pathlib import Path

import paramiko

import config

logger = logging.getLogger(__name__)


def upload_files(file_paths: list[str]) -> bool:
    """Upload a list of local files to the Hostinger remote directory.

    Args:
        file_paths: List of absolute paths to files to upload.

    Returns:
        True if all files uploaded successfully.
    """
    if not config.FTP_HOST:
        logger.warning("FTP_HOST not configured — skipping upload")
        return False

    try:
        transport = paramiko.Transport((config.FTP_HOST, config.FTP_PORT))
        transport.connect(username=config.FTP_USERNAME, password=config.FTP_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        # Ensure remote directory exists
        _mkdir_p(sftp, config.FTP_REMOTE_DIR)

        for local_path in file_paths:
            filename = Path(local_path).name
            remote_path = config.FTP_REMOTE_DIR.rstrip("/") + "/" + filename
            logger.info("Uploading %s -> %s", filename, remote_path)
            sftp.put(local_path, remote_path)

            # Verify upload
            remote_stat = sftp.stat(remote_path)
            local_size = os.path.getsize(local_path)
            if remote_stat.st_size != local_size:
                logger.error(
                    "Size mismatch for %s: local=%d remote=%d",
                    filename, local_size, remote_stat.st_size,
                )
                return False

        sftp.close()
        transport.close()
        logger.info("All %d files uploaded successfully", len(file_paths))
        return True

    except Exception:
        logger.exception("SFTP upload failed")
        return False


def upload_css() -> bool:
    """Upload the CSS file (only needs to be done once or when CSS changes)."""
    css_path = str(config.TEMPLATES_DIR / "style.css")
    if not Path(css_path).exists():
        logger.warning("style.css not found at %s", css_path)
        return False
    return upload_files([css_path])


def _mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str):
    """Recursively create remote directories if they don't exist."""
    dirs_to_create = []
    current = remote_dir
    while current and current != "/":
        try:
            sftp.stat(current)
            break
        except FileNotFoundError:
            dirs_to_create.insert(0, current)
            current = str(Path(current).parent).replace("\\", "/")

    for d in dirs_to_create:
        try:
            sftp.mkdir(d)
            logger.debug("Created remote directory: %s", d)
        except IOError:
            pass  # May already exist
