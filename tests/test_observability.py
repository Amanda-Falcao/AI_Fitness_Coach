import json
import logging
from types import SimpleNamespace

from app.observability import JsonLogFormatter, aggregate_token_usage


def test_json_formatter_emits_allowlisted_event_fields_only():
    record = logging.LogRecord(
        "app.main", logging.INFO, "main.py", 1, "generation complete", (), None
    )
    record.event = "agent.plan_generation_completed"
    record.duration_ms = 12.5
    record.api_key = "must-not-be-serialized"

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["event"] == "agent.plan_generation_completed"
    assert payload["duration_ms"] == 12.5
    assert "api_key" not in payload
    assert "must-not-be-serialized" not in json.dumps(payload)


def test_aggregates_provider_usage_metadata_and_returns_none_when_missing():
    messages = [
        SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}),
        SimpleNamespace(response_metadata={"token_usage": {"prompt_tokens": 5, "completion_tokens": 2}}),
        SimpleNamespace(),
    ]

    assert aggregate_token_usage(messages) == {
        "input_tokens": 15,
        "output_tokens": 6,
        "total_tokens": 21,
    }
    assert aggregate_token_usage([SimpleNamespace()]) is None
