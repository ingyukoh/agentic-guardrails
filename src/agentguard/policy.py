"""Core guardrail types shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    guardrail: str
    reason: str = ""
    # Guards may rewrite content (e.g. redaction) instead of blocking it.
    rewritten: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class GuardrailViolation(Exception):
    def __init__(self, verdict: Verdict):
        super().__init__(f"[{verdict.guardrail}] {verdict.reason}")
        self.verdict = verdict


class Guardrail(Protocol):
    name: str


def allow(name: str, rewritten: str | None = None, **meta: Any) -> Verdict:
    return Verdict(Decision.ALLOW, name, rewritten=rewritten, meta=meta)


def deny(name: str, reason: str, **meta: Any) -> Verdict:
    return Verdict(Decision.DENY, name, reason, meta=meta)


def needs_approval(name: str, reason: str, **meta: Any) -> Verdict:
    return Verdict(Decision.REQUIRE_APPROVAL, name, reason, meta=meta)
