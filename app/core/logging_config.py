import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format logs as JSON for centralized observability."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        safe_fields = (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "environment",
        )

        for field in safe_fields:
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(log_entry, ensure_ascii=False)


def configure_logging(log_level: str = "INFO") -> None:
    """Set up JSON logging without duplicate root handlers."""

    numeric_level = getattr(logging, log_level.upper(), None)

    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid logging level: {log_level}")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)