# Anthropic Metrics Tracking

**There is no LaunchDarkly provider package for Anthropic direct API today.** The canonical path is the generic `trackMetricsOf` wrapper (Tier 3) with a small custom extractor that reads `response.usage.input_tokens` and `response.usage.output_tokens`. The instinct to "default to generic" is correct here — there is no Tier-2 shortcut to take.

Three viable paths, in order of preference:

1. **Route Anthropic through LangChain.** If the app already uses LangChain (or can adopt it cheaply), install the LangChain provider package and use it as Tier 2. LangChain's `ChatAnthropic` wrapper exposes the standardized `usage_metadata` that `getAIMetricsFromResponse` reads.
2. **Route Anthropic through Bedrock Converse.** If the app can switch to Bedrock Converse (Claude is available on Bedrock), you inherit Bedrock's Converse response shape and a custom-extractor pattern that's slightly cleaner. See [bedrock-tracking.md](bedrock-tracking.md).
3. **Custom extractor on the direct SDK** (this file's primary pattern).

## Tier 1 is not available

`ManagedModel` does not currently ship an Anthropic provider. If you need Tier 1 for a chat app, use option 1 or 2 above — the LangChain provider package lets `ManagedModel` wrap a `ChatAnthropic` under the hood, which restores the zero-tracker-call experience.

## Tier 3 — Custom extractor + `trackMetricsOf` (primary)

**Python** — direct Anthropic SDK:

```python
import anthropic
from ldai.providers.types import LDAIMetrics, TokenUsage

client = anthropic.Anthropic()

def anthropic_extractor(response) -> LDAIMetrics:
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(
            total=response.usage.input_tokens + response.usage.output_tokens,
            input=response.usage.input_tokens,
            output=response.usage.output_tokens,
        ),
    )

def call_with_tracking(ai_config, user_prompt: str) -> str | None:
    if not ai_config.enabled:
        return None

    system_content = ai_config.messages[0].content if ai_config.messages else ""

    def call_anthropic():
        return client.messages.create(
            model=ai_config.model.name,
            max_tokens=1024,
            system=system_content,
            messages=[{"role": "user", "content": user_prompt}],
        )

    tracker = ai_config.create_tracker()
    # Exceptions are tracked automatically here: track_metrics_of catches
    # exceptions, records tracker.track_error(), and re-raises. Do NOT add
    # except: tracker.track_error() on top — it's a noop that trips the
    # at-most-once guard. Wrap in your own try/except only if you need
    # local handling (logging, fallback, alert); the error is already tracked.
    response = tracker.track_metrics_of(anthropic_extractor, call_anthropic)
    return response.content[0].text
```

**Node** — direct Anthropic SDK:

```typescript
import Anthropic from '@anthropic-ai/sdk';
import type { LDAIMetrics } from '@launchdarkly/server-sdk-ai';

const client = new Anthropic();

const anthropicExtractor = (response: Anthropic.Message): LDAIMetrics => ({
  success: true,
  tokens: {
    total: response.usage.input_tokens + response.usage.output_tokens,
    input: response.usage.input_tokens,
    output: response.usage.output_tokens,
  },
});

async function callWithTracking(
  aiConfig: LDAICompletionConfig,
  userPrompt: string,
): Promise<string | null> {
  if (!aiConfig.enabled) return null;

  const systemContent = aiConfig.messages?.[0]?.content ?? '';

  const tracker = aiConfig.createTracker();
  // Exceptions are tracked automatically: trackMetricsOf catches exceptions,
  // records tracker.trackError(), and re-throws. Do NOT add
  // catch (err) { tracker.trackError(); throw err } on top — it's a noop
  // that trips the at-most-once guard. Wrap in your own try/catch only if
  // you need local handling (logging, fallback); the error is already tracked.
  const response = await tracker.trackMetricsOf(
    anthropicExtractor,
    () => client.messages.create({
      model: aiConfig.model!.name,
      max_tokens: 1024,
      system: systemContent,
      messages: [{ role: 'user', content: userPrompt }],
    }),
  );
  return response.content[0].type === 'text' ? response.content[0].text : null;
}
```

Notes on the extractor shape:

- Anthropic returns `input_tokens` / `output_tokens` on `response.usage`. Compute `total` yourself; Anthropic does not provide it.
- `LDAIMetrics` is a typed surface — Python has it at `ldai.providers.types`, Node exports it from `@launchdarkly/server-sdk-ai`. Keep the extractor pure: no side effects, no network calls.
- `success: true` in the extractor is not a lie — `trackMetricsOf` only calls the extractor on the success path. On the error path, `trackMetricsOf` records `trackError()` internally and re-throws; no caller-side catch block is required.

## Tier 2 option — route via LangChain

If the app can adopt LangChain, the LangChain provider package handles Anthropic (via `@langchain/anthropic`) through the same `trackMetricsOf(getAIMetricsFromResponse, ...)` pattern used for any other LangChain model. This is often the cleanest answer if the app already uses or is open to LangChain, because the extractor is built in and shared with every other LangChain-wrapped model.

```python
from ldai_langchain import create_langchain_model, get_ai_metrics_from_response

ai_config = ai_client.completion_config("my-config-key", context, default_config)
llm = create_langchain_model(ai_config)  # ChatAnthropic under the hood

tracker = ai_config.create_tracker()
response = tracker.track_metrics_of(
    get_ai_metrics_from_response,
    lambda: llm.invoke(messages),
)
```

## Tier 4 — Manual (streaming only)

Streaming Anthropic needs manual TTFT tracking; the pattern is identical to OpenAI streaming. See [streaming-tracking.md](streaming-tracking.md).

## What NOT to do

- **Do not hand-wire `track_duration_of` + `track_tokens` + `track_success` as three separate calls** unless you're on the streaming path. That's Tier 4, and `trackMetricsOf` gives you the same three metrics in one call with half the drift surface.
- **Do not look for a `track_anthropic_metrics` helper** — it doesn't exist, never has, and won't be added. Anthropic direct support lives in the extractor you write above.
- **Do not invent a provider package** like `@launchdarkly/server-sdk-ai-anthropic`. It doesn't exist as of this writing. Check [js-core ai-providers](https://github.com/launchdarkly/js-core/tree/main/packages/ai-providers) before recommending one.
