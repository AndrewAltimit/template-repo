"""Log cleanup worker - removes old log files."""

from datetime import datetime, timedelta
import logging
import time

from core.config import settings

logger = logging.getLogger(__name__)


def cleanup_old_logs():
    """Remove log files older than retention period."""
    try:
        logs_dir = settings.logs_directory

        if not logs_dir.exists():
            logger.debug("Logs directory %s does not exist, skipping cleanup", logs_dir)
            return

        cutoff_date = datetime.now() - timedelta(days=settings.log_retention_days)
        removed_count = 0
        total_size = 0

        for log_file in logs_dir.glob("*.log"):
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

                if mtime < cutoff_date:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    removed_count += 1
                    total_size += file_size
                    logger.info("Removed old log file: %s", log_file.name)

            except Exception as e:
                logger.error("Failed to process log file %s: %s", log_file, e)

        if removed_count > 0:
            size_mb = total_size / (1024 * 1024)
            logger.info("Log cleanup complete: removed %s files, freed %.2f MB", removed_count, size_mb)
        else:
            logger.debug("No old log files to remove")

    except Exception as e:
        logger.error("Log cleanup failed: %s", e)


def start_log_cleanup_worker():
    """Start background worker for log cleanup.

    Runs cleanup every 24 hours.
    """
    logger.info("Starting log cleanup worker")

    while True:
        try:
            cleanup_old_logs()
        except Exception as e:
            logger.error("Log cleanup worker error: %s", e)

        # Sleep for 24 hours
        time.sleep(86400)
