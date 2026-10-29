# OpenAI Metrics Tracking

OpenAI is covered by a first-class LaunchDarkly provider package in both Python and Node. Walk the tiers from top to bottom and stop at the first one that fits the call shape.

## Tier 1 — Managed runner (chat apps)

The simplest path for conversational OpenAI calls. Zero tracker calls — duration, tokens, and success/error are all captured by `run()`.

**Python** — `ManagedModel` via `ai_client.create_model()`:

```python
from ldclient import Context
from ldai import LDAIClient, AICompletionConfigDefault, ModelConfig, LDMessage, ProviderConfig

default_config = AICompletionConfigDefault(
    enabled=True,
    model=ModelConfig(name="gpt-4o"),
    provider=ProviderConfig(name="openai"),
    messages=[LDMessage(role="system", content="You are a helpful assistant.")],
)

async def handle_turn(ai_client: LDAIClient, context: Context, user_input: str) -> str:
    model = await ai_client.create_model(
        "customer-support-chat",
        context,
        default_config,
    )
    if not model:
        return "Feature is currently unavailable."
    response = await model.run(user_input)
    return response.content
```

**Node** — `ManagedModel` via `aiClient.createModel()`:

```typescript
import { init } from '@launchdarkly/node-server-sdk';
import { initAi } from '@launchdarkly/server-sdk-ai';

const ldClient = init(process.env.LD_SDK_KEY!);
const aiClient = initAi(ldClient);

async function handleTurn(context: LDContext, userInput: string): Promise<string> {
  const model = await aiClient.createModel(
    'customer-support-chat',
    context,
    {
      enabled: true,
      model: { name: 'gpt-4o' },
      provider: { name: 'openai' },
      messages: [{ role: 'system', content: 'You are a helpful assistant.' }],
    },
  );
  if (!model) return 'Feature is currently unavailable.';
  const response = await model.run(userInput);
  return response.content;
}
```

Tracking is handled inside `run()`. You do not need `trackMetricsOf`, `trackSuccess`, or `trackTokens` at this tier.

## Tier 2 — Provider package + `trackMetricsOf` (non-chat shapes)

Use this when the call isn't a chat loop (one-shot completion, structured output, batch job, agent step). The provider package exposes a static `getAIMetricsFromResponse` that knows how to pull tokens out of an OpenAI response; you compose it with the generic `trackMetricsOf` wrapper.

**Python** — `launchdarkly-server-sdk-ai-openai`:

```python
managed = await ai_client.create_model("my-config-key", context, default_config)
if managed:
    result = await managed.run(user_prompt)
    return result.content
```

`managed.run()` tracks automatically — the managed runner handles duration, tokens, and success/error end-to-end. If you need finer-grained control (e.g., you want to supply your own OpenAI client with custom retries), use the raw SDK + `track_metrics_of` with the bare extractor:

```python
import openai
from ldai_openai import get_ai_metrics_from_response

client = openai.OpenAI()

ai_config = ai_client.completion_config("my-config-key", context, default_config)
if not ai_config.enabled:
    return None

tracker = ai_config.create_tracker()

def call_openai():
    return client.chat.completions.create(
        model=ai_config.model.name,
        messages=[
            {"role": "system", "content": ai_config.messages[0].content},
            {"role": "user", "content": user_prompt},
        ],
    )

response = tracker.track_metrics_of(get_ai_metrics_from_response, call_openai)
return response.choices[0].message.content
```

**Node** — `@launchdarkly/server-sdk-ai-openai`:

```typescript
import { OpenAI } from 'openai';
import { getAIMetricsFromResponse } from '@launchdarkly/server-sdk-ai-openai';

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const aiConfig = await aiClient.completionConfig('my-config-key', context, defaultConfig);
if (!aiConfig.enabled) return null;

const tracker = aiConfig.createTracker();
const response = await tracker.trackMetricsOf(
  getAIMetricsFromResponse,
  () => client.chat.completions.create({
    model: aiConfig.model!.name,
    messages: [
      ...aiConfig.messages,
      { role: 'user', content: userPrompt },
    ],
  }),
);
return response.choices[0].message.content;
```

**Error handling.** `trackMetricsOf` catches exceptions internally, records `trackError()` on the tracker, and re-throws — so you do **not** need a try/catch block that calls `trackError()` yourself. Call the wrapper directly; if the caller wants to log or handle the exception, do that in addition to (not instead of) letting it propagate:

```typescript
const tracker = aiConfig.createTracker();
const response = await tracker.trackMetricsOf(
  getAIMetricsFromResponse,
  () => client.chat.completions.create({ /* ... */ }),
);
return response.choices[0].message.content;
```

Python behaves the same with `track_metrics_of`. Do not add `except: tracker.track_error()` on top — it's a noop that would also trip the at-most-once guard.

## Tier 3 — Custom extractor (fallback)

You should not need Tier 3 for OpenAI — the provider package covers it. If you're using a fork, a drop-in replacement (LiteLLM, Azure OpenAI via raw HTTP), or something the provider package doesn't recognize, write a small extractor:

```python
from ldai.providers.types import LDAIMetrics, TokenUsage

def my_openai_extractor(response) -> LDAIMetrics:
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(
            total=response.usage.total_tokens,
            input=response.usage.prompt_tokens,
            output=response.usage.completion_tokens,
        ),
    )

tracker = ai_config.create_tracker()
response = tracker.track_metrics_of(my_openai_extractor, call_openai)
```

## Tier 4 — Manual (streaming only)

For OpenAI streaming calls you need manual tracking because the current provider packages don't capture TTFT. See [streaming-tracking.md](streaming-tracking.md) for the full pattern. The short version: the helper that looks like it should work (`trackStreamMetricsOf` in Node) captures tokens from stream chunks but does not record TTFT, so you still need a manual `trackTimeToFirstToken` call on the first content chunk.
