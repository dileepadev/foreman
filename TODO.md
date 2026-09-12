# TODO

This file tracks tasks, improvements, and features planned for upcoming updates or releases of this repository.

> [!Note]
> This list is **not exhaustive** and may change over time. Items are not necessarily in priority order.

Phases are **dependency order, not a schedule**. Each phase ends with a gate that either passes or does not — do not start a phase before the previous gate is green. Full definitions: [docs/FOREMAN_SPEC.md](docs/FOREMAN_SPEC.md#10-build-plan).

## Progress

| Phase | Scope | Status |
| --- | --- | --- |
| [Specification](#specification) | Design documentation | ✅ Complete |
| [Phase 0](#phase-0--scaffold) | Scaffold | ⬜ Not started |
| [Phase 1](#phase-1--deterministic-core-and-the-agent-loop) | Deterministic core and the agent loop | ⬜ Not started |
| [Phase 2](#phase-2--protocol-and-integration) | Protocol and integration | ⬜ Not started |
| [Phase 3](#phase-3--knowledge) | Knowledge | ⬜ Not started |
| [Phase 4](#phase-4--observability-and-evaluation) | Observability and evaluation | ⬜ Not started |
| [Phase 5](#phase-5--service-security-and-governance) | Service, security and governance | ⬜ Not started |
| [Phase 6](#phase-6--orchestration-models-and-delivery) | Orchestration, models and delivery | ⬜ Not started |

---

## Specification

- [x] Master technical specification with capability coverage map
- [x] Architecture, layers, invariants and failure model
- [x] Process decomposition method and scenario catalogue
- [x] Agent architecture, orchestration patterns, runtime protocol
- [x] Memory tiers and compaction
- [x] Full MCP surface, transports, authorization and threat model
- [x] Enterprise integration, auth patterns and write safety
- [x] Retrieval and GraphRAG
- [x] Model routing, structured output and cost control
- [x] Security, privacy and governance
- [x] Observability and evaluation
- [x] Concurrency and scalability
- [x] Development, operations and runbook
- [x] Architecture decision records and glossary
- [x] Complete tech stack: dependency groups, versions, licences, supply chain
- [x] [AGENTS.md](AGENTS.md) — the rules, conventions, phase order and definition of done for AI coding agents, following the [agents.md](https://agents.md/) standard

---

## Phase 0 — Scaffold

- [ ] `uv init` with a `src/` layout — the package is `src/foreman/`, console script `foreman.cli:app`
- [ ] Dependency groups per [tech-stack.md §4](docs/tech-stack.md#4-dependency-groups): `dev`, `api`, `mcp`, `graph`, `models`, `rag`, `pgvector`, `obs`
- [ ] Commit `uv.lock`
- [ ] `core/errors.py` — `TransientError`, `PermanentError`, `ToolError`, `PolicyViolation`, `BudgetExceeded`
- [ ] `core/config.py` — settings, secrets as `SecretStr`, a feature flag per optional service
- [ ] `.env.example` documenting every variable
- [ ] Package directories for Phase 1 modules only
- [ ] `ruff`, `mypy --strict` and `import-linter` configuration
- [ ] Pre-commit hooks including secret scanning
- [ ] **Gate:** `uv sync` succeeds · `uv run pytest` collects zero tests without error · `uv run mypy .` clean

---

## Phase 1 — Deterministic core and the agent loop

> The bar for making the repository public. If only this ships, it is still worth having.

### Domain and state

- [ ] `models/procurement.py` — `OrderLine`, `PurchaseOrder`, `ConfirmedLine`, `SupplierConfirmation`, `GoodsReceipt`
- [ ] Field-level constraints throughout (`quantity: int = Field(gt=0)`); `Decimal` on every monetary path
- [ ] `models/agent_state.py` — `ToolCall`, `ToolResult`, `AgentStep`, `StopReason`, `AgentState`
- [ ] `models/tenancy.py` — `Tenant`, `Principal`, `Role`, `Scope`
- [ ] Cycle detection: action signatures, consecutive repeats **and** two-tool oscillation over a sliding window

### Rules

- [ ] `rules/policies.py` — tolerance bands and spend thresholds, each with ID, version, owner and description
- [ ] `rules/engine.py` — evaluation returning **which rule fired**, not a boolean
- [ ] `rules/matching.py` — two- and three-way match, pure and total
- [ ] `rules/decision_tables.py` — SME-readable tables, loaded and validated
- [ ] Property tests: rules are exhaustive and unambiguous
- [ ] No model call anywhere in `rules/`

### Resilience

- [ ] `utils/retry.py` — `classify_http_error`, backoff with full jitter, `Retry-After` honoured
- [ ] `utils/idempotency.py` — deterministic keys over the business payload plus a time bucket; dedupe store
- [ ] `utils/concurrency.py` — `bounded_gather` with per-item isolation
- [ ] `utils/pagination.py` — cursor iteration with page caps
- [ ] `utils/clock.py` — injectable time

### Agent

- [ ] `agent/tool_registry.py` — schema generation from type hints, argument validation, read/write separation
- [ ] Registry refuses to register a `mutates=True` tool without a required scope
- [ ] Structured `ToolError` with `error_type`, `message`, `suggestion` — never a traceback
- [ ] `providers/base.py` — `LLMProvider` protocol
- [ ] `providers/mock.py` — scripted, deterministic, no network
- [ ] `agent/prompts.py` — versioned prompts with negative constraints and a few-shot trajectory
- [ ] `runtime/protocol.py` — the `Runtime` protocol
- [ ] `runtime/native.py` — the loop, four stopping conditions, returning `StopReason` **and** partial state

### CLI and tests

- [ ] `cli.py` — `foreman run --scenario happy-path | price-variance | partial | quantity-short`
- [ ] `tests/test_models.py`, `test_rules.py`, `test_resilience.py`, `test_tool_registry.py`, `test_native_runtime.py`
- [ ] Property tests with `hypothesis` on rules, idempotency and concurrency
- [ ] Coverage ≥ 95% on `rules/` and `utils/`
- [ ] **Gate:** `uv run pytest -v` green · `happy-path` confirms all lines in ≤ 6 steps · `price-variance` escalates and names the rule that fired · `mypy --strict` clean

---

## Phase 2 — Protocol and integration

### MCP

- [ ] `mcp_server/protocol.py` — JSON-RPC 2.0 framing, lifecycle, capability negotiation, hand-rolled
- [ ] Notifications never receive a response (enforced structurally)
- [ ] Protocol errors vs `isError: true` tool results, correctly distinguished
- [ ] `mcp_server/server.py` — tools, resources, prompts, completion
- [ ] `mcp_server/transport/stdio.py` with a stdout guard
- [ ] `agent/mcp_client.py` — SDK client, discovery, dispatch, per-server tool namespacing
- [ ] Interop test: official SDK client drives the hand-rolled server end to end

### Connectors

- [ ] `connectors/base.py` — `Connector` protocol; `idempotency_key` required on `mutate`
- [ ] `connectors/erp.py` — service account auth, cursor pagination, optimistic locking
- [ ] `connectors/crm.py` — OAuth 2.1 client credentials, short-lived tokens
- [ ] `connectors/portal.py` — API key auth, rate limiting, eventual consistency
- [ ] `connectors/logistics.py` — delegated token with **single-flight** refresh, webhooks, out-of-order events
- [ ] Deliberately divergent field names and conventions across all four
- [ ] `connectors/resolver.py` — source of truth **per field**; conflicts returned as values
- [ ] Circuit breaker withdrawing tools and emitting `list_changed`

### Mapping and memory

- [ ] `mapping/schema_mapper.py` — candidates with confidence **and** weight; `requires_review` derived
- [ ] `mapping/review.py` — per-field accept/reject report, versioned
- [ ] `agent/memory/` — window budgets, working-state projection, budget-triggered compaction
- [ ] Numeric-preservation property test on summarisation
- [ ] **Gate:** `initialize`, `tools/list`, `tools/call` over stdio · agent completes a scenario through MCP · a price conflict between ERP and portal is surfaced · connector tests green

---

## Phase 3 — Knowledge

- [ ] `ingestion/extract.py` — text and table extraction
- [ ] `ingestion/dedupe.py` — content hashing plus near-duplicate detection with `supersedes` links
- [ ] `ingestion/categorise.py` — `doc_type`, `access_roles`, `supplier_id`, `effective_date`
- [ ] `ingestion/pipeline.py` — incremental re-index and **deletion propagation**
- [ ] Embedding source behind the provider layer: deterministic hash embeddings in the mock, Ollama locally, hosted when configured
- [ ] Embeddings cached by content hash; the embedding model ID stored with every vector, so a model change forces a re-index
- [ ] `rag/chunker.py` — paragraph boundaries, overlap, ACL metadata denormalised onto every chunk
- [ ] `rag/retriever.py` — dense + BM25, RRF fusion
- [ ] Tokeniser preserving hyphenated alphanumerics (`WDG-003-A` ≠ `WDG-003-B`)
- [ ] **ACL pre-filter applied before scoring**
- [ ] `rag/generator.py` — inline citations, citation validity check, conflict surfacing with dates
- [ ] `rag/graph/` — entity graph, multi-hop traversal, community summaries; in-memory default, Neo4j optional
- [ ] `tests/corpus/` — adversarial document set
- [ ] **Gate:** exact part-number retrieval succeeds where dense-only fails · an unpermitted role returns **zero** restricted chunks · a two-hop impact question is answered · retrieval tests green

---

## Phase 4 — Observability and evaluation

- [ ] `obs/tracing.py` — OpenTelemetry spans, append-only JSONL fallback, versioned schema
- [ ] `foreman trace <run-id>` — readable tree renderer
- [ ] `obs/langfuse_export.py` — trace → generation → span → event
- [ ] `obs/warehouse.py` — DuckDB medallion over Parquet
- [ ] `obs/metrics.py` — outcome, behaviour, cost and performance KPIs
- [ ] `silent_error_rate` and `auto_resolution_rate` always reported as a pair
- [ ] `eval/suite.py` — golden traces with property assertions, including forbidden-tool invariants
- [ ] `eval/judge.py` — rubric scoring, 100-run human calibration set, Cohen's κ reported per dimension
- [ ] `eval/drift.py` — PSI on inputs, rate-of-change alerting, canary prompts
- [ ] `eval/shadow.py` — writes suppressed, decisions diffed
- [ ] **Gate:** golden suite at 100% property pass · trace renders readably · warehouse produces a KPI table · shadow mode reports a decision diff

---

## Phase 5 — Service, security and governance

### Security

- [ ] `security/guardrails/` — input, output and action layers, independently testable
- [ ] `security/injection.py` — heuristics, normalisation, randomised untrusted-content delimiters
- [ ] Injection attack corpus shipped as tests
- [ ] `security/rbac.py` — allow-lists, hard write ceilings, soft escalation bands, enforced at dispatch
- [ ] Every denial audited
- [ ] `security/privacy.py` — PII detection, redaction **at trace-write time**, retention, erasure
- [ ] `security/masking.py` — pattern-based secret redaction
- [ ] `security/mcp_threats.py` — one control per threat-table row
- [ ] Tenant isolation by **namespace**, not by filter

### Governance

- [ ] `governance/registry.py` — model, prompt and rule versions per run
- [ ] `governance/audit.py` — hash-chained append-only log with tamper detection

### Service

- [ ] `api/main.py` — FastAPI app, lifespan, health
- [ ] `api/auth.py` — API keys (hashed), OAuth 2.1, service accounts
- [ ] `api/limits.py` — per-tenant rate limits, concurrency caps, token and cost quotas
- [ ] `api/runs.py` — start a run, stream over SSE with heartbeats and sequence numbers
- [ ] `api/history.py` — persistence and resume
- [ ] `api/review.py` — HITL queue with a **diff payload**; approve/reject
- [ ] `mcp_server/transport/streamable_http.py` with `Origin` validation
- [ ] `mcp_server/auth.py` — OAuth 2.1 resource server, Protected Resource Metadata, audience validation, no token passthrough
- [ ] `notify/webhook.py` — signed escalation delivery
- [ ] **Gate:** SSE run streams · an over-tolerance scenario produces a usable review diff · **an injected document produces no write because RBAC blocks it** · a wrong-audience token is rejected · erasure reaches every store

---

## Phase 6 — Orchestration, models and delivery

- [ ] `runtime/langgraph_runtime.py` — checkpointing, `interrupt()`, resume
- [ ] `runtime/graph.py` — supervisor plus extraction, verification and escalation workers
- [ ] Typed hand-offs, never free text; every hand-off a trace span
- [ ] `runtime/patterns/` — ReAct, plan-execute, reflection, routing
- [ ] `eval/pattern_benchmark.py` — populate the pattern comparison table with real numbers
- [ ] `tests/conformance/` — the shared suite both runtimes must pass
- [ ] `providers/base.py` — `ProviderCapabilities`: tools, structured output, streaming, prompt caching, cost reporting, max context
- [ ] `providers/openai_compat.py` — one adapter for OpenAI, Groq, OpenRouter and Ollama
- [ ] `providers/anthropic.py` and `providers/google.py` — native adapters
- [ ] `providers/local.py` — Ollama
- [ ] `providers/registry.py` — providers built from config; a provider with no key is skipped, not an error
- [ ] `providers/pricing.toml` — per-model rates, versioned; **an unknown model ID is a hard error, never a zero**
- [ ] `tests/providers/` — one contract suite every provider must pass against its declared capabilities
- [ ] `providers/structured.py` — strategy ladder plus a bounded repair loop
- [ ] `providers/router.py` — deterministic tier selection, then an ordered provider chain per tier
- [ ] Fallback distinct from retry: next provider, re-estimated budget, `fallback_from` on the span
- [ ] `providers/cost.py` — accounting, per-run and per-day ceilings, kill switch checked **before** the call
- [ ] Document the provider-side per-key spend cap in the README — the only ceiling that does not depend on our code being correct
- [ ] `providers/cache.py` — exact, semantic (off by default) and prompt cache
- [ ] `eval/cost_benchmark.py` — routed vs frontier-only, ≥ 60% saving at equal quality
- [ ] Multi-stage `Dockerfile` with `uv sync --locked --no-editable`, non-root user, healthcheck
- [ ] `docker-compose.yml` — Neo4j, Postgres+pgvector, Ollama, Langfuse, all optional
- [ ] `.github/workflows/ci.yml` — lint, types, import contracts, tests, security corpus, **evaluation gate**
- [ ] Every degradation-ladder fallback exercised in CI
- [ ] `scripts/load_test.py` and the performance targets
- [ ] **Gate:** conformance suite passes against both runtimes · CI green on a clean clone · `docker compose up` starts the stack · an interrupted run resumes after process restart · the router shows a measured cost reduction

---

## Ongoing

- [ ] Every incident becomes a golden scenario or a security-corpus case
- [ ] Every working injection technique is added to the corpus permanently
- [ ] Documentation updated in the same commit as the code it describes
- [ ] README status table kept accurate — the item most likely to slip
- [ ] `CHANGELOG.md` updated per release, per [VERSIONING.md](VERSIONING.md)
- [ ] No employer, product, customer or individual names anywhere in the repository
