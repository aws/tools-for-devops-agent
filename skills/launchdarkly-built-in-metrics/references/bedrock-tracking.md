# AWS Bedrock Metrics Tracking

**There is no LaunchDarkly provider package for Bedrock today** (neither Python nor Node). Two practical paths:

1. **Route Bedrock through LangChain** (`ChatBedrockConverse` / `langchain-aws`). If you're open to LangChain, this is the closest thing to Tier 2 — you use the LangChain provider package's `getAIMetricsFromResponse` and inherit the whole `trackMetricsOf` pattern for free.
2. **Custom extractor on `boto3`** (this file's primary pattern). Bedrock Converse returns a stable response shape with `usage.inputTokens` / `usage.outputTokens` / `usage.totalTokens`, so the extractor is three lines.

## Tier 1 is not available

`ManagedModel` does not ship a Bedrock provider today (Python or Node). If you want Tier 1 for a Bedrock chat app, route via LangChain — `ManagedModel` can wrap a `ChatBedrockConverse` through the LangChain provider package.

## Tier 3 — Custom extractor + `trackMetricsOf` (primary)

### Converse API (recommended)

**Python:**

```python
import boto3
from ldai.providers.types import LDAIMetrics, TokenUsage

bedrock = boto3.client("bedrock-runtime")

def bedrock_converse_extractor(response) -> LDAIMetrics:
    usage = response.get("usage", {})
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(
            total=usage.get("totalTokens", 0),
            input=usage.get("inputTokens", 0),
            output=usage.get("outputTokens", 0),
        ),
    )

def call_with_tracking(ai_config, user_prompt: str) -> str | None:
    if not ai_config.enabled:
        return None

    system_content = ai_config.messages[0].content if ai_config.messages else ""

    def call_bedrock():
        kwargs = {
            "modelId": ai_config.model.name,
            "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
        }
        if system_content:
            kwargs["system"] = [{"text": system_content}]
        return bedrock.converse(**kwargs)

    tracker = ai_config.create_tracker()
    # Exceptions are tracked automatically — track_metrics_of catches
    # exceptions, records tracker.track_error(), and re-raises.
    response = tracker.track_metrics_of(bedrock_converse_extractor, call_bedrock)
    return response["output"]["message"]["content"][0]["text"]
```

**Node:**

```typescript
import { BedrockRuntimeClient, ConverseCommand, type ConverseCommandOutput } from '@aws-sdk/client-bedrock-runtime';
import type { LDAIMetrics } from '@launchdarkly/server-sdk-ai';

const bedrock = new BedrockRuntimeClient({});

const bedrockConverseExtractor = (response: ConverseCommandOutput): LDAIMetrics => ({
  success: true,
  tokens: {
    total: response.usage?.totalTokens ?? 0,
    input: response.usage?.inputTokens ?? 0,
    output: response.usage?.outputTokens ?? 0,
  },
});

async function callWithTracking(
  aiConfig: LDAICompletionConfig,
  userPrompt: string,
): Promise<string | null> {
  if (!aiConfig.enabled) return null;

  const systemContent = aiConfig.messages?.[0]?.content;

  const tracker = aiConfig.createTracker();
  // Exceptions are tracked automatically — trackMetricsOf catches
  // exceptions, records tracker.trackError(), and re-throws.
  const response = await tracker.trackMetricsOf(
    bedrockConverseExtractor,
    () => bedrock.send(new ConverseCommand({
      modelId: aiConfig.model!.name,
      messages: [{ role: 'user', content: [{ text: userPrompt }] }],
      ...(systemContent ? { system: [{ text: systemContent }] } : {}),
    })),
  );
  return response.output?.message?.content?.[0]?.text ?? null;
}
```

### Legacy InvokeModel API

`InvokeModel` returns per-model shapes (Anthropic on Bedrock returns Anthropic's shape, Llama on Bedrock returns Meta's shape, etc.), so the extractor has to branch. **Prefer Converse** unless you're locked into InvokeModel by an older model that Converse doesn't support. If you must use InvokeModel, switch the extractor based on the model family:

```python
def invoke_model_extractor(response) -> LDAIMetrics:
    body = json.loads(response["body"].read())
    # Claude on InvokeModel
    if "usage" in body:
        return LDAIMetrics(
            success=True,
            tokens=TokenUsage(
                total=body["usage"]["input_tokens"] + body["usage"]["output_tokens"],
                input=body["usage"]["input_tokens"],
                output=body["usage"]["output_tokens"],
            ),
        )
    # Llama / Titan — use the fields on the specific body shape
    # ...
    return LDAIMetrics(success=True, tokens=TokenUsage(total=0, input=0, output=0))
```

This is a good reason to migrate to Converse if you can.

## Tier 2 option — route via LangChain

If the app uses LangChain, the LangChain provider package's `ChatBedrockConverse` support gives you the Tier-2 experience:

```python
from ldai_langchain import create_langchain_model, get_ai_metrics_from_response

ai_config = ai_client.completion_config("my-config-key", context, default_config)
llm = create_langchain_model(ai_config)  # ChatBedrockConverse when provider=bedrock

tracker = ai_config.create_tracker()
response = tracker.track_metrics_of(
    get_ai_metrics_from_response,
    lambda: llm.invoke(messages),
)
```

LangChain normalizes the Converse response shape into `AIMessage.usage_metadata`, which `get_ai_metrics_from_response` reads — so you don't need a Bedrock-specific extractor.

## Tier 4 — Manual (streaming only)

Bedrock Converse streaming (`ConverseStream`) needs manual TTFT tracking. The pattern is identical to OpenAI streaming. See [streaming-tracking.md](streaming-tracking.md).
