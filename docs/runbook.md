# Runbook

> Status: specification. Procedures reference commands and modules that arrive with Phases 4–6.
> This is a reference implementation with no production deployment. The runbook exists because writing one is part of building a system properly — and because the procedures are the honest test of whether the observability is good enough.

## Table of contents

1. [First response](#1-first-response)
2. [Severity](#2-severity)
3. [Diagnostics](#3-diagnostics)
4. [Incidents](#4-incidents)
5. [Kill switches](#5-kill-switches)
6. [Recovery](#6-recovery)
7. [Post-incident](#7-post-incident)

---

## 1. First response

For any alert, in order:

1. **Is anything being written wrongly?** If yes, disable writes first (§5). Stopping the bleeding beats diagnosis.
2. **How much is affected?** One tenant, one scenario, or everything?
3. **What changed?** Recent deploy, model version, connector, policy, corpus. `governance/registry.py` records model, prompt and rule versions per run — start there.
4. **Get a trace.** `foreman trace <run-id>` on an affected run.
5. **Reproduce.** `foreman run --scenario <name> --replay <run-id>` against the mock provider.

The order matters. The instinct is to diagnose first; the correct move when writes may be wrong is to stop them, because every minute of diagnosis is more wrong writes.

---

## 2. Severity

| Sev | Definition | Response |
| --- | --- | --- |
| **1** | Wrong writes reaching a system of record; unauthorised write; data leak across tenants | Kill writes immediately, then investigate |
| **2** | System down; all runs failing; budget exhausted | Restore service, then investigate |
| **3** | Degraded quality; escalation rate abnormal; a connector down with a working fallback | Investigate within the day |
| **4** | Single-run failure; cosmetic; slow but correct | Ticket it |

**A silent error is always Sev 1**, even a single confirmed instance, and even if it was caught by an audit rather than reported by a user. One found by sampling means an unknown number were not.

---

## 3. Diagnostics

| Question | Command |
| --- | --- |
| What did this run do? | `foreman trace <run-id>` |
| What are recent runs doing? | `foreman runs --since 1h --status any` |
| Is a connector healthy? | `foreman health --connector erp` |
| What is current spend? | `foreman cost --since today` |
| What is the review queue like? | `foreman reviews --stats` |
| Are metrics abnormal? | `foreman metrics --since 24h --compare baseline` |
| Does the golden suite still pass? | `foreman eval` |
| Did the model change? | `foreman canary` |

### Reading a trace

Work down the tree and check, in order:

1. **Rule spans.** Did the right rule fire with the right inputs? If the inputs are wrong, the problem is upstream in extraction or connectors, not in the rules.
2. **Tool calls.** Right tools, right arguments, right order? Any retries?
3. **Authorisation outcomes.** Any denials? A denial is either an attack or a misconfiguration.
4. **Model calls.** Which tier, which prompt version, what confidence?
5. **Stop reason.** `MAX_STEPS` or `CYCLE_DETECTED` means the agent was lost, not that the task was hard.

---

## 4. Incidents

### 4.1 Silent error detected — Sev 1

**Symptom:** an audit, reconciliation or user report shows an auto-resolved run reached the wrong decision.

1. Disable writes (§5).
2. Get the run's trace. Identify which step was wrong: extraction, matching, rule evaluation, or the write itself.
3. Query the warehouse for runs sharing the characteristic — same supplier, same document type, same rule, same time window.
4. Quantify: how many runs are affected, and what did they write?
5. Add the case to the golden suite as a failing scenario **before fixing it**.
6. Fix. Verify the new scenario passes and nothing else regresses.
7. Re-enable writes after a shadow-mode run over the affected population shows no recurrence.

Never skip step 5. A fix without a regression test is an invitation to repeat.

### 4.2 Unauthorised write attempt — Sev 1

**Symptom:** an audit entry shows a denied write, or worse, an allowed one that should not have been.

1. If a write succeeded that should not have, disable writes immediately.
2. Identify the principal and whether the request was legitimate.
3. If the input contained injected content, add it to the security corpus as a permanent test.
4. Verify RBAC configuration for that role — was the ceiling right, was the scope right?
5. If a control failed rather than fired, treat it as a defect in the control, not in the model. The model being fooled is expected; the control failing is the incident.

### 4.3 Budget exhausted — Sev 2

**Symptom:** runs failing with `BudgetExceeded`, or the kill switch tripped.

1. `foreman cost --since today --group-by scenario,tenant,model` — find the source.
2. Common causes: a run looping (check `stop_reason` distribution), routing regression sending everything to the frontier tier, cache hit rate collapsed, a retry storm against a failing provider.
3. Immediate mitigation: force `provider=local`, or raise the ceiling only if the spend is legitimate.
4. Fix the cause. A raised ceiling with no diagnosis is how a budget becomes a bill.

### 4.4 Connector down — Sev 2 or 3

**Symptom:** tool failure rate spike; circuit breaker open.

1. `foreman health --connector <name>`.
2. Confirm the breaker opened and the tools were withdrawn — if the agent is still selecting a dead tool, that is a second bug.
3. Verify the fallback engaged where one exists.
4. If the connector is genuinely down, pause affected scenarios rather than letting runs consume retry budget to no purpose.
5. On recovery, confirm the breaker half-opens and closes, and check for duplicate writes from retries during the outage.

### 4.5 Escalation rate abnormal — Sev 3

**Rising:** extraction quality dropped (check confidence distribution), a supplier changed document format, a policy threshold changed, or a model was silently swapped (`foreman canary`).

**Falling:** more dangerous. Either genuine improvement, or the system has started auto-confirming things it should escalate. Check silent-error indicators before celebrating. Cross-check with a sampled audit.

### 4.6 Agent looping — Sev 3

**Symptom:** `CYCLE_DETECTED` or `MAX_STEPS` rate rising.

1. Trace an affected run and find the repeating signature.
2. Usual causes:

- a tool returns an error the model cannot do anything with
- there is no tool for an action the agent needs
- a prompt became ambiguous after a change
- a tool description does not mention a precondition

1. Fix the tool's error message or description before touching the prompt — a `ToolError` with a good `suggestion` fixes more loops than prompt edits do.

### 4.7 Review queue backing up — Sev 3

**Symptom:** oldest review item exceeds SLA.

1. Is it volume or staffing? Compare escalation rate to baseline.
2. If escalation precision is low, the queue is full of items that did not need a human — fix precision and the queue drains.
3. Apply the ageing policy: unreviewed items escalate to a higher authority or expire per policy. **They must never sit silently**, because a queue nobody is watching eventually gets approved without being read, which turns a backlog problem into a wrong-answer problem.

### 4.8 Model behaviour changed with no deploy — Sev 3

**Symptom:** quality shifted; no commits.

1. `foreman canary` — fixed prompts with known-stable answers.
2. Compare `governance/registry.py` model identifiers across the change window. A provider alias may now point at a different model.
3. Pin the exact model version.
4. Re-run the golden suite and the cost benchmark against the new version before accepting it.

---

## 5. Kill switches

Ordered from most surgical to most severe. Use the smallest one that stops the harm.

| Switch | Effect | Command |
| --- | --- | --- |
| Disable one tool | That action becomes unavailable | `foreman tools disable confirm_order_line` |
| Disable writes | All runs continue read-only, escalating instead | `foreman writes disable` |
| Force local provider | No frontier spend | `FOREMAN_PROVIDER=local` |
| Budget kill switch | All inference stops | `FOREMAN_KILL_SWITCH=true` |
| Pause a scenario | That workflow stops accepting triggers | `foreman scenario pause price-variance` |
| Stop the service | Everything halts; in-flight runs checkpoint | Stop the container |

**Disabling writes is the default first response** to anything Sev 1. Runs continue and escalate, which means the work is captured for humans rather than lost — a paused system loses the queue, a read-only system does not.

---

## 6. Recovery

### Resuming interrupted runs

Runs checkpoint before every write and at every interrupt, so a restart resumes rather than restarts. Verify with `foreman runs --status interrupted` and resume with `foreman runs resume --all`.

Idempotency keys are derived from the business payload, so a resumed run recomputes the same key and a repeated write is recognised rather than duplicated. **Verify this after any incident involving retries** — it is the property that makes recovery safe, and the one worth confirming rather than assuming.

### Replaying failed runs

```bash
foreman runs list --status failed --since 24h
foreman runs replay <run-id> --dry-run     # shadow: what it would do
foreman runs replay <run-id>               # actually
```

Always dry-run first after an incident. The system's state may have changed since the original attempt, and a replay against changed state is a new decision, not a repeat of the old one.

### Rebuilding derived state

| Store | Command | Notes |
| --- | --- | --- |
| Vector index | `foreman index rebuild` | From source documents |
| Graph | `foreman graph rebuild` | From connectors + documents |
| Warehouse silver/gold | `foreman warehouse rebuild` | From bronze; bronze is immutable |

All three are derived and rebuildable. Nothing irreplaceable lives in them, which is deliberate — the sources of truth are the connectors, the documents and the bronze traces.

---

## 7. Post-incident

For every Sev 1 and Sev 2:

1. **Timeline** from the traces and audit log, not from memory.
2. **Root cause**, distinguishing the trigger from the underlying condition. "The model was fooled" is a trigger; "the extraction agent held a write scope" is a cause.
3. **A regression test.** Every incident becomes a scenario in the golden suite or a case in the security corpus. This is non-negotiable.
4. **Detection review.** How long until it was noticed? If the answer came from a user rather than a monitor, the monitoring is the finding.
5. **Control review.** Did a control fail, or was one missing? A model behaving badly is expected. A control not holding is the defect.

The system's quality over time is mostly a function of how seriously step 3 is taken. A golden suite that grows with every incident is a system that cannot repeat its mistakes; one that does not is a system relearning them.
