# Metrics API

Retrieve config metrics via the LaunchDarkly REST API.

## Endpoint

```
GET /api/v2/projects/{projectKey}/ai-configs/{configKey}/metrics
```

## Authentication

Requires an API token with `ai-configs:read` permission.

```python
headers = {
    "Authorization": "your-api-token",
    "LD-API-Version": "beta"
}
```

## Implementation
```python
import requests
import time
import os

def get_ai_config_metrics(project_key: str, config_key: str, env: str = "production", hours: int = 24):
    """Get config metrics for the last N hours."""
    API_TOKEN = "{api_token}"  # token the user provided for this session

    now = int(time.time())
    start = now - (hours * 3600)

    url = f"https://app.launchdarkly.com/api/v2/projects/{project_key}/ai-configs/{config_key}/metrics"

    params = {
        "from": start,
        "to": now,
        "env": env
    }

    headers = {
        "Authorization": API_TOKEN,
        "LD-API-Version": "beta"
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        metrics = response.json()
        print(f"[OK] Metrics for {config_key} (last {hours} hours, {env}):")
        print(f"     Generations: {metrics.get('generationCount', 0):,}")
        print(f"     Success: {metrics.get('generationSuccessCount', 0):,}")
        print(f"     Errors: {metrics.get('generationErrorCount', 0):,}")
        print(f"     Input Tokens: {metrics.get('inputTokens', 0):,}")
        print(f"     Output Tokens: {metrics.get('outputTokens', 0):,}")
        print(f"     Total Tokens: {metrics.get('totalTokens', 0):,}")
        print(f"     Input Cost: ${metrics.get('inputCost', 0):.4f}")
        print(f"     Output Cost: ${metrics.get('outputCost', 0):.4f}")
        print(f"     Duration (ms): {metrics.get('durationMs', 0):,}")
        print(f"     TTFT (ms): {metrics.get('timeToFirstTokenMs', 0):,}")
        print(f"     Thumbs Up: {metrics.get('thumbsUp', 0)}")
        print(f"     Thumbs Down: {metrics.get('thumbsDown', 0)}")
        return metrics
    else:
        print(f"[ERROR] Failed to get metrics: {response.status_code}")
        return None
```

## Response Fields

| Field | Description |
|-------|-------------|
| `generationCount` | Total number of generations |
| `generationSuccessCount` | Successful generations |
| `generationErrorCount` | Failed generations |
| `inputTokens` | Total input tokens used |
| `outputTokens` | Total output tokens generated |
| `totalTokens` | Sum of input + output tokens |
| `inputCost` | Cost for input tokens |
| `outputCost` | Cost for output tokens |
| `durationMs` | Total duration in milliseconds |
| `timeToFirstTokenMs` | Time to first token (streaming) |
| `thumbsUp` | Positive feedback count |
| `thumbsDown` | Negative feedback count |

## Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | int | Unix timestamp for start of range |
| `to` | int | Unix timestamp for end of range |
| `env` | string | Environment key (default: "production") |

## Notes

- Time range is specified in Unix timestamps (seconds)
- Costs are calculated based on model pricing and token usage
- Feedback counts require user feedback tracking implementation
- Rate limits apply; see API documentation for details
