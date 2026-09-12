# AGENT.md

**This file is the single source of truth.** Guidance for AI coding agents working in this repository.

`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/project.mdc` and `.agents/rules/project.md` all point here. Change guidance in this file, not in those.

---

## 1. What this repository is

Foreman handles supplier order confirmations using AI agents. It is a reference implementation built to professional standards. It is not a live production system.

**Current state: specification. There is no code yet.** Work starts at Phase 0. Read [docs/FOREMAN_SPEC.md](docs/FOREMAN_SPEC.md) before you write anything.

The main idea, which answers most design questions on its own:

> Every part of the system is either **deterministic** (fixed rules, same answer every time) or **model-driven** (it asks an AI model). Never both at once. About 80% of this system is ordinary software engineering. Every control that matters runs in code at the moment the action happens, never in a prompt.

How to tell which side something belongs on: *given the same inputs and the same policy document, could two competent people disagree about the right answer?* If they could not, it is a rule. Putting it in a prompt is a bug.

---

## 2. Read before you build

| Working on | Read first |
| --- | --- |
| Anything | [FOREMAN_SPEC.md](docs/FOREMAN_SPEC.md), [architecture.md](docs/architecture.md) |
| Why something is the way it is | [decisions.md](docs/decisions.md) — 17 decision records |
| Rules, policies, decision tables | [process-decomposition.md](docs/process-decomposition.md) |
| The agent loop and how work is arranged | [agent-architecture.md](docs/agent-architecture.md) |
| What the model sees, and shrinking it | [memory.md](docs/memory.md) |
| MCP server or client | [mcp.md](docs/mcp.md) |
| Connectors, login, retries, safe writes | [integration.md](docs/integration.md) |
| Loading documents, search, knowledge graph | [retrieval.md](docs/retrieval.md) |
| Model providers, routing, cost | [models.md](docs/models.md) |
| Guardrails, permissions, privacy | [security.md](docs/security.md) |
| Traces, metrics, analytics | [observability.md](docs/observability.md) |
| Tests, judges, merge checks | [evaluation.md](docs/evaluation.md) |
| Waiting vs doing, limits, caching | [scalability.md](docs/scalability.md) |
| Dependencies | [tech-stack.md](docs/tech-stack.md) |
| Build, CI, releases | [operations.md](docs/operations.md) |
| Something is broken | [runbook.md](docs/runbook.md) |
| A word you do not recognise | [glossary.md](docs/glossary.md) |

---

## 3. Rules you must not break

Breaking any of these is a bug, even if every test passes.

### Business rules

1. Business rules live in `rules/` as versioned code. Never in a prompt.
2. `rules/` and `models/` must not import from `agent/`, `api/`, `connectors/`, `providers/` or `runtime/`.
3. No file imports both `rules/` and `providers/`, except files in `runtime/`.
4. Evaluating a rule returns **which rule fired**, not just true or false. An escalation that cannot say why is useless to a reviewer.
5. Money is always `Decimal`. Never `float`, anywhere money is involved.

### Model output

1. Model output is untrusted input. It must pass through a Pydantic model before it reaches a rule, a tool argument, or a write.
2. A provider returns validated data or raises an error. It never returns a string and hopes the caller can parse it.

### Writes and permissions

1. Every tool marked `mutates=True` must declare the permission it needs. The registry refuses to accept one without it.
2. Permission checks happen in `security/rbac.py` at dispatch — after the model has chosen, before anything actually happens.
3. Every write carries an **idempotency key**: a fingerprint calculated from the data being written. If the network drops the reply and the code retries, the server recognises the same fingerprint and does not write twice.
4. A `ToolError` is feedback to the model, so it can try again. A `PolicyViolation` is not — never word it as advice, or the model will try to work around it.

### Search

 1. Filter by permission **before** ranking results, never after.
 2. Keep tenants apart with a separate index per tenant, not a filter on a shared one. A filter is one forgotten line of code away from leaking another customer's data.

### Recording what happened

 1. Never drop a trace. If the tracing backend is down, write a JSONL file instead.
 2. Remove personal data as the trace is written, not when it is read.
 3. The trace format is a contract. Three other parts of the system read it.

### Async code

 1. Never block the event loop. CPU-heavy work goes to a thread with `asyncio.to_thread` — standard library, no dependency needed.
 2. Every `await` has a timeout.
 3. Limit how many things run at once, and isolate failures. One failed line must not fail the whole run.

### Honesty

 1. Only claim what the code actually does. A document about something not yet built says so on its first line, and the status table in the README stays accurate.

---

## 4. Conventions

### Folder layout

This project uses a `src/` layout. The package is `src/foreman/`. Documents refer to files by their path inside the package: `rules/engine.py` means `src/foreman/rules/engine.py`, and the import is `from foreman.rules import engine`.

### Code

- Python 3.12. Write `X | None`, not `Optional[X]`. Use `match` where it reads better than `if`.
- Type hints everywhere. `mypy --strict` must pass.
- Pydantic v2 wherever data enters the system. Put limits on the field itself: `quantity: int = Field(gt=0)`.
- The core is `async`. The CLI gets a thin synchronous wrapper on top. Never the other way round.
- Use `Protocol` for extension points, not abstract base classes.
- Match the naming, comment style and structure of the code around you.

### Dependencies

**Do not add a dependency without adding it to [tech-stack.md](docs/tech-stack.md)**, with its group, the reason for it, and what it was chosen over. The base install is four packages and stays that way. Everything else goes in a dependency group.

Before reaching for a library, check [tech-stack.md §13](docs/tech-stack.md#13-deliberately-not-in-the-stack). It may already have been considered and turned down.

### Commits and branches

- Branch names: [BRANCH_NAMING_GUIDELINES.md](BRANCH_NAMING_GUIDELINES.md). `main` and `dev` are protected, so always work on a branch.
- Commit format: [COMMIT_MESSAGE_GUIDELINES.md](COMMIT_MESSAGE_GUIDELINES.md) — `<type>(<scope>): <Message> (refs #N)`.
- Keep commits small and focused. One commit of 8,000 lines looks machine-generated; the history is part of what people judge.
- Pull requests: [PULL_REQUEST_GUIDELINES.md](PULL_REQUEST_GUIDELINES.md).

### Documentation

Documentation ships with the code it describes. If you change a module, update its document **in the same commit**. Reasons for a design choice go in [decisions.md](docs/decisions.md) as a new numbered record. Add new records at the end; never renumber the existing ones.

---

## 5. Commands

> Phase 0 has not run yet, so none of these work. They are the commands the phase checkpoints are measured against.

```bash
uv sync                                  # install: base packages plus dev tools
uv run pytest -v                         # full test suite: no API key, no internet
uv run pytest -m "not slow"              # quick subset while working
uv run ruff check --fix && uv run ruff format
uv run mypy .                            # strict type checking
uv run lint-imports                      # checks the folder rules in section 3

uv run foreman run --scenario happy-path
uv run foreman trace <run-id>
uv run foreman eval
uv run python -m mcp_server              # MCP server over stdio
uv run uvicorn api.main:app --reload
```

---

## 6. Phase order

There are six phases. They run in order because each one needs the one before it, not because of a calendar. Each ends with a checkpoint that either passes or does not. Do not start a phase until the previous checkpoint passes. See [FOREMAN_SPEC.md §10](docs/FOREMAN_SPEC.md#10-build-plan) and the checklists in [TODO.md](TODO.md).

Phase 1 is the point where this repository becomes worth reading. Two things done properly beat eight done halfway.

---

## 7. Definition of done

A change is finished when all of these are true:

- [ ] `uv run pytest` passes on a fresh clone, with no API key and no internet
- [ ] `uv run mypy .` passes under `--strict`
- [ ] `uv run ruff check` and `ruff format --check` pass
- [ ] The import checks pass
- [ ] New behaviour has a test; a fixed bug has a test that would have caught it
- [ ] Any new dependency is recorded in [tech-stack.md](docs/tech-stack.md)
- [ ] The document for the module you changed is updated in the same commit
- [ ] The status table in the README is still true
- [ ] No employer, product, customer or personal names anywhere

---

## 8. Common mistakes in this repository

Listed roughly by how often they happen.

| Mistake | Do this instead |
| --- | --- |
| Putting a threshold or a limit in a prompt | Put it in `rules/policies.py`, with an ID, a version and an owner |
| Asking the model to respect a permission | Enforce it in `security/rbac.py`, at dispatch |
| Filtering search results after ranking them | Filter the index before ranking |
| Adding every tool result to the conversation | Keep only the fields the decision needs |
| Using a random ID as the idempotency key | Calculate it from the data being written, so a retry produces the same key |
| Retrying an HTTP 4xx error | Classify the error first with `classify_http_error`. 4xx means the request was wrong and will stay wrong |
| Using a default tokeniser for BM25 search | Use the one that keeps `WDG-003-A` and `WDG-003-B` apart |
| Reaching for LangChain, LlamaIndex or LiteLLM | Already turned down, with reasons — [ADR-016](docs/decisions.md#adr-016--what-was-deliberately-left-out), [ADR-017](docs/decisions.md#adr-017--one-compatibility-adapter-plus-native-adapters-where-they-pay) |
| Adding a second agent because it sounds more capable | One agent is the default — [ADR-006](docs/decisions.md#adr-006--single-agent-is-the-default) |
| A `print()` inside an MCP stdio handler | Print to stderr. Standard output carries protocol messages, and anything else breaks the connection |
| Reporting only how often the agent finished on its own | Always report it next to how often it was silently wrong |
| Writing a document for a module that does not exist | Say so honestly in its status line |

---

## 9. When you are not sure

1. Check [decisions.md](docs/decisions.md). The question may already be answered, including the options that were rejected.
2. Check [glossary.md](docs/glossary.md). Words in this repository have specific meanings.
3. Prefer the deterministic option. It is testable, explainable and free to run.
4. Prefer the smaller option. Anything that added complexity without adding proof was cut on purpose.
5. If a design question is genuinely open, write it up as a decision record with the options, rather than quietly deciding it in code.
