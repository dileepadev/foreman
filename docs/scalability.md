# Concurrency and Scalability

> Status: specification. Concurrency primitives are Phase 1; rate limits, quotas and caching are Phase 5–6.

Sync versus async, where concurrency is bounded and why, and what would have to change for this to serve real load. The targets here describe a laptop and a small container, honestly labelled — this is a reference implementation, not a capacity claim.

## Table of contents

1. [Sync and async](#1-sync-and-async)
2. [The async rules](#2-the-async-rules)
3. [Concurrency control](#3-concurrency-control)
4. [Rate limiting](#4-rate-limiting)
5. [Backpressure](#5-backpressure)
6. [Long-running work](#6-long-running-work)
7. [Caching](#7-caching)
8. [Scaling out](#8-scaling-out)
9. [Load testing](#9-load-testing)

---

## 1. Sync and async

Foreman is **async at its core with a synchronous facade**, and the choice is dictated by the workload.

An agent run is almost entirely waiting: waiting for a model, waiting for a connector, waiting for a retrieval. CPU time is negligible. That is the exact profile async I/O exists for — one process can hold hundreds of in-flight runs, because at any moment nearly all of them are blocked on something external.

| | **Async** | **Sync** |
| --- | --- | --- |
| Used for | Everything I/O-bound: connectors, providers, the API, the agent loop | CLI, scripts, notebooks, tests that need no concurrency |
| Mechanism | `asyncio`, `httpx.AsyncClient`, `async def` throughout | Thin `asyncio.run()` wrappers over the async API |
| Cost | Every caller must be async; one blocking call stalls everything | Serial |

### The facade

```python
# async core
async def run_confirmation(request: RunRequest) -> RunResult: ...

# sync facade — one line, for the CLI and scripts
def run_confirmation_sync(request: RunRequest) -> RunResult:
    return asyncio.run(run_confirmation(request))
```

The facade wraps the async core, never the reverse. Writing sync code and wrapping it in threads to fake async gives you the complexity of both models and the benefits of neither.

### Where sync is genuinely correct

| Work | Why sync |
| --- | --- |
| The rules engine | Pure computation, microseconds, no I/O |
| Schema validation | Same |
| Idempotency key derivation | Same |
| Local embedding of one chunk | CPU-bound — belongs in a thread, not in the loop |

The deterministic core is entirely synchronous, and that is a feature. It makes it trivially testable and impossible to accidentally make slow.

---

## 2. The async rules

Four rules, each of which exists because breaking it produces a bug that is hard to diagnose.

**1. Never block the event loop.** A synchronous HTTP call, a `time.sleep`, or a large CPU operation inside a coroutine stalls **every** concurrent run in the process. The symptom is baffling: unrelated requests time out and the profiler shows nothing wrong. CPU-bound work goes to a thread:

```python
result = await asyncio.to_thread(embed_batch, chunks)
```

**2. Every await has a timeout.** An `await` with no timeout is an unbounded wait, and a connector that hangs rather than failing will exhaust the concurrency limit and take the process with it. Timeouts are set per operation, not globally.

**3. Cancellation is cooperative and must be handled.** When a run is cancelled, in-flight work receives `CancelledError`. Cleanup goes in `finally`; `CancelledError` is never swallowed. A cancelled run that leaves a half-written state is worse than one that completed.

**4. Shared mutable state needs a lock, even in a single-threaded loop.** Async does not remove race conditions; it changes where they happen. Any `await` inside a read-modify-write sequence is a yield point where another task can interleave. The single-flight token refresh in [integration.md](integration.md) §3.4 is exactly this bug, solved.

---

## 3. Concurrency control

Limits at four levels, each protecting something different.

| Level | Limit | Protects |
| --- | --- | --- |
| Per run | Parallel line items | Connector rate limits |
| Per connector | Global in-flight calls | The downstream system |
| Per tenant | Concurrent runs | Fair sharing |
| Per process | Total concurrent runs | Memory and the event loop |

### Bounded gather with isolation

```python
results = await bounded_gather(
    *(process(line) for line in order.lines),
    limit=5,
    return_exceptions=True,
    timeout=30,
)
```

Two guarantees:

- **Never more than `limit` concurrent.** A 50-line order does not open 50 connections.
- **Per-item isolation.** One failure does not fail the batch. Results come back as values or exceptions, per item, and the caller decides.

Isolation is what turns "the run crashed" into "four lines confirmed, one escalated". That distinction is the difference between a system people trust and one they turn off.

### Choosing limits

Not guesses. Derived from the downstream system's published rate limit, its observed p95 latency, and Little's Law:

```text
   concurrency  ≈  target_throughput × p95_latency
```

A connector allowing 10 requests/second with a p95 of 200ms supports about 2 in flight sustainably. Setting the limit to 20 does not make it faster; it makes it return 429s.

---

## 4. Rate limiting

Two directions, both required.

### Inbound — protecting Foreman

| Limit | Scope | Response |
| --- | --- | --- |
| Requests per minute | Per API key | 429 with `Retry-After` |
| Concurrent runs | Per tenant | 429 |
| Tokens per day | Per tenant | 402 |
| Cost per day | Per tenant | 402 |

Token-bucket, so bursts are absorbed while the sustained rate holds. State is in-process by default and in Redis when running multiple replicas — a per-replica limiter with four replicas is a limit four times higher than the one you configured.

### Outbound — respecting others

| Mechanism | Detail |
| --- | --- |
| Client-side limiter per connector | Configured below the published limit, so 429s are rare rather than routine |
| `Retry-After` honoured | Always wins over the computed backoff |
| Adaptive throttling | Sustained 429s reduce the local limit; success restores it |
| Circuit breaker | Repeated failure opens the breaker and withdraws the tools |

Treating 429 as a normal part of the control loop rather than an error is what separates a well-behaved client from one that gets its API key revoked.

---

## 5. Backpressure

When demand exceeds capacity, something must give. The only real choice is what.

| Strategy | Effect | Used |
| --- | --- | --- |
| **Queue** | Absorbs bursts | Yes, bounded |
| **Reject** | Fast failure with a clear signal | Yes, at the queue's limit |
| **Degrade** | Smaller model, skip re-ranking, cached retrieval | Yes, under budget pressure |
| Drop silently | Data loss | **Never** |
| Unbounded queue | Memory exhaustion, then everything fails at once | **Never** |

**A queue with no size limit does not fix overload. It only delays the crash.**

Here is what happens. Requests pile up. They get slower. In the end they all time out. By then the queue is full of work nobody is waiting for. Everything fails at the same moment, and nothing tells you why.

So give the queue a limit. When it is full, refuse new work and say so. The caller finds out straight away and can try again later.

Rejection carries a `Retry-After` derived from the actual queue drain rate, so a client's retry has some chance of succeeding.

---

## 6. Long-running work

An agent run takes seconds; an escalation waits days. A run interrupted for human review may outlive the process. So the request cannot own the work.

| Pattern | Use | Client sees |
| --- | --- | --- |
| **Synchronous** | Fast, bounded reads | Result in the response |
| **SSE stream** | Interactive runs | Events as they happen |
| **Task handle** | Bulk operations | `202` + a task ID to poll |
| **Webhook** | Fire-and-forget | Signed callback on completion |
| **Durable interrupt** | Human review | Run persists; resumes on decision |

The last two are why durability is a design constraint rather than an optimisation. See [agent-architecture.md](agent-architecture.md) §9, and MCP's task support in [mcp.md](mcp.md) §6.

### SSE specifics

- Heartbeat every 15s, or proxies close the connection.
- Every event carries a sequence number, so a reconnect can resume.
- The run continues if the client disconnects; the stream is a view of the work, not the work.

---

## 7. Caching

| Layer | Key | TTL | Notes |
| --- | --- | --- | --- |
| Connector reads | System + resource + params + tenant | 60s | Short — a stale PO is a wrong decision |
| Tolerance policy | Version | Until change | Read every run, changes rarely |
| Embeddings | Content hash | Permanent | Deterministic per model; re-embed on model change |
| Retrieval results | Query + filters + corpus version | 5min | Invalidated by re-index |
| LLM exact | Messages + model + params | 1h | Highest-value layer |
| LLM semantic | Embedding similarity | 1h | **Off by default** — see below |
| Provider prompt cache | Stable prefix | Provider-managed | Free; needs prefix stability |

Every key includes the tenant. A cache key without a tenant is a cross-tenant leak waiting for a collision.

### Semantic caching is dangerous here

Two questions that embed similarly can have different correct answers. "What is the tolerance for PO-9931?" and "What is the tolerance for PO-9933?" are 0.98 similar and have different answers.

Semantic caching is therefore **disabled for anything feeding a write**, enabled only for read-only explanatory queries, with a high threshold, and every hit is marked in the trace. A cache hit that returns another order's answer is a silent error, which is the failure class this system exists to eliminate.

---

## 8. Scaling out

What would change for real load. Stated as an analysis, because the reference deployment is a single container and pretending otherwise would be dishonest.

### Already stateless

The API layer holds no run state between requests. Runs live in the run store, checkpoints in the checkpointer. Horizontal scaling of the API is a replica count.

### What would need to change

| Component | Now | At scale | Why |
| --- | --- | --- | --- |
| Run store | SQLite | Postgres | Concurrent writers |
| Checkpointer | In-process / SQLite | Postgres or Redis | Any replica must resume any run |
| Rate limiter | In-process | Redis | Per-replica limits multiply |
| Queue | `asyncio` queue | Redis or SQS | Survive a restart |
| Vector index | numpy in-memory | pgvector or a vector DB | Memory ceiling and index build time |
| Graph | In-memory | Neo4j | Traversal cost |
| Traces | JSONL on disk | OTel collector → backend | Volume, retention |
| Warehouse | Local DuckDB | DuckDB over object storage | Data volume |

Each has an interface in place ([architecture.md](architecture.md) §8), so these are configuration swaps rather than rewrites. That is the actual claim being made — not that it scales, but that the seams are in the right places.

### The real bottleneck

Not the API and not the database. It is **inference throughput and connector rate limits**, and neither is fixed by adding replicas. Scaling this system means routing more work to smaller models, caching harder, and negotiating higher limits with the systems of record.

The second bottleneck is human: the review queue. An automation rate of 85% at 10,000 confirmations a day is 1,500 escalations for humans to process. If escalation precision is poor, that queue becomes the constraint and people start approving without reading — which converts a precision problem into a silent-error problem.

---

## 9. Load testing

`scripts/load_test.py` drives the mock provider so runs are free and deterministic.

| Scenario | Measures |
| --- | --- |
| Sustained 20 concurrent runs | Steady-state p50/p95/p99, memory stability |
| Burst 100 runs | Queue behaviour, rejection correctness, recovery |
| Connector at its rate limit | Throttling, 429 handling, no duplicate writes |
| Connector returning 503 | Circuit breaker opens and recovers |
| Slow connector, 5s p95 | Concurrency limits hold; no event-loop starvation |
| Sustained load for 1 hour | Memory leaks, file handles, connection pool exhaustion |

### Targets

| Metric | Target |
| --- | --- |
| 20 concurrent runs | No p95 degradation vs. serial |
| Throughput, mock provider | ≥ 10 runs/second |
| Memory, 20 concurrent | < 500MB |
| Recovery after burst | Queue drains, no lost runs |
| Duplicate writes under any fault | **0** |

The last row is the one worth running the whole suite for. Everything else is performance; that one is correctness under concurrency, and it is the property that idempotency exists to guarantee.
