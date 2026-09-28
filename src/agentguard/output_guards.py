"""Guards applied to model output and tool results before they leave the system."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agentguard.policy import Verdict, allow, deny

_PII = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}\b"),
    "card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
}

_SECRETS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "generic_api_key": re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{20,}\b"),
}


@dataclass
class PIIRedactor:
    """Rewrites PII to typed placeholders rather than blocking the response."""

    name: str = "output.pii_redaction"

    def check(self, text: str) -> Verdict:
        found: dict[str, int] = {}
        out = text
        for kind, rx in _PII.items():
            out, n = rx.subn(f"[REDACTED_{kind.upper()}]", out)
            if n:
                found[kind] = n
        return allow(self.name, rewritten=out if found else None, redactions=found)


@dataclass
class SecretLeakBlocker:
    """Secrets are never rewritten-and-passed: the whole response is blocked."""

    name: str = "output.secret_leak"

    def check(self, text: str) -> Verdict:
        for kind, rx in _SECRETS.items():
            if rx.search(text):
                return deny(self.name, f"response contains a {kind}")
        return allow(self.name)
