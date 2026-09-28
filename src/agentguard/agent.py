"""A provider-agnostic agent loop with guardrails at every boundary.

    user input ─► input guards ─► model ─► tool guards ─► (approval) ─► tool
                                    ▲                                    │
                                    └──────── tool result guards ◄───────┘
                                    │
                                    └─► output guards ─► user
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from agentguard.audit import AuditLog
from agentguard.policy import Decision, GuardrailViolation, Verdict
from agentguard.tools import ToolRegistry


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelTurn:
    """What the model returned: either final text or tool calls."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class Model(Protocol):
    def __call__(self, messages: list[dict[str, Any]], tools: list[str]) -> ModelTurn: ...


class TextGuard(Protocol):
    name: str

    def check(self, text: str) -> Verdict: ...


class ToolGuard(Protocol):
    name: str

    def check(self, tool: Any, tool_name: str, args: dict[str, Any]) -> Verdict: ...


Approver = Callable[[ToolCall, Verdict], bool]


def deny_all(call: ToolCall, verdict: Verdict) -> bool:
    return False


@dataclass
class GuardedAgent:
    model: Model
    tools: ToolRegistry
    input_guards: list[TextGuard] = field(default_factory=list)
    tool_guards: list[ToolGuard] = field(default_factory=list)
    output_guards: list[TextGuard] = field(default_factory=list)
    approver: Approver = deny_all  # fail closed when no human is wired up
    max_steps: int = 8
    audit: AuditLog = field(default_factory=AuditLog)

    def _run_text_guards(self, guards: list[TextGuard], text: str, stage: str) -> str:
        for g in guards:
            v = g.check(text)
            self.audit.record("guard", stage=stage, guard=g.name,
                              decision=v.decision.value, reason=v.reason, meta=v.meta)
            if not v.allowed:
                raise GuardrailViolation(v)
            if v.rewritten is not None:
                text = v.rewritten
        return text

    def _authorize(self, call: ToolCall) -> tuple[bool, str]:
        tool = self.tools.get(call.name)
        for g in self.tool_guards:
            v = g.check(tool, call.name, call.args)
            self.audit.record("guard", stage="tool", guard=g.name, tool=call.name,
                              decision=v.decision.value, reason=v.reason)
            if v.decision is Decision.DENY:
                return False, v.reason
            if v.decision is Decision.REQUIRE_APPROVAL:
                approved = self.approver(call, v)
                self.audit.record("approval", tool=call.name, args=call.args, approved=approved)
                if not approved:
                    return False, f"human reviewer declined: {v.reason}"
        return tool is not None, "" if tool else f"unknown tool {call.name!r}"

    def run(self, user_input: str) -> str:
        text = self._run_text_guards(self.input_guards, user_input, "input")
        messages: list[dict[str, Any]] = [{"role": "user", "content": text}]

        for step in range(self.max_steps):
            turn = self.model(messages, self.tools.names())
            self.audit.record("model_turn", step=step, text=turn.text,
                              tool_calls=[c.name for c in turn.tool_calls])
            if not turn.tool_calls:
                return self._run_text_guards(self.output_guards, turn.text, "output")

            messages.append({"role": "assistant", "content": turn.text,
                             "tool_calls": [c.__dict__ for c in turn.tool_calls]})
            for call in turn.tool_calls:
                ok, reason = self._authorize(call)
                if not ok:
                    # Tell the model it was blocked so it can recover or explain.
                    result = f"BLOCKED: {reason}"
                else:
                    try:
                        result = str(self.tools.get(call.name).fn(**call.args))  # type: ignore[union-attr]
                    except Exception as exc:  # noqa: BLE001 -- tool errors go back to the model, not the user
                        result = f"ERROR: {type(exc).__name__}: {exc}"
                # Tool output is untrusted too: it is a common injection vector.
                result = self._screen_tool_result(result)
                self.audit.record("tool_result", tool=call.name, ok=ok, result=result[:500])
                messages.append({"role": "tool", "name": call.name, "content": result})

        self.audit.record("halt", reason="max_steps")
        return "I couldn't finish this request safely within the step limit."

    def _screen_tool_result(self, result: str) -> str:
        try:
            return self._run_text_guards(self.input_guards, result, "tool_result")
        except GuardrailViolation as exc:
            return f"BLOCKED: tool result failed {exc.verdict.guardrail}"
