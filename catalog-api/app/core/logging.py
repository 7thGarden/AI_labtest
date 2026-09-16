"""Structured JSON logging for the Catalog API.

Produces machine-readable JSON log lines so Fluent Bit/Logstash can
parse them into fields (timestamp, service, namespace, pod, container,
level, message, error, request_id, trace_id).
"""

import json
import logging
import sys
from datetime import datetime, timezone
from uuid import uuid4


class JsonFormatter(logging.Formatter):
    """Emit a single JSON object per log line."""

    def __init__(self, service: str = "catalog-api", include_stack: bool = True):
        super().__init__()
        self.service = service
        self.include_stack = include_stack

    def format(self, record):
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        obj: dict = {
            "timestamp": ts,
            "service": self.service,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "request_id") and record.request_id:
            obj["request_id"] = record.request_id
        if hasattr(record, "trace_id") and record.trace_id:
            obj["trace_id"] = record.trace_id
        if record.exc_info and record.exc_info[0] is not None:
            obj["error"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }
            if self.include_stack:
                obj["error"]["stack"] = self.formatException(record.exc_info)
        if getattr(record, "status_code", None) is not None:
            obj["status_code"] = record.status_code
        return json.dumps(obj)


def configure_logging(service: str = "catalog-api", level: str = "INFO"):
    """Attach a JSON formatter to the root logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service=service))
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.addHandler(handler)
    return logger


class RequestContext(logging.Filter):
    """Inject request_id / trace_id into every log record."""

    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = getattr(record, "request_id", None)
        if not hasattr(record, "trace_id"):
            record.trace_id = getattr(record, "trace_id", None)
        return True
