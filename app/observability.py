"""Small standard-library JSON logging and provider token-usage helpers."""

import json
import logging
from datetime import datetime, timezone
from typing import Any


_SAFE_EXTRA_FIELDS = (
    "event",
    "duration_ms",
    "session_count",
    "model_name",
    "token_usage",
    "error_type",
    "output_path",
)


class JsonLogFormatter(logging.Formatter):
    """Format logs as single-line JSON without request or credential contents."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _SAFE_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(level: int = logging.INFO) -> None:
    """Configure concise JSON logs for CLI runs."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def aggregate_token_usage(messages: list[Any]) -> dict[str, int] | None:
    """Aggregate token metadata when the provider supplies it; never estimate cost."""
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    found = False
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if not isinstance(usage, dict):
            metadata = getattr(message, "response_metadata", None)
            usage = metadata.get("token_usage") if isinstance(metadata, dict) else None
        if not isinstance(usage, dict):
            continue
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
        total_tokens = usage.get("total_tokens")
        if not all(isinstance(value, int) and value >= 0 for value in (input_tokens, output_tokens)):
            continue
        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["total_tokens"] += (
            total_tokens if isinstance(total_tokens, int) and total_tokens >= 0
            else input_tokens + output_tokens
        )
        found = True
    return totals if found else None
