# AGENT.md

**This file is the single source of truth.** Guidance for AI coding agents working in this repository.

`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/project.mdc` and `.agents/rules/project.md` all defer here. Change guidance in this file, not in those.

---

## 1. What this repository is

Foreman is an enterprise agent platform for procure-to-pay exception handling — a reference implementation built to production engineering standards, not a production system.

**Current state: specification. There is no code yet.** Implementation begins at Phase 0. Read [docs/FOREMAN_SPEC.md](docs/FOREMAN_SPEC.md) before writing anything.

The organising principle, which decides most design questions on its own:

> Every component is either **deterministic** or **model-driven**, never quietly both. Roughly 80% of this system is deterministic software engineering. Every control that matters is enforced in code at dispatch, never in a prompt.

The test for which side something belongs on: *can two competent people, given the same inputs and the policy document, disagree about the correct answer?* If not, it is a rule, and putting it in a prompt is a bug.

---

## 2. Read before you build

| Working on | Read first |
| --- | --- |
| Anything | [FOREMAN_SPEC.md](docs/FOREMAN_SPEC.md), [architecture.md](docs/architecture.md) |
| Why something is the way it is | [decisions.md](docs/decisions.md) — 17 ADRs |
| Rules, policies, decision tables | [process-decomposition.md](docs/process-decomposition.md) |
| The agent loop, patterns, orchestration | [agent-architecture.md](docs/agent-architecture.md) |
| Context, working state, compaction | [memory.md](docs/memory.md) |
| MCP server or client | [mcp.md](docs/mcp.md) |
| Connectors, auth, retries, idempotency | [integration.md](docs/integration.md) |
| Ingestion, retrieval, GraphRAG | [retrieval.md](docs/retrieval.md) |
| Providers, routing, cost | [models.md](docs/models.md) |
| Guardrails, RBAC, privacy | [security.md](docs/security.md) |
| Traces, metrics, warehouse | [observability.md](docs/observability.md) |
| Tests, judges, CI gates | [evaluation.md](docs/evaluation.md) |
| Async, concurrency, caching | [scalability.md](docs/scalability.md) |
| Dependencies | [tech-stack.md](docs/tech-stack.md) |
| Build, CI, release | [operations.md](docs/operations.md) |
| Something is broken | [runbook.md](docs/runbook.md) |
| Unfamiliar term | [glossary.md](docs/glossary.md) |

---

## 3. Non-negotiables

Violating any of these is a defect, regardless of whether tests pass.

**Deterministic core**

1. Business rules live in `rules/` as versioned code. Never in a prompt.
2. `rules/` and `models/` import nothing from `agent/`, `api/`, `connectors/`, `providers/` or `runtime/`.
3. No module imports both `rules/` and `providers/` except `runtime/`.
4. Rule evaluation returns **which rule fired**, not a boolean.
5. Money is `Decimal`. Never `float`, anywhere on a monetary path.

**Model boundary**

6. Every model output crosses a Pydantic boundary before it reaches a rule, a tool argument or a write.
7. A provider returns validated data or raises. It never returns a string a caller has to hope is JSON.

**Writes and authorisation**

8. Every `mutates=True` tool declares a required scope. The registry refuses to register one without it.
9. Authorisation happens at dispatch, in `security/rbac.py`, after the model chooses and before anything happens.
10. Every mutation carries a deterministic idempotency key derived from the business payload.
11. `ToolError` is a conversation with the model. `PolicyViolation` is not — never phrase it as correctable advice.

**Retrieval**

12. ACL filtering happens **before** scoring, never after.
13. Tenant isolation is a separate index namespace, not a metadata filter.

**Observability**

14. A trace is never dropped. If the backend is down, write JSONL.
15. Traces are redacted at write time, never at read time.
16. The trace schema is a versioned contract — three consumers depend on it.

**Async**

17. Never block the event loop. CPU-bound work goes to a thread via `asyncio.to_thread` — stdlib, no dependency.
18. Every `await` has a timeout.
19. Concurrency is bounded and per-item isolated. One failed line does not fail the run.

**Honesty**

20. Claim only what the code does. A document describing something unbuilt says so in its first line, and the README status table stays accurate.

---

## 4. Conventions

### Layout

`src/` layout. The package is `src/foreman/`. Docs cite modules package-relative: `rules/engine.py` means `src/foreman/rules/engine.py`, and imports read `from foreman.rules import engine`.

### Code

- Python 3.12. `X | None`, not `Optional[X]`. `match` where it reads better than `if`.
- Type hints everywhere; `mypy --strict` must pass.
- Pydantic v2 at every boundary. Constrain at field level: `quantity: int = Field(gt=0)`.
- `async` core, thin sync facade for the CLI. Never the reverse.
- `Protocol` for extension points, not ABCs.
- Match the surrounding code's naming, comment density and idiom.

### Dependencies

**Do not add a dependency without adding it to [tech-stack.md](docs/tech-stack.md)** with its group, its rationale and what it was chosen over. The base install is four packages and stays that way; everything else is a dependency group.

Before reaching for a library, check [tech-stack.md §13](docs/tech-stack.md#13-deliberately-not-in-the-stack) — it may already have been considered and declined.

### Commits and branches

- Branch naming: [BRANCH_NAMING_GUIDELINES.md](BRANCH_NAMING_GUIDELINES.md). `main` and `dev` are protected — always branch.
- Commit format: [COMMIT_MESSAGE_GUIDELINES.md](COMMIT_MESSAGE_GUIDELINES.md) — `<type>(<scope>): <Message> (refs #N)`.
- Small, coherent commits. One 8,000-line commit reads as generated; the history is part of the artefact.
- Pull requests: [PULL_REQUEST_GUIDELINES.md](PULL_REQUEST_GUIDELINES.md).

### Documentation

Documentation is versioned with the code it describes. A change to a module updates its document **in the same commit**. Design rationale goes in [decisions.md](docs/decisions.md) as an ADR — new ADRs are appended and numbered, never renumbered.

---

## 5. Commands

> Phase 0 has not run, so none of these work yet. They are the commands the phase gates are defined against.

```bash
uv sync                                  # install; base + dev groups
uv run pytest -v                         # full suite: green, no API key, no network
uv run pytest -m "not slow"              # fast feedback loop
uv run ruff check --fix && uv run ruff format
uv run mypy .                            # strict
uv run lint-imports                      # architectural contracts

uv run foreman run --scenario happy-path
uv run foreman trace <run-id>
uv run foreman eval
uv run python -m mcp_server              # stdio
uv run uvicorn api.main:app --reload
```

---

## 6. Phase discipline

Six phases, **dependency order, not a schedule**. Each ends with a gate that either passes or does not. Do not start a phase before the previous gate is green — see [FOREMAN_SPEC.md §10](docs/FOREMAN_SPEC.md#10-build-plan) and the checklists in [TODO.md](TODO.md).

Phase 1 is the bar for the repository being worth reading. A repository that does two things properly beats one that does eight halfway.

---

## 7. Definition of done

A change is finished when all of these hold:

- [ ] `uv run pytest` green, on a clean clone, with no API key and no network
- [ ] `uv run mypy .` clean under `--strict`
- [ ] `uv run ruff check` and `ruff format --check` clean
- [ ] Import contracts pass
- [ ] New behaviour has a test; a fixed bug has a regression test
- [ ] Any new dependency is recorded in [tech-stack.md](docs/tech-stack.md)
- [ ] The document describing the changed module is updated in the same commit
- [ ] The README status table still tells the truth
- [ ] No employer, product, customer or individual names anywhere

---

## 8. Mistakes this repository invites

Specific to this codebase, in rough order of likelihood.

| Mistake | Instead |
| --- | --- |
| Putting a threshold or tolerance in a prompt | `rules/policies.py`, versioned, with an ID and an owner |
| Asking the model to respect a permission | Enforce it in `security/rbac.py` at dispatch |
| Filtering retrieval results after scoring | Pre-filter the index |
| Appending every tool result to the context | Project to the fields the decision needs |
| Adding a UUID idempotency key per attempt | Derive it deterministically from the business payload |
| Retrying a 4xx | Classify first — `classify_http_error` |
| A default tokeniser for BM25 | The one that keeps `WDG-003-A` distinct from `WDG-003-B` |
| Reaching for LangChain, LlamaIndex or LiteLLM | Already declined, with reasons — [ADR-016](docs/decisions.md#adr-016--what-was-deliberately-left-out), [ADR-017](docs/decisions.md#adr-017--one-compatibility-adapter-plus-native-adapters-where-they-pay) |
| Adding a second agent because it feels more capable | Single agent is the default — [ADR-006](docs/decisions.md#adr-006--single-agent-is-the-default) |
| A `print()` in an MCP stdio handler | stderr only; stdout carries protocol messages |
| Optimising auto-resolution rate alone | Report it paired with silent-error rate |
| Writing a document for a module that does not exist | Mark its status line honestly |

---

## 9. When you are unsure

1. Check [decisions.md](docs/decisions.md) — the question may already be answered, including the alternatives that were rejected.
2. Check [glossary.md](docs/glossary.md) — terms in this repository have specific meanings.
3. Prefer the deterministic option. It is testable, auditable and free.
4. Prefer the smaller surface. Anything that adds surface without adding evidence was cut on purpose.
5. If a design question is genuinely open, write it down as an ADR with the alternatives rather than deciding silently in code.
