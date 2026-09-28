# agentic-guardrails

Layered guardrails for tool-using LLM agents: the controls that sit between a
model and real side effects, packaged as a small, dependency-free Python
library (`agentguard`) with tests, a runnable example, and design notes for
taking agents into production.

```
user input ─► input guards ─► model ─► tool guards ─► (human approval) ─► tool
                                ▲                                          │
                                └──────────── tool-result guards ◄─────────┘
                                │
                                └─► output guards ─► user
```

## Why

An agent is an LLM with permission to act. Most failures in production aren't
the model "being wrong"; they come from missing boundaries:

| Failure mode | Guard in this repo |
|---|---|
| Prompt injection via user input **or tool output** | `PromptInjectionHeuristic` (run on input *and* every tool result) |
| Model calls a tool that doesn't exist or it shouldn't have | `ToolAllowlist` |
| Hallucinated / out-of-range arguments (`refund(amount=10000)`) | `ArgumentValidator` (types, min/max, enum, no extra args) |
| Irreversible actions without oversight | `RiskGate` + pluggable `approver`, **fails closed** |
| Runaway loops, cost blowups | `RateLimit`, `max_steps` |
| PII leaking into responses | `PIIRedactor` (rewrites, doesn't block) |
| Credentials leaking into responses | `SecretLeakBlocker` (blocks outright) |
| "What did the agent do and why?" | `AuditLog` (JSONL, every decision) |

## Quick start

```bash
git clone https://github.com/ingyukoh/agentic-guardrails
cd agentic-guardrails
pip install -e ".[dev]"
pytest -q
python examples/refund_agent.py
```

```text
1) normal request
  [approval] issue_refund({'order_id': 'A100', 'amount': 42.0}) -> auto-approved for demo
  -> Done. refunded 42.00 on A100. Receipt sent to [REDACTED_EMAIL].
2) prompt injection
  -> blocked: [input.prompt_injection] matched injection pattern: 'Ignore all previous instructions'
```

## Usage

```python
from agentguard import GuardedAgent, Tool, ToolRegistry
from agentguard.input_guards import MaxLength, PromptInjectionHeuristic
from agentguard.output_guards import PIIRedactor, SecretLeakBlocker
from agentguard.tools import ArgumentValidator, RateLimit, RiskGate, ToolAllowlist

tools = ToolRegistry([
    Tool("issue_refund", issue_refund, risk="write",
         params={"order_id": {"type": "string"},
                 "amount": {"type": "number", "minimum": 0, "maximum": 100}},
         required=("order_id", "amount")),
])

agent = GuardedAgent(
    model=my_model,                 # any callable(messages, tool_names) -> ModelTurn
    tools=tools,
    input_guards=[MaxLength(), PromptInjectionHeuristic()],
    tool_guards=[ToolAllowlist({"issue_refund"}), ArgumentValidator(),
                 RateLimit(max_calls=10), RiskGate()],
    output_guards=[SecretLeakBlocker(), PIIRedactor()],
    approver=slack_or_ticket_approver,  # default denies: fail closed
)
answer = agent.run(user_message)
```

The model is a plain callable, so the library works with any provider SDK;
write a thin adapter that maps the provider's tool-use response to `ModelTurn`.

## Repository layout

```
src/agentguard/
  policy.py         Decision / Verdict / GuardrailViolation
  input_guards.py   length limit, prompt-injection heuristics
  tools.py          registry, allowlist, argument validation, risk gate, rate limit
  output_guards.py  PII redaction, secret-leak blocking
  audit.py          append-only JSONL audit log
  agent.py          the guarded agent loop
examples/           runnable, offline refund-agent demo
tests/              pytest suite (19 tests)
docs/               design notes and production checklist
```

## Docs

- [Architecture](docs/architecture.md): where each guard sits and why
- [Production checklist](docs/production-checklist.md): what to have before an agent touches real systems
- [Evaluation](docs/evaluation.md): how to measure guardrails, not just the agent

## Scope and limits

The injection and PII detectors are deliberately simple regex layers: cheap,
deterministic and auditable. In a real deployment they are the first line, backed
by a classifier model and by least-privilege credentials on the tools themselves.
Guardrails reduce risk; they don't replace authorization in the systems the tools
call.

## License

MIT
