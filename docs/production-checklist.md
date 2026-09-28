# Production checklist for agentic systems

Use this before an agent is allowed to touch real systems or real users.

## Permissions
- [ ] Every tool is on an explicit allowlist; no dynamic tool discovery in prod
- [ ] Tool credentials are least-privilege and scoped per agent, not shared with humans
- [ ] Each tool is labeled `read` or `write`; irreversible actions are `write`
- [ ] Write actions require human approval, or have a hard numeric ceiling (amount, count)
- [ ] Downstream systems enforce their own authorization; the agent is not the only check

## Inputs
- [ ] Input length limits
- [ ] Injection screening on user input **and** on every tool result (web pages, emails, docs, DB rows)
- [ ] Untrusted content is clearly delimited in the prompt as data, not instructions

## Tool calls
- [ ] Arguments validated against a schema: types, ranges, enums, no extra fields
- [ ] Per-run step limit and per-window rate limit
- [ ] Token and cost budget per run and per tenant
- [ ] Idempotency keys on write tools so retries don't double-execute

## Outputs
- [ ] Secret and credential scanning blocks the response
- [ ] PII redaction, or a policy decision documenting why not
- [ ] Refusals and blocks produce a useful message, not a stack trace

## Operations
- [ ] Audit log of every guard decision, approval and tool call, with a run ID
- [ ] Alerts on spikes in denials, approvals or halts; a sudden change usually means an attack or a regression
- [ ] Kill switch: disable write tools globally without a deploy
- [ ] Shadow mode first: run the agent, log the actions it *would* take, execute nothing
- [ ] Staged rollout by tenant or traffic percentage

## Evaluation
- [ ] Regression suite of red-team prompts that must stay blocked (see [evaluation.md](evaluation.md))
- [ ] Guardrail false-positive rate tracked on real traffic
- [ ] Re-run evals on every model version or prompt change
