# Gemini Metrics Tracking

**There is no LaunchDarkly provider package for Gemini today** (neither Python nor Node). The canonical path is Tier 3: a small custom extractor composed with `trackMetricsOf`. The Gemini response shape is stable — `response.usage_metadata` / `response.usageMetadata` carries `prompt_token_count` / `promptTokenCount`, `candidates_token_count` / `candidatesTokenCount`, and `total_token_count` / `totalTokenCount` — so the extractor is three lines.

## Tier 1 is not available

`ManagedModel` does not currently ship a Gemini provider. If you need Tier 1 for a chat app, route via the LangChain provider package (`ChatGoogleGenerativeAI` under the hood), which restores the zero-tracker-call experience. See [langchain-tracking.md](langchain-tracking.md).

## Tier 3 — Custom extractor + `trackMetricsOf` (primary)

Gemini's API diverges from OpenAI's in three places that matter for a wrapper:

1. **System messages are a top-level field.** `GenerateContentConfig.system_instruction` / `systemInstruction` carries the system prompt; the `contents` array only holds `user` and `model` turns. You cannot put a `role: "system"` item in `contents`.
2. **Assistant messages use role `model`.** Convert `role: "assistant"` → `role: "model"` when mapping LD messages into Gemini's `contents`.
3. **Parameter names differ.** `max_tokens` on a LaunchDarkly variation (the snake_case key shown in the LD UI) becomes `max_output_tokens` on Python's `GenerateContentConfig`, or `maxOutputTokens` in Node. Other LD parameter names (`temperature`, `top_p`, `top_k`) either pass through or map with the same helper.

Two helpers absorb the divergence — a message splitter and a parameter remapper — and the metrics extractor sits on top.

**Python** — `google-genai`:

```python
from google import genai
from google.genai.types import Content, Part, GenerateContentConfig
from ldai.providers.types import LDAIMetrics, TokenUsage

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def gemini_metrics(response) -> LDAIMetrics:
    usage = response.usage_metadata
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(
            total=usage.total_token_count or 0,
            input=usage.prompt_token_count or 0,
            output=usage.candidates_token_count or 0,
        ) if usage else None,
    )

def map_to_gemini_messages(ld_messages):
    """Split LD messages into (system_instruction, contents) for google-genai.
    System messages concatenate into the top-level system_instruction; user and
    assistant messages become Content items with role 'user' or 'model'."""
    system_parts: list[str] = []
    contents: list[Content] = []
    for m in ld_messages or []:
        if m.role == "system":
            system_parts.append(m.content)
        elif m.role == "user":
            contents.append(Content(role="user", parts=[Part(text=m.content)]))
        elif m.role == "assistant":
            contents.append(Content(role="model", parts=[Part(text=m.content)]))
    return (" ".join(system_parts) or None), contents

def gemini_config_kwargs(params):
    """Map config parameter names to google-genai's GenerateContentConfig.
    LaunchDarkly stores max_tokens (snake_case, matching the LD UI); Gemini's
    Python SDK expects max_output_tokens. Drop `tools` — they go on
    GenerateContentConfig.tools directly; leaving them here would double-pass."""
    mapping = {"max_tokens": "max_output_tokens"}
    return {mapping.get(k, k): v for k, v in (params or {}).items() if k != "tools"}

def call_with_tracking(ai_config, user_prompt: str) -> str | None:
    if not ai_config.enabled:
        return None

    system_instruction, contents = map_to_gemini_messages(ai_config.messages or [])
    contents.append(Content(role="user", parts=[Part(text=user_prompt)]))

    params = (ai_config.model.to_dict().get("parameters") if ai_config.model else None) or {}

    def call_gemini():
        return gemini_client.models.generate_content(
            model=ai_config.model.name,
            contents=contents,
            config=GenerateContentConfig(
                system_instruction=system_instruction,
                **gemini_config_kwargs(params),
            ),
        )

    tracker = ai_config.create_tracker()
    # Exceptions are tracked automatically — track_metrics_of catches
    # exceptions, records tracker.track_error(), and re-raises.
    response = tracker.track_metrics_of(gemini_metrics, call_gemini)
    return response.text
```

**Node** — `@google/genai`:

```typescript
import { GoogleGenAI, type Content } from '@google/genai';
import type { LDAIMetrics } from '@launchdarkly/server-sdk-ai';

const genAI = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY! });

const geminiMetrics = (response: any): LDAIMetrics => {
  const usage = response.usageMetadata;
  return {
    success: true,
    tokens: usage
      ? {
          total: usage.totalTokenCount ?? 0,
          input: usage.promptTokenCount ?? 0,
          output: usage.candidatesTokenCount ?? 0,
        }
      : undefined,
  };
};

function mapToGeminiMessages(
  ldMessages?: Array<{ role: string; content: string }>,
): { systemInstruction: string | undefined; contents: Content[] } {
  const contents: Content[] = [];
  const systemParts: string[] = [];
  for (const m of ldMessages ?? []) {
    if (m.role === 'system') systemParts.push(m.content);
    else if (m.role === 'user') contents.push({ role: 'user', parts: [{ text: m.content }] });
    else if (m.role === 'assistant') contents.push({ role: 'model', parts: [{ text: m.content }] });
  }
  return {
    systemInstruction: systemParts.length ? systemParts.join(' ') : undefined,
    contents,
  };
}

// Map config parameter names to @google/genai's GenerateContentConfig keys.
// LaunchDarkly stores max_tokens (snake_case, matching the LD UI); @google/genai
// expects maxOutputTokens. Drop `tools` — they go on GenerateContentConfig.tools
// directly; leaving them here would double-pass.
function geminiConfigFields(params: Record<string, unknown>): Record<string, unknown> {
  const mapping: Record<string, string> = { max_tokens: 'maxOutputTokens' };
  return Object.fromEntries(
    Object.entries(params ?? {})
      .filter(([k]) => k !== 'tools')
      .map(([k, v]) => [mapping[k] ?? k, v]),
  );
}

async function callWithTracking(
  aiConfig: LDAICompletionConfig,
  userPrompt: string,
): Promise<string | null> {
  if (!aiConfig.enabled) return null;

  const { systemInstruction, contents } = mapToGeminiMessages(aiConfig.messages);
  contents.push({ role: 'user', parts: [{ text: userPrompt }] });

  const params = (aiConfig.model?.parameters ?? {}) as Record<string, unknown>;

  const tracker = aiConfig.createTracker();
  // Exceptions are tracked automatically — trackMetricsOf catches
  // exceptions, records tracker.trackError(), and re-throws.
  const response = await tracker.trackMetricsOf(
    geminiMetrics,
    () => genAI.models.generateContent({
      model: aiConfig.model!.name,
      contents,
      config: {
        systemInstruction,
        ...geminiConfigFields(params),
      },
    }),
  );
  return response.text ?? null;
}
```

Notes on the extractor shape:

- Gemini uses `snake_case` in Python (`prompt_token_count`) and `camelCase` in Node (`promptTokenCount`). The LD `TokenUsage` / `LDAIMetrics` type is the same in both.
- `total_token_count` already includes input + output from Google; do not recompute it.
- `success: true` in the extractor is not a lie — `trackMetricsOf` only calls the extractor on the success path. On the error path, `trackMetricsOf` records `trackError()` internally and re-throws; no caller-side catch block is required.

## Tools

LaunchDarkly stores attached tools on `ai_config.model.parameters.tools` in the flat `{type, name, description, parameters}` shape. Gemini's `GenerateContentConfig.tools` expects a list of `{function_declarations: [{name, description, parameters}]}` blocks (Python) or `{functionDeclarations: [...]}` (Node), so convert at runtime:

```python
ld_tools = (params.get("tools") or [])
gemini_tools = [
    {
        "function_declarations": [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in ld_tools
        ],
    }
] if ld_tools else []
```

Tool handlers stay in your application code — LaunchDarkly stores the schema, your application owns the behavior. For the full agent loop pattern (`MAX_STEPS`, `functionCalls` handling, `tracker.track_tool_call`), see the agent-mode section of `launchdarkly-tools`.

## Tier 2 option — route via LangChain

If the app can adopt LangChain, the LangChain provider package handles Gemini (via `@langchain/google-genai` / `langchain-google-genai`) through the standard `trackMetricsOf(getAIMetricsFromResponse, ...)` pattern. The provider package handles LaunchDarkly→LangChain provider-name mapping (for example, `"gemini"` → `"google_genai"`) and forwards all variation parameters automatically, so you do not need your own mapping helper. See [langchain-tracking.md](langchain-tracking.md).

## Tier 4 — Manual (streaming only)

Streaming Gemini needs manual TTFT tracking; the pattern is identical to OpenAI streaming. See [streaming-tracking.md](streaming-tracking.md).

## What NOT to do

- **Do not look for a `track_gemini_metrics` helper** — it does not exist. Gemini support lives in the extractor above.
- **Do not invent a provider package** like `@launchdarkly/server-sdk-ai-gemini` or `launchdarkly-server-sdk-ai-gemini`. Neither exists on npm or PyPI. Check [ai-providers in js-core](https://github.com/launchdarkly/js-core/tree/main/packages/ai-providers) and [python-server-sdk-ai/packages/ai-providers](https://github.com/launchdarkly/python-server-sdk-ai/tree/main/packages/ai-providers) before recommending one.
- **Do not put `role: "system"` items inside `contents`.** Gemini will either ignore them or error. The system prompt goes on `system_instruction` / `systemInstruction`.
- **Do not assume LaunchDarkly stores `maxTokens` (camelCase) as the parameter key.** The UI and the stored variation use `max_tokens`. The mapping helper renames it to `max_output_tokens` / `maxOutputTokens` for Gemini's SDK.
