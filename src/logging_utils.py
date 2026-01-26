import json
import logging
from typing import Any

from .utils import utc_now_iso


def configure_logging(level: str = "INFO", json_enabled: bool = True) -> None:
    if json_enabled:
        logging.basicConfig(level=level, format="%(message)s", force=True)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            force=True,
        )


def log_event(
    logger: logging.Logger,
    action: str,
    status: str,
    level: int = logging.INFO,
    json_enabled: bool = True,
    **fields: Any,
) -> None:
    if not json_enabled:
        logger.log(level, "%s %s %s", action, status, fields)
        return

    payload = {
        "timestamp": utc_now_iso(),
        "level": logging.getLevelName(level),
        "action": action,
        "status": status,
        **fields,
    }
    logger.log(level, json.dumps(payload, ensure_ascii=True))
