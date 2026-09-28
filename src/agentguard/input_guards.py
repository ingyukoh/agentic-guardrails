"""Guards applied to untrusted text before it reaches the model."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agentguard.policy import Verdict, allow, deny

# Heuristics only. A classifier model should sit behind this in production;
# the regex layer exists to be cheap, deterministic, and auditable.
_INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (the |your )?(system|previous) (prompt|instructions)",
    r"you are now (in )?(developer|dan|jailbreak) mode",
    r"reveal (your|the) (system prompt|hidden instructions)",
    r"</?(system|assistant)>",
]


@dataclass
class MaxLength:
    limit: int = 20_000
    name: str = "input.max_length"

    def check(self, text: str) -> Verdict:
        if len(text) > self.limit:
            return deny(self.name, f"input is {len(text)} chars, limit {self.limit}")
        return allow(self.name)


@dataclass
class PromptInjectionHeuristic:
    name: str = "input.prompt_injection"

    def __post_init__(self) -> None:
        self._rx = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

    def check(self, text: str) -> Verdict:
        for rx in self._rx:
            if m := rx.search(text):
                return deny(self.name, f"matched injection pattern: {m.group(0)!r}")
        return allow(self.name)
