---
name: launchdarkly-custom-metrics
description: "Create, track, retrieve, update, and delete custom business metrics for configs. Covers full lifecycle: define metrics with the LaunchDarkly MCP server, emit events via SDK, and query results."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server to create and read metrics. Updating or deleting a metric needs a LaunchDarkly API token with the `writer` role. SDK examples use `launchdarkly-ai-server` 0.3.0+ (Python) or `@launchdarkly/ai-node` 0.3.0+ (Node.js).
metadata:
  author: launchdarkly
  version: "1.1.0-experimental"
---

# Custom Metrics for Configs

Full lifecycle management of custom business metrics: create metric definitions with the MCP server, track events via SDK, retrieve metric data, and manage metrics programmatically.

## Prerequisites

- LaunchDarkly AI SDK initialized (see `sdk-install`). The SDK reads `LD_SDK_KEY` from the environment.
- The remotely hosted LaunchDarkly MCP server configured in your environment
- A LaunchDarkly API token with the `writer` role, only to update or delete metrics, or for scripts that can't use MCP
- Understanding of built-in agent metrics (see `launchdarkly-built-in-metrics`)

## API Access

Use the LaunchDarkly MCP server tools wherever one exists: they authenticate via OAuth and need no token. Create metrics with `create-metric`, check that events are arriving with `list-metric-events`, and read definitions with `get-metric` and `list-metrics`. The MCP server can't update or delete metrics, so those steps use the REST API. For them, or for scripts that can't use MCP, ask the user to paste an API access token for this session and substitute it for `{api_token}` in the examples below. Do not search environment variables, `.env` files, or agent/MCP config files for credentials.

## Metrics Lifecycle Overview

| Step | Method | Purpose |
|------|--------|---------|
| 1. Create | MCP `create-metric` | Define metric in LaunchDarkly |
| 2. Track | SDK | Send events to the metric |
| 3. Get | MCP `get-metric`, `list-metrics` | Retrieve metric definition/data |
| 4. Update | API | Modify metric properties |
| 5. Delete | API | Remove metric |

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

`measureType` is `count` (how many times the event fired), `occurrence` (whether each user fired it at all), or `value` (a number sent with the event). Then confirm with `get-metric`.

### Scripts without MCP

The REST API equivalent:

**Required fields for numeric custom metrics:**
- `successCriteria` - Must be one of: `"HigherThanBaseline"`, `"LowerThanBaseline"`
- `unit` - e.g., `"count"`, `"percent"`, `"milliseconds"`

The API will return `400 Bad Request` if these are missing for numeric metrics.

```python
import requests
import os

def create_metric(
    project_key: str,
    metric_key: str,
    name: str,
    kind: str = "custom",
    is_numeric: bool = True,
    unit: str = "count",
    success_criteria: str = "HigherThanBaseline",
    event_key: str = None,
    description: str = None
):
    """Create a new metric definition in LaunchDarkly."""
    API_TOKEN = "{api_token}"  # token the user provided for this session

    url = f"https://app.launchdarkly.com/api/v2/metrics/{project_key}"

    payload = {
        "key": metric_key,
        "name": name,
        "kind": kind,
        "isNumeric": is_numeric,
        "eventKey": event_key or metric_key
    }

    # Unit and successCriteria are required for numeric custom metrics
    if is_numeric and kind == "custom":
        payload["unit"] = unit
        payload["successCriteria"] = success_criteria

    if description:
        payload["description"] = description

    headers = {
        "Authorization": API_TOKEN,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        print(f"[OK] Created metric: {metric_key}")
        return response.json()
    elif response.status_code == 409:
        print(f"[INFO] Metric already exists: {metric_key}")
        return None
    else:
        print(f"[ERROR] Failed to create metric: {response.status_code}")
        print(f"        {response.text}")
        return None
```

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

Use `get-metric` for one metric and `list-metrics` for all of them. After you start tracking, `list-metric-events` shows which event keys have arrived and when, which is the fastest way to catch an `eventKey` that doesn't match `track()`. The REST equivalents for scripts:

### Get Single Metric

```python
def get_metric(project_key: str, metric_key: str):
    """Get a single metric definition."""
    API_TOKEN = "{api_token}"  # token the user provided for this session

    url = f"https://app.launchdarkly.com/api/v2/metrics/{project_key}/{metric_key}"

    headers = {"Authorization": API_TOKEN}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        metric = response.json()
        print(f"[OK] Metric: {metric['key']}")
        print(f"     Name: {metric.get('name', 'N/A')}")
        print(f"     Kind: {metric.get('kind', 'N/A')}")
        print(f"     Numeric: {metric.get('isNumeric', False)}")
        print(f"     Event Key: {metric.get('eventKey', 'N/A')}")
        return metric
    elif response.status_code == 404:
        print(f"[INFO] Metric not found: {metric_key}")
        return None
    else:
        print(f"[ERROR] Failed to get metric: {response.status_code}")
        return None
```

### List All Metrics

```python
def list_metrics(project_key: str, limit: int = 20):
    """List all metrics in a project."""
    API_TOKEN = "{api_token}"  # token the user provided for this session

    url = f"https://app.launchdarkly.com/api/v2/metrics/{project_key}"

    headers = {"Authorization": API_TOKEN}
    params = {"limit": limit}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        metrics = data.get("items", [])
        print(f"[OK] Found {len(metrics)} metrics:")
        for metric in metrics:
            numeric = "numeric" if metric.get("isNumeric") else "non-numeric"
            print(f"     - {metric['key']} ({metric.get('kind', 'custom')}, {numeric})")
        return metrics
    else:
        print(f"[ERROR] Failed to list metrics: {response.status_code}")
        return None
```

## 4. Update Metric (API)

```python
def update_metric(project_key: str, metric_key: str, updates: list):
    """
    Update a metric using JSON Patch operations.

    Args:
        updates: List of patch operations, e.g.:
            [{"op": "replace", "path": "/name", "value": "New Name"}]
    """
    API_TOKEN = "{api_token}"  # token the user provided for this session

    url = f"https://app.launchdarkly.com/api/v2/metrics/{project_key}/{metric_key}"

    headers = {
        "Authorization": API_TOKEN,
        "Content-Type": "application/json"
    }

    response = requests.patch(url, json=updates, headers=headers)

    if response.status_code == 200:
        print(f"[OK] Updated metric: {metric_key}")
        return response.json()
    elif response.status_code == 404:
        print(f"[ERROR] Metric not found: {metric_key}")
        return None
    else:
        print(f"[ERROR] Failed to update metric: {response.status_code}")
        print(f"        {response.text}")
        return None

# Example: Update metric name and description
def rename_metric(project_key: str, metric_key: str, new_name: str, new_description: str = None):
    """Rename a metric and optionally update description."""
    updates = [
        {"op": "replace", "path": "/name", "value": new_name}
    ]
    if new_description:
        updates.append({"op": "replace", "path": "/description", "value": new_description})

    return update_metric(project_key, metric_key, updates)
```

## 5. Delete Metric (API)

```python
def delete_metric(project_key: str, metric_key: str):
    """Delete a metric from the project."""
    API_TOKEN = "{api_token}"  # token the user provided for this session

    url = f"https://app.launchdarkly.com/api/v2/metrics/{project_key}/{metric_key}"

    headers = {"Authorization": API_TOKEN}

    response = requests.delete(url, headers=headers)

    if response.status_code == 204:
        print(f"[OK] Deleted metric: {metric_key}")
        return True
    elif response.status_code == 404:
        print(f"[INFO] Metric not found: {metric_key}")
        return False
    else:
        print(f"[ERROR] Failed to delete metric: {response.status_code}")
        return False
```

## Complete Workflow Example

```python
import asyncio
from ldclient import Context
from launchdarkly_ai_server import get_client, init_client, shutdown

API_TOKEN = "{api_token}"  # token the user provided for this session
PROJECT_KEY = "support-ai"

async def main():
    # 1. Create metric
    create_metric(
        PROJECT_KEY,
        "ai.task.completion",
        name="Agent Task Completion Rate",
        kind="custom",
        is_numeric=True,
        description="Tracks successful agent task completions"
    )

    # 2. Track events
    await init_client()  # reads LD_SDK_KEY
    ld_client = get_client()
    context = Context.builder("user-123").build()
    ld_client.track("ai.task.completion", context, metric_value=1.0)
    ld_client.track("ai.task.completion", context, metric_value=1.0)
    ld_client.track("ai.task.completion", context, metric_value=0.0)  # failure
    await shutdown()  # flushes events, then closes the client

    # 3. Get metric definition
    metric = get_metric(PROJECT_KEY, "ai.task.completion")

    # 4. Update metric name
    rename_metric(PROJECT_KEY, "ai.task.completion", "Agent Task Success Rate")

    # 5. List all metrics
    list_metrics(PROJECT_KEY)

    # 6. Delete metric (when no longer needed)
    # delete_metric(PROJECT_KEY, "ai.task.completion")

asyncio.run(main())
```

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
2. **Use Numeric Metrics** - Set `isNumeric=True` for aggregation
3. **Consistent Keys** - Use same key in `create_metric()` and `ld_client.track()`
4. **Always shut down cleanly** - Call `await shutdown()` before your process exits. It flushes pending events and then closes the client. Trailing events are at risk of being lost otherwise, in short-lived scripts and long-running services alike. This is not a serverless-only rule; it applies to any process that exits.
5. **Rate Limit** - Don't track on every keystroke

## Viewing Metrics

Custom metrics appear in:
- **Metrics** page in LaunchDarkly UI
- **Monitoring tab** of your config
- From the agent with the `get-metric`, `list-metrics`, and `list-metric-events` MCP tools
- From scripts with `get_metric()` or `list_metrics()`

## Related Skills

- `sdk-install` - SDK setup
- `launchdarkly-built-in-metrics` - Built-in agent metrics (tokens, duration, cost)
- `launchdarkly-online-evals` - Quality metrics via judges

## References

- [Metrics API Documentation](https://apidocs.launchdarkly.com/tag/Metrics)
- [Custom Events Documentation](https://docs.launchdarkly.com/sdk/features/events)
- [AI SDK reference for Python](https://launchdarkly.com/docs/sdk/ai/python)
- [AI SDK reference for Node.js](https://launchdarkly.com/docs/sdk/ai/node-js)
