# Foreman Documentation

Specification and design documentation for Foreman, an enterprise agent platform for procure-to-pay exception handling.

> **Status:** these documents specify a system under construction. Each one states at the top which build phase its modules belong to. Where a document describes something not yet built, it says so — see [Repository hygiene](FOREMAN_SPEC.md#12-repository-hygiene).

## Start here

| If you want to | Read |
| --- | --- |
| Understand the whole system | [FOREMAN_SPEC.md](FOREMAN_SPEC.md) |
| Know why it is built this way | [decisions.md](decisions.md) |
| See how a business process becomes an agent | [process-decomposition.md](process-decomposition.md) |
| Know exactly what is installed and why | [tech-stack.md](tech-stack.md) |
| Look up a term | [glossary.md](glossary.md) |

## All documents

### Foundations

| Document | Covers |
| --- | --- |
| [FOREMAN_SPEC.md](FOREMAN_SPEC.md) | The master specification: scope, coverage map, architecture, stack, non-functional requirements, build plan, acceptance criteria |
| [architecture.md](architecture.md) | Layers, structural invariants, run lifecycle, state, failure model, extension points |
| [tech-stack.md](tech-stack.md) | The complete stack: dependency groups, the full `pyproject.toml`, per-layer rationale, model providers, optional services, environment variables, version and licence policy, supply chain, and everything deliberately excluded |
| [decisions.md](decisions.md) | Seventeen architecture decision records, including what was deliberately left out |
| [glossary.md](glossary.md) | Domain and platform vocabulary |

### Design

| Document | Covers |
| --- | --- |
| [process-decomposition.md](process-decomposition.md) | SME elicitation, decision tables, the automation boundary, agent specifications, KPI binding, change management |
| [agent-architecture.md](agent-architecture.md) | Generative vs agentic, the runtime protocol, the loop, stopping conditions, tool design, agent patterns, orchestration patterns, single vs multi-agent, durable HITL |
| [memory.md](memory.md) | Context window, working state, retrieved and episodic memory; compaction; failure modes |
| [models.md](models.md) | LLM and SLM, local and frontier, routing, structured output, cost control, caching, prompt management, model governance |

### Capabilities

| Document | Covers |
| --- | --- |
| [mcp.md](mcp.md) | Full MCP surface: base protocol, lifecycle, server and client features, utilities, transports, OAuth 2.1 authorization, threat model |
| [integration.md](integration.md) | Four enterprise connectors, four auth patterns, per-field source of truth, schema mapping, write safety, resilience |
| [retrieval.md](retrieval.md) | Ingestion, chunking, hybrid retrieval, permission-aware retrieval, grounded generation, GraphRAG, evaluation |
| [security.md](security.md) | Threat model, three guardrail layers, prompt injection, authentication, RBAC, multi-tenancy, secrets, privacy, governance |

### Operations

| Document | Covers |
| --- | --- |
| [observability.md](observability.md) | Trace schema, OpenTelemetry and Langfuse, the DuckDB warehouse, metrics, silent errors, analytics, performance, alerting |
| [evaluation.md](evaluation.md) | The five-layer evaluation stack, golden traces, calibrated judges, component metrics, shadow mode, drift, CI gating |
| [scalability.md](scalability.md) | Sync and async, concurrency control, rate limiting, backpressure, long-running work, caching, scaling out, load testing |
| [operations.md](operations.md) | Local development, uv, configuration, containers, CI/CD, environments, release, sustaining engineering |
| [runbook.md](runbook.md) | Severity levels, diagnostics, eight incident procedures, kill switches, recovery, post-incident |

## Conventions

- **Module paths are package-relative.** Foreman uses a `src/` layout, so `rules/engine.py` means `src/foreman/rules/engine.py` and imports read `from foreman.rules import engine`. See [FOREMAN_SPEC.md §9](FOREMAN_SPEC.md#9-repository-layout).
- **Phase markers.** Every document states which build phase its subject belongs to. Phases are dependency order, not a schedule; see [FOREMAN_SPEC.md](FOREMAN_SPEC.md) §10.
- **Claims match code.** A document describing something unbuilt says so in its status line.
- **Decisions live in one place.** Rationale belongs in [decisions.md](decisions.md); other documents link to it rather than re-arguing.
- **Documentation is versioned with the code it describes.** A change to a module updates its document in the same commit.

## Repository documents

| Document | Purpose |
| --- | --- |
| [../README.md](../README.md) | Project overview and current status |
| [../TODO.md](../TODO.md) | Phase checklists |
| [../CHANGELOG.md](../CHANGELOG.md) | Release history |
| [../VERSIONING.md](../VERSIONING.md) | Version scheme and release process |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | How to contribute |
| [../SECURITY.md](../SECURITY.md) | Vulnerability reporting |
| [../AGENT.md](../AGENT.md) | Guidance for AI coding agents |
