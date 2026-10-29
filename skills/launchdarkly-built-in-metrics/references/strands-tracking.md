# Strands Agents Metrics Tracking

**There is no LaunchDarkly provider package for Strands.** Strands is a provider-agnostic agent SDK — the same `Agent` class runs against Anthropic, OpenAI, and Bedrock by swapping the `model` argument — so the tracking pattern plugs in at the agent layer, not the provider layer. Tier 3 (custom extractor + `trackMetricsOf`) is the canonical path.

The Strands `AgentResult` object exposes a `metrics.accumulated_usage` dict (Python) / `metrics.accumulatedUsage` object (Node) that already aggregates token counts across every provider call the agent made in a single `invoke_async` turn — including any tool-calling round trips. That means one extractor call covers the whole turn, unlike the per-response shape from Anthropic or OpenAI direct.

The key names inside `accumulated_usage` are camelCase even in Python: `inputTokens`, `outputTokens`, `totalTokens`.

## Tier 1 is not available

`ManagedModel` does not currently ship a Strands runner. Strands owns its own agent loop and short-term memory (`SlidingWindowConversationManager`), so wrapping it in a LaunchDarkly managed runner would fight against the framework. Stay on Tier 3.

## Tier 3 — Explicit `track_duration_of` + manual `track_tokens` (primary)

This is the shape in the LaunchDarkly Strands integration guide. Use it when the call site is already async and you want token extraction split out from duration tracking.

```python
from ldai.tracker import TokenUsage


def track_strands_metrics(tracker, result):
    """Record token usage from a Strands AgentResult on the LD tracker."""
    usage = getattr(result.metrics, "accumulated_usage", {}) or {}
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    total = usage.get("totalTokens", 0) or (input_tokens + output_tokens)
    if total > 0:
        tracker.track_tokens(
            TokenUsage(input=input_tokens, output=output_tokens, total=total)
        )


async def run_turn(agent, tracker, user_input):
    try:
        result = await tracker.track_duration_of(lambda: agent.invoke_async(user_input))
        tracker.track_success()
        track_strands_metrics(tracker, result)
        return result.message["content"][0]["text"]
    except Exception:
        tracker.track_error()
        raise
```

**What this tracks:**
- Duration — from the `track_duration_of` wrapper around `invoke_async`.
- Tokens — from `accumulated_usage`, including any tool-calling round trips inside the turn.
- Success / error — explicit, in the try/except.

## Tier 3 — Single-call `track_metrics_of_async` variant

If you prefer the single-call form that matches the rest of the provider-tracking references, fold the extractor into an `LDAIMetrics` return and use `track_metrics_of_async`:

```python
from ldai.providers.types import LDAIMetrics, TokenUsage


def strands_extractor(result) -> LDAIMetrics:
    usage = getattr(result.metrics, "accumulated_usage", {}) or {}
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    total = usage.get("totalTokens", 0) or (input_tokens + output_tokens)
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(input=input_tokens, output=output_tokens, total=total),
    )


async def run_turn(agent, tracker, user_input):
    # Exceptions are tracked automatically — track_metrics_of_async catches
    # exceptions, records tracker.track_error(), and re-raises.
    result = await tracker.track_metrics_of_async(
        strands_extractor,
        lambda: agent.invoke_async(user_input),
    )
    return result.message["content"][0]["text"]
```

Pick the style that matches the rest of the codebase — the two variants record the same metrics.

## Provider dispatch stays in your code

Strands model classes are provider-specific (`AnthropicModel`, `OpenAIModel`, `BedrockModel`). To serve more than one provider from a single config key, dispatch on `agent_config.provider.name` before constructing the `Agent`. See [agent-mode-frameworks.md § Strands Agent](../../launchdarkly-migrate/references/agent-mode-frameworks.md) for the `create_strands_model` dispatcher, including the rule that `parameters.tools` must be dropped before being passed into the Strands model class (tools flow through the `Agent` constructor, not through model params).

## Always flush before exit

Strands examples are commonly short-lived scripts (`python run_agent.py ...`). Trailing analytics events can be lost if the client closes before flushing. Always call `ldclient.get().flush()` (and `ldclient.get().close()` on exit) after the last turn.

## Node / TypeScript caveat

The Strands TypeScript SDK ships `BedrockModel` and `OpenAIModel` only — no `AnthropicModel`. The same Tier-3 pattern applies (custom extractor over `result.metrics.accumulatedUsage`, then `tracker.trackMetricsOf` or explicit `trackDurationOf` + `trackTokens`), but multi-provider variations that include Anthropic require the Python SDK today.
