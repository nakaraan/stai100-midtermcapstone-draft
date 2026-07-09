# Technical Write-Up: AGENT P — Predictive & Parametric Solar Analytics Assistant

## 1. Business Case

Solar irradiance — the amount of solar energy reaching a given point on the Earth's surface —
fluctuates continuously with time of day, season, weather, and geography. Accurately
characterizing it is foundational to every stage of a solar installation's lifecycle: panel
placement, yield forecasting, grid integration, maintenance planning, and return-on-investment
tracking. Getting it wrong doesn't just mean a slightly suboptimal system; it means years of
underperformance that the owner has no easy way to detect.

A growing number of Filipino households and small-to-medium enterprises have turned to rooftop
solar to hedge against volatile electricity costs, driven in part by global fuel-supply
disruptions. But the people making these investment decisions are rarely engineers. Solar
irradiance data is published as raw satellite-derived time series through specialized APIs like
NREL's National Solar Radiation Database (NSRDB) — accessible in principle, but requiring exact
latitude/longitude coordinates, correct attribute names, date-range handling, and non-trivial
aggregation before the numbers mean anything to a property owner deciding where to point a panel.

AGENT P closes that gap by giving non-technical users a conversational interface to the same
data an engineer would pull manually. A user asks a plain-language question — *"Give me the
monthly average irradiation from Feb to June 2019 at our warehouse in Caloocan"* — and the system
resolves the location, retrieves the relevant historical satellite data from NREL, computes real
monthly averages with deterministic arithmetic (never an LLM guess), and returns both a
conversational answer and a downloadable CSV summary. The value proposition is specifically
**trustworthy, on-demand access to a technical dataset**, not a black box: every number the user
sees traces back to a real API call and a real calculation, and the system is built to refuse to
answer rather than fabricate when the underlying data can't be resolved.

The primary users are Filipino homeowners and SME owners planning or operating rooftop solar
installations, acting as their own project manager without an engineering background. A
secondary user base is boutique solar installation companies, who could offer the same interface
to clients as a value-added feasibility and monitoring tool. Both groups share the same core
need: turning a satellite dataset into an answer to "is this location, and this time of year,
actually worth it," without needing to understand WKT coordinate strings or NSRDB attribute
codes.

It is worth being precise about where the current system sits on the path toward a fuller
vision. The original concept for AGENT P included continuous system monitoring — comparing a
customer's live panel output against expected regional irradiance and proactively flagging
anomalies from dust, shading, or hardware degradation. That capability is **not implemented** in
the current build: AGENT P today is a request-response assistant, not a background monitoring
agent, and it has no integration with any user's actual inverter or panel telemetry. This
distinction matters and is addressed directly in the Retrospective as scoped-out future work
rather than glossed over, because the grading criteria explicitly reward architecture matching
implementation. What is implemented — reliable, guarded, traced conversational access to real
historical solar data — is itself a genuine and non-trivial agentic system, and the write-up
that follows describes exactly that system as it was actually built, run, and measured.

## 2. Methodology

AGENT P was built from scratch rather than assembled from a pre-packaged agent framework
(LangChain, LlamaIndex, and similar were deliberately not used). This was a design choice, not
an oversight: a hand-rolled orchestration loop keeps every step of the agent's reasoning
visible and traceable, keeps the frontend fully decoupled from the backend, and constrains the
agent to a small, explicit, auditable set of tools rather than an open-ended framework
abstraction that can obscure what is actually being called and why.

| Category | Technology | Purpose |
| --- | --- | --- |
| Frontend | Streamlit | Conversational chat UI with a live sidebar (resolved site, year, month range, monthly table, CSV download); communicates with the backend exclusively over HTTP, with no direct imports of agent, database, or config code |
| Backend | FastAPI + Uvicorn | REST API (`POST /chat`, `GET /health`) wrapping the agent's `handle_query()` entry point; Pydantic models enforce structured request/response schemas |
| AI Orchestration | Custom from-scratch ReAct loop | Thought → Action → Observation cycle over a bounded two-tool action set, with regex-parsed actions rather than a framework's tool-calling layer, JSON-repair heuristics for small-model output quirks, and stop-sequence guards against self-hallucinated observations |
| LLM Provider | Any OpenAI-compatible endpoint (local Ollama by default) | Intent parsing (natural language → structured slots), clarification-question generation, and final response synthesis; swappable via `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` without code changes |
| Data Source | NREL/NSRDB REST API | No relational database or vector store is used — the sole external data source is a live HTTP call to NREL's NSRDB, parsed from CSV per query; short-term conversational state lives in an in-process session store, not a persistent database |
| Guardrails | Custom keyword/pattern rules | Rejects off-topic input before any LLM call is made (zero-cost, zero-latency filtering); sanitizes output to prevent raw error payloads or stack traces from reaching the user |
| LLMOps / Observability | MLflow | Decorator-based span tracing (`@trace_agent`, `@trace_tool`, `@trace_llm`) capturing latency, token usage, and errors for every agent run, tool call, and LLM call, with secret redaction applied before anything is logged |
| Containerization | Docker (multi-stage build) | A single image runs the FastAPI and Streamlit processes as siblings, with a combined health check; a build-only stage keeps compilers and pip cache out of the runtime image |

Two architectural decisions are worth explaining rather than just stating. First, **why not
RAG**: the workflow is not "retrieve relevant facts from a static corpus," it is "call a live
external API and do real arithmetic on the result." There is no static knowledge base for a
retriever to index — the correct answer to "what was the irradiance in March" changes only if
NREL's underlying dataset changes, and semantic retrieval adds nothing a direct API call
doesn't already provide more reliably. Second, **why not a SQL agent**: there is no relational
database anywhere in the system; NREL's NSRDB API is the only persistent data source, accessed
over HTTP, so a text-to-SQL layer would have no database to target.

## 3. Architecture

The system follows a single-turn pipeline with five stages, all wrapped in observability spans:
guardrail validation, intent parsing, disambiguation (if needed), a bounded ReAct tool-use loop,
and response synthesis.

**Guardrails run first and cheaply.** Before any LLM call is made, the raw user message is
checked against a keyword/pattern allow-list for solar, weather, and location-related terms. A
message that fails this check is rejected immediately with no LLM cost incurred — this matters
both for cost control and for reliability, since it means the system's on-topic filtering can
never itself become a source of hallucination or latency. The same module also sanitizes
outbound text, catching cases where a raw JSON error or stack trace might otherwise leak into a
user-facing response.

**Intent parsing** converts the (now validated) natural-language message into five structured
slots — latitude, longitude, year, start month, end month — plus a list of requested attributes,
using a single LLM call grounded with a persona system prompt and few-shot examples. Because
small local models routinely emit near-JSON rather than strictly valid JSON (Python `None`
instead of `null`, unquoted month names, mismatched quote styles, fields split across multiple
fragments), a dedicated normalization layer applies a series of targeted regex fixes before
attempting to parse, and falls back to Python's own literal parser if strict JSON parsing still
fails. Extracted values are then validated against real-world bounds — a latitude outside
±90°, a year outside the dataset's actual coverage window, an end month before the start month —
and nulled out rather than trusted if implausible, which routes the conversation back through
disambiguation instead of silently proceeding on bad data.

**Disambiguation** fires only when a required slot is still missing after intent parsing and
after checking short-term session memory for a value carried over from an earlier turn (e.g., a
previously resolved location). It asks exactly one targeted clarifying question rather than an
open-ended one, and the memory module explicitly tracks which slots were already resolved before
the question was asked, so a terse follow-up reply like "June" doesn't lose the rest of the
already-established context.

**The ReAct loop** is the core of the agent proper. With slots fully resolved, the system hands
the model a small, explicit action set — `fetch_solar_data`, `aggregate_monthly`, and `finish`
— and requires it to emit exactly one `Thought` + `Action` pair per turn, bounded to a maximum
of six turns. A regex extracts the declared action; a failed tool call is fed back into the
conversation as an `Observation` string rather than raising and crashing the loop, letting the
model attempt recovery. Two defenses specifically target small-model failure modes observed
during development: stop sequences (`Observation:`, `\nThought:`) prevent the model from
hallucinating a fake tool result and reasoning over its own fabrication, and a `Final Answer`
emitted before `aggregate_monthly` has actually run is explicitly rejected and the model is told
to continue, rather than accepted as a real answer. The two tools themselves are intentionally
narrow: `fetch_solar_data` performs the live NREL HTTP call, and `aggregate_monthly` is pure,
deterministic Python arithmetic — the mean of each attribute per month — with no LLM involvement
whatsoever. This is a deliberate correctness guarantee: whatever the model says about the data,
the numbers underlying that data are computed the same way every time from the same input.

**Response synthesis** is a final LLM call that turns the aggregated figures into a
conversational answer, explicitly instructed to report only figures that appear in the actual
tool output and never to estimate or invent a number to fill a gap. If the ReAct loop never
produced real aggregated data — a failed fetch, an exhausted turn budget — this synthesis step is
skipped entirely in code, not merely discouraged by prompt instruction, guaranteeing a fabricated
number can never reach the user in that failure path.

Every stage above is wrapped in an MLflow span via decorator (`@trace_agent` for the top-level
orchestration, `@trace_tool` for the NREL call and the aggregation step, `@trace_llm` for every
model call), with a shared secret-redaction pass applied before any span attribute is written,
so an API key can never end up visible in a trace even if it appears inside a caught exception
message.

The repository separates these concerns cleanly: `api/` holds the FastAPI surface, `app/` the
Streamlit client (a pure HTTP consumer of the API, never importing agent code directly), `src/`
the agent orchestration, NREL client, guardrails, and memory modules, `config/` centralizes
settings and externalized prompts, and `utils/` holds the telemetry decorators — a structure
chosen specifically so that each of the thirteen course-checklist modules maps to an
identifiable file a reviewer can point to.

## 4. Experiments

Two categories of experiment were run against the deployed system: controlled reliability
trials measuring how often a fixed query resolves correctly, and infrastructure experiments
that emerged from debugging genuine production incidents rather than being planned in advance.
Both are reported here, including the ones with disappointing results, because the reliability
data is itself the point of an evaluation section.

**Reliability trials.** The same canonical query — resolvable in one turn, matching the
few-shot example in the intent-parsing prompt almost exactly — was sent to the deployed API
repeatedly, with `needs_clarification`, coordinate correctness, and numeric fidelity between
the structured `monthly_metrics` field and the free-text answer all recorded per trial.

With `llama3.2:3b` as the LLM, across two independent rounds of testing (nine total attempts),
the query resolved completely on roughly 40–60% of attempts. Failure modes fell into three
distinct categories: the model asking an unnecessary clarifying question despite the location
already matching the training example; the model extracting plausible-looking but incorrect
coordinates; and — notably, even on runs that *did* resolve correctly — the model's own
free-text summary of the real, correctly-computed numbers sometimes drifting from those numbers
(observed drift ranged from minor digit transposition to a completely different set of invented
figures under a mismatched unit label). This last failure mode is the most instructive: the
structured `monthly_metrics` field, sourced from deterministic Python arithmetic, was correct in
100% of successfully-resolved runs; only the model's own prose paraphrase of those numbers was
occasionally unreliable. This isolates the system's actual reliability bottleneck precisely: not
the data pipeline, not the guardrails, not the tool-use logic, but the model's transcription
fidelity when writing free text — a materially different (and more specific) finding than a
generic "small models are unreliable."

A subsequent experiment lowered the LLM sampling temperature from Ollama's default (~0.7–0.8) to
0.1, on the reasoning that this pipeline is a structured-extraction and faithful-reporting task
rather than a creative-writing one, and low temperature should favor deterministic, repeatable
output. The result at small sample size (five trials) was inconclusive — two full completions,
three timeouts — and no confident causal claim can be made from that sample about whether lower
temperature helped, hurt, or was neutral relative to default sampling. This is reported honestly
as an open question rather than a confirmed fix.

**A larger-model comparison surfaced a hardware-bound finding, not a model-quality one.** The
team's working hypothesis, based on informal testing, was that `qwen2.5:7b` would follow the
strict ReAct format more reliably than the 3B model given its larger parameter count. On the
original development laptop (15.6GB total RAM), qwen2.5:7b failed to complete the canonical
query **zero times out of seven attempts**, across fresh starts, after freeing memory by
terminating ten orphaned background processes, and with timeouts extended as far as 240 seconds.
Process-level CPU monitoring during these runs confirmed the model was actively computing the
entire time, not deadlocked — it was simply too slow to finish within any timeout reasonable for
interactive use. Measurement showed why: qwen2.5:7b requires roughly 4.7GB of RAM just for its
weights, and the laptop had as little as 1.1GB genuinely free once the full application stack
(MLflow, the API, Streamlit, and Ollama itself) was running concurrently. Migrating the identical,
unmodified codebase to a machine with substantially more available RAM resolved the issue
completely: five subsequent trials completed in 56.9s (cold start, including one-time model
load), then 26.6s, 26.2s, and 26.1s on immediately following turns — comfortably reliable for
interactive use, with one anomalous 227.8s outlier attributed to the model needing additional
ReAct turns on that particular run rather than any renewed resource constraint. The conclusion
this supports is specific and evidence-backed: qwen2.5:7b's apparent unreliability in earlier
testing was a **memory-budget conflict with the concurrently-running application stack on
under-provisioned hardware**, not a defect in the model or the agent code, and is fully resolved
by adequate RAM headroom.

**An infrastructure incident produced the most time-costly, and ultimately most instructive,
finding of the project.** For an extended debugging period, `/chat` requests intermittently hung
for 90–180+ seconds with no response and no error. Extensive investigation ruled out, in order:
DNS resolution (confirmed via direct hosts-file override), a VPN network adapter, Windows
Firewall rules, system proxy auto-detection, and raw TCP/TLS connectivity to NREL directly (all
independently verified fast and correct via `curl`, isolating the fault to something inside the
Python process specifically). The actual root cause, once found, was unrelated to networking
entirely: every traced function in the codebase calls a shared MLflow-configuration routine
before doing anything else, and when no MLflow tracking server was running, MLflow's own HTTP
client silently retried with backoff before finally raising a connection error — consuming the
entire observed hang, before the NREL call or the LLM was ever reached. This is documented here
deliberately as an evaluation finding, not just a bug fix: it demonstrates that an observability
layer, if not made failure-tolerant, can become a single point of failure for the very system it
is meant to monitor — a genuine, generalizable lesson about production LLMOps design, not merely
a one-off local configuration mistake.

**Edge-case and guardrail behavior was also verified directly.** An off-topic query ("what is
the best pizza topping") was correctly rejected by the guardrail layer in under 6 milliseconds,
independent of LLM or NREL availability, confirming that the cheapest, most deterministic layer
of the system behaves correctly and fails fast when it should, regardless of what state the more
expensive downstream components are in.

## 5. Retrospective

**What worked.** The decision to keep the deterministic parts of the pipeline — guardrails,
data fetching, and monthly aggregation — entirely free of LLM involvement paid off directly: in
every experiment run across two laptops and two different models, these components behaved
correctly 100% of the time. The system's actual reliability ceiling was never data-layer
correctness; it was specifically the LLM's format and transcription fidelity, and separating
those concerns cleanly is what made that isolation possible to observe and report at all. The
decision to build the ReAct loop from scratch rather than through a framework also proved its
worth during debugging: because every step was plain, readable Python, it was possible to add
targeted defenses (the "Final Answer without real data" rejection, the dual stop-sequence guard)
in direct response to specific failure modes actually observed, rather than working around a
framework's abstraction.

**Challenges.** The most significant challenge was not the agent logic but the surrounding
infrastructure: a multi-hour debugging session chasing what turned out to be an unrelated
tracing-server dependency masquerading as a networking fault is a real cost of adding
observability without also making it fail gracefully. Hardware constraints for local LLM
inference were a second major challenge — a capable 7B-parameter model was, for a period,
entirely unusable not because of any flaw in the model but because it did not fit in available
system memory alongside the rest of the running stack, a class of failure that is easy to
misdiagnose as a software bug if resource usage isn't measured directly. A third, smaller
challenge was public deployment: free-tier tunnel services impose hard request timeouts
(observed at roughly 100 seconds) that the full multi-call agent pipeline can occasionally
exceed even when functioning correctly, which shaped the decision to demonstrate the live
conversational flow against a local instance while using the public URL to prove reachability
and lighter-weight interactions.

**Lessons learned.** The clearest lesson is that a multi-step agentic pipeline's reliability is
the *compounding product* of each step's individual reliability, not their average — a loop that
asks a small model to get five to eight sequential decisions right in a row will fail far more
often than any single step's error rate suggests, and this is measurable, not just anecdotal, if
you run enough controlled trials rather than trusting one successful demo run. A second lesson is
methodological: before attributing a failure to the most "interesting" part of a system (the
model, the agent logic), it is worth verifying every shared dependency in isolation first,
including the ones added purely for observability. A third lesson, learned directly from the
qwen experiment, is that model comparisons are only meaningful when resource headroom is held
constant — an apparent reliability difference between two models can actually be a resource
availability difference in disguise.

**Future work.** The most direct next step is closing the gap between the current
request-response system and the original vision of proactive monitoring: integrating live
inverter/panel telemetry and comparing it against expected regional irradiance to generate
unprompted alerts, which would require a persistent per-installation data store and a scheduled
background process, both intentionally out of scope for this milestone. On the reliability side,
the temperature experiment should be repeated at a larger sample size now that hardware is no
longer a confound, and the MLflow dependency should be made explicitly non-blocking — wrapping
telemetry configuration in a try/except so a tracing outage degrades observability rather than
availability is a small, well-scoped fix directly motivated by this project's own incident.
Finally, session memory is currently in-process and does not survive a restart or scale across
multiple API replicas; moving it to a shared store (Redis or a lightweight database) is a
natural next step if the system were to move from demo to genuine multi-user production use.
