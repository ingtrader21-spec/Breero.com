"""Canonical event envelope shared by CRM delivery providers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def value_from(source: object, name: str, default: Any = None) -> Any:
    return source.get(name, default) if isinstance(source, dict) else getattr(source, name, default)


def build_event_envelope(event: object) -> dict[str, Any]:
    event_id = value_from(event, "id")
    created_at = value_from(event, "created_at") or datetime.now(UTC)
    return {
        "event_id": str(event_id),
        "event_type": value_from(event, "event_type"),
        "schema_version": value_from(event, "schema_version", 1),
        "aggregate_id": str(value_from(event, "aggregate_id")),
        "aggregate_version": value_from(event, "aggregate_version", 1),
        "occurred_at": created_at.isoformat(),
        "idempotency_key": value_from(event, "idempotency_key") or str(event_id),
        "source": "breero",
        "payload": value_from(event, "payload", {}),
    }
