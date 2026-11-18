"""Log JSON một dòng ra stdout, che nội dung nhạy cảm (10 mục 3.10)."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)

SENSITIVE_KEYS = ("password", "token", "secret", "authorization", "text", "content", "payload", "body")
_TOKEN_LIKE = re.compile(r"[A-Za-z0-9_\-+/=.]{25,}")
_LONG_DIGITS = re.compile(r"\d{9,}")
_STANDARD_ATTRS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


def redact_text(value: str) -> str:
    value = _TOKEN_LIKE.sub("[che]", value)
    return _LONG_DIGITS.sub("[che]", value)


def redact_value(key: str, value):
    if any(s in key.lower() for s in SENSITIVE_KEYS):
        return "[che]"
    if isinstance(value, dict):
        return {k: redact_value(k, v) for k, v in value.items()}
    if isinstance(value, str):
        return redact_text(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_text(record.getMessage()),
        }
        request_id = request_id_var.get()
        if request_id:
            data["request_id"] = request_id
        user_id = user_id_var.get()
        if user_id:
            data["user_id"] = user_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                data[key] = redact_value(key, value)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("uvicorn.access", "botocore", "urllib3", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
