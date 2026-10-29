# SDK Agent Tracker Patterns

The main novel content of this skill — a per-method reference for the LaunchDarkly config tracker in Python and Node side by side. **No existing skill covers this.** The `launchdarkly-metric-instrument` skill is for `ldClient.track()` feature metrics, which is a different API.

All method names and signatures below describe the current public surface of `launchdarkly-server-sdk-ai` (Python) and `@launchdarkly/server-sdk-ai` (Node). If a method is not listed, it does not exist — do not invent it. For per-release breaking changes and renames, consult the SDK CHANGELOGs:

- Python: https://github.com/launchdarkly/python-server-sdk-ai/blob/main/packages/sdk/server-ai/CHANGELOG.md
- Node: https://github.com/launchdarkly/js-core/blob/main/packages/sdk/server-ai/CHANGELOG.md

## Tracker lifetime

Both SDKs obtain a tracker via the **`create_tracker` / `createTracker` factory** on the resolved config. Each call to the factory mints a fresh tracker with a unique `runId` for that execution. The `runId` tags every event emitted by that tracker so events from a single run can be correlated downstream (via exported events / analytics pipelines). The Monitoring tab aggregates events rather than grouping them by run today, but the `runId` also scopes the SDK's at-most-once guards on `track_duration` / `track_tokens` / `track_success` — minting a fresh tracker resets the guard, so accidental per-iteration factory calls don't just fragment downstream views, they also defeat the at-most-once semantics those guards enforce. **Call the factory once at the start of each execution and reuse the returned tracker for all calls within that execution.**

**What counts as one "execution":**

| Shape | One execution = | Where to call `create_tracker()` |
|-------|-----------------|----------------------------------|
| Single provider call (one-shot completion) | the function that handles one request | Right after `completion_config(...)` returns |
| Chat loop via `ManagedModel` | one `run()` / `invoke()` call | Never — the managed runner handles it |
| Multi-step ReAct / LangGraph loop (model → tool → model → tool → model) | one full user turn, including every loop iteration | A `setup_run` entry node that executes once before the loop; stash the tracker on state |
| Custom ReAct loop in application code | one call to your turn handler | Top of the handler, before the `for` loop |
| Streaming response | the streaming call + its consumer | Before the stream is opened; reuse across chunks |

The common mistake: calling `create_tracker()` inside a function that runs more than once per turn (a LangGraph `call_model` node, a recursive tool-dispatch helper, a per-chunk callback). Each call mints a fresh `runId`, so a three-step ReAct turn becomes three runs in the Monitoring tab and three billed executions. Tracker lifetime must match user-turn lifetime.

### At-most-once guards on `track_duration` / `track_tokens` / `track_success`

The tracker's methods split into two groups by whether repeated calls are safe. Knowing which is which is the difference between a correctly-instrumented agent loop and one that silently drops data:

| Method | Category | Safe to call per loop step? | What happens if you exceed |
|---|---|---|---|
| `track_duration` / `trackDuration` | **at-most-once** | ❌ | Second and later calls log a warning and are dropped |
| `track_tokens` / `trackTokens` | **at-most-once** | ❌ | Same |
| `track_success` / `trackSuccess` | **at-most-once** | ❌ | Same |
| `track_error` / `trackError` | **at-most-once** (mutually exclusive with `track_success`) | ❌ | Same |
| `track_time_to_first_token` / `trackTimeToFirstToken` | **at-most-once** | ❌ | Same |
| `track_tool_call` / `trackToolCall` | **per-event** | ✅ | Metadata records each invocation; no dedup |
| `track_tool_calls` / `trackToolCalls` | **per-event** | ✅ | Same; iterable variant for batching |
| `track_feedback` / `trackFeedback` | **per-event** | ✅ | Each feedback signal is a new event |
| `track_judge_result` / `trackJudgeResult` | **per-event** | ✅ | Each judge evaluation is a new event |
| `track_metrics_of` / `trackMetricsOf` | **wrapper over at-most-once methods** | ❌ | Internally emits `track_duration` + `track_success`/`track_error` + `track_tokens` once per wrapped call — so calling `trackMetricsOf` twice on the same tracker re-trips the guards |

The pattern for an agent loop follows from the split: accumulate `usage_metadata` across iterations (sum into a `TokenUsage` running total) and stash `time.perf_counter_ns()` up top; emit the four **at-most-once** methods exactly once in a terminal / finalize node. Per-step metadata like `track_tool_calls` goes inside the loop body where it belongs.

```python
tracker = ai_config.create_tracker()   # one call, one runId
tracker.track_success()
tracker.track_tokens(usage)
```
```typescript
const tracker = aiConfig.createTracker();   // one call, one runId
tracker.trackSuccess();
tracker.trackTokens(tokens);
```

Other API notes worth knowing:

- **Python:** `AIGraphTracker.track_latency` is `track_duration`. The `LDAIConfigTracker.track_*()` methods do not take a `graph_key` keyword — trackers obtained inside a graph traversal are already bound to the right graph key.
- **Python:** `Judge.evaluate()` / `evaluate_messages()` return a `JudgeResult`; check `result.sampled` to know whether the evaluation ran. Record it with `tracker.track_judge_result(result)`.
- **Node:** `Judge.evaluate()` / `evaluateMessages()` return `LDJudgeResult`; check `result.sampled`. Record it with `tracker.trackJudgeResult(result)`.
- **Both:** managed-runner constructors (`ManagedModel`, `ManagedAgent`, `Judge`, `ManagedAgentGraph`) do not accept a tracker parameter; they create one internally from the factory.
- **Both:** cross-process tracker resumption is supported. Python exposes `LDAIConfigTracker.resumption_token` + `from_resumption_token(...)`; Node exposes `LDAIClient.createTracker()` / `createGraphTracker()` that accept the same token.

## Two tracker classes

| Class | Where it lives | When you use it |
|-------|----------------|-----------------|
| `LDAIConfigTracker` (Python) / `LDAIConfigTracker` (Node) | Returned from `config.create_tracker()` / `aiConfig.createTracker()` | **Per-request tracking.** Call the factory once per execution; reuse the returned tracker for all calls in that execution. This is the one this skill wires in Stage 4. |
| `AIGraphTracker` (Python) / graph tracker (Node) | Created alongside a graph-definition traversal | **Graph-level tracking.** Covers path, handoffs, total tokens, total duration for a multi-node traversal. See [agent-graph-reference.md](agent-graph-reference.md). |

This doc focuses on `LDAIConfigTracker`. For graph tracking, see the graph reference.

## Config tracker methods — Python ↔ Node

All examples assume you have already obtained `tracker` via:
```python
tracker = ai_config.create_tracker()
```
```typescript
const tracker = aiConfig.createTracker();
```

### `track_success` / `trackSuccess`

Record a successful generation. Required — the Monitoring tab does not populate without it.

```python
tracker.track_success()
```
```typescript
tracker.trackSuccess();
```

No arguments. Call once per request after the provider call returns.

### `track_error` / `trackError`

Record a failed generation. Required for error-rate metrics.

```python
tracker.track_error()
```
```typescript
tracker.trackError();
```

Call from the exception path. Do not also call `track_success` in the same request.

### `track_duration` / `trackDuration`

Record latency in milliseconds. Measure wall-clock time across the provider call.

```python
import time
start = time.time()
response = openai_client.chat.completions.create(...)
tracker.track_duration(int((time.time() - start) * 1000))
```
```typescript
const start = Date.now();
const response = await openai.chat.completions.create(/* ... */);
tracker.trackDuration(Date.now() - start);
```

**Python note:** there is no `track_request()` context-manager method on `LDAIConfigTracker`. Some older guides show it; it does not exist. Use `track_duration` + `track_success`/`track_error` explicitly, or use `track_duration_of` / `track_metrics_of` (below) which wrap the whole thing.

### `track_tokens` / `trackTokens`

Record token usage. The shape is `(input, output, total)` in both SDKs.

```python
from ldai.tracker import TokenUsage

tracker.track_tokens(TokenUsage(
    input=response.usage.prompt_tokens,
    output=response.usage.completion_tokens,
    total=response.usage.total_tokens,
))
```
```typescript
tracker.trackTokens({
  input: response.usage?.prompt_tokens ?? 0,
  output: response.usage?.completion_tokens ?? 0,
  total: response.usage?.total_tokens ?? 0,
});
```

Token field names vary by provider. OpenAI's `usage.prompt_tokens` is the input count; Anthropic's `usage.input_tokens` is. Always pull from the provider response, not from a re-tokenization.

### `track_time_to_first_token` / `trackTimeToFirstToken`

For streaming calls, record the time from request-start to first-chunk.

```python
tracker.track_time_to_first_token(time_to_first_token_ms)
```
```typescript
tracker.trackTimeToFirstToken(timeToFirstTokenMs);
```

Skip for non-streaming calls. See the "Streaming" section below.

### `track_feedback` / `trackFeedback`

Record user feedback (thumbs-up/down). Both SDKs take a `{kind}` object with a `FeedbackKind` enum.

```python
from ldai.tracker import FeedbackKind
tracker.track_feedback({"kind": FeedbackKind.Positive})
tracker.track_feedback({"kind": FeedbackKind.Negative})
```
```typescript
import { LDFeedbackKind } from '@launchdarkly/server-sdk-ai';
tracker.trackFeedback({ kind: LDFeedbackKind.Positive });
tracker.trackFeedback({ kind: LDFeedbackKind.Negative });
```

Wire this only when the app has a UI that captures the signal — e.g. thumbs-up/down buttons on each response. If the thumbs-up happens in a later request than the one that produced the response, use **cross-process tracker resumption** (below) — persist the tracker's resumption token alongside the message ID, then rehydrate the tracker in the feedback handler.

### `track_tool_call` / `trackToolCall`

Record a tool invocation on the config that issued it.

```python
tracker.track_tool_call("search_kb")
```
```typescript
tracker.trackToolCall('search_kb');
```

If the tracker was obtained inside a graph traversal it is already bound to the right graph key. Nothing else to do at the call site.

### `track_tool_calls` / `trackToolCalls`

```python
tracker.track_tool_calls(["search_kb", "calculator"])
```
```typescript
tracker.trackToolCalls(['search_kb', 'calculator']);
```

Iterable variant. Call once per request with the full list of tools invoked.

### `track_judge_result` / `trackJudgeResult`

Record a judge evaluation (scores + reasoning).

The full programmatic direct-judge pattern (Python):

```python
from ldai.client import AIJudgeConfigDefault

judge = ai_client.create_judge(
    judge_key,                               # judge config key in LD
    ld_context,
    AIJudgeConfigDefault(enabled=False),     # fallback: skip eval on SDK miss
)

if judge and judge.enabled:
    result = await judge.evaluate(
        input_text,
        output_text,
        sampling_rate=0.25,                  # optional; default 1.0 (always eval)
    )
    if result.sampled:
        tracker.track_judge_result(result)
```

**Rules for the Python shape:**

- `create_judge` returns `Optional[Judge]` — guard with `if judge and judge.enabled:` before calling `.evaluate`. A direct `.evaluate()` on a `None` return raises `AttributeError`.
- The `default` argument is typed `Optional[AIJudgeConfigDefault]`. Pass `AIJudgeConfigDefault`, not `AICompletionConfigDefault` — the type is strict.
- `sampling_rate` is a parameter on `Judge.evaluate()`, **not** on `create_judge`. It defaults to `1.0` (evaluate every call).
- `evaluate()` returns a `JudgeResult` object (never `None`). If the evaluation was skipped by sampling, `result.sampled` is `False`. Guard `track_judge_result` with `if result.sampled:`.

Node equivalent:

```typescript
const result = await judge.evaluate(inputText, outputText, { samplingRate: 0.25 });
if (result.sampled) {
  tracker.trackJudgeResult(result);
}
```

Only needed when you call `create_judge(...).evaluate(...)` directly. Automatic evaluation via managed runners records scores without this call.

## Auto-tracking helpers

The canonical tracking surface is **`trackMetricsOf` composed with a provider-package `getAIMetricsFromResponse` extractor** (Tier 2) — or, one level up, the managed runners (`ManagedModel`) which track everything automatically and don't require any tracker calls at all (Tier 1). Both Python and Node SDK READMEs document this tiering exclusively.

### Python

| Helper | Signature | Tier | Notes |
|--------|-----------|------|-------|
| `track_metrics_of(extractor, func)` | `tracker.track_metrics_of(extractor, func)` | **2 / 3** | **Canonical generic wrapper.** Sync. Calls `extractor(result)` to get an `LDAIMetrics` object; records tokens + duration + success. Use a provider package's `get_ai_metrics_from_response` as the extractor for Tier 2, or write a small custom function for Tier 3. |
| `track_metrics_of_async(extractor, func)` | `await tracker.track_metrics_of_async(extractor, async_func)` | 2 / 3 | Async variant. |
| `track_duration_of(func)` | `tracker.track_duration_of(lambda: provider_call())` | 4 | Wraps a sync callable; captures duration only. Pair with explicit `track_tokens` + `track_success`. Useful when the response shape makes `track_metrics_of` awkward. |

Example — OpenAI via `track_metrics_of` + the provider package extractor:
```python
from ldai_openai import get_ai_metrics_from_response

tracker = ai_config.create_tracker()

def call_openai():
    return openai_client.chat.completions.create(
        model=ai_config.model.name,
        messages=[m.to_dict() for m in ai_config.messages or []],
    )

completion = tracker.track_metrics_of(get_ai_metrics_from_response, call_openai)
```

Example — custom extractor for Anthropic direct (Tier 3):
```python
from ldai.providers.types import LDAIMetrics, TokenUsage

def anthropic_extractor(response) -> LDAIMetrics:
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(
            total=response.usage.input_tokens + response.usage.output_tokens,
            input=response.usage.input_tokens,
            output=response.usage.output_tokens,
        ),
    )

tracker = ai_config.create_tracker()
response = tracker.track_metrics_of(
    anthropic_extractor,
    lambda: anthropic_client.messages.create(...),
)
```

### Node.js / TypeScript

| Helper | Signature | Tier | Notes |
|--------|-----------|------|-------|
| `trackMetricsOf<T>(extractor, func)` | `await tracker.trackMetricsOf((result) => extractor(result), async () => ...)` | **2 / 3** | **Canonical generic wrapper.** `extractor` maps provider response → `LDAIMetrics`. Use a provider package's bare `getAIMetricsFromResponse` for Tier 2 (`@launchdarkly/server-sdk-ai-openai`, `-langchain`, `-vercel`) or a small custom function for Tier 3. |
| `trackStreamMetricsOf<T>(extractor, streamCreator)` | `tracker.trackStreamMetricsOf(async (chunks) => extractor(chunks), () => createStream())` | 2 / 3 | Stream variant. Does **not** capture TTFT automatically — if you need TTFT, use the manual pattern in [streaming-tracking.md](../../launchdarkly-built-in-metrics/references/streaming-tracking.md). |
| `trackDurationOf<T>(func)` | `await tracker.trackDurationOf(async () => ...)` | 4 | Wraps an async callable; captures duration only. Pair with explicit `trackTokens` + `trackSuccess`. |
Example — OpenAI via `trackMetricsOf` + the provider package:
```typescript
import { getAIMetricsFromResponse } from '@launchdarkly/server-sdk-ai-openai';

const tracker = aiConfig.createTracker();
const response = await tracker.trackMetricsOf(
  getAIMetricsFromResponse,
  () => openai.chat.completions.create({
    model: aiConfig.model?.name ?? 'gpt-4o',
    messages: [...(aiConfig.messages ?? []), { role: 'user', content: userPrompt }],
  }),
);
```

Example — LangChain via `trackMetricsOf` (works for any model LangChain wraps, including Anthropic and Bedrock):
```typescript
import {
  createLangChainModel,
  getAIMetricsFromResponse,
} from '@launchdarkly/server-sdk-ai-langchain';

const llm = await createLangChainModel(aiConfig);
const tracker = aiConfig.createTracker();
const response = await tracker.trackMetricsOf(
  getAIMetricsFromResponse,
  () => llm.invoke(messages),
);
```

### Tier 1 — Managed runners (mention)

For chat-loop applications, both SDKs expose a higher-level API that handles tracking end-to-end with no tracker calls at all:

- Python: `ai_client.create_model(...)` → `ManagedModel`, then `await model.run(user_input)`
- Node: `aiClient.createModel(...)` → `ManagedModel`, then `await model.run(userInput)`

The managed runner handles message history, provider dispatch (via the installed provider package — OpenAI, LangChain, Vercel), and tracker wiring. The runner creates its own tracker internally via the factory — you do **not** pass a tracker in. If the migration target is conversational, this is the right tier and you don't need anything from the tables above.

### Anthropic has no provider package today

Neither `@launchdarkly/server-sdk-ai-anthropic` nor `launchdarkly-server-sdk-ai-anthropic` exists as of this writing. For Anthropic direct calls, write a custom extractor and pass it to `track_metrics_of` / `trackMetricsOf` — see the Python example above or the full walk-through in [anthropic-tracking.md](../../launchdarkly-built-in-metrics/references/anthropic-tracking.md). If the app is open to LangChain, routing Anthropic through `ChatAnthropic` and the LangChain provider package recovers Tier 2 with zero extractor code.

## Tier decision table

| Situation | Tier | Pattern |
|-----------|------|---------|
| Chat loop (history, turn-based), any provider with a package | **1** | `ManagedModel` / `createModel` — no tracker calls |
| OpenAI direct SDK, non-chat shape | **2** | `trackMetricsOf(getAIMetricsFromResponse, fn)` (extractor from `@launchdarkly/server-sdk-ai-openai`) |
| LangChain / LangGraph (any underlying model), non-chat shape | **2** | `trackMetricsOf(getAIMetricsFromResponse, fn)` (extractor from `@launchdarkly/server-sdk-ai-langchain`) |
| Vercel AI SDK, non-chat shape (Node only) | **2** | `trackMetricsOf` with the Vercel provider package's extractor |
| Anthropic direct SDK | **3** | Custom extractor reading `response.usage.input_tokens` / `output_tokens` |
| Bedrock Converse (no provider package) | **3** | Custom extractor reading `response.usage.inputTokens` / `outputTokens` (or route via LangChain for Tier 2) |
| Gemini / Google GenAI, Cohere, custom HTTP | **3** | Custom extractor |
| Streaming response with TTFT required | **4** | Manual `trackTimeToFirstToken` + `trackDuration` + `trackTokens` + `trackSuccess` — see [streaming-tracking.md](../../launchdarkly-built-in-metrics/references/streaming-tracking.md) |
| Streaming response without TTFT (Node) | **2 / 3** | `trackStreamMetricsOf(extractor, streamFn)` |

## Streaming responses

Streaming is trickier because duration and tokens aren't known until the stream completes.

**Python — manual pattern for streaming OpenAI:**
```python
import time

tracker = ai_config.create_tracker()
start = time.time()
first_chunk_time = None
input_tokens = 0
output_tokens = 0

stream = openai_client.chat.completions.create(stream=True, ...)
for chunk in stream:
    if first_chunk_time is None:
        first_chunk_time = time.time()
        tracker.track_time_to_first_token(int((first_chunk_time - start) * 1000))
    # accumulate output tokens from chunk.usage if provider emits them
    # or use a tokenizer for an estimate

tracker.track_duration(int((time.time() - start) * 1000))
tracker.track_tokens(TokenUsage(input=input_tokens, output=output_tokens, total=input_tokens + output_tokens))
tracker.track_success()
```

**Node — use `trackStreamMetricsOf`:**
```typescript
const tracker = aiConfig.createTracker();
const stream = await tracker.trackStreamMetricsOf(
  () => openai.chat.completions.create({ stream: true, /* ... */ }),
  async (s) => {
    // Drain the stream and extract LDAIMetrics
    return extractMetricsFromDrainedStream(s);
  },
);
```

## Cross-process tracker resumption

Sometimes a tracker call needs to happen in a different process from the one that produced the response — the archetypal case is **deferred feedback** (thumbs-up saved to a DB, processed later by a worker) but it also applies to any event-driven pipeline.

**Python:**
```python
# Producer process: persist the resumption token with the message
tracker = ai_config.create_tracker()
response = call_provider(...)
save_message(message_id, response.content, resumption_token=tracker.resumption_token)

# Consumer process: rehydrate the tracker from the token
row = load_message(message_id)
result = LDAIConfigTracker.from_resumption_token(row.resumption_token, ld_client, ld_context)
if result.success:
    result.value.track_feedback({"kind": FeedbackKind.Positive})
```

**Node:**
```typescript
// Producer process: persist the token (accessor on the tracker)
const tracker = aiConfig.createTracker();
const response = await callProvider(...);
await saveMessage(messageId, response.content, { resumptionToken: tracker.resumptionToken });

// Consumer process: rehydrate via LDAIClient.createTracker()
const tracker = aiClient.createTracker(row.resumptionToken, ldContext);
tracker.trackFeedback({ kind: LDFeedbackKind.Positive });
```

The same resumption token carries the `runId`, so feedback lands on the same run the Monitoring tab already knows about. For graph traversals, use `createGraphTracker(...)` on Node / the graph-tracker resumption helper on Python.

## Where tracker calls should live

- **Inside a retry wrapper**, not outside it. If your request has 3 retry attempts and 2 fail + 1 succeeds, you want 1 `track_success`. Putting the tracker outside the retry would cause 3 events or 0.
- **Per request**, not cached across requests. Each execution should call `create_tracker()` once to get a tracker with a fresh `runId`, then use it for every tracking call in that request.
- **Before any return statement.** A tracker call that never runs (because an early return bypasses it) produces silent data loss. Use try/finally in complex handlers if needed.
- **After the provider returns**, not before. Duration measured from before the provider call; tokens and success/error from the response.

## Troubleshooting: Monitoring tab shows no data

Run the checklist in order. Each step rules out one cause.

1. **SDK key** — is `LD_SDK_KEY` the server-side key (starts with `sdk-`), not the client-side key or the API key?
2. **Enabled check** — is `ai_config.enabled` / `aiConfig.enabled` `True`? A disabled config will not record traffic. Check the config's targeting in LaunchDarkly and confirm the context matches a rule that serves an enabled variation.
3. **Any tracker call at all** — did `track_success` / `trackSuccess` fire? Without at least one generation-level call, the Monitoring tab has nothing to show. Log a one-liner next to the call to confirm it runs.
4. **Config key match** — is the string passed to `completion_config` / `completionConfig` exactly the same as the config key in LaunchDarkly? Keys are case-sensitive.
5. **Mode match** — if the code calls `completion_config` but the config in LaunchDarkly is in agent mode (or vice versa), the SDK call will error out. Check the mode in the UI.
6. **Flush on shutdown** — on short-lived processes (tests, scripts), call `ld_client.flush()` before exit. Long-running servers flush automatically on an interval.
7. **Data delay** — the Monitoring tab updates within 1–2 minutes. If you just deployed, wait and retry before debugging further.
8. **SDK version** — confirm the installed `launchdarkly-server-sdk-ai` (Python) / `@launchdarkly/server-sdk-ai` (Node) version supports the API the code is calling. Methods like `create_tracker` / `createTracker`, `runId`-grouped metrics, `track_judge_result`, and `trackToolCall` / `trackToolCalls` (Node) were added in recent releases — see the SDK CHANGELOGs linked at the top of this file for the version they landed in.
9. **Debug logging** — enable SDK debug logging (`LD_LOG_LEVEL=debug` / `setLevel('debug')`) to see evaluation results and tracker calls in stdout.
10. **Error path silent** — are you catching exceptions that swallow tracker errors? The tracker should never raise, but if a custom wrapper catches everything, confirm the call fires by logging before and after.

## Common gotchas

- **`model.parameters` vs `model.custom`.** `create_langchain_model` (Python) / `createLangChainModel` (Node) forwards every key in `model.parameters` to the provider SDK. App-scoped knobs (search result limits, retry budgets, feature toggles) **must** live in `model.custom` or the provider will crash at runtime with an unexpected-keyword-argument error. Read them with `ai_config.model.get_custom("key")`. Full walk-through with the MCP/REST-API caveat in [langchain-tracking.md § `model.parameters` vs `model.custom`](../../launchdarkly-built-in-metrics/references/langchain-tracking.md).
- **`track_tokens` token shape.** The Python `TokenUsage` dataclass requires `total` to be set — it is not derived. Compute `total = input + output` if the provider doesn't return one.
- **`track_feedback` lifecycle.** The feedback call must be made on a tracker bound to the same `runId` that produced the response. If the thumbs-up comes in a later process, use the cross-process resumption pattern above — do **not** call `create_tracker()` again in the consumer, because that mints a *new* `runId`.
- **OpenAI streaming tokens.** OpenAI only emits `usage` in the final chunk when `stream_options={"include_usage": True}` is passed. Without that flag, you have to tokenize manually — `tiktoken` for OpenAI models.
- **Anthropic token field names.** Anthropic uses `response.usage.input_tokens` and `output_tokens`, not `prompt_tokens`/`completion_tokens`. Do not copy the OpenAI shape.
- **Bedrock Converse response shape.** `response["usage"]["inputTokens"]` (camelCase, not snake). The auto-helper handles this — prefer it over manual extraction.
- **Retry loops and `track_duration`.** If you wrap the whole retry in `track_duration`, the value includes backoff sleeps. Either measure only the final-attempt provider call, or document that duration includes retries — don't leave it ambiguous.
- **Do not call `create_tracker()` more than once per execution.** Each call mints a new tracker with a new `runId`. Subsequent tracker calls landing on a different `runId` can't be correlated with the first one downstream (exported events, analytics pipelines), and each fresh tracker resets the at-most-once guard — so per-iteration factory calls double-count `track_duration` / `track_tokens` / `track_success` instead of deduplicating. For agent loops, "execution" is the full user turn, not one LLM call — see the table above for where to place the call in each shape.
- **Do not emit `track_duration` / `track_tokens` / `track_success` inside a loop body.** These fire at-most-once per tracker; per-iteration calls log warnings and are dropped. Accumulate, emit once after the loop.
- **Do not call `track_metrics_of` / `track_metrics_of_async` inside an agent loop node.** The wrapper records duration + success per invocation, which collides with the at-most-once guard when the node runs multiple times in a turn. Use `track_metrics_of` for one-shot provider calls; use explicit `track_duration` + `track_tokens` + `track_success` in a terminal node for agent loops.
