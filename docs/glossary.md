# Glossary

Domain and platform vocabulary, so the documents and the code use words the same way. Where a term is contested in the wider field, the definition here is the one this project uses.

## Domain

| Term | Definition |
| --- | --- |
| **Purchase order (PO)** | A buyer's commitment to purchase specific items at specific terms. The reference against which everything else is compared. |
| **Order line** | One item on a purchase order: SKU, quantity, unit price, promised date. The unit of decision in this system. |
| **Supplier confirmation** | The supplier's response to a PO, which may differ from it. Arrives as a PDF, an email body, a portal record or an EDI-shaped payload. |
| **Goods receipt** | A record that items physically arrived, with quantities. |
| **Three-way match** | Comparing purchase order, goods receipt and invoice. The classic accounts-payable control. |
| **Tolerance band** | The variance range within which a difference is acceptable without human approval. |
| **Variance** | The difference between ordered and confirmed values, on price, quantity or date. |
| **ASN** | Advance shipping notice — the supplier's declaration of what is being shipped and when. |
| **Procure-to-pay** | The end-to-end process from requisition through payment. Foreman automates the exception-handling part. |
| **SME** | Subject-matter expert. The person who knows the process, whose knowledge is the actual specification. |
| **Escalation** | Routing a decision to a human, with enough context to decide quickly. |
| **Touchless processing** | A transaction completed with no human involvement. The headline business metric. |

## Agent platform

| Term | Definition |
| --- | --- |
| **Agent** | A system where a model's output selects the next action, in a loop, with side effects. Distinct from a single generative call. |
| **Agent loop** | Perceive → reason → act → observe, repeated until a stopping condition fires. |
| **Stopping condition** | A rule that halts the loop: terminal signal, step ceiling, token ceiling, or cycle detection. All four are mandatory. |
| **Runtime** | An implementation of the agent execution engine. Foreman has two behind one protocol. |
| **Conformance suite** | Tests every runtime must pass identically, which is what makes two runtimes a design decision rather than two behaviours. |
| **Tool** | A function the model may call. Declared with a schema, a `mutates` flag and a required scope. |
| **Tool registry** | The catalogue of available tools, tracking reads and writes separately. |
| **Action signature** | Tool name plus canonically sorted arguments, hashed. Used for cycle detection. |
| **Working state** | Typed facts the run has established, held outside the context window and checkpointed. |
| **Context window** | What the model sees this step. A projection rebuilt each step, never an accumulator. |
| **Episodic memory** | Summarised history of past runs for the same entity. Informs; never decides. |
| **Compaction** | Reducing a context segment that exceeds its budget: projection, summary, or eviction. |
| **Checkpoint** | A serialised run state that survives process restart. |
| **Interrupt** | A pause for human input, with the run persisted and resumable. |
| **Hand-off** | Transfer of work between agents, always as a typed object, never free text. |
| **Supervisor** | An agent that decomposes work and delegates to workers with narrower permissions. |

## Retrieval

| Term | Definition |
| --- | --- |
| **RAG** | Retrieval-augmented generation: fetch relevant content, then generate grounded in it. |
| **GraphRAG** | Retrieval over an entity graph, for questions where relationships carry the meaning. |
| **Chunk** | A retrievable unit of a document, carrying the parent's full metadata including its ACL. |
| **Dense retrieval** | Embedding similarity. Strong on paraphrase, weak on identifiers. |
| **Sparse retrieval / BM25** | Term-frequency ranking. Strong on exact tokens, weak on vocabulary mismatch. |
| **Hybrid retrieval** | Both, fused. Necessary because each fails where the other succeeds. |
| **RRF** | Reciprocal Rank Fusion — combines rankings by position, avoiding incomparable score scales. |
| **Re-ranking** | A cross-encoder pass over candidates. Higher precision, one model call per candidate. |
| **ACL pre-filter** | Applying permissions before scoring, so the caller's world contains only what they may see. |
| **Grounded generation** | Every claim traceable to a cited source. |
| **Groundedness** | The measured proportion of claims actually supported by their citations. |
| **Multi-hop** | A question requiring traversal across several relationships. |

## Models

| Term | Definition |
| --- | --- |
| **LLM** | Large language model. Used here for judgement, ambiguity and human-facing output. |
| **SLM** | Small language model, roughly 1–8B. Used for classification, extraction and routing — about 80% of calls. |
| **Frontier model** | A large hosted model accessed by API. |
| **Local model** | A model running on the developer's machine, typically via Ollama. Zero marginal cost, total privacy. |
| **Provider** | An implementation of the inference interface: mock, local Ollama, or a hosted vendor. |
| **Provider capabilities** | What a provider actually supports — tools, structured output, streaming, prompt caching, cost reporting. Declared, so the router never dispatches a step a provider cannot serve. |
| **OpenAI-compatible** | Speaks `POST /v1/chat/completions`. True of OpenAI, Groq, OpenRouter and Ollama, so one adapter covers all four. |
| **Provider chain** | The ordered list of providers a tier resolves to. Tried in order; unconfigured, broken, incapable or over-budget providers are skipped. |
| **Fallback** | Moving to the *next provider* in the chain. Distinct from a retry, which re-attempts the same one. |
| **Reported vs computed cost** | Some providers return spend in the response; for the rest it is computed from a versioned price table. |
| **Per-key spend cap** | A hard limit set at the vendor on an API key. The only budget ceiling that does not depend on Foreman being correct. |
| **Routing** | Deterministic per-step selection of a model tier. The largest single cost lever. |
| **Tier** | `MOCK`, `SMALL` or `LARGE`. |
| **Structured output** | Model output constrained to a schema and validated before use. |
| **Repair loop** | Feeding a validation error back to the model to correct its output. Bounded at two attempts. |
| **Extraction confidence** | Per-field confidence in an extracted value, used to gate escalation. |
| **Prompt version** | An immutable prompt with a recorded golden-suite pass rate. Never edited in place. |
| **Canary prompt** | A fixed prompt with a known-stable answer, run daily to detect a silently changed model. |

## Protocol

| Term | Definition |
| --- | --- |
| **MCP** | Model Context Protocol — a standard interface between agents and the systems they act on. |
| **JSON-RPC 2.0** | The message format MCP uses. Requests carry an `id`; notifications do not and must not be answered. |
| **Capability negotiation** | Each side declares what it supports at initialise; neither may use what the other did not declare. |
| **Resource** | Application-controlled read-only context, addressed by URI. Reads must have no side effects. |
| **Prompt (MCP)** | A user-invoked template with typed arguments. |
| **Sampling** | A server asking the client for a model completion, so the server needs no API key. |
| **Roots** | Client-declared URI boundaries constraining where a server may operate. |
| **Elicitation** | A server asking the user for information mid-operation, in `form` or `url` mode. Never for credentials. |
| **Task** | A long-running operation with a handle, pollable and cancellable, outliving its request. |
| **stdio transport** | Subprocess over stdin/stdout. Nothing but protocol messages on stdout, ever. |
| **Streamable HTTP** | HTTP transport with optional SSE, sessions and OAuth 2.1. |
| **Protected Resource Metadata** | The discovery document telling a client which authorization server to use. Required. |
| **Token passthrough** | Forwarding a caller's token downstream. Forbidden — it is the confused-deputy pattern. |

## Security and governance

| Term | Definition |
| --- | --- |
| **Guardrail** | A check at the input, output or action layer. Action guardrails never consult the model. |
| **Prompt injection** | Instructions embedded in content the model reads. Direct (from the user) or indirect (from a document). |
| **Tool poisoning** | Malicious instructions hidden in a tool's description. |
| **Rug pull** | A server changing a tool's behaviour after it was approved. |
| **Confused deputy** | A privileged component tricked into using its authority for someone who lacks it. |
| **Untrusted-content delimiting** | Wrapping external content in randomised boundary tags and labelling it as data. |
| **RBAC** | Role-based access control. Enforced at dispatch, never in a prompt. |
| **Scope** | A named permission a tool requires and a principal may hold. |
| **Write ceiling** | A hard monetary cap on what a run may write. Not overridable in-band. |
| **Escalation band** | A soft threshold routing an action to a human, below the hard ceiling. |
| **Principal** | The authenticated identity making a request: tenant, role and scopes. |
| **Service account** | A named non-human identity with its own permissions, distinct from any user's. |
| **Single-flight refresh** | Ensuring concurrent token expiry triggers exactly one refresh. |
| **Idempotency key** | A deterministic hash of the business payload, making a write exactly-once. |
| **Hash-chained audit** | An append-only log where each entry's hash covers its predecessor, making tampering detectable. |

## Observability and evaluation

| Term | Definition |
| --- | --- |
| **Trace** | The append-only record of everything a run did, including why. Three consumers depend on its schema. |
| **Span** | One unit within a trace: a step, tool call, model call, rule evaluation, retrieval or guardrail check. |
| **Golden trace** | A recorded run replayed as property assertions. |
| **Property assertion** | An assertion about a trajectory rather than an exact output — "never called `confirm_order_line`". |
| **Silent error** | A run that completed without escalating and was wrong. The metric the system is organised around. |
| **Escalation precision** | The proportion of escalations a human agreed with. Low precision trains reviewers to rubber-stamp. |
| **LLM-as-judge** | Using a model to score qualities that cannot be asserted. Advisory until calibrated. |
| **Calibration** | Measuring judge–human agreement, reported as Cohen's κ per dimension. |
| **Shadow mode** | Running against real inputs with writes suppressed, diffing against human decisions. |
| **Drift** | Degradation over time with no code change — input mix, model version, or supplier document formats. |
| **PSI** | Population Stability Index, for detecting input distribution drift. |
| **Medallion** | Bronze (raw) → silver (conformed) → gold (aggregated) warehouse layering. |
| **Evaluation gate** | A CI check that blocks a merge on golden-suite, cost or latency regression. |

## Concurrency

| Term | Definition |
| --- | --- |
| **Bounded gather** | Concurrent execution with a hard limit and per-item failure isolation. |
| **Per-item isolation** | One failed item yields a partial result rather than a failed batch. |
| **Backpressure** | Signalling that demand exceeds capacity. A bounded queue plus rejection — never an unbounded queue. |
| **Circuit breaker** | Failing fast after repeated failures, with a probe before closing. Also withdraws the connector's tools. |
| **Token bucket** | A rate limiter absorbing bursts while holding a sustained rate. |
| **Little's Law** | `concurrency ≈ throughput × latency`. Used to derive concurrency limits rather than guess them. |
| **Degradation ladder** | The defined fallback for each optional dependency, each one tested. |
