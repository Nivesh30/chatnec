"""Structured (JSON) logging setup. Kept to the standard library — no structlog —
since chatnec's logging needs are a handful of fields per event, not a full
structured-logging pipeline.
"""
from __future__ import annotations

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key.startswith("chatnec_"):
                payload[key[len("chatnec_") :]] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if json_format
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
