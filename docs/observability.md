# Observability

> Status: specification. Tracing, warehouse and metrics are Phase 4.

You cannot debug what you cannot see, and you cannot improve what you do not measure. In an agentic system this is more acute than usual: the failure is rarely a stack trace. It is a plausible answer that happens to be wrong.

## Table of contents

1. [Why agent observability is different](#1-why-agent-observability-is-different)
2. [The trace](#2-the-trace)
3. [OpenTelemetry and Langfuse](#3-opentelemetry-and-langfuse)
4. [The warehouse](#4-the-warehouse)
5. [Metrics](#5-metrics)
6. [Silent errors](#6-silent-errors)
7. [Analytics](#7-analytics)
8. [Performance](#8-performance)
9. [Alerting](#9-alerting)

---

## 1. Why agent observability is different

| Traditional service | Agent system |
| --- | --- |
| Failures raise | Failures return a confident answer |
| A request has one path | A run has a path the model chose |
| Latency is the performance metric | Latency, tokens **and cost** |
| Logs explain what happened | Logs must explain **why** a decision was made |
| Success is a 200 | Success is a correct decision, which may be unknowable at the time |

The consequence: a trace has to capture **reasoning and decision provenance**, not just calls and timings. "Escalated" is not an observation. "Escalated because `PRICE_TOL_003` fired at 4.2% variance on a £8,000 line, having retrieved clause 7.2 of contract C-4471" is.

---

## 2. The trace

Append-only, one per run, capturing every step.

```python
class Span(BaseModel):
    run_id: str
    span_id: str
    parent_span_id: str | None
    kind: SpanKind          # AGENT_STEP | TOOL_CALL | LLM_CALL | RULE_EVAL | RETRIEVAL | GUARDRAIL
    name: str
    started_at: datetime
    duration_ms: int
    status: Literal["ok", "error"]
    attributes: dict[str, Any]
    tenant_id: str
    trace_schema_version: str
```

Per-kind attributes:

| Kind | Attributes |
| --- | --- |
| `AGENT_STEP` | Step index, reasoning summary, chosen tool, stop evaluation |
| `LLM_CALL` | Model, tier, prompt version, input/output/cached tokens, cost, latency, temperature |
| `TOOL_CALL` | Tool, arguments (masked), result summary, `mutates`, idempotency key, authorisation outcome |
| `RULE_EVAL` | Rule ID, version, inputs, outcome — **the provenance of the decision** |
| `RETRIEVAL` | Query, strategy, candidate count, returned IDs, ACL filter applied |
| `GUARDRAIL` | Guardrail name, verdict, reason |

### The schema is a contract

Three consumers depend on it: the review UI, the warehouse, and the evaluation suite (golden traces are recorded runs replayed as assertions). Because of the third, **a breaking change to the trace schema is a breaking change to the product** — it is versioned, and migrations are written.

### Local first

The default sink is append-only JSONL on disk. No service, no key, no network. `foreman trace <run-id>` renders it as a readable tree:

```text
run 8f2a  order_confirmation  ·  ESCALATED  ·  4.1s  ·  $0.004  ·  6 steps

├─ step 0  assemble_context                              120ms
│  ├─ tool  get_purchase_order        PO-9931             40ms   read
│  └─ tool  get_supplier              SUP-114             35ms   read
├─ step 1  extract_confirmation                          1.8s
│  └─ llm   local/qwen2.5:7b          in 2.1k out 340    $0.000
│     └─ 3 lines, confidence [0.96, 0.91, 0.62]
├─ step 2  reconcile                    (deterministic)    2ms
│  └─ rule  PRICE_TOL_003 v3           4.2% > 3.0%       FIRED
├─ step 3  retrieve_contract_terms                        310ms
│  └─ 4 chunks, ACL filtered 12 → 7, cited C-4471 §7.2
├─ step 4  draft_escalation                              1.7s
│  └─ llm   hosted/frontier            in 3.4k out 210   $0.004
└─ step 5  escalate_to_buyer                              90ms   write
   └─ authz  role=agent  value=£8,240  band=5,000  → HUMAN_REQUIRED
```

An unreadable trace is just a log file. The renderer is not a nice-to-have; it is what makes the trace usable during development, which is when most of its value is realised.

---

## 3. OpenTelemetry and Langfuse

Spans are emitted in OpenTelemetry shape, so any OTel-compatible backend works and no vendor is load-bearing.

**Langfuse** is the default backend when configured, because it understands LLM-specific concepts natively — generations with token counts and cost, prompt versions, scores attached to traces, and datasets for offline experiments. Self-hosted via `docker compose`, so the zero-budget constraint holds.

| Foreman concept | OTel | Langfuse |
| --- | --- | --- |
| Run | Trace | Trace |
| Agent step | Span | Span |
| Model call | Span with `gen_ai.*` attributes | Generation |
| Tool call | Span | Span |
| Evaluation result | — | Score |
| Golden scenario set | — | Dataset |

Langfuse's Python SDK is OpenTelemetry-based, so instrumentation is a sink configuration rather than a parallel code path. The JSONL sink remains active alongside it — **a dropped trace is never acceptable**, and an observability backend being down must never lose the record of a decision.

---

## 4. The warehouse

Traces answer "what happened in this run". Analytics answers "what is happening across runs". Those are different queries and different stores.

DuckDB over Parquet, in a medallion layout, because it needs no server and reads Parquet directly.

| Layer | Content | Grain |
| --- | --- | --- |
| **Bronze** | Raw spans as ingested | One row per span |
| **Silver** | Conformed runs — joined, typed, deduplicated | One row per run, one per tool call, one per decision |
| **Gold** | Aggregated KPIs | Per day × tenant × scenario × model |

Why this and not "just query the JSONL": bronze is immutable and reprocessable, silver absorbs schema evolution, and gold is what dashboards and CI read. When the trace schema changes, silver's transformation is updated and bronze is reprocessed — the history is not lost and not rewritten.

Gold tables are also what the CI evaluation gate reads, so "did this PR make things worse" is a SQL query against the same numbers the dashboard shows.

---

## 5. Metrics

### Outcome

| Metric | Definition | Target |
| --- | --- | --- |
| `auto_resolution_rate` | Runs completed with no human | Up, subject to precision |
| `escalation_rate` | Runs routed to a human | Context-dependent |
| `escalation_precision` | Escalations a human agreed with | ≥ 0.90 |
| `escalation_recall` | Cases needing a human that got one | ≥ 0.99 |
| `silent_error_rate` | Wrong completions not flagged | **0** |
| `block_rate` | Runs unable to proceed | Down |

### Behaviour

| Metric | Why it is watched |
| --- | --- |
| `steps_per_run` (p50, p95) | A rising p95 means the agent is wandering |
| `tool_failure_rate` by tool | Isolates a bad connector from a bad agent |
| `tool_retry_rate` | Rising retries precede an outage |
| `cycle_detection_rate` | Should be near zero; a rise means a prompt or tool regression |
| `stop_reason` distribution | `MAX_STEPS` climbing is a warning, not a statistic |
| `guardrail_trigger_rate` by guardrail | A spike in injection flags is a security signal |

### Cost and performance

| Metric | Target |
| --- | --- |
| `cost_per_run` (mean, p95) | < $0.02 mean |
| `tokens_per_run` | Tracked; input/output/cached split |
| `cache_hit_rate` | Reported per layer |
| `model_tier_mix` | ~80% SMALL |
| `run_latency` (p50, p95, p99) | p95 < 2s mock, < 30s local |
| `time_to_first_event` | < 500ms — perceived responsiveness on SSE |
| `queue_depth`, `review_queue_age` | Rising review age means the humans are the bottleneck |

### Paired reporting

`auto_resolution_rate` and `silent_error_rate` are always reported together, because they move in opposite directions and either alone is misleading. Loosening thresholds always raises automation and always raises silent errors. The dashboard shows them side by side and the CI gate checks both.

---

## 6. Silent errors

The metric the whole system is organised around.

**Definition:** a run that completed without escalating, whose decision was wrong.

Why it dominates: an over-escalation costs a buyer two minutes and is visible, measurable and tunable. A silent wrong confirmation enters the ledger, is discovered at reconciliation weeks later, and destroys confidence in the system permanently. They are not symmetric and must not be traded off as if they were.

### Detection

| Source | Latency | Coverage |
| --- | --- | --- |
| Golden suite | Immediate | Known scenarios only |
| Groundedness checking | Immediate | Ungrounded claims |
| Rule/model disagreement | Immediate | Where both produce a verdict |
| Shadow mode against human decisions | Days | Broad, pre-deployment |
| Downstream reconciliation feedback | Weeks | The ground truth |
| Human spot audit of auto-resolved runs | Sampled | The honest check |

The spot audit matters most. A sample of auto-resolved runs is reviewed by a human who does not see the agent's reasoning first. Without it, silent errors are by definition invisible — that is what makes them silent. Any system reporting a silent-error rate without a sampling mechanism is reporting the rate of errors it already knew about.

---

## 7. Analytics

Questions the gold tables are built to answer:

| Question | Serves |
| --- | --- |
| Which scenario has the worst automation rate? | Where to improve next |
| Which tool fails most, and against which connector? | Integration triage |
| What does a run cost by scenario and tier mix? | Cost optimisation |
| Which rules fire most, and which never fire? | Dead policy detection |
| How long do escalations wait? | Whether the review queue is staffed |
| Which prompt version has the best pass rate? | Prompt selection |
| Is auto-resolution improving without silent errors rising? | The only question that matters overall |

"Which rules never fire" is quietly one of the most valuable. A rule that has not fired in six months is either dead policy or a bug in its condition, and both are worth knowing.

---

## 8. Performance

### Latency budget, mock provider

| Segment | Budget |
| --- | --- |
| Auth, admission, rate check | 10ms |
| Context assembly (cached connectors) | 100ms |
| Extraction | 200ms |
| Reconcile + rules | 5ms |
| Retrieval, when invoked | 200ms |
| Write | 50ms |
| Trace and record | 20ms |

Deterministic work is a rounding error. **Latency is inference and network, which is why routing to smaller models improves latency and cost together.**

### Profiling

| Question | Method |
| --- | --- |
| Where does wall-clock go? | Span durations from the trace |
| Which calls could be parallel? | Dependency analysis of the span tree |
| Where is the p99 coming from? | Percentile breakdown per span kind |
| Is retrieval or generation slow? | Separate spans, always |

Because the trace already carries per-span durations, performance analysis is a warehouse query rather than a separate profiling exercise.

---

## 9. Alerting

Alert on **rate of change and on business outcomes**, not on individual events. A single failed tool call is not an incident; a tool failure rate tripling in an hour is.

| Alert | Condition | Severity |
| --- | --- | --- |
| Silent error detected | Any confirmed instance | **Critical** |
| Unauthorised write attempt | Any | **Critical** |
| Budget kill switch tripped | Any | High |
| Escalation precision drop | > 10% below baseline over 24h | High |
| Tool failure rate spike | 3× baseline over 1h | High |
| Cycle detection rate rise | > 1% of runs | Medium |
| Review queue age | Oldest item > SLA | Medium |
| Cost per run rise | > 50% above baseline | Medium |
| Drift detected | See [evaluation.md](evaluation.md) | Medium |

Responses for each: [runbook.md](runbook.md).
