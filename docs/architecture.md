# Architecture

## Principle: guard every boundary, not just the prompt

A tool-using agent has four trust boundaries. Each one gets its own guards
because each one fails differently.

| Boundary | Threat | Guard behavior |
|---|---|---|
| User → model | Injection, oversized input | **Raise** `GuardrailViolation`; request never reaches the model |
| Model → tool | Wrong tool, bad args, risky action, loops | **Block the call** and return `BLOCKED: <reason>` to the model so it can recover or explain |
| Tool → model | Indirect injection in fetched content | **Replace** the result with `BLOCKED: tool result failed ...` |
| Model → user | PII, secrets | **Rewrite** (PII) or **raise** (secrets) |

## Decisions

Every guard returns a `Verdict` with one of three decisions:

- `ALLOW`, optionally with `rewritten` content (redaction)
- `DENY` with a reason
- `REQUIRE_APPROVAL`, routed to the `approver` callback

## Fail closed

- The default `approver` denies everything. A write tool cannot execute until
  someone deliberately wires in a human-review path.
- Unknown tools are denied even if the model insists.
- Hitting `max_steps` ends the run with a safe message and a `halt` audit event.

## Tool errors go to the model, not the user

Exceptions inside tools are caught and returned to the model as
`ERROR: <type>: <message>`. That lets it retry or explain without surfacing
stack traces, and the error still passes through tool-result screening.

## Audit

`AuditLog` records `guard`, `approval`, `model_turn`, `tool_result` and `halt`
events with a per-run `run_id`. Point it at a file to get an append-only
JSONL trail you can ship to your log pipeline.
