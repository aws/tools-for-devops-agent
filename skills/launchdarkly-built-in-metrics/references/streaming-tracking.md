# Streaming Metrics Tracking

**This is Tier 4 — the manual fallback.** Streaming is the one case where no current helper captures everything you need. The Node SDK ships `trackStreamMetricsOf`, which can pull tokens from stream chunks, but it does **not** capture time-to-first-token (TTFT). Python doesn't have a streaming helper at all. So if you want TTFT in the Monitoring tab, you have to wire it manually — and since TTFT is the whole point of streaming observability, this is almost always what you want.

If the app doesn't need TTFT (you just want total duration + tokens + success), you can use Tier 2 / Tier 3 patterns in Node via `trackStreamMetricsOf`, and Tier 3 in Python by consuming the whole stream into a response object and then calling `trackMetricsOf` on the assembled result. TTFT is the tiebreaker that forces Tier 4.

## What you track

- **Time to first token (TTFT)** — measured from "stream request sent" to "first content chunk received."
- **Total duration** — measured from "stream request sent" to "stream fully consumed."
- **Tokens** — read from the final stream event (if the provider includes usage) or from `tiktoken` / provider-native counters if not.
- **Success / error** — explicit calls in the consumer loop.

## Python — OpenAI streaming

```python
import time
import openai
from ldai.tracker import TokenUsage

def call_streaming_with_tracking(ai_config, user_prompt: str) -> str | None:
    if not ai_config.enabled:
        return None

    tracker = ai_config.create_tracker()
    start_time = time.time()
    first_token_time = None

    try:
        stream = openai.chat.completions.create(
            model=ai_config.model.name,
            messages=[
                {"role": "system", "content": ai_config.messages[0].content},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            stream_options={"include_usage": True},  # Required to get usage in final chunk
        )

        response_text = ""
        final_usage = None
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                if first_token_time is None:
                    first_token_time = time.time()
                    tracker.track_time_to_first_token(
                        int((first_token_time - start_time) * 1000)
                    )
                response_text += chunk.choices[0].delta.content
            if getattr(chunk, "usage", None):
                final_usage = chunk.usage

        tracker.track_duration(int((time.time() - start_time) * 1000))
        tracker.track_success()

        if final_usage:
            tracker.track_tokens(TokenUsage(
                total=final_usage.total_tokens,
                input=final_usage.prompt_tokens,
                output=final_usage.completion_tokens,
            ))

        return response_text

    except Exception:
        tracker.track_error()
        raise
```

The `stream_options={"include_usage": True}` flag is required — without it, OpenAI streaming does not include usage data and you fall back to `tiktoken` estimation.

## Python — tiktoken fallback

If you can't set `include_usage` (older SDK, Azure OpenAI on an endpoint that doesn't support it), count tokens locally with `tiktoken`:

```python
import tiktoken
from ldai.tracker import TokenUsage

def estimate_tokens(model_name: str, prompt: str, response: str) -> TokenUsage:
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    input_tokens = len(enc.encode(prompt))
    output_tokens = len(enc.encode(response))
    return TokenUsage(
        total=input_tokens + output_tokens,
        input=input_tokens,
        output=output_tokens,
    )
```

Drop it into the streaming consumer where `final_usage` would have been.

## Node — OpenAI streaming with manual TTFT

```typescript
import { OpenAI } from 'openai';

const client = new OpenAI();

async function callStreamingWithTracking(
  aiConfig: LDAICompletionConfig,
  userPrompt: string,
): Promise<string | null> {
  if (!aiConfig.enabled) return null;

  const tracker = aiConfig.createTracker();
  const startTime = Date.now();
  let firstTokenTime: number | null = null;

  try {
    const stream = await client.chat.completions.create({
      model: aiConfig.model!.name,
      messages: [
        ...aiConfig.messages,
        { role: 'user', content: userPrompt },
      ],
      stream: true,
      stream_options: { include_usage: true },
    });

    let responseText = '';
    let finalUsage: OpenAI.CompletionUsage | undefined;

    for await (const chunk of stream) {
      const delta = chunk.choices[0]?.delta?.content;
      if (delta) {
        if (firstTokenTime === null) {
          firstTokenTime = Date.now();
          tracker.trackTimeToFirstToken(firstTokenTime - startTime);
        }
        responseText += delta;
      }
      if (chunk.usage) {
        finalUsage = chunk.usage;
      }
    }

    tracker.trackDuration(Date.now() - startTime);
    tracker.trackSuccess();

    if (finalUsage) {
      tracker.trackTokens({
        total: finalUsage.total_tokens,
        input: finalUsage.prompt_tokens,
        output: finalUsage.completion_tokens,
      });
    }

    return responseText;
  } catch (err) {
    tracker.trackError();
    throw err;
  }
}
```

## Node — `trackStreamMetricsOf` (no TTFT)

If the app doesn't need TTFT, the Node SDK has a built-in streaming wrapper that handles tokens + success/error + duration:

```typescript
const tracker = aiConfig.createTracker();
const response = await tracker.trackStreamMetricsOf(
  (chunks) => {
    // Extract usage from the final chunk
    const final = chunks[chunks.length - 1];
    return {
      success: true,
      tokens: {
        total: final.usage?.total_tokens ?? 0,
        input: final.usage?.prompt_tokens ?? 0,
        output: final.usage?.completion_tokens ?? 0,
      },
    };
  },
  () => client.chat.completions.create({ /* ... */, stream: true, stream_options: { include_usage: true } }),
);
```

This is cleaner when TTFT doesn't matter (batch processing, log summarization, tasks where latency-to-first-byte isn't user-facing). If the user is going to look at the Monitoring tab's TTFT chart, though, you need the manual pattern above.

## What to avoid

- **Do not wrap `openai.chat.completions.create(stream=True)` with `trackMetricsOf`.** It'll record duration as the time to get the stream *object*, not the time to consume it — and tokens won't be captured at all because the extractor sees a stream object, not a response with `usage`.
- **Do not forget `track_success()` / `trackSuccess()`.** Unlike `trackMetricsOf`, the manual pattern doesn't call it for you. If you skip it, the Monitoring tab won't count the generation.
- **Do not set `first_token_time` on the first *chunk*.** Set it on the first chunk with non-empty `delta.content`. Many providers emit a role/metadata chunk before the first content chunk.
