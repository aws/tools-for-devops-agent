---
name: launchdarkly-guarded-rollout
description: "Configure guarded rollouts with progressive traffic increases, metric monitoring, and automatic rollback. Use when releasing features gradually with safety thresholds."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: "nieblara"
  version: "1.0.0"
  summary: "Roll out a LaunchDarkly flag in guarded stages that watch metrics and roll back automatically on a regression."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "CHAT"
---

# LaunchDarkly Guarded Rollouts

You're using a skill that will guide you through configuring guarded rollouts in LaunchDarkly. Your job is to design rollout stages, select monitoring metrics, choose which regressions roll back automatically, and start the rollout.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `start-guarded-rollout` -- start a progressive rollout with monitoring
- `get-flags` -- inspect the flag and its variations
- `get-metrics` -- find metrics to monitor during the rollout

**Optional MCP tools:**
- `stop-guarded-rollout` -- halt an active rollout immediately
- `toggle-flag` -- ensure the flag is turned on before starting
- `create-metric` -- create metrics if they don't exist

## Core Concepts

### What Are Guarded Rollouts?

A guarded rollout progressively increases traffic to a new feature flag variation through a series of stages. At each stage, LaunchDarkly monitors selected metrics for regressions. If a regression is detected, the rollout can automatically pause and notify the team — or even roll back.

### Key Components

| Component | Description |
|-----------|-------------|
| **Test variation** | The new variation being rolled out |
| **Control variation** | The existing/baseline variation |
| **Stages** | Steps with increasing traffic percentage and monitoring windows |
| **Metrics** | What to monitor for regressions (error rate, latency, etc.) |
| **Auto-rollback** | Per metric: whether a regression rolls back automatically or only notifies |

### Rollout Weight Units

Rollout weights use thousandths (basis points):
- `1000` = 1%
- `10000` = 10%
- `50000` = 50%, the maximum for a guarded stage

### Monitoring Window

The monitoring window is specified in milliseconds:
- `3600000` = 1 hour
- `86400000` = 24 hours
- `604800000` = 7 days

## Core Principles

1. **Start Small**: Begin with a low percentage (1-5%) to catch issues early
2. **Monitor What Matters**: Choose metrics that reflect user experience
3. **Choose Rollback Deliberately**: Auto-roll back on metrics that signal real harm; notify only on noisy ones
4. **Allow Time**: Each stage needs enough monitoring time for signal to emerge
5. **Have a Rollback Plan**: Always configure at least notification on regression

## Workflow

### Step 1: Prepare

Before starting a guarded rollout:

1. Use `get-flags` with `flagKey` and `env` to inspect the flag — note the variation IDs for test and control
2. Use `get-metrics` to find metrics suitable for monitoring
3. Ensure the flag is **on** in the target environment (if needed, call `toggle-flag` with `on: true` and `confirm: true`)
4. Confirm there's no active guarded rollout on this flag already

### Step 2: Design Stages

Plan the rollout progression. A typical pattern:

| Stage | Traffic | Monitoring Window | Purpose |
|-------|---------|-------------------|---------|
| 1 | 1% | 1 hour | Smoke test — catch obvious crashes |
| 2 | 10% | 24 hours | Early signal on metrics |
| 3 | 50% | 24 hours | Confidence building |

Each stage's `rolloutWeight` is capped at 50000 (50%). Do not add a 100% stage: after the last stage passes, LaunchDarkly completes the rollout.

### Step 3: Configure Metrics

Select metrics that indicate problems. Each metric entry takes exactly `key` (a metric or metric group key), `isGroup`, and `autoRollback` (roll back automatically on regression, or only notify):

| Metric Type | Example | `autoRollback` |
|-------------|---------|----------------|
| Error rate | `api-error-rate` | `true` |
| Latency | `p99-response-time` | `false` (notify only) |
| Conversion | `checkout-completed` | `true` |

### Step 4: Start the Rollout

Use `start-guarded-rollout`:

```json
{
  "projectKey": "my-project",
  "flagKey": "new-checkout-flow",
  "environmentKey": "production",
  "testVariationId": "variation-id-for-new-flow",
  "controlVariationId": "variation-id-for-current-flow",
  "randomizationUnit": "user",
  "stages": [
    {"rolloutWeight": 1000, "monitoringWindowMilliseconds": 3600000},
    {"rolloutWeight": 10000, "monitoringWindowMilliseconds": 86400000},
    {"rolloutWeight": 50000, "monitoringWindowMilliseconds": 86400000}
  ],
  "metrics": [
    {"key": "api-error-rate", "isGroup": false, "autoRollback": true},
    {"key": "checkout-completed", "isGroup": false, "autoRollback": true}
  ]
}
```

### Step 5: Verify

1. Use `get-flags` with `flagKey` and `env` to confirm the guarded rollout is active
2. Check that the flag shows the rollout configuration in the environment
3. Monitor for any immediate regression notifications

**Report results:**
- Guarded rollout started with N stages
- M metrics being monitored
- First stage at X% traffic for Y hours

## Stopping a Rollout

If issues arise or you need to halt the rollout, call `stop-guarded-rollout`:

```json
{
  "projectKey": "my-project",
  "flagKey": "new-checkout-flow",
  "environmentKey": "production",
  "confirm": true
}
```

Without `outcome`, stopping rolls back: the flag serves the control variation. To keep the new variation instead, pass `outcome: "rollForward"`; that can fail if the rollout has already moved past that phase. For a rollout on a targeting rule rather than the default rule, add its `ruleId`.

## Edge Cases

| Situation | Action |
|-----------|--------|
| Flag is off | Turn it on first with `toggle-flag` (`on: true`, `confirm: true`) — rollouts require the flag to be on |
| Active rollout exists | Stop it first with `stop-guarded-rollout` before starting a new one |
| No suitable metrics | Create metrics first with `create-metric` |
| Approval required | The tool returns `requiresApproval: true` and how to submit the change with `create-approval-request`; share that request's `approvalRequest.url` |

## What NOT to Do

- Don't start a guarded rollout on a flag that's turned off
- Don't skip the monitoring window design — rushing through stages defeats the purpose
- Don't forget to configure at least one metric — a rollout without monitoring is just a regular rollout
