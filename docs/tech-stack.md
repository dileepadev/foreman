# Tech Stack

> Status: specification. Nothing is installed yet — Phase 0 creates `pyproject.toml` and the lockfile. Version floors below are minimums; **`uv.lock` is the authoritative record** of what is actually installed.

The complete dependency picture in one place: what is used, which group it lives in, why it was chosen, and what was rejected. [FOREMAN_SPEC.md §7](FOREMAN_SPEC.md#7-tech-stack) carries the summary table; this is the full reference.

## Table of contents

1. [Principles](#1-principles)
2. [At a glance](#2-at-a-glance)
3. [Runtime and packaging](#3-runtime-and-packaging)
4. [Dependency groups](#4-dependency-groups)
5. [The complete pyproject.toml](#5-the-complete-pyprojecttoml)
6. [Layer by layer](#6-layer-by-layer)
7. [Model providers](#7-model-providers)
8. [Optional services](#8-optional-services)
9. [Environment variables](#9-environment-variables)
10. [Version policy](#10-version-policy)
11. [Licence posture](#11-licence-posture)
12. [Supply chain](#12-supply-chain)
13. [Deliberately not in the stack](#13-deliberately-not-in-the-stack)
14. [Install recipes](#14-install-recipes)

---

## 1. Principles

Five rules that decided every row in this document.

| Principle | Consequence |
| --- | --- |
| **Zero-key default** | The base install has no provider SDK, no service client and no network dependency. `uv sync && uv run pytest` passes offline on a clean clone. |
| **Every optional dependency has a tested fallback** | Neo4j → in-memory graph. pgvector → numpy. Langfuse → JSONL. Ollama → mock. A fallback that is never exercised does not work, so CI exercises all of them. |
| **Hand-roll where the mechanism is the lesson** | The MCP server protocol, the agent loop, rank fusion, retry and idempotency are ours. See [decisions.md](decisions.md). |
| **Borrow where rebuilding teaches nothing** | Durable execution, JSON-RPC clients, HTTP, validation, analytics. |
| **One tool per job** | One packager, one linter, one formatter, one type checker, one test runner. Overlapping tools produce arguments, not quality. |

The base install is **four packages** — Pydantic, pydantic-settings, httpx and Typer. That is not minimalism for its own sake — it is what makes "clone it and read the rules engine" a thirty-second operation.

---

## 2. At a glance

| Layer | Choice | Group |
| --- | --- | --- |
| Language | Python 3.12 | — |
| Packaging | uv | — |
| Validation | Pydantic v2, pydantic-settings | base |
| HTTP | httpx | base |
| CLI | Typer | base |
| Service | FastAPI, Uvicorn, sse-starlette | `api` |
| Agent orchestration | LangGraph | `graph` |
| Protocol | MCP Python SDK (client), hand-rolled server | `mcp` |
| Model providers | openai, anthropic, google-genai, ollama | `models` |
| Retrieval | numpy, rank-bm25, pypdf, pdfplumber | `rag` |
| Graph | neo4j driver | `graph` |
| Vector store | pgvector, psycopg | `pgvector` |
| Analytics | DuckDB, PyArrow | `obs` |
| Tracing | OpenTelemetry SDK, Langfuse | `obs` |
| Testing | pytest, pytest-asyncio, hypothesis, pytest-cov | `dev` |
| Quality | ruff, mypy, import-linter | `dev` |
| Container | Docker multi-stage, docker compose | — |
| CI | GitHub Actions | — |

---

## 3. Runtime and packaging

### Python 3.12

| Feature | Used for |
| --- | --- |
| `X \| None` union syntax | Every signature in the codebase |
| `match` statements | Error classification, `StopReason` dispatch |
| `typing.Protocol` | `Runtime`, `LLMProvider`, `Connector`, `AuthStrategy` |
| Generics on `Resolved[T]` | Source-of-truth resolution results |
| `tomllib` in the standard library | Reading `pricing.toml` and policy tables with no dependency |
| `asyncio.TaskGroup` | Structured concurrency in `bounded_gather` |

3.12 rather than 3.13 for dependency availability, and not below 3.12 because `TaskGroup` and the typing improvements are essential here.

### uv

One tool for the virtual environment, resolution, locking, installing and running.

| Capability | Why it matters here |
| --- | --- |
| `uv.lock`, committed | Reproducible installs; CI asserts freshness with `--locked` |
| Dependency groups | The base install stays at four packages |
| Resolution speed | Keeps the full CI quality gate under five minutes, which is the threshold at which people wait for it rather than merge around it |
| `uv run` | No activation step in any documented command |
| `uv python install` | Pins the interpreter as well as the packages |

Rationale and rejected alternatives: [ADR-009](decisions.md#adr-009--uv-for-packaging).

---

## 4. Dependency groups

Groups compose. Install only what the task needs.

| Group | Packages | Install |
| --- | --- | --- |
| *(base)* | pydantic, pydantic-settings, httpx, typer | `uv sync` |
| `dev` | pytest, pytest-asyncio, pytest-cov, hypothesis, ruff, mypy, import-linter | `uv sync` *(default)* |
| `api` | fastapi, uvicorn, sse-starlette | `uv sync --group api` |
| `mcp` | mcp[cli] | `uv sync --group mcp` |
| `graph` | langgraph, langgraph-checkpoint-sqlite, neo4j | `uv sync --group graph` |
| `models` | openai, anthropic, google-genai, ollama | `uv sync --group models` |
| `rag` | numpy, rank-bm25, pypdf, pdfplumber | `uv sync --group rag` |
| `pgvector` | psycopg[binary], pgvector | `uv sync --group pgvector` |
| `obs` | opentelemetry-sdk, opentelemetry-exporter-otlp, langfuse, duckdb, pyarrow | `uv sync --group obs` |
| `all` | everything above | `uv sync --all-groups` |

`dev` is a default group, so a bare `uv sync` gives a working test environment. Phase 1 needs nothing beyond that — which is the point.

---

## 5. The complete pyproject.toml

```toml
[project]
name = "foreman"
version = "0.2.0"
description = "An enterprise agent platform that shows its work."
requires-python = ">=3.12"
license = { text = "MIT" }
dependencies = [
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "httpx>=0.27",
    "typer>=0.12",
]

[project.scripts]
foreman = "foreman.cli:app"

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "hypothesis>=6.112",
    "ruff>=0.7",
    "mypy>=1.13",
    "import-linter>=2.1",
]
api      = ["fastapi>=0.115", "uvicorn[standard]>=0.32", "sse-starlette>=2.1"]
mcp      = ["mcp[cli]>=1.9"]
graph    = ["langgraph>=1.0", "langgraph-checkpoint-sqlite>=2.0", "neo4j>=5.25"]
models   = ["openai>=1.54", "anthropic>=0.39", "google-genai>=1.0", "ollama>=0.4"]
rag      = ["numpy>=1.26", "rank-bm25>=0.2.2", "pypdf>=5.1", "pdfplumber>=0.11"]
pgvector = ["psycopg[binary]>=3.2", "pgvector>=0.3"]
obs = [
    "opentelemetry-sdk>=1.28",
    "opentelemetry-exporter-otlp>=1.28",
    "langfuse>=3.0",
    "duckdb>=1.1",
    "pyarrow>=18.0",
]

[tool.uv]
default-groups = ["dev"]

[tool.hatch.build.targets.wheel]
packages = ["src/foreman"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "PT", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = ["slow: excluded from the fast feedback loop"]

[tool.importlinter]
root_package = "foreman"

[[tool.importlinter.contracts]]
name = "Deterministic core imports no provider"
type = "forbidden"
source_modules = ["foreman.rules", "foreman.models"]
forbidden_modules = ["foreman.providers", "foreman.agent", "foreman.api", "foreman.connectors"]

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = ["foreman.api", "foreman.runtime", "foreman.agent", "foreman.providers", "foreman.connectors", "foreman.core"]
```

The package lives at `src/foreman/`, which is why every contract below names `foreman.*`. The `import-linter` contracts are the mechanism behind [architecture.md §3](architecture.md#3-structural-invariants) — the structural invariants are enforced by CI, not by discipline.

---

## 6. Layer by layer

### 6.1 Base — always installed

| Package | Role | Why this one |
| --- | --- | --- |
| **pydantic** | Runtime validation of every model output, connector payload and tool argument | The boundary that makes "model output is untrusted input" enforceable rather than aspirational. v2's Rust core makes validation cheap enough to do everywhere. |
| **pydantic-settings** | Configuration from environment, `SecretStr` for credentials | Secrets that do not appear in a repr, a log or a traceback |
| **httpx** | Async HTTP for every connector and provider | Async-first, per-request timeouts, connection pooling, and a transport layer that retry and rate-limit hooks can wrap |
| **typer** | CLI for scenarios, traces, evaluation and diagnostics | Type hints become the argument parser; the CLI stays in step with the code |

*Rejected:* `requests` (sync only — see [scalability.md §1](scalability.md#1-sync-and-async)); `dataclasses` (no runtime validation); `argparse` and `click` directly (Typer is Click with the types done for you); `python-dotenv` alone (pydantic-settings covers it and validates).

### 6.2 Service — `api`

| Package | Role |
| --- | --- |
| **fastapi** | Routing, dependency injection, OpenAPI, request validation via the Pydantic models already defined |
| **uvicorn[standard]** | ASGI server; `standard` adds uvloop and httptools |
| **sse-starlette** | Server-sent events for run streaming |

*Rejected:*

- **Flask, Django** — built for synchronous code; async was added later.
- **Starlette on its own** — FastAPI's validation and OpenAPI support are the reason to use it.
- **WebSockets** — streaming run events only goes one way, which is what SSE does, and SSE passes through proxies more reliably.

### 6.3 Agent orchestration — `graph`

| Package | Role |
| --- | --- |
| **langgraph** | The durable runtime: state graph, checkpointing, `interrupt()` / `Command(resume=...)`, subgraphs, supervisor topologies |
| **langgraph-checkpoint-sqlite** | Checkpoint persistence with no server; swaps to the Postgres checkpointer at scale |

The native runtime depends on **none** of this — it needs only Pydantic. That is deliberate: Phase 1 ships an agent loop with no orchestration dependency at all. Reasoning: [ADR-002](decisions.md#adr-002--two-runtimes-behind-one-protocol).

*Rejected:*

- **Full LangChain** — LangGraph is used directly; the chain abstractions layered on top are not needed.
- **CrewAI, AutoGen** — role-play abstractions that give too little control over the loop.
- **Temporal** — the right answer at real scale, but far too much to operate here.

### 6.4 Protocol — `mcp`

| Package | Role |
| --- | --- |
| **mcp[cli]** | The official SDK, used for the **client** side and for interop testing. The `cli` extra provides `mcp dev`, which runs a server under the MCP Inspector. |

The **server** is hand-rolled over JSON-RPC 2.0 — the wire format is the subject. The SDK client driving the hand-rolled server end to end is the test that proves the implementation is real: [ADR-003](decisions.md#adr-003--hand-rolled-mcp-server-sdk-client).

### 6.5 Model providers — `models`

| Package | Serves |
| --- | --- |
| **openai** | OpenAI, and — pointed at a different `base_url` — Groq, OpenRouter and Ollama's compatibility endpoint |
| **anthropic** | Native Messages API |
| **google-genai** | Native Gemini API (`from google import genai`) |
| **ollama** | Native local endpoint, including model management and embeddings |

One SDK covers four backends because they share a wire format. Full reasoning: [models.md §3](models.md#3-the-provider-catalogue) and [ADR-017](decisions.md#adr-017--one-compatibility-adapter-plus-native-adapters-where-they-pay).

**Token estimation.** The budget guard must estimate cost *before* a call, which needs an input token count before the provider reports one. Foreman uses a character-based approximation with a safety margin rather than adding a tokeniser dependency — over-estimating is safe, since the consequence is a slightly conservative ceiling. Exact counts come from the response and are what gets recorded.

### 6.6 Retrieval — `rag`

| Package | Role |
| --- | --- |
| **numpy** | Dense vectors and cosine similarity |
| **rank-bm25** | Sparse retrieval, fed by Foreman's own tokeniser (the one that keeps `WDG-003-A` distinct from `WDG-003-B`) |
| **pypdf** | PDF text extraction |
| **pdfplumber** | PDF **table** extraction — a price list flattened into prose loses the row/column relationship that made it useful |

**Embeddings** come from the provider layer, not from a separate dependency. The mock uses a fixed hash-based embedding, so search tests give the same answer every time, offline. Development uses a local embedding model in Ollama. A hosted embedding endpoint is used when one is configured. Embeddings are cached by content hash and are permanently valid for a given model, so switching embedding models means a full re-index — which is why the model identifier is stored alongside every vector.

*Rejected:*

- **LlamaIndex, LangChain retrievers** — writing the hybrid search in fifty lines is the point ([ADR-004](decisions.md#adr-004--hybrid-retrieval-instead-of-a-vector-database)).
- **sentence-transformers** — pulls in PyTorch, hundreds of megabytes, for something the provider layer already does.
- **A managed vector database** — the interface is there; pgvector is the drop-in replacement.

### 6.7 Data and analytics — `obs`, `pgvector`

| Package | Role |
| --- | --- |
| **duckdb** | The medallion warehouse. No server, reads Parquet directly, and SQL over trace data is how KPIs are computed. |
| **pyarrow** | Parquet read and write |
| **psycopg[binary]** + **pgvector** | Persistent vector index when the in-memory one is outgrown |
| **neo4j** | Cypher traversal for GraphRAG; in-memory graph is the default |

The run store is **SQLite via the standard library** at small scale and Postgres via psycopg at larger scale. No ORM: the schema is small, the queries are explicit, and an ORM here would be indirection without payoff. Migrations arrive with the Postgres run store in Phase 5.

*Rejected:*

- **pandas** — DuckDB does the aggregation in SQL, and PyArrow moves the data.
- **SQLAlchemy, Alembic** — postponed rather than rejected. They arrive if the database schema ever justifies them.
- **A hosted warehouse** — nothing here comes close to that much data.

### 6.8 Observability — `obs`

| Package | Role |
| --- | --- |
| **opentelemetry-sdk** | Span creation in a standard format, so no single backend is essential |
| **opentelemetry-exporter-otlp** | Export to any OTLP collector |
| **langfuse** | LLM-native backend: generations with tokens and cost, prompt versions, scores, datasets. Self-hosted via compose, so the zero-budget constraint holds. |

The **JSONL sink is in the base package**, not this group. Tracing must work with nothing installed, because a dropped trace is never acceptable — see [observability.md §3](observability.md#3-opentelemetry-and-langfuse).

### 6.9 Testing and quality — `dev`

| Package | Role |
| --- | --- |
| **pytest** | Test runner |
| **pytest-asyncio** | `asyncio_mode = "auto"`, so async tests need no decorator |
| **pytest-cov** | Coverage, gated at ≥ 95% on `rules/` and `utils/` |
| **hypothesis** | Property-based testing — the layer that finds the tolerance band with a gap at exactly 3.0% |
| **ruff** | Lint **and** format, replacing flake8, isort, black and several plugins |
| **mypy** | `--strict`, enforced in CI |
| **import-linter** | Enforces the architectural layering contracts in §5 |

*Rejected:*

- **black + isort + flake8** — ruff replaces all three and is far faster.
- **pyright** — mypy's strict mode is enough, and its plugins suit this project better.
- **tox, nox** — uv's dependency groups plus the CI matrix already cover this.
- **`unittest`** — pytest's fixtures and parametrisation are what make the shared test suites possible.

---

## 7. Model providers

| Provider | Package | Base URL | Env var | Tier |
| --- | --- | --- | --- | --- |
| Mock | — | — | — | MOCK |
| Ollama | `ollama` | `http://localhost:11434` | — | SMALL |
| Groq | `openai` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | SMALL |
| OpenRouter | `openai` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | SMALL or LARGE |
| OpenAI | `openai` | default | `OPENAI_API_KEY` | LARGE |
| Anthropic | `anthropic` | default | `ANTHROPIC_API_KEY` | LARGE |
| Google | `google-genai` | default | `GEMINI_API_KEY` | LARGE |

**A provider with no key present is skipped, not an error.** That is what makes the default configuration resolve to the mock on a clean clone with no `.env`. Selection, chains and fallback: [models.md §4](models.md#4-routing-and-provider-selection).

---

## 8. Optional services

All via `docker compose`, all with a tested in-process fallback.

| Service | Image | Enables | Fallback |
| --- | --- | --- | --- |
| Ollama | `ollama/ollama` | Local inference and embeddings | Mock provider |
| Neo4j | `neo4j:5-community` | Cypher traversal | In-memory graph |
| Postgres + pgvector | `pgvector/pgvector:pg16` | Persistent vectors, run store, checkpoints | numpy index, SQLite |
| Langfuse | `langfuse/langfuse` | Trace UI, datasets, scores | JSONL traces plus the CLI viewer |

None is required for `uv run pytest` to pass.

---

## 9. Environment variables

All prefixed `FOREMAN_` except provider keys, which keep their conventional names so existing shell setups work. Full list in `.env.example`; none is required.

| Variable | Default | Purpose |
| --- | --- | --- |
| `FOREMAN_ENV` | `dev` | Environment profile |
| `FOREMAN_TIER_SMALL` | `["mock"]` | Provider chain for the SMALL tier |
| `FOREMAN_TIER_LARGE` | `["mock"]` | Provider chain for the LARGE tier |
| `FOREMAN_RUNTIME` | `native` | `native` or `graph` |
| `FOREMAN_MAX_COST_PER_RUN_CENTS` | `10` | Per-run budget ceiling |
| `FOREMAN_MAX_COST_PER_DAY_CENTS` | `100` | Daily ceiling |
| `FOREMAN_KILL_SWITCH` | `false` | Disables all hosted inference |
| `FOREMAN_ENABLE_GRAPH_STORE` | `false` | Neo4j instead of in-memory |
| `FOREMAN_ENABLE_PGVECTOR` | `false` | pgvector instead of numpy |
| `FOREMAN_ENABLE_LANGFUSE` | `false` | Langfuse export in addition to JSONL |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local endpoint |
| `OPENAI_API_KEY` … `GEMINI_API_KEY` | unset | Provider credentials; absent means that provider is skipped |

---

## 10. Version policy

| Rule | Reason |
| --- | --- |
| Floors in `pyproject.toml`, exact pins in `uv.lock` | Installs are reproducible without over-constraining the resolver |
| `uv.lock` committed; CI runs `uv sync --locked` | A stale lockfile fails the build instead of silently resolving something else |
| Dependency updates are their own commit | A bump is never buried in a feature diff |
| Monthly update cadence, plus immediate security patches | Predictable, and small enough to review |
| **Model IDs pinned exactly, never aliases** | An alias that moves is a change to the system nobody made — the canary check in [evaluation.md §7](evaluation.md#7-drift-detection) exists because of this |

Pinning the model version causes the most trouble, and it is not something a package manager can fix: `uv.lock` cannot protect you from a provider repointing an alias.

---

## 11. Licence posture

Foreman is MIT. Every dependency must be permissive — MIT, BSD or Apache-2.0 — so the combined work stays MIT-licensable.

| Note | Detail |
| --- | --- |
| Base and dev dependencies | MIT / BSD / Apache-2.0 throughout |
| **Neo4j Community** | GPLv3, but it is a **service reached over the network** via the Apache-2.0 Python driver — no linking, no derivative work. Optional in any case. |
| Copyleft in the dependency tree | Not permitted. A licence check runs in CI. |
| Model weights | Not redistributed. Ollama models carry their own licences, which the user accepts on pull. |

---

## 12. Supply chain

| Control | Mechanism |
| --- | --- |
| Reproducible installs | `uv.lock` with hashes; CI asserts freshness |
| Vulnerability scanning | Dependency audit in CI, blocking on high severity |
| Automated updates | Dependabot, grouped, reviewed like any other change |
| Secret scanning | Pre-commit hook plus CI |
| Container provenance | Pinned base image digests; non-root user; multi-stage so build tooling never ships |
| Minimal attack surface | Three base packages; each group is an explicit decision to add surface |
| Pinned CI actions | GitHub Actions pinned by commit SHA, not by tag |

The last row matters more than it looks: a mutable tag on a third-party action is arbitrary code execution in your CI, retroactively.

---

## 13. Deliberately not in the stack

Each considered and declined for a stated reason. Fuller treatment in [ADR-016](decisions.md#adr-016--what-was-deliberately-left-out).

| Not used | Instead | Why |
| --- | --- | --- |
| LangChain (full framework) | LangGraph directly | The chain abstractions add indirection over things this project does explicitly |
| LlamaIndex | Hand-rolled hybrid retrieval | Rank fusion in fifty lines is the lesson |
| LiteLLM | Own provider adapters | Hides the capability differences the router needs to see — [ADR-017](decisions.md#adr-017--one-compatibility-adapter-plus-native-adapters-where-they-pay) |
| Pinecone / Weaviate / Qdrant / Chroma | numpy, then pgvector | Interface exists; a managed service would hide why hybrid retrieval is necessary |
| sentence-transformers | Provider embeddings | Avoids a PyTorch-sized dependency for something already available |
| Celery / RQ / Arq | `asyncio` queues | Matches the scale; the swap is documented in [scalability.md §8](scalability.md#8-scaling-out) |
| Redis | In-process state | Named as the scale-out swap for rate limiting and checkpoints, not a default |
| Airflow / Prefect / Dagster | The agent, and scripts | The agent *is* the orchestrator; ingestion is a batch script |
| SQLAlchemy / Alembic | Explicit SQL | Small schema; deferred rather than rejected |
| pandas | DuckDB + PyArrow | Aggregation belongs in SQL |
| Poetry / pip-tools / PDM | uv | [ADR-009](decisions.md#adr-009--uv-for-packaging) |
| black / isort / flake8 | ruff | One tool, one config, far faster |
| Streamlit / Gradio / React | An API with a diff payload | A front end would be the largest component and would demonstrate nothing about applied AI engineering |
| Kubernetes / Helm | One container, one compose file | Writing manifests for a cluster that does not exist is pointless |
| Prometheus / Grafana | DuckDB + Langfuse | The metrics are LLM-shaped; a time-series stack would be a second system |

---

## 14. Install recipes

| I want to… | Command |
| --- | --- |
| Read the code and run the tests | `uv sync && uv run pytest` |
| Run a CLI scenario | `uv sync && uv run foreman run --scenario happy-path` |
| Work on retrieval | `uv sync --group rag` |
| Run the MCP server | `uv sync --group mcp && uv run python -m mcp_server` |
| Serve the API | `uv sync --group api && uv run uvicorn api.main:app --reload` |
| Use the durable runtime | `uv sync --group graph` |
| Call a real model | `uv sync --group models`, set one provider key |
| See traces and KPIs | `uv sync --group obs` |
| Everything | `uv sync --all-groups && docker compose up -d` |
| Reproduce CI exactly | `uv sync --locked --all-groups` |

**Set a hard spend cap on any provider key before you use it.** It is the only budget control that does not depend on this code being correct — [models.md §6](models.md#6-cost-accounting-and-budget-control).
