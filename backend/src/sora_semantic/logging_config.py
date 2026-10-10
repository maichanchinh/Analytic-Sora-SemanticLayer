"""JSON logging configuration shared by the API and MCP launchers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import logging.config
import os
from pathlib import Path
import re
from typing import Any


_REQUEST_ID = re.compile(r"\brequest_id=([A-Za-z0-9._-]{1,128})\b")
_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


class JsonFormatter(logging.Formatter):
    """Format each record as one operational JSON event."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        event: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "service": os.getenv("SERVICE_NAME", "semantic-layer"),
            "logger": record.name,
            "message": message,
        }
        request_id = getattr(record, "request_id", None)
        if request_id is None:
            match = _REQUEST_ID.search(message)
            request_id = match.group(1) if match else None
        if request_id is not None:
            event["request_id"] = str(request_id)
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


class MinimumLevelFilter(logging.Filter):
    """Apply the LOG_LEVEL environment setting to stdout log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        minimum = _LEVELS.get(level_name, logging.INFO)
        return record.levelno >= minimum


def configure_json_logging() -> None:
    """Load the JSON logging config baked into the backend image."""
    config_path = Path(__file__).with_name("logging.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    logging.config.dictConfig(config)
