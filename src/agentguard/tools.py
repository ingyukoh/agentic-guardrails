"""Tool registry plus the guards that sit between the model and side effects."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agentguard.policy import Verdict, allow, deny, needs_approval

_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


@dataclass
class Tool:
    name: str
    fn: Callable[..., Any]
    description: str = ""
    # Minimal JSON-schema subset: {"arg": {"type": "number", "maximum": 500}}
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    # "read" tools run freely; "write" tools can be gated behind approval.
    risk: str = "read"


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for t in tools or []:
            self.register(t)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)


@dataclass
class ToolAllowlist:
    allowed: set[str]
    name: str = "tool.allowlist"

    def check(self, tool: Tool | None, tool_name: str, args: dict[str, Any]) -> Verdict:
        if tool is None or tool_name not in self.allowed:
            return deny(self.name, f"tool {tool_name!r} is not allowlisted")
        return allow(self.name)


@dataclass
class ArgumentValidator:
    """Rejects hallucinated or out-of-range arguments before execution."""

    name: str = "tool.arguments"

    def check(self, tool: Tool | None, tool_name: str, args: dict[str, Any]) -> Verdict:
        assert tool is not None
        for req in tool.required:
            if req not in args:
                return deny(self.name, f"missing required argument {req!r}")
        for key, value in args.items():
            spec = tool.params.get(key)
            if spec is None:
                return deny(self.name, f"unexpected argument {key!r}")
            expected = _JSON_TYPES.get(spec.get("type", ""), object)
            if isinstance(value, bool) and spec.get("type") in ("integer", "number"):
                return deny(self.name, f"{key!r} must be {spec['type']}, got bool")
            if not isinstance(value, expected):
                return deny(self.name, f"{key!r} must be {spec.get('type')}")
            if "maximum" in spec and value > spec["maximum"]:
                return deny(self.name, f"{key!r}={value} exceeds maximum {spec['maximum']}")
            if "minimum" in spec and value < spec["minimum"]:
                return deny(self.name, f"{key!r}={value} below minimum {spec['minimum']}")
            if "enum" in spec and value not in spec["enum"]:
                return deny(self.name, f"{key!r}={value!r} not in {spec['enum']}")
        return allow(self.name)


@dataclass
class RiskGate:
    """Routes write/irreversible tools to a human before they execute."""

    gated_risks: set[str] = field(default_factory=lambda: {"write"})
    name: str = "tool.risk_gate"

    def check(self, tool: Tool | None, tool_name: str, args: dict[str, Any]) -> Verdict:
        assert tool is not None
        if tool.risk in self.gated_risks:
            return needs_approval(self.name, f"{tool_name} is a {tool.risk} action", args=args)
        return allow(self.name)


@dataclass
class RateLimit:
    """Sliding-window limit on tool calls, to stop runaway loops."""

    max_calls: int = 10
    window_s: float = 60.0
    name: str = "tool.rate_limit"
    clock: Callable[[], float] = time.monotonic
    _calls: deque[float] = field(default_factory=deque, repr=False)

    def check(self, tool: Tool | None, tool_name: str, args: dict[str, Any]) -> Verdict:
        now = self.clock()
        while self._calls and now - self._calls[0] > self.window_s:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            return deny(self.name, f"{self.max_calls} tool calls in {self.window_s}s")
        self._calls.append(now)
        return allow(self.name)
