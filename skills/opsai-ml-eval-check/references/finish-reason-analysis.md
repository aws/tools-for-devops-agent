# Finish-Reason Drift Analysis

**A small check with outsized value.** The finish-reason distribution is an early,
otherwise-invisible indicator of quality regression that **no AWS alarm watches by default**. It
costs almost nothing to monitor and it moves *before* users file complaints — which is exactly why
the OpsAI strategy calls it out as a first-class quality signal rather than a footnote.

This reference backs two checks:

- **LLM-EVAL-012** — the finish-reason distribution *shift itself* (the regression signal).
- **LLM-EVAL-013** — the *metric filter being absent*, so the shift can never be seen. This is the
  in-skill id for an absent `stopReason` metric filter.

---

## Why the finish-reason distribution is a quality signal

Every Bedrock invocation ends for a reason, recorded in the `stopReason` field of the invocation
log. Over a healthy, stable workload the mix of those reasons is roughly constant. When the mix
*moves* — specifically when more and more responses end in `max_tokens` (truncation) instead of
`end_turn` (natural completion) — the model is increasingly being cut off mid-answer. Truncated
answers read as lower quality to users (dropped conclusions, half-finished code, missing final
steps), but nothing in the default `AWS/Bedrock` metric set surfaces it. Latency looks fine; error
rates look fine; invocation counts look fine. The only visible symptom is a slow drift in a
distribution nobody is trending.

Because the shift **precedes visible quality complaints by hours or days**, catching it early turns
a user-reported quality incident into a quiet, pre-emptive fix.

---

## The `stopReason` field values

| Value | Meaning |
|---|---|
| `end_turn` | Natural completion — the model finished its answer on its own. The healthy majority case. |
| `max_tokens` | **Truncation** — the model hit the output token limit and was cut off. The value to watch. |
| `stop_sequence` | The model emitted a configured stop sequence and halted (usually expected). |
| `tool_use` | The model paused to invoke a tool (agentic / tool-calling flows). |
| `guardrail_intervened` | A guardrail blocked or altered the response before completion. |

A stable workload is dominated by `end_turn` (plus `tool_use` for agentic flows). A rising
`max_tokens` share is the regression indicator.

---

## What a shift from `end_turn` toward `max_tokens` means

A growing `max_tokens` share means outputs are being cut off. The three usual causes:

1. **Prompts grew.** A prompt-template change, a larger retrieved-context window, or longer
   conversation history crowds the output budget — the input eats into the room left for the
   response, so more answers hit the ceiling.
2. **`maxTokens` was reduced.** A configuration or deployment change lowered the output cap, so
   responses that used to complete now truncate.
3. **A model version changed generation length.** A new model/version generates longer answers for
   the same prompt and bumps into the existing cap.

In every case the shift **precedes visible quality complaints by hours or days** — users notice
truncated answers only after the drift is well underway. When the shift correlates with a known
deployment, treat the deployment as the prime suspect: roll back or adjust the output budget.

---

## How to measure it

**Prerequisite: model invocation logging must be enabled** (otherwise `stopReason` is never
emitted — this is a Bedrock invocation-logging area check). Without
it, LLM-EVAL-013 fires: the signal is simply invisible.

Once logging is on:

1. Create a CloudWatch Logs **metric filter** on the Bedrock invocation log group:
   ```
   { $.stopReason = "max_tokens" }
   ```
2. Publish it as a **custom metric** (for example namespace `OpsAI/FinishReason/MaxTokens` with a
   `ModelId` dimension).
3. **Alarm** when the 1-hour `max_tokens` rate exceeds the established baseline by **more than 10
   percentage points**.

> The **>10pp threshold is DERIVED, not AWS-published.** AWS documents the `stopReason` field and the
> metric-filter mechanism, but not a numeric drift bar. Treat 10pp as a sensible starting default and
> tune it per workload; report it as a derived/`workload-specific` value, never as an AWS number.

### Logs Insights query — compute the distribution

To see the full distribution (not just the `max_tokens` count), run this CloudWatch Logs Insights
query over the invocation log group:

```
fields @timestamp, modelId, output.stopReason
| filter ispresent(output.stopReason)
| stats count(*) as invocations by output.stopReason, modelId
| sort invocations desc
```

Compare the `max_tokens` share across two windows (baseline vs current) to quantify the shift.

---

## Correlated signals

A finish-reason drift rarely travels alone. Corroborate it with:

- **`OutputTokenCount` spikes** — responses getting longer is often the leading edge of a truncation
  shift (and always raises cost). This is check **LLM-EVAL-014**.
- **`InvocationLatency` rising** — longer generations take longer, so latency often creeps up
  alongside the drift.
- **User complaints about truncated / cut-off answers** — the lagging, human-visible symptom the
  distribution shift precedes.

If the `max_tokens` share is climbing *and* `OutputTokenCount` is climbing *and* a prompt or model
change landed in the same window, the diagnosis is strong: outputs grew, the output budget is being
exhausted, and quality is regressing through truncation.

---

## Linked checks

| check-id | Family | What it covers |
|---|---|---|
| LLM-EVAL-012 | Evaluation | The finish-reason distribution **shift itself** — the regression signal. |
| LLM-EVAL-013 | Evaluation | **No metric filter** on `stopReason`, so the shift cannot be trended. |
| LLM-EVAL-014 | Evaluation | **`OutputTokenCount` rising** with flat `Invocations` — the correlated precursor. |
