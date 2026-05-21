from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from ksef.utils import ensure_dir


def configure_logging(log_dir: Path, mode: str) -> Path:
    ensure_dir(log_dir)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log_file = log_dir / f"ksef-sync_{mode}_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    logging.info("Log file: %s", log_file)
    return log_file
