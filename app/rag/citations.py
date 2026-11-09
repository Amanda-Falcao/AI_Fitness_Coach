"""Extract authoritative citation records from internal retriever tool messages."""

import json
import re
from typing import Any


_REFERENCE_PATTERN = re.compile(r"^KB-[0-9a-f]{12}$")
RAG_TOOL_NAME = "fitness_knowledge_base_search"


def citation_registry_from_messages(messages: list[Any]) -> dict[str, dict[str, str]]:
    """Build a deduplicated citation registry from actual RAG tool results.

    Only messages produced by the internal knowledge tool are accepted. The
    model may select reference IDs in its plan but cannot supply source metadata.
    """
    registry: dict[str, dict[str, str]] = {}
    for message in messages:
        if getattr(message, "name", None) != RAG_TOOL_NAME:
            continue
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip().startswith(("[", "{")):
            continue
        try:
            records = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("RAG tool returned malformed citation records") from exc
        if not isinstance(records, list):
            raise ValueError("RAG tool citation result must be a JSON list")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("RAG tool citation record must be an object")
            ref_id = record.get("ref_id")
            source = record.get("source")
            evidence = record.get("evidence")
            if (
                not isinstance(ref_id, str)
                or not _REFERENCE_PATTERN.fullmatch(ref_id)
                or not isinstance(source, str)
                or not source.strip()
                or not isinstance(evidence, str)
                or not evidence.strip()
            ):
                raise ValueError("RAG tool returned an invalid citation record")
            normalized = {"source": source.strip(), "evidence": evidence.strip()}
            if ref_id in registry and registry[ref_id] != normalized:
                raise ValueError(f"Conflicting RAG citation record: {ref_id}")
            registry[ref_id] = normalized
    return registry
