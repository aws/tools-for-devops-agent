---
name: launchdarkly-experiment-setup
description: "Set up and run experiments in LaunchDarkly. Create experiments with metrics, treatments, and flag config, start iterations to collect data, swap design between iterations, and stop with a winner."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "0.3.0"
---

# LaunchDarkly Experiment Setup

You're using a skill that guides you through setting up and running experiments in LaunchDarkly. Your job is to design the experiment, create it with the right metrics, treatments, and flag config, start data collection, evolve the design between iterations when needed, and stop with a winner. Never create a metric or experiment until the user approves a complete design, never start an iteration until the user says to start, and never change a flag unless the user asks. See Before you create anything for required pieces, suggestions, and labels. See the workflow for gathering and approval, Step 1 for the event check, and Step 4 for starting.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `create-experiment` — create a new experiment with its initial iteration (hypothesis, metrics, treatments, flag config).
- `start-experiment-iteration` — begin collecting data for an experiment's current draft iteration.
- `get-experiment` — check experiment status, treatments, metrics, and current iteration.

**Optional MCP tools:**
- `list-experiments` — browse existing experiments in the project.
- `update-experiment` — update fields on the experiment or its current iteration. Honours `mutableFieldsByStatus`, so what's editable depends on whether the iteration is `not_started`, `running`, or `stopped`. Returns rejected inputs under `skipped`.
- `save-and-start-experiment-iteration` — the API-recommended way to change locked fields on a running experiment. Stops the current iteration, creates a new draft with the supplied field updates, and starts it in one call.
- `stop-experiment-iteration` — stop the running iteration. You must declare a winner: pass the `winningTreatmentId` (and a `winningReason`). If no variation outperformed, pick the baseline/control as the winner.
- `list-metrics`, `create-metric`, `list-metric-events` — manage metrics referenced by the experiment.
- `get-flag` — read one flag's targeting in an environment: whether it is on, the variation a rule serves, its off variation, and whether that rule is a percentage rollout.
- `list-flags` — search flags in a project by name or key.
- `create-flag` — create a feature flag in a project. It is off in every environment until turned on.
- `get-flag-status-across-envs` — read a flag's status in each environment (`new`, `active`, `launched`, or `inactive`).
- `search-contexts` — find stored contexts in an environment by kind, to see which context kinds are in use.

## Core Concepts

### What Are Experiments?

Experiments in LaunchDarkly measure the impact of feature flag variations on key metrics. An experiment consists of:

- **Treatments**: the flag variations being compared (control vs. test). Each treatment has an `allocationPercent`; the values across treatments should sum to 100.
- **Metrics**: what you're measuring (conversion rate, latency, revenue, etc.). One must be the primary metric.
- **Flag config**: the `flagKey`, `ruleId`, and `flagConfigVersion` of the targeting rule that drives the experiment.
- **Iteration**: a single data-collection window. Created in `not_started` status, becomes `running` when started, transitions to `stopped` when ended.
- **Holdout** (optional): a project-level group of users excluded from the experiment for baseline measurement (`holdoutId`).

### Experiment Lifecycle

1. **Create** the experiment with its first iteration (`create-experiment`).
2. **Start the iteration** to begin data collection (`start-experiment-iteration`), only after the user explicitly says to start.
3. **Monitor** results as data accumulates (`get-experiment`).
4. **Evolve the design** mid-experiment if needed — change locked fields like `treatments`, `metrics`, or `methodology` by calling `save-and-start-experiment-iteration`, which stops the current iteration, creates a new draft with your changes, and starts it. That call starts data collection, so make it only after the user explicitly says to start.
5. **Stop the iteration** when you have a winner or a clear call (`stop-experiment-iteration`).
6. **Ship** the winning variation.

## Core Principles

1. **Metrics first**: ensure the metrics you'll reference exist before creating the experiment.
2. **Clear hypothesis**: every iteration requires a `hypothesis` string from the user. See Before you create anything.
3. **Proper controls**: exactly one treatment must have `baseline: true`.
4. **Sufficient sample size**: let iterations run long enough to support a decision. See Step 7.
5. **One change at a time**: test one variable per experiment for clear attribution.

## Before you create anything

These three must come from the user. Never fill them in:

- **Flag and variations**: which flag to test, and which of its variations are in the experiment.
- **Hypothesis**: what they expect to improve, and by how much if they know.
- **Primary metric**: the single metric or funnel that decides the result.

If any of these three are missing, leave them blank until the user supplies them. They go in the gather message. See the workflow. Once the user names the flag, see Step 2.

**Control variation**: which of those variations is the baseline (`baseline: true`). If the user named it, use that. If they did not:

- Ask, and leave it blank, when the flag is brand new, the targeted rule serves a percentage rollout, or the flag is off and `get-flag-status-across-envs` reports that environment as `inactive`. A flag is brand new if you created it in this conversation, or `get-flag-status-across-envs` reports that environment as `new`: the flag was created fewer than seven days ago and has never been evaluated there. A percentage rollout is a targeted rule that splits traffic across variations instead of serving one. `get-flag` shows which. `inactive` means the flag has not been evaluated for at least seven days, so no one is currently being served the off variation.
- Otherwise suggest one. If the flag is on, suggest the variation the targeted rule serves today. If the flag is off, suggest its off variation.

**Randomization unit**: the context kind the experiment randomizes on. If the user named it, use that. If they did not, call `search-contexts` for this project and environment. Suggest `user` only when a `kind` of `user` returns contexts and `filter` `kind notEquals "user"` returns `totalCount` 0, so `user` is the only context kind in use. If `search-contexts` is unavailable, returns no contexts, or any other kind is stored, ask and leave it blank.

Label every suggested value in the design as suggested, with a one-line reason, for example `Control (suggested, what users see today): Start free trial`. The user can change any suggestion before approving. Approving the design accepts the suggestions still shown in it.

Settings the user did not mention can stay on LaunchDarkly's defaults. List each default you are using in the design:

- **Traffic split**: equal `allocationPercent` across the variations the user named (two variations is 50/50). The values must sum to 100.
- **Statistics**: LaunchDarkly default (frequentist, sequential testing). Do not send `methodology` unless the user chooses one. If they choose one, send that value and show it here instead of this default. A Bayesian choice is `methodology` `"bayesian"`.
- **Data source**: `dataSource` `"launchdarkly"`.
- **Reshuffle**: `canReshuffleTraffic` `true`.

Leave `analysisConfig` unset unless the user set it, and say that in the design. The randomization unit is never one of these defaults.

## Workflow

If nothing is missing, skip the gather message and go straight to the design. Otherwise gather every missing piece in one message before you show any design, then wait:

- the flag and variations, the hypothesis, or the primary metric, when one is missing
- the named flag, when `get-flag` cannot find it: say so and offer three choices in one message: correct the key (list similar flags from `list-flags`); create the flag themselves, then tell you to continue; or have you create it. For that last choice, propose the key, name, type, and variations from their design, say it will be created off, and wait for an explicit yes before calling `create-flag`. If `launchdarkly-flag-create` is installed, follow it for that step. After the flag exists, continue setup. Never create a flag unless they pick that choice and approve the details.
- the control or the randomization unit, when the rules above say to ask instead of suggest
- for a new primary metric, its kind (`custom`, `pageview`, or `click`), what it is based on (event key, URL match, or click selector), and how it is measured (share of units who converted, a total count, or an average), when the user has not already made that clear

`list-metrics` and `get-flag` are fine while you gather this. `create-metric` and `create-experiment` are not.

If the user's wording already makes one of these clear, do not ask about it. "The share of users who sent the `cta-clicked` event" already names the measure, the kind, and the event key.

Show the design only when nothing is blank. Never show a design with a missing value. Include every piece gathered above, the other treatments, flag config (`flagKey`, `ruleId`, `flagConfigVersion`), and every default you are applying. Statistics reads `LaunchDarkly default (frequentist, sequential testing)` unless the user chose a methodology, in which case show their choice. Label each suggested value. See Before you create anything.

**STOP HERE** until the user approves the design.

Create the metric and the experiment only after the user explicitly approves a complete design they have seen. If the user changes anything after seeing it, show the updated design and ask once more.

### Step 1: Prepare Metrics

1. Use `list-metrics` to find existing metrics. The user names the primary metric.
2. If it already exists, keep its name and key for the design review.
3. If it does not exist, a miss only means the metric is new. The user has often named the metric and not its kind or event key. Gather those before the design. Until the user has said the kind and, for a custom event, the event key:
   - Do not call `list-metric-events`.
   - Do not check the metric name, or any other key the user did not give, as the event key.
   - Do not skip the flow check by treating the metric as `pageview` or `click`.
   - Do not block creation for an event you have not identified.
4. See the gather rule for a new metric's kind, what it is based on, and how it is measured.
5. After the user has said the new metric is `custom` and named its event key, call `list-metric-events` for that event key. Either way, the metric goes in the design once nothing else is blank. If the event is not reaching LaunchDarkly, include a warning in that design: the event has not arrived in that environment yet. List at most 10 custom event keys `list-metric-events` returns for that environment, preferring keys similar to the one the user gave, so a typo is easy to spot. Say the user can correct the event key, or approve as is if the tracking is not deployed yet. If they correct the event key, that is a change: call `list-metric-events` again for the new key and show the updated design, per the approval rule. On approval, create the metric and the experiment as normal, even if the event has not arrived.
6. Pageview and click metrics have no custom event key. Skip `list-metric-events` only after the user has said the kind is `pageview` or `click`.
7. Pass the user-named primary metric as `primarySingleMetricKey` or `primaryFunnelKey`.

| Goal | Metric type | Example key |
|------|-------------|-------------|
| Conversion | Custom conversion | `checkout-completed` |
| Performance | Custom numeric | `page-load-time-ms` |
| Engagement | Custom conversion | `feature-clicked` |
| Revenue | Custom numeric | `order-value` |

### Step 2: Identify the Targeting Rule

You need the `ruleId` and current `flagConfigVersion` of the flag rule that will drive the experiment. Use `get-flag` on the flag (or its environment-scoped status) to find them. The fallthrough rule's id is the string `"fallthrough"`.

### Step 3: Create the Experiment

See the gather and approval rule above, then call `create-metric` for a new metric and `create-experiment`. See Step 1 for the event check.

Call `create-experiment`. The top-level fields describe the experiment; the nested `iteration` object describes the first data-collection window. The values in the example below are the shape of the call, not values to copy. See Before you create anything for the randomization unit.

```json
{
  "projectKey": "my-project",
  "environmentKey": "production",
  "key": "checkout-flow-v2-experiment",
  "name": "Checkout Flow v2 Experiment",
  "description": "Compare the redesigned checkout against the current flow.",
  "tags": ["growth", "checkout"],
  "iteration": {
    "hypothesis": "The redesigned checkout will lift completion rate by 3%.",
    "primarySingleMetricKey": "checkout-completed",
    "metrics": [
      { "key": "checkout-completed" },
      { "key": "checkout-time-seconds" }
    ],
    "treatments": [
      {
        "name": "Control",
        "baseline": true,
        "allocationPercent": 50,
        "parameters": [
          { "flagKey": "checkout-flow-v2", "variationId": "variation-a-id" }
        ]
      },
      {
        "name": "New Checkout",
        "baseline": false,
        "allocationPercent": 50,
        "parameters": [
          { "flagKey": "checkout-flow-v2", "variationId": "variation-b-id" }
        ]
      }
    ],
    "flags": {
      "checkout-flow-v2": {
        "ruleId": "fallthrough",
        "flagConfigVersion": 7
      }
    },
    "randomizationUnit": "user"
  }
}
```

Omit `methodology` unless the user chose one. When they did, set it to that value (`"bayesian"`, `"frequentist"`, or `"export_only"`).

Useful optional top-level fields:
- `holdoutId` — attach an existing holdout.
- `dataSource` — `"launchdarkly"` (default), `"snowflake"`, or `"databricks"`.
- `methodology` — send only when the user chooses one: `"bayesian"`, `"frequentist"`, or `"export_only"`. Omit it otherwise. LaunchDarkly's default is frequentist with sequential testing.
- `analysisConfig` — set only the fields the user set. Leave it unset to keep sequential testing on.

Useful optional iteration fields:
- `attributes` — array of context attribute keys to slice results by (e.g. `["country", "device"]`).
- `covariateId` — covariate CSV id for stratified sampling.
- `canReshuffleTraffic` — defaults to `true`; set `false` to lock users to their initial variation when allocations change.

### Step 4: Start Data Collection

Creating the experiment leaves the iteration in `not_started`. Call `start-experiment-iteration` only after the user explicitly says to start. That same wait applies to any other call that starts an iteration.

```json
{
  "projectKey": "my-project",
  "environmentKey": "production",
  "experimentKey": "checkout-flow-v2-experiment"
}
```

Before starting, the API requires that:
- the flag is toggled on,
- the iteration has a `randomizationUnit`, and
- at least one treatment has a non-zero `allocationPercent`.

If the primary metric is a custom event, call `list-metric-events` again right before starting. If the event is arriving, start as normal once the flag is on. If it still is not arriving, the experiment can start but results will stay empty until the event arrives, so ask whether to start anyway.

If the flag is off in that environment when the user says to start, don't change the flag. Tell the user the flag must be on in that environment, and that turning it on starts serving its variations to users there. Ask whether they want to turn it on themselves or have you do it, and wait for an explicit answer before calling any tool that changes the flag. Once the flag is on, call `get-flag` again to get the current `flagConfigVersion`, update the draft to use it, and tell the user you did, before starting.

If the flag is off and the custom event still is not arriving, raise both in one message, the flag question and whether to start anyway, and wait for that one answer. Do not ask them separately.

Pass `changeJustification` if you're restarting after a prior iteration was stopped.

### Step 5: Verify

1. After the user has asked you to start, call `get-experiment` and confirm `currentIteration.status === "running"`.
2. Check that treatments are present with the expected allocations.
3. Check the metric list and the primary metric.

### Step 6: Evolve the Design Mid-Experiment (when needed)

Most structural fields (treatments, metrics, methodology, hypothesis, …) are locked while an iteration is `running`. Two ways to change them:

- **Light edits while running** — `update-experiment` will let through anything `mutableFieldsByStatus` permits in the `running` state (typically just metadata like `name`, `description`, `maintainerId`, `tags`, plus appending `metrics`/`attributes`). It surfaces rejected fields under `skipped` with a reason.
- **Real design changes** — call `save-and-start-experiment-iteration`. It stops the current iteration, creates a new draft with the supplied field updates applied, and starts it in one call. Inputs match `update-experiment`, plus `changeJustification`. Mutability is checked against `not_started` since updates land on the new draft.

`save-and-start-experiment-iteration` starts the new iteration. Show the change, then wait until the user explicitly says to start before calling it.

Example: swap the treatment allocation and add a metric in a single call.

```json
{
  "projectKey": "my-project",
  "environmentKey": "production",
  "experimentKey": "checkout-flow-v2-experiment",
  "changeJustification": "Lowering control allocation now that variant looks safe.",
  "treatments": [
    {
      "name": "Control",
      "baseline": true,
      "allocationPercent": 30,
      "parameters": [{ "flagKey": "checkout-flow-v2", "variationId": "variation-a-id" }]
    },
    {
      "name": "New Checkout",
      "baseline": false,
      "allocationPercent": 70,
      "parameters": [{ "flagKey": "checkout-flow-v2", "variationId": "variation-b-id" }]
    }
  ],
  "metrics": [
    { "key": "checkout-completed" },
    { "key": "checkout-time-seconds" },
    { "key": "checkout-error-rate" }
  ]
}
```

### Step 7: Stop the Iteration

When the results support a decision, or the user has made a call, stop the iteration. For a frequentist experiment that decision is statistical significance. For a Bayesian experiment it is the probability to beat baseline or the probability to be best. Quote only the statistic for the methodology in use. **A winning treatment is required to stop** — LaunchDarkly does not let you end an iteration without declaring a winner. Pass the winning treatment's id (returned in `get-experiment` as `_id` on each treatment) plus a `winningReason`.

If the experiment was inconclusive or no variation beat the control, declare the **baseline/control treatment as the winner** and say so in `winningReason` (e.g. "Inconclusive — keeping control"). There is no "stop without a winner" path.

```json
{
  "projectKey": "my-project",
  "environmentKey": "production",
  "experimentKey": "checkout-flow-v2-experiment",
  "winningTreatmentId": "treat-002",
  "winningReason": "Two weeks of data, +4.1% lift on the primary metric."
}
```

Name the decision statistic in `winningReason`. Frequentist: significance, or that it was not significant. Bayesian: probability to beat baseline or probability to be best. Do not quote a Bayesian probability, or a prior, on a frequentist experiment.

**Report results:**
- Iteration stopped with the declared `winningTreatmentId` (the control/baseline if inconclusive).
- Lift on the primary metric, plus the decision statistic for the methodology in use.
- Next steps (ship the winner, roll back, or start a follow-up iteration).

## Edge Cases

| Situation | Action |
|-----------|--------|
| A new primary metric's kind or event key is unknown | Gather them before the event check. See Step 1. |
| The new metric is a custom event and the user named its event key | Warn in the design if it has not arrived; still create on approval. See Step 1. |
| Flag, variations, hypothesis, or primary metric is missing | Ask, and leave them blank. See Before you create anything. |
| The named flag does not exist in the project | Offer to correct the key, have them create it, or create it after they approve the details. Never create a flag otherwise. See the gather rule. |
| User did not name the control, and the rules say to ask | Ask for the control; don't suggest one. See Before you create anything. |
| User did not name the control, and the rules say to suggest | Suggest the control and label it. See Before you create anything. |
| User did not name the randomization unit | Suggest or ask for the randomization unit. See Before you create anything. |
| Design not approved | Leave `create-metric` and `create-experiment` uncalled. See the gather and approval rule above. |
| User has not said to start | Leave the iteration in `not_started`. `start-experiment-iteration` and `save-and-start-experiment-iteration` stay uncalled. |
| Flag is off when the user says to start | Don't change the flag; ask first. See Step 4. |
| Flag has no variations to compare | Add variations only when the user explicitly asks. Otherwise say which variations exist and ask. |
| You don't know the flag's `ruleId` / `flagConfigVersion` | Use `get-flag` or `get-flag-status-across-envs`. The fallthrough rule's id is the string `"fallthrough"`. |
| Experiment already exists | Use `list-experiments` to find it; `get-experiment` for details. |
| Need to change locked fields mid-experiment | Use `save-and-start-experiment-iteration` (single call) rather than stopping and recreating by hand. |
| `update-experiment` returns `skipped` for a field | Inspect the `currentStatus` and `allowedFields` in the response — that field isn't mutable in the current iteration status. Either stop the iteration first or use `save-and-start-experiment-iteration`. |

## What NOT to Do

- Don't fill in a required piece yourself, or present a suggestion without labeling it as suggested. See Before you create anything.
- Don't call `list-metric-events` before Step 1 says to, or block creation because an event has not arrived. See Step 1.
- Don't call `create-metric` or `create-experiment` before the approval rule above is satisfied.
- Don't call `start-experiment-iteration` or `save-and-start-experiment-iteration` until the user explicitly says to start.
- Don't turn a flag on or off, or change its targeting, unless the user explicitly asks you to.
- Don't create a flag unless the user asks you to and approves the proposed key, name, type, and variations. See the gather rule.
- Don't omit `iteration` on `create-experiment` — it's required.
- Don't set `baseline: true` on more than one treatment.
- Don't let `allocationPercent` values fail to sum to 100 across treatments.
- Don't try to change locked iteration fields with `update-experiment` while the iteration is `running` — reach for `save-and-start-experiment-iteration` instead.
- Don't stop iterations early — wait for a decision the methodology supports. See Step 7.
- Don't run multiple experiments on the same flag at the same time without a careful holdout design.
