"""Append-only JSONL audit trail: every guard decision and tool call is recorded."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.events: list[dict[str, Any]] = []
        self.run_id = uuid.uuid4().hex[:12]

    def record(self, event: str, **data: Any) -> None:
        entry = {"ts": time.time(), "run_id": self.run_id, "event": event, **data}
        self.events.append(entry)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

    def of(self, event: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["event"] == event]
