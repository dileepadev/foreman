# Architecture Decisions

Engineering notes: what was chosen, what was rejected, and what the trade-off cost. Usually the most-read file in a repository, because it answers the question code cannot — *why is it like this?*

Each record is short on purpose. A decision that needs three pages of justification is usually two decisions.

| # | Decision | Status |
| --- | --- | --- |
| [001](#adr-001--business-rules-are-code-not-prompts) | Business rules are code, not prompts | Accepted |
| [002](#adr-002--two-runtimes-behind-one-protocol) | Two runtimes behind one protocol | Accepted |
| [003](#adr-003--hand-rolled-mcp-server-sdk-client) | Hand-rolled MCP server, SDK client | Accepted |
| [004](#adr-004--hybrid-retrieval-instead-of-a-vector-database) | Hybrid retrieval instead of a vector database | Accepted |
| [005](#adr-005--acl-filtering-before-scoring) | ACL filtering before scoring | Accepted |
| [006](#adr-006--single-agent-is-the-default) | Single agent is the default | Accepted |
| [007](#adr-007--idempotency-keys-are-deterministic-over-the-payload) | Idempotency keys are deterministic over the payload | Accepted |
| [008](#adr-008--the-mock-provider-is-the-default) | The mock provider is the default | Accepted |
| [009](#adr-009--uv-for-packaging) | uv for packaging | Accepted |
| [010](#adr-010--duckdb-medallion-instead-of-a-warehouse) | DuckDB medallion instead of a warehouse | Accepted |
| [011](#adr-011--the-judge-is-calibrated-before-it-is-trusted) | The judge is calibrated before it is trusted | Accepted |
| [012](#adr-012--silent-errors-outrank-visible-ones) | Silent errors outrank visible ones | Accepted |
| [013](#adr-013--source-of-truth-is-per-field) | Source of truth is per field | Accepted |
| [014](#adr-014--tenant-isolation-by-namespace-not-by-filter) | Tenant isolation by namespace, not by filter | Accepted |
| [015](#adr-015--traces-are-redacted-at-write-time) | Traces are redacted at write time | Accepted |
| [016](#adr-016--what-was-deliberately-left-out) | What was deliberately left out | Accepted |
| [017](#adr-017--one-compatibility-adapter-plus-native-adapters-where-they-pay) | One compatibility adapter, plus native adapters where they pay | Accepted |

---

## ADR-001 — Business rules are code, not prompts

**Context.** Tolerance bands, spend thresholds and approval routing could live in a system prompt. It is faster to write and easier to change.

**Decision.** They live in `rules/`, as versioned Python with IDs, owners and descriptions.

**Why.** A prompt rule is applied probabilistically — it will be followed most of the time, which is the worst possible reliability profile because it looks like it works. It cannot be unit tested. It cannot be versioned meaningfully. And it is not an answer an auditor accepts: "the model was told to use a 3% tolerance" is not the same statement as "a 3% tolerance was applied."

**Cost.** Policy changes require a code change and a deploy rather than a prompt edit. Accepted — a policy change *should* be a reviewed, tested, versioned event.

**Rejected:** prompt-embedded rules; a rules DSL (more machinery than twelve rules justify); a commercial BRMS (vastly more product than domain).

---

## ADR-002 — Two runtimes behind one protocol

**Context.** Either hand-roll the agent loop, or adopt a framework. Hand-rolling demonstrates understanding; a framework provides durability, checkpointing and human-in-the-loop resume, which this domain genuinely needs because an escalation can wait days.

**Decision.** Both, behind one `Runtime` protocol, with a shared conformance suite. `runtime/native.py` is hand-rolled and is the default for tests and CLI. `runtime/langgraph_runtime.py` uses LangGraph and is the default for the served API.

**Why LangGraph specifically.** Six reasons:

- Runs survive a restart, because each one is checkpointed.
- `interrupt()` and `Command(resume=...)` match the review queue exactly: pause, wait for a human, carry on.
- A cross-thread store maps directly onto episodic memory.
- Subgraphs and supervisor patterns cover the multi-agent work.
- Its tracing is OpenTelemetry-compatible, so it feeds the same Langfuse pipeline.
- The graph is explicit, with no hidden control flow. That matters in a repository whose whole point is that you can inspect the reasoning.

**Cost.** Two implementations to keep in step. Mitigated by the conformance suite — a new runtime is not a runtime until it passes. Without that suite this would be sprawl rather than a decision.

**Rejected:**

| Alternative | Why not |
| --- | --- |
| Hand-rolled only | Rebuilding durable checkpointing badly teaches nothing and ships less |
| LangGraph only | Loses the demonstration that the loop is understood, and adds a dependency to the Phase 1 core |
| Pydantic AI | Excellent typing and OTel story, but weaker durable-execution and interrupt primitives, which is the requirement that decided it |
| OpenAI Agents SDK | Provider-tilted; this project is explicitly multi-provider and local-first |
| CrewAI / AutoGen | Role-play abstractions optimised for multi-agent demos; too little control over the loop |
| Temporal + custom | The right answer at real scale; far too much operational weight here |

---

## ADR-003 — Hand-rolled MCP server, SDK client

**Context.** MCP has mature SDKs. Using one for both sides would be faster.

**Decision.** The server is hand-rolled over JSON-RPC 2.0. The client uses the official SDK.

**Why.** For the server, the wire format *is* the subject: framing, lifecycle, capability negotiation, and the distinction between a protocol error and a tool error that returns `isError: true`. An SDK hides exactly those parts. For the client, the realistic enterprise case is consuming servers you did not write, and reimplementing a client teaches nothing the server did not already teach.

**Cost.** More code, and the responsibility to track spec revisions. Mitigated by an interop test: the official SDK client drives the hand-rolled server end to end. A hand-rolled server that only works against a hand-rolled client has proven nothing.

---

## ADR-004 — Hybrid retrieval instead of a vector database

**Context.** A managed vector database would be less code.

**Decision.** Dense cosine over numpy plus BM25, fused with Reciprocal Rank Fusion, behind a `VectorIndex` interface with an optional pgvector backend.

**Why.** Vector search cannot reliably distinguish `WDG-003-A` from `WDG-003-B` — they embed almost identically, and in this domain that is the difference between two products. BM25 fixes it, but only with a tokeniser that preserves hyphenated alphanumerics; a default tokeniser splits both into the same tokens and reproduces the failure. Writing the fusion in fifty lines makes both facts visible, where a managed service would make them invisible and unfixable.

**Cost.** Bounded corpus size in the default configuration. Acceptable: the interface exists, and pgvector is a configuration change.

---

## ADR-005 — ACL filtering before scoring

**Context.** Filtering after retrieval is simpler and often faster.

**Decision.** The permission filter is applied to the index before scoring, always.

**Why.** Post-filtering leaks in two ways. The obvious one: top-k is consumed by documents the caller cannot see, so a permitted document ranked 11th silently disappears. The subtle one: result counts and latencies reveal that restricted documents exist. And once a restricted chunk is in the context window, it is also in the answer, in the trace, and possibly in episodic memory. Telling a model to ignore something you have already shown it is not access control.

**Cost.** The index must support filtered search efficiently, and ACL metadata must be denormalised onto every chunk rather than kept on the parent document.

---

## ADR-006 — Single agent is the default

**Context.** Multi-agent architectures are the most fashionable pattern in the field.

**Decision.** One agent unless a specific criterion is met: tool sets diverge, permissions differ, models differ, or hand-offs need supervision. Foreman includes a supervisor setup because reasons 2 and 3 apply here. Extraction should be cheap and hold no write permissions. Judging a case needs both permissions and a capable model. The trade-off is written down rather than presented as obviously correct.

**Why.** Every additional agent adds a hand-off surface, latency, 3–5× token usage from re-established context, an extra loop with its own stopping conditions, harder debugging from interleaved traces, and an attribution problem in evaluation.

**Cost.** The single-agent path handles more tool variety than a decomposed design would. Bounded by keeping the registry small and per-run allow-listed.

---

## ADR-007 — Idempotency keys are deterministic over the payload

**Context.** A UUID per attempt is simpler.

**Decision.** `sha256(tenant | operation | business_identity | normalised_payload | time_bucket)`.

**Why.** The case this exists for is a write that succeeded and whose response was lost. A per-attempt UUID makes the retry a *new* write and double-confirms the order. A deterministic key makes it recognisably the same write. It also survives a process restart — a run resumed after human review recomputes the identical key, which a run-local counter or a UUID cannot.

**Cost.** Payload normalisation must be exact and stable — field order, decimal representation, whitespace. Tested with property assertions, because a normalisation bug produces duplicate writes, silently.

**Rejected:** per-attempt UUID (defeats the purpose); server-generated key (unavailable before the call succeeds); timestamp-based (breaks on retry).

---

## ADR-008 — The mock provider is the default

**Context.** The default configuration could use a local or a hosted model.

**Decision.** `provider=mock` by default: a scripted, deterministic provider with no network.

**Why.** Four things follow from it. `uv sync && uv run pytest` passes on a clean clone in under a minute with no key — which is the difference between a reader who runs the tests and one who does not. CI is deterministic, so a failure means the logic changed rather than a model having a different day. CI is free, so nobody learns to skip an expensive suite. And a test failure is never ambiguous between "the code broke" and "the model drifted."

**Cost.** The mock's scripts must be maintained alongside the scenarios. Worth it — the scripts double as documentation of what a correct trajectory looks like.

---

## ADR-009 — uv for packaging

**Context.** pip + requirements, Poetry, PDM, or uv.

**Decision.** uv, with dependency groups and a committed `uv.lock`.

**Why.** A real lockfile that CI can assert against with `--locked`. Resolution fast enough that CI is not waiting on dependency installs, which keeps the full quality gate under five minutes — and a gate under five minutes is one people wait for. Dependency groups keep the base install at four packages, which makes the "runs with no services" claim structural. And one tool covers environment, install and run, so there is one command in the README rather than four.

**Cost.** Newer than Poetry; contributors may not have it. Mitigated by a one-line install in the README.

---

## ADR-010 — DuckDB medallion instead of a warehouse

**Context.** Metrics could be computed ad hoc from JSONL, or pushed to a real warehouse.

**Decision.** DuckDB over Parquet in bronze / silver / gold layers.

**Why.** Ad hoc queries over JSONL do not survive a trace-schema change: the history becomes unqueryable. A medallion layout keeps bronze immutable and reprocessable, absorbs schema evolution in the silver transformation, and gives dashboards and the CI evaluation gate a stable gold contract. DuckDB needs no server, reads Parquet directly, and scales far past this project's data volume.

**Cost.** A transformation layer to maintain. It pays for itself the first time the trace schema changes.

---

## ADR-011 — The judge is calibrated before it is trusted

**Context.** LLM-as-judge is the standard approach for qualities that cannot be asserted.

**Decision.** Ship a 100-run human-labelled calibration set, report Cohen's κ per rubric dimension, and use the judge as a gate only at κ ≥ 0.80. Below that it is advisory.

**Why.** An unchecked judge does not solve the trust problem. It just moves it somewhere else — you have replaced "do I trust the agent" with "do I trust the grader", and the second question is usually never asked. Judges have known, measurable biases: position, verbosity, leniency clustering, self-preference and sycophancy. Reporting agreement is the only honest way to use one.

**Cost.** 100 human labels, and re-labelling whenever the judge model changes. This is the single most tedious task in the project and the one most worth doing.

**Corollary.** The judge scores outputs, never decisions. Whether to escalate is a rule, and asking a model to grade a subtraction reintroduces probabilistic error into the deterministic core.

---

## ADR-012 — Silent errors outrank visible ones

**Context.** Tolerance thresholds trade automation rate against error rate.

**Decision.** Optimise for zero silent errors, accept over-escalation, and always report `auto_resolution_rate` and `silent_error_rate` as a pair.

**Why.** They are not symmetric. An over-escalation costs a buyer two minutes, is visible, is measurable and is tunable. A silent wrong confirmation enters the ledger, surfaces weeks later at reconciliation, and permanently destroys confidence in the system. Any single-number automation metric hides this trade, so the metrics are paired everywhere they appear — the dashboard, the CI gate, and the report.

**Cost.** Lower headline automation rate than a system tuned to look good. That is the correct trade and stating it is part of the design.

---

## ADR-013 — Source of truth is per field

**Context.** The simple design nominates one system as authoritative.

**Decision.** A field-level registry in `connectors/resolver.py`. Conflicts are returned as values, never resolved silently.

**Why.** Reality is not that simple: the ERP owns contract price, the portal owns what the supplier confirmed, logistics owns the real delivery date, the CRM owns which contract applies. A system-level nomination forces the wrong answer somewhere. The resolver also refuses to decide what a conflict *means*. That is a rule. The same disagreement can be a normal business variance in one situation and a data-quality incident in another.

**Cost.** A registry to maintain per field, and every consumer must handle `conflicts` being non-empty. Enforced by the type: `Resolved[T]` carries the list.

---

## ADR-014 — Tenant isolation by namespace, not by filter

**Context.** Tenant scoping could be a metadata filter on a shared index.

**Decision.** A separate index namespace per tenant.

**Why.** A filter is one forgotten predicate away from a cross-tenant leak, and that failure mode is silent, plausible and catastrophic. A namespace fails closed: a bug returns nothing rather than someone else's contract pricing. Given the asymmetry of consequences, the more expensive option is correct.

**Cost.** Some duplication, and per-tenant index management. Cheap relative to the failure it prevents.

---

## ADR-015 — Traces are redacted at write time

**Context.** Redaction could happen when a trace is read, keeping full fidelity on disk for debugging.

**Decision.** Redaction happens as the trace is written.

**Why.** Redaction on read means the raw personal data exists on disk, in backups, in every replica and in every copy anyone exported. An erasure request then has to chase all of them, and it will miss one. Redaction on write means it never lands, so erasure is a deletion of records rather than a hunt.

**Cost.** A redacted trace cannot be un-redacted when debugging needs the original value. Accepted, and mitigated by preserving structure and types — a redacted field still shows it was a phone number in position three.

---

## ADR-016 — What was deliberately left out

As informative as what is in. Each of these was considered and declined for a stated reason, not overlooked.

| Left out | Why |
| --- | --- |
| Fine-tuning | The bottleneck here is control and integration, not model capability. Fine-tuning would add cost, an MLOps surface and reproducibility problems while solving nothing on the critical path. |
| A web UI | The review queue is an API with a diff payload. A React front end would be the largest component in the repository and would demonstrate nothing about applied AI engineering. |
| Real vendor integrations | Requires credentials nobody reading this has, and would make the repository unrunnable. The mocks carry the realistic friction instead. |
| Kubernetes manifests | A single container and a compose file match the actual deployment. Writing manifests for a cluster that does not exist is pointless. |
| A message broker | `asyncio` queues match the scale. The interface is in place; swapping in Redis is documented in [scalability.md](scalability.md) §8. |
| Open-ended autonomy | No part of this domain benefits from an agent setting its own goals in a procurement ledger. |
| Multi-modal input | Scanned-document OCR is a real problem and an entirely separate one. Extraction is tested on text and tables. |
| Streaming token output to the reviewer | Reviewers need a diff, not a typewriter. SSE streams run *events*, not tokens. |
| A prompt-management SaaS | Prompts are versioned in code with recorded pass rates, so they move with the tests that validate them. |
| Agent-to-agent negotiation | Interesting, and unrelated to whether a purchase order was confirmed correctly. |

The pattern: **anything that adds surface without adding evidence was cut.** A repository that does a few things properly, and says plainly what it does not do, is more convincing than one that hints at everything.

---

## ADR-017 — One compatibility adapter, plus native adapters where they pay

**Context.** Foreman supports six model backends: Ollama locally, and OpenAI, Anthropic, Google, Groq and OpenRouter hosted. Three ways to span them — force everything through OpenAI-compatible endpoints, write a native adapter per vendor, or adopt a unification library.

**Decision.** A shared `openai_compat.py` adapter for the providers that genuinely speak `POST /v1/chat/completions` (OpenAI, Groq, OpenRouter, Ollama), plus native adapters for Anthropic and Google. Every provider declares a `ProviderCapabilities` object, and each tier resolves to an ordered provider chain defined in configuration.

**Why.** Small models are a commodity. They are interchangeable, and the cheapest working endpoint wins. One adapter pointed at four different URLs is exactly right for them.

Large models are not a commodity. That is where prompt caching, native tool-use blocks and the vendor's own token counting are worth having. The OpenAI-compatible endpoints Anthropic and Google offer are a stripped-down translation that throws all of that away.

Paying extra for a special capability and then reaching it through a generic adapter gives you the worst of both.

The capability object is what makes the chain safe. Providers are **not** interchangeable. The failure this prevents is a quiet one. Send a tool-calling request to a model that does not support tools, and it replies with a fluent paragraph describing the call it would have made. Nothing throws an error. The router checks capabilities before dispatch instead.

**Cost.** Two adapter shapes rather than one, and a capability matrix that has to stay honest — a provider whose declared capabilities are wrong fails confusingly. Mitigated by a per-provider contract test: each provider runs the same suite and must behave as it declares, which is the provider-layer analogue of the runtime conformance suite in [ADR-002](#adr-002--two-runtimes-behind-one-protocol).

**Rejected:**

| Alternative | Why not |
| --- | --- |
| OpenAI-compatible only | Loses prompt caching, native tool blocks and accurate accounting on the one tier where the calls are expensive |
| A native adapter per provider | Four near-identical HTTP clients for four providers that already agree on the wire format |
| LiteLLM or a similar unification library | Hides exactly the capability differences the router needs to see, and its translation bugs become yours. The dependency would be reasonable in a product; here it would remove the lesson. |
| One hardcoded provider | The budget constraint makes vendor portability a requirement, not a nicety — a price change or an outage must be a config edit |
