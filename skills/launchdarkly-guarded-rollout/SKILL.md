---
name: launchdarkly-guarded-rollout
description: "Configure guarded rollouts with progressive traffic increases, metric monitoring, and automatic rollback. Use when releasing features gradually with safety thresholds."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "0.1.0"
---

# LaunchDarkly Guarded Rollouts

You're using a skill that will guide you through configuring guarded rollouts in LaunchDarkly. Your job is to design rollout stages, select monitoring metrics, configure regression thresholds, and start the rollout.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `start-guarded-rollout` -- start a progressive rollout with monitoring
- `get-flag` -- inspect the flag and its variations
- `list-metrics` -- find metrics to monitor during the rollout

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
| **Regression threshold** | How much a metric can degrade before triggering action |
| **On regression** | Whether to notify, rollback, or both when a threshold is breached |

### Rollout Weight Units

Rollout weights use thousandths (basis points):
- `1000` = 1%
- `10000` = 10%
- `50000` = 50%
- `100000` = 100%

### Monitoring Window

The monitoring window is specified in milliseconds:
- `3600000` = 1 hour
- `86400000` = 24 hours
- `604800000` = 7 days

## Core Principles

1. **Start Small**: Begin with a low percentage (1-5%) to catch issues early
2. **Monitor What Matters**: Choose metrics that reflect user experience
3. **Set Realistic Thresholds**: Too tight = false alarms; too loose = missed regressions
4. **Allow Time**: Each stage needs enough monitoring time for signal to emerge
5. **Have a Rollback Plan**: Always configure at least notification on regression

## Workflow

### Step 1: Prepare

Before starting a guarded rollout:

1. Use `get-flag` to inspect the flag — note the variation IDs for test and control
2. Use `list-metrics` to find metrics suitable for monitoring
3. Ensure the flag is **on** in the target environment (use `toggle-flag` if needed)
4. Confirm there's no active guarded rollout on this flag already

### Step 2: Design Stages

Plan the rollout progression. A typical pattern:

| Stage | Traffic | Monitoring Window | Purpose |
|-------|---------|-------------------|---------|
| 1 | 1% | 1 hour | Smoke test — catch obvious crashes |
| 2 | 10% | 24 hours | Early signal on metrics |
| 3 | 50% | 24 hours | Confidence building |
| 4 | 100% | 24 hours | Full rollout with monitoring |

### Step 3: Configure Metrics

Select metrics that indicate problems:

| Metric Type | Example | Threshold | Action |
|-------------|---------|-----------|--------|
| Error rate | `api-error-rate` | 0.05 (5% increase) | Rollback |
| Latency | `p99-response-time` | 0.2 (20% increase) | Notify |
| Conversion | `checkout-completed` | 0.1 (10% decrease) | Notify + Rollback |

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
    {"rolloutWeight": 50000, "monitoringWindowMilliseconds": 86400000},
    {"rolloutWeight": 100000, "monitoringWindowMilliseconds": 86400000}
  ],
  "metrics": [
    {
      "metricKey": "api-error-rate",
      "onRegression": {"notify": true, "rollback": true},
      "regressionThreshold": 0.05
    },
    {
      "metricKey": "checkout-completed",
      "onRegression": {"notify": true, "rollback": false},
      "regressionThreshold": 0.1
    }
  ]
}
```

### Step 5: Verify

1. Use `get-flag` to confirm the guarded rollout is active
2. Check that the flag shows the rollout configuration in the environment
3. Monitor for any immediate regression notifications

**Report results:**
- Guarded rollout started with N stages
- M metrics being monitored
- First stage at X% traffic for Y hours

## Stopping a Rollout

If issues arise or you need to halt the rollout:

```json
{
  "projectKey": "my-project",
  "flagKey": "new-checkout-flow",
  "environmentKey": "production"
}
```

This immediately stops the progressive rollout and locks the flag at its current state.

## Edge Cases

| Situation | Action |
|-----------|--------|
| Flag is off | Turn it on first with `toggle-flag` — rollouts require the flag to be on |
| Active rollout exists | Stop it first with `stop-guarded-rollout` before starting a new one |
| No suitable metrics | Create metrics first with `create-metric` |
| Approval required | If the environment requires approvals, the tool will return an approval URL |

## What NOT to Do

- Don't start a guarded rollout on a flag that's turned off
- Don't skip the monitoring window design — rushing through stages defeats the purpose
- Don't set regression thresholds to 0 — small fluctuations are normal
- Don't forget to configure at least one metric — a rollout without monitoring is just a regular rollout
