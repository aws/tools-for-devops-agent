---
name: launchdarkly-custom-metrics
description: "Create, track, retrieve, update, and delete custom business metrics for configs. Covers full lifecycle: define metrics with the LaunchDarkly MCP server, emit events via SDK, and query results."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server. SDK examples use `launchdarkly-ai-server` 0.3.0+ (Python) or `@launchdarkly/ai-node` 0.3.0+ (Node.js).
metadata:
  author: "nieblara"
  version: "1.0.0"
  summary: "Define custom business metrics for AgentControl configs, check that their events arrive and read the results."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "CHAT"
---

# Custom Metrics for Configs

Full lifecycle management of custom business metrics: create metric definitions with the MCP server, track events via SDK, retrieve metric data, and update or delete metrics.

## Prerequisites

- LaunchDarkly AI SDK initialized in the application that sends the events. The SDK reads `LD_SDK_KEY` from the environment.
- The remotely hosted LaunchDarkly MCP server configured in your environment

## API Access

Use the LaunchDarkly MCP server tools: they authenticate with the connection the customer set up. Create metrics with `create-metric`, check that events are arriving with `get-metric-events`, read definitions with `get-metrics`, and change or remove them with `update-metric` and `delete-metric`. Never ask the user for an API access token.

## Metrics Lifecycle Overview

| Step | Method | Purpose |
|------|--------|---------|
| 1. Create | MCP `create-metric` | Define metric in LaunchDarkly |
| 2. Track | SDK | Send events to the metric |
| 3. Get | MCP `get-metrics` (with `metricKey` for one), `get-metric-events` | Retrieve metric definition/data |
| 4. Update | MCP `update-metric` | Modify metric properties |
| 5. Delete | MCP `delete-metric` | Remove metric |

## 1. Create Metric

Call `create-metric`. `eventKey` must match the key your code passes to `track()`:

```json
{
  "projectKey": "support-ai",
  "key": "ai.task.completion",
  "name": "Agent Task Completion Rate",
  "kind": "custom",
  "eventKey": "ai.task.completion",
  "measureType": "value",
  "valueAggregation": "average",
  "successCriteria": "HigherThanBaseline",
  "unit": "count",
  "description": "Tracks successful agent task completions"
}
```

`measureType` is `count` (how many times the event fired), `occurrence` (whether each user fired it at all), or `value` (a number sent with the event). Then confirm with `get-metrics` and `metricKey`.

**Metric Kinds:**
- `custom` - Track any event (most common for agent metrics)
- `pageview` - Track page views
- `click` - Track click events

**Success Criteria** (for numeric metrics):
- `HigherThanBaseline` - Higher values are better (e.g., revenue, satisfaction)
- `LowerThanBaseline` - Lower values are better (e.g., errors, latency)

**Common Units:**
- `count` - Generic count
- `milliseconds` - Time duration
- `percent` - Percentage values
- `dollars` - Currency

## 2. Track Events (SDK)

Once the metric is created, track events with the client the AI SDK manages. `get_client()` returns the underlying LaunchDarkly server SDK client, so `track()` takes a `Context`, optional data, and a numeric value:

```python
from ldclient import Context
from launchdarkly_ai_server import get_client, init_client

await init_client()  # reads LD_SDK_KEY
ld_client = get_client()

def track_metric(ld_client, user_id: str, metric_key: str, value: float, data: dict = None):
    """Track an event to a metric."""
    context = Context.builder(user_id).build()

    ld_client.track(
        metric_key,
        context,
        data=data,
        metric_value=value
    )
```

### Attribute Metrics to a Config Variation

To see a custom metric next to a config's built-in metrics, and to compare it across variations, send the `track_data` (`trackData`) from the `invoke()` result as the event data. It carries the config key, variation key, version, and model:

```python
from ldclient import Context
from launchdarkly_ai_server import config, get_client

context = {"kind": "user", "key": "user-123"}
result = await config(key="support-agent", handler=handler).invoke(user_input, context)

resolved = customer_confirmed_resolution(result.response)
get_client().track(
    "ai.task.completion",
    Context.from_dict(context),
    result.track_data,
    1.0 if resolved else 0.0,
)
```

```typescript
import { config, getClient } from '@launchdarkly/ai-node';

const context = { kind: 'user', key: 'user-123' };
const result = await config({ key: 'support-agent', handler }).invoke(userInput, context);

const resolved = customerConfirmedResolution(result.response);
getClient().track('ai.task.completion', context, result.trackData, resolved ? 1 : 0);
```

> **Note:** `invoke()` takes the context as a plain dict, but the Python `track()` needs an `ldclient` `Context`, so convert it with `Context.from_dict()`. Node.js accepts the same object in both places.

### Common Tracking Patterns

```python
def track_conversion(ld_client, user_id: str, amount: float, config_key: str):
    """Track a conversion event with revenue."""
    context = Context.builder(user_id).build()

    ld_client.track(
        "business.conversion",
        context,
        data={"configKey": config_key, "category": "electronics"},
        metric_value=amount
    )

def track_task_success(ld_client, user_id: str, task_type: str, success: bool):
    """Track task completion success/failure."""
    context = Context.builder(user_id).build()

    ld_client.track(
        "task.success_rate",
        context,
        data={"taskType": task_type},
        metric_value=1.0 if success else 0.0
    )

def track_satisfaction(ld_client, user_id: str, score: float, feedback_type: str):
    """Track user satisfaction (0-100 scale)."""
    context = Context.builder(user_id).build()

    ld_client.track(
        "user.satisfaction",
        context,
        data={"feedbackType": feedback_type},
        metric_value=score
    )

    # Track negative feedback separately for alerts
    if score < 50:
        ld_client.track(
            "user.negative_feedback",
            context,
            metric_value=1.0
        )

def track_revenue(ld_client, user_id: str, revenue: float, source: str):
    """Track revenue generated after agent interaction."""
    context = Context.builder(user_id).set("tier", "premium").build()

    if revenue > 0:
        ld_client.track(
            "revenue.impact",
            context,
            data={"source": source},
            metric_value=revenue
        )
```

## 3. Get Metrics

Use `get-metrics` with `metricKey` for one metric, or without it for all of them. After you start tracking, `get-metric-events` shows which event keys have arrived, which is the fastest way to catch an `eventKey` that doesn't match `track()`.

## 4. Update Metric

Call `update-metric` with the project key, the metric key and only the fields to change. Each field replaces the current value, so `tags` must list every tag the metric should keep. Tell the user what will change and wait for their confirmation before the call, then confirm the result with `get-metrics` and `metricKey`.

## 5. Delete Metric

Deleting a metric is permanent. Call `get-metrics` with `metricKey` first to see what uses it, tell the user, and call `delete-metric` only after they confirm. LaunchDarkly refuses to delete a metric that a flag, experiment, guarded rollout, metric group or release policy still uses.

## Session Metrics Tracker

```python
import time
from ldclient import Context

class SessionMetricsTracker:
    """Track metrics across an entire user session."""

    def __init__(self, ld_client):
        self.ld_client = ld_client
        self.session_data = {}

    def start_session(self, user_id: str, session_id: str):
        """Initialize session tracking."""
        self.session_data[session_id] = {
            "user_id": user_id,
            "start_time": time.time(),
            "interactions": 0,
            "successful_tasks": 0
        }

    def track_interaction(self, session_id: str, success: bool):
        """Track individual interaction within session."""
        if session_id not in self.session_data:
            return
        session = self.session_data[session_id]
        session["interactions"] += 1
        if success:
            session["successful_tasks"] += 1

    def end_session(self, session_id: str):
        """Finalize and track session metrics."""
        if session_id not in self.session_data:
            return None

        session = self.session_data[session_id]
        duration = time.time() - session["start_time"]

        context = Context.builder(session["user_id"]).build()

        # Track session duration
        self.ld_client.track(
            "session.duration",
            context,
            data={"interactions": session["interactions"]},
            metric_value=duration
        )

        # Track session success rate
        if session["interactions"] > 0:
            success_rate = session["successful_tasks"] / session["interactions"]
            self.ld_client.track(
                "session.success_rate",
                context,
                metric_value=success_rate * 100
            )

        result = dict(session)
        result["duration"] = duration
        del self.session_data[session_id]
        return result
```

## Naming Conventions

```python
# Use dot notation for hierarchy
"quality.accuracy"
"quality.relevance"
"user.satisfaction"
"user.engagement"
"revenue.conversion"
"task.success_rate"
"session.duration"
"ai.task.completion"
"ai.recommendation.conversion"
```

## Best Practices

1. **Create Before Track** - Metric must exist before tracking events
2. **Use Numeric Metrics** - Set `measureType` to `value` in `create-metric` for aggregation
3. **Consistent Keys** - Use the same key as `eventKey` in `create-metric` and in `ld_client.track()`
4. **Always shut down cleanly** - Call `await shutdown()` before your process exits. It flushes pending events and then closes the client. Trailing events are at risk of being lost otherwise, in short-lived scripts and long-running services alike. This is not a serverless-only rule; it applies to any process that exits.
5. **Rate Limit** - Don't track on every keystroke

## Viewing Metrics

Custom metrics appear in:
- **Metrics** page in LaunchDarkly UI
- **Monitoring tab** of your config
- From the agent with the `get-metrics` and `get-metric-events` MCP tools

## Related Skills

- `launchdarkly-online-evals` - Quality metrics via judges

## References

- [Metrics API Documentation](https://apidocs.launchdarkly.com/tag/Metrics)
- [Custom Events Documentation](https://docs.launchdarkly.com/sdk/features/events)
- [AI SDK reference for Python](https://launchdarkly.com/docs/sdk/ai/python)
- [AI SDK reference for Node.js](https://launchdarkly.com/docs/sdk/ai/node-js)
