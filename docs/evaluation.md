# Evaluating guardrails

Agent evals ask "did it do the task?" Guardrail evals ask two different questions:

1. **Recall on attacks:** of the inputs that *should* be blocked, how many were?
2. **False-positive rate:** of legitimate traffic, how much got blocked or sent to approval?

A guard with perfect recall and a 20% false-positive rate will be turned off
by the team within a week. Track both.

## Building the eval set

| Bucket | Examples |
|---|---|
| Direct injection | "ignore previous instructions...", role-play jailbreaks, fake system tags |
| Indirect injection | Instructions hidden in a fetched web page, email body, PDF, or DB field |
| Argument abuse | Amounts over limit, wrong types, extra fields, IDs belonging to another user |
| Exfiltration | Requests to echo env vars, keys, other customers' data |
| Loops | Tasks that tempt the model into repeating the same tool call |
| Benign look-alikes | "How do I ignore a previous email thread?"; these must *pass* |

## Running it

Each case is `(input, scripted or real model, expected_outcome)` where outcome
is `allowed`, `blocked_at=<guard name>`, or `approval_requested`. Assert on
`agent.audit` events, not only on the final string, so you know *which* layer
caught it. `tests/test_guards.py` shows the pattern.

## Keep it in CI

Every model upgrade, prompt edit, or guard change re-runs the full set. A
guard that silently stops firing is worse than one that never existed,
because people are relying on it.
