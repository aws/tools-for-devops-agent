---
name: launchdarkly-metric-choose
description: "Choose the right metrics for a LaunchDarkly experiment, guarded rollout, or release policy. Use when the user wants to know which metrics to use, which is the primary metric for an experiment, what guardrails to add, or which events to monitor in a rollout. Surfaces what will auto-attach from existing release policies before making additional recommendations."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0-experimental"
---

# LaunchDarkly Metric Choose

You're using a skill that helps users select the right metrics before setting up an experiment, guarded rollout, or release policy. Your job is to understand the feature context, surface what will auto-attach from existing project policies, inventory what's available and healthy, and produce a clear typed recommendation.

This skill is advisory. It does not create metrics, attach them to experiments, or configure rollouts. For those tasks, see the related skills at the end of this document.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `list-metrics` — inventory available metrics with their types and event keys
- `list-metric-events` — check which event keys have recent activity

**Optional MCP tools (enhance workflow):**
- `list-release-policies` — fetch project-level policies that configure which metrics auto-attach to guarded rollouts. Use this for the guarded rollout and release policy paths.

## Workflow

### Step 1: Identify the Context

Ask two questions upfront:

1. **What is this for?**
   - **(a) Experiment** — testing a hypothesis with a flag variant
   - **(b) Guarded rollout** — progressively rolling out a change with automatic regression detection
   - **(c) Release policy** — creating or editing a project-wide policy that configures default metrics for all guarded rollouts matching certain conditions

2. **What is the change?**
   - Flag key (if applicable)
   - Plain-language description: "Rolling out a new checkout flow" / "Testing a new recommendation algorithm"

### Step 2: Fetch Existing Configuration (Guarded Rollout and Release Policy only)

**For experiments — skip this step.** There is no pre-existing configuration to surface.

**For guarded rollouts and release policy work**, call `list-release-policies` first:

```
list-release-policies(projectKey)
```

Surface the results before making any recommendations:

```
Your project has 2 release policies:

Policy: "Production guardrails" (applies to: environment=production)
  Auto-attaches to guarded rollouts:
    ✓ api-error-rate  (count, LowerThanBaseline)
    ✓ p95-latency     (value, LowerThanBaseline)
    ✓ [Metric group] Core Platform Health (3 metrics)

Policy: "Default" (applies to: all environments)
  No metrics configured.
```

This tells the user what's already covered before they choose anything additional. For a guarded rollout, these metrics will appear automatically — the recommendation is about what to add on top, not rebuild from scratch.

If no policies exist or none have metrics configured, note that all metrics must be selected manually.

### Step 3: Inventory Available Metrics with Event Health

Call `list-metrics` to see all metrics in the project, then cross-reference with `list-metric-events`.

Organize into two groups:

| Group | Criteria | Note |
|-------|----------|------|
| **Healthy** | Event key appears in `list-metric-events` | Safe to recommend |
| **At-risk** | Event key absent from `list-metric-events` | Warn: may not produce data |

Show this inventory before recommending — it may reveal that a metric the user has in mind has no events flowing.

### Step 4: Recommend

The reasoning differs meaningfully by context.

---

#### (a) Experiment

**Start with the hypothesis, not the metric list.**

Ask the user to complete this sentence before looking at available metrics:

> "If this change succeeds, [metric] will [increase / decrease]."

The primary metric must directly measure that hypothesis — not a proxy, not a correlation. If the user can't complete the sentence, help them get there first.

**Propose one primary metric.** It must:
- Directly measure the hypothesis
- Have events actively flowing
- Have an unambiguous success direction (`HigherThanBaseline` or `LowerThanBaseline`)

**Propose typed secondary metrics.** Suggest at least one of each type that applies:

| Type | Purpose | Example |
|------|---------|---------|
| **Guardrail** | Did the change break anything? | Error rate, crash rate, latency p95 |
| **Counter-metric** | Did A improve at the cost of B? | If primary is conversion, add support tickets or session length |
| **Supporting signal** | Does correlated behavior confirm the hypothesis? | If primary is signup, add onboarding step 2 completion |

One of each type is usually the right amount. More secondary metrics add noise and interpretation burden.

---

#### (b) Guarded Rollout

Guarded rollouts are safety mechanisms, not experiments. Each metric you add is a potential automatic rollback trigger — if it regresses beyond its threshold before the rollout completes, LaunchDarkly can stop and revert the release.

**Start from what auto-attaches.** After surfacing the release policy results in Step 2, ask: "Are the auto-attached metrics enough, or do you want to add more for this specific rollout?"

**When recommending additional metrics:**
- Bias toward reliability — engineering metrics (error rate, latency, crash rate) with stable, predictable baselines
- Avoid exploratory product metrics that are noisy or hard to interpret under regression analysis
- **Fewer is better.** Two or three high-signal metrics is the right size. More than five creates false positive rollback risk.
- **Only recommend metrics with events actively flowing.** An at-risk metric in a guarded rollout either produces no signal or, worse, triggers a false rollback due to data quality issues, not a real regression.

Suggested starting point for any guarded rollout (if not already covered by a policy):
1. Error rate — are we seeing more errors in the new variation?
2. Latency / response time — is the new variation slower?
3. One domain-specific metric tied to the core user action the change affects

---

#### (c) Release Policy

Release policies apply to every rollout in the project that matches their conditions. This is the highest bar.

**Start from the current state.** After surfacing existing policies in Step 2, ask: "Which policy are you editing, or do you want to create a new one? What environments or flag conditions will it apply to?"

**When recommending metrics for a policy:**
- **2–3 metrics maximum.** More than that turns the policy into a burden on every rollout, including ones where the metrics don't apply well.
- **Only recommend metrics with a long, stable event history.** If an event has been flowing reliably for months, it's a safe project-wide default. Occasional gaps will create problems at scale.
- **Push back on additions.** If the user proposes more than 3, ask which ones they'd remove. The discipline of choosing is the point.
- **Explain scope conditions.** A policy scoped to `environment=production` only applies to production rollouts. Help the user think through whether they want the same metrics in staging (where baselines may differ) or a separate policy.

Typical strong policy candidates: error rate, a core conversion or engagement metric, latency.

### Step 5: Deliver the Recommendation

Output a clear, named list. Be explicit about what each metric is for and what's already covered:

```
Recommended metrics for: new checkout flow guarded rollout (environment: production)

AUTO-ATTACHED (from "Production guardrails" policy):
  ✓ api-error-rate    (count, LowerThanBaseline)
  ✓ p95-latency       (value, LowerThanBaseline)

ADDITIONAL — recommended for this rollout:
  ✓ checkout-conversion  (occurrence, HigherThanBaseline)
    → Confirms the rollout isn't degrading the core conversion the feature targets

⚠ page-load-time — no recent events. Instrument the event before including it,
  or remove it from the list to avoid a false rollback trigger.
```

Then close with next steps:
- If a metric the user needs doesn't exist → use the **metric-create** skill
- If an event isn't flowing → use the **metric-instrument** skill
- Once the list is confirmed → configure the guarded rollout or experiment (via the LaunchDarkly UI or API)

## Important Context

- **Mid-experiment metric changes require a restart.** LaunchDarkly snapshots the metric configuration when an experiment starts. Adding, removing, or changing metrics after launch requires stopping the experiment and restarting it — historical data from before the change is not comparable. Raise this immediately if the user mentions they're mid-experiment.
- **A primary metric with no events is worse than no primary metric.** The experiment produces no statistical output. Event health is a hard requirement for the primary metric.
- **CUPED and percentile analysis are incompatible.** If the experiment uses CUPED variance reduction, percentile-based metrics (e.g. p95 latency) silently degrade to mean-based analysis. Flag this if the user selects a percentile metric in a CUPED-enabled experiment.
- **Context kind mismatches cause missing data.** If the metric event is tracked with a `device` context but the experiment randomizes on `user`, the event won't be attributed correctly. Confirm that the context kind in `track()` calls matches the experiment's randomization unit.
- **Release policy metrics must share the same context kind.** All metrics in a guarded rollout release policy must use the same randomization unit. If the user proposes metrics with mismatched context kinds, flag it before they try to configure the policy.

## Related Skills

- [`launchdarkly-metric-create`](../launchdarkly-metric-create/SKILL.md) — create a metric that doesn't exist yet
- [`launchdarkly-metric-instrument`](../launchdarkly-metric-instrument/SKILL.md) — add a `track()` call so events start flowing
