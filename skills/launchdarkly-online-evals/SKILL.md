---
name: launchdarkly-online-evals
description: Attach judges to config variations for automatic LLM-as-a-judge evaluation. Create custom judges, configure sampling rates, and monitor quality scores.
compatibility: Requires the remotely hosted LaunchDarkly MCP server. Scripted setup without MCP needs an API access token with ai-configs:write permission. SDK examples use `launchdarkly-ai-server` 0.3.0+ (Python) or `@launchdarkly/ai-node` 0.3.0+ (Node.js).
metadata:
  author: launchdarkly
  version: "1.0.0"
---

# Config Online Evaluations

Attach judges to config variations for automatic quality scoring using LLM-as-a-judge methodology. Judges evaluate responses and return scores between 0.0 and 1.0.

## Prerequisites

- LaunchDarkly account with AgentControl enabled
- The remotely hosted LaunchDarkly MCP server configured in your environment
- Existing config with variations (use `launchdarkly-configs-create` skill)
- To run judges from your application: `launchdarkly-ai-server` 0.3.0+ (Python) or `@launchdarkly/ai-node` 0.3.0+ (Node.js), plus a provider handler package for each provider your configs and judges use

## API Access

Use the LaunchDarkly MCP server tools for every step in the workflow: they authenticate via OAuth and need no token. The REST API is only for scripts and CI that can't use MCP (see [Scripting without MCP](#scripting-without-mcp)). In that case, ask the user to paste an API access token for this session and substitute it for `{api_token}` in the examples below. Do not search environment variables, `.env` files, or agent/MCP config files for credentials.

## Core Concepts

### What Are Judges?

Judges are specialized configs in **judge mode** that evaluate responses from other configs. They use an LLM to score outputs and return structured results:

```json
{
  "score": 0.85,
  "reasoning": "Answered correctly with one minor omission"
}
```

### Built-in Judges

LaunchDarkly provides three pre-configured judges:

| Judge | Metric Key | Measures |
|-------|-----------|----------|
| Accuracy | `$ld:ai:judge:accuracy` | How correct and grounded the response is |
| Relevance | `$ld:ai:judge:relevance` | How well it addresses the user request |
| Toxicity | `$ld:ai:judge:toxicity` | Harmful or unsafe phrasing (lower = safer) |

### Completion Mode Only

Judges can only be attached to **completion mode** configs in the UI. Attaching them through the API (Step 2) works for any config, and the SDK runs whatever judges the served variation has.

### Restrictions

- Cannot attach judges to judges (no recursion)
- Cannot attach multiple judges with the same metric key to a single variation
- Cannot view/edit model parameters or tools on judge variations

## Workflow

### Step 1: Create Custom Judges (Optional)

For domain-specific evaluation, create a judge config with `create-agentcontrol-config`:

```json
{
  "projectKey": "{projectKey}",
  "key": "security-judge",
  "name": "Security Judge",
  "mode": "judge",
  "evaluationMetricKey": "$ld:ai:judge:security",
  "isInverted": false
}
```

> **Note:** `evaluationMetricKey` must start with `$ld:ai:judge:`. Set `isInverted: true` for metrics like toxicity where 0.0 is better.

Then add a variation with the evaluation prompt using `create-agentcontrol-config-variation`. Get `modelConfigKey` from `list-agentcontrol-model-configs`:

```json
{
  "projectKey": "{projectKey}",
  "configKey": "security-judge",
  "key": "default",
  "name": "Default",
  "modelConfigKey": "OpenAI.gpt-4o-mini",
  "modelName": "gpt-4o-mini",
  "parameters": {"temperature": 0.3},
  "messages": [
    {
      "role": "system",
      "content": "You are a security auditor. Score from 0.0 to 1.0:\n- 1.0: No security issues\n- 0.7-0.9: Minor issues\n- 0.4-0.6: Moderate issues\n- 0.1-0.3: Serious vulnerabilities\n- 0.0: Critical vulnerabilities\n\nCheck for: SQL injection, XSS, hardcoded secrets, command injection.\n\n{{message_history}}"
    }
  ]
}
```

> **Important:** End the judge prompt with `{{message_history}}`. The SDK fills that variable with the conversation being judged, so a prompt without it never sees the response it's scoring. The SDK adds the score-and-reasoning output format itself.

### Step 2: Attach Judges to Variations

Use `update-agentcontrol-config-variation` with `judgeConfiguration`. Get `variationKey` from `get-agentcontrol-config`:

```json
{
  "projectKey": "{projectKey}",
  "configKey": "{configKey}",
  "variationKey": "{variationKey}",
  "judgeConfiguration": {
    "judges": [
      {"judgeConfigKey": "security-judge", "samplingRate": 1.0},
      {"judgeConfigKey": "api-contract-judge", "samplingRate": 0.5}
    ]
  }
}
```

> **Important:** The `judges` array **replaces all existing** judge attachments. An empty array removes all judges.

### Step 3: Set Fallthrough on Judges

Each judge config needs its fallthrough set to the enabled variation in every environment that runs it. Configs default to the "disabled" variation. Use `update-agentcontrol-config-rollout`:

```json
{
  "projectKey": "{projectKey}",
  "configKey": "security-judge",
  "env": "production",
  "rolloutType": "variation",
  "variationKey": "default"
}
```

Then run `get-agentcontrol-config-health` on the judge to confirm it's targetable.

## Scripting without MCP

For CI or scripts that can't use the MCP server, the same three steps through the REST API. `turnTargetingOn` does not work for configs, so `set_fallthrough` sends `updateFallthroughVariationOrRollout`:

```python
import requests
import os
from typing import Optional

class AIConfigJudges:
    """Manager for config judge attachments"""

    def __init__(self, api_token: str, project_key: str):
        self.api_token = api_token
        self.project_key = project_key
        self.base_url = "https://app.launchdarkly.com/api/v2"
        self.headers = {
            "Authorization": api_token,
            "Content-Type": "application/json",
            "LD-API-Version": "beta"
        }

    def attach_judges(self, config_key: str, variation_key: str,
                      judges: list[dict]) -> dict:
        """
        Attach judges to a variation.

        Args:
            config_key: config key
            variation_key: Variation key
            judges: List of {"judgeConfigKey": str, "samplingRate": float}
        """
        url = f"{self.base_url}/projects/{self.project_key}/ai-configs/{config_key}/variations/{variation_key}"

        response = requests.patch(url, headers=self.headers, json={
            "judgeConfiguration": {"judges": judges}
        })

        if response.status_code == 200:
            print(f"[OK] Attached {len(judges)} judges to {config_key}/{variation_key}")
            return response.json()
        print(f"[ERROR] {response.status_code}: {response.text}")
        return {}

    def create_judge(self, key: str, name: str, metric_key: str,
                     system_prompt: str, model: str = "OpenAI.gpt-4o-mini",
                     is_inverted: bool = False) -> dict:
        """
        Create a judge config.

        Args:
            key: Judge config key
            name: Display name
            metric_key: Metric key for scoring; "security" is sent as "$ld:ai:judge:security"
            system_prompt: Evaluation instructions; {{message_history}} is appended if missing
            is_inverted: True if lower scores are better (e.g., toxicity)
        """
        # The API rejects a bare metric key
        if not metric_key.startswith("$ld:ai:judge:"):
            metric_key = f"$ld:ai:judge:{metric_key}"

        # Create config
        config_url = f"{self.base_url}/projects/{self.project_key}/ai-configs"
        response = requests.post(config_url, headers=self.headers, json={
            "key": key,
            "name": name,
            "mode": "judge",
            "evaluationMetricKey": metric_key,
            "isInverted": is_inverted
        })

        if response.status_code not in [200, 201]:
            print(f"[ERROR] Creating config: {response.text}")
            return {}

        # Without {{message_history}} the judge never sees the conversation it scores
        if "{{message_history}}" not in system_prompt:
            system_prompt = f"{system_prompt}\n\n{{{{message_history}}}}"

        # Create variation
        var_url = f"{self.base_url}/projects/{self.project_key}/ai-configs/{key}/variations"
        response = requests.post(var_url, headers=self.headers, json={
            "key": "default",
            "name": "Default",
            "messages": [{"role": "system", "content": system_prompt}],
            "modelConfigKey": model,
            "model": {"parameters": {"temperature": 0.3}}
        })

        if response.status_code in [200, 201]:
            print(f"[OK] Created judge: {key}")
            return response.json()
        print(f"[ERROR] Creating variation: {response.text}")
        return {}

    def set_fallthrough(self, config_key: str, environment: str,
                        variation_key: str = "default") -> bool:
        """
        Set fallthrough to enable a judge config.

        Note: turnTargetingOn doesn't work for configs. Instead, set the
        fallthrough from disabled (index 0) to the enabled variation.
        """
        # Get variation ID
        url = f"{self.base_url}/projects/{self.project_key}/ai-configs/{config_key}/targeting"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(f"[ERROR] {response.status_code}: {response.text}")
            return False

        targeting = response.json()
        variation_id = None
        for var in targeting.get("variations", []):
            # The variation key is in value._ldMeta.variationKey, not on the item itself
            meta_key = ((var.get("value") or {}).get("_ldMeta") or {}).get("variationKey")
            if meta_key == variation_key or var.get("name") == variation_key:
                variation_id = var.get("_id")
                break

        if not variation_id:
            print(f"[ERROR] Variation '{variation_key}' not found")
            return False

        # Set fallthrough
        response = requests.patch(url, headers={
            **self.headers,
            "Content-Type": "application/json; domain-model=launchdarkly.semanticpatch"
        }, json={
            "environmentKey": environment,
            "instructions": [{
                "kind": "updateFallthroughVariationOrRollout",
                "variationId": variation_id
            }]
        })

        if response.status_code == 200:
            print(f"[OK] Fallthrough set for {config_key}")
            return True
        print(f"[ERROR] {response.status_code}: {response.text}")
        return False
```

## SDK: Inline Evaluation

`invoke()` runs every judge attached to the served variation, samples each at its rate, and records the scores as metrics. Pass a handler for each provider your config and its judges use. The config must be completion mode: a messages handler does not match an agent-mode config.

```python
import asyncio
from launchdarkly_ai_server import config, shutdown
from launchdarkly_ai_openai_messages import create_openai_messages_handler

config_key = "support-agent"  # completion mode

async def main():
    # Reads LD_SDK_KEY and OPENAI_API_KEY from the environment
    result = await config(
        key=config_key,
        handler=create_openai_messages_handler(),
    ).invoke("How can LaunchDarkly help me?", {"kind": "user", "key": "user-123"})

    print(result.response)
    for judge_key, judge in (result.judge_results or {}).items():
        print(judge_key, judge.score)

    # Flushes trailing events, including judge scores
    await shutdown()

asyncio.run(main())
```

```typescript
import { config, shutdown } from '@launchdarkly/ai-node';
import { createOpenAIHandler } from '@launchdarkly/ai-openai-messages';

const result = await config({
  key: 'support-agent',
  handler: createOpenAIHandler(),
}).invoke('How can LaunchDarkly help me?', { kind: 'user', key: 'user-123' });

console.log(result.response);
for (const [judgeKey, judge] of Object.entries(result.judgeResults ?? {})) {
  console.log(judgeKey, judge.score);
}

await shutdown();
```

Inline judges add their latency to the request. To keep them off the request path, run them in the background.

## SDK: Background Evaluation

Pass `skip_judges=True` (`skipJudges: true`) and `invoke()` returns the sampled judges as `judge_tasks` (`judgeTasks`) instead of running them. Hand each task to a worker, run it with `run_judge`, and record the score yourself, because `run_judge` doesn't:

```python
from ldclient import Context
from launchdarkly_ai_server import config, get_client, run_judge
from launchdarkly_ai_openai_messages import create_openai_messages_handler

handler = create_openai_messages_handler()

config_key = "support-agent"  # completion mode

result = await config(key=config_key, handler=handler, skip_judges=True).invoke(
    "How can LaunchDarkly help me?", {"kind": "user", "key": "user-123"}
)

# In your worker:
for task in result.judge_tasks or []:
    judged = await run_judge(task, [handler])
    if judged and task.evaluation_metric_key:
        get_client().track(
            task.evaluation_metric_key,
            Context.from_dict(task.user_context),
            judged.track_data,
            judged.score,
        )
```

```typescript
import { config, getClient, runJudge } from '@launchdarkly/ai-node';
import { createOpenAIHandler } from '@launchdarkly/ai-openai-messages';

const handler = createOpenAIHandler();

const result = await config({ key: 'support-agent', handler, skipJudges: true }).invoke(
  'How can LaunchDarkly help me?',
  { kind: 'user', key: 'user-123' },
);

// In your worker:
for (const task of result.judgeTasks ?? []) {
  const judged = await runJudge(task, [handler]);
  if (judged && task.evaluationMetricKey) {
    getClient().track(task.evaluationMetricKey, task.userContext, judged.trackData, judged.score);
  }
}
```

> **Note:** In Python, `task.user_context` is a plain dict, so convert it with `Context.from_dict()` before calling `track()`. `track_data` (`trackData`) already includes `judgeConfigKey`.

## SDK: Custom Pipelines

If your application calls the model itself, wrap that call in a handler with `create_handler` (`createHandler`). `invoke()` then runs your code and the attached judges, the same as with a built-in handler. The judges still need a handler for their own provider:

```python
from launchdarkly_ai_server import config, create_handler, parse_template
from launchdarkly_ai_openai_messages import create_openai_messages_handler

config_key = "support-agent"  # completion mode

# run_my_agent is your existing pipeline; it returns the text and the provider's usage object
async def my_pipeline(ld_config, user_input, tool_handlers, variables, history):
    # Custom handlers fill {{name}} placeholders themselves
    messages = [{**m, "content": parse_template(m["content"], variables)} for m in ld_config.get("messages", [])]
    output, usage = await run_my_agent(messages, user_input)
    return {"output": output, "usage": {"input": usage.input_tokens, "output": usage.output_tokens}}

handlers = [
    create_handler(("Anthropic", "messages"), my_pipeline),  # the config's provider and mode
    create_openai_messages_handler(),                       # the judge's provider
]

result = await config(key=config_key, handler=handlers).invoke(user_input, context)
```

The provider name in `create_handler` must match the config's model provider exactly, including case, and the first argument must be a tuple. For the full handler contract, see the `launchdarkly-tools` skill.

## Sampling Rates

Each evaluated response sends an additional request to your model provider, increasing token usage and costs. Start with a lower sampling percentage and increase only if you need more evaluation coverage.

You can adjust sampling rates at any time from the Judges section of a variation, or disable a judge by setting its sampling to 0%.

## Viewing Results

1. Navigate to **configs** > select your config
2. Click **Monitoring** tab
3. Select **Evaluator metrics** from dropdown
4. View scores by variation and time range

Results appear within 1-2 minutes of evaluation.

## Use in Guardrails and Experiments

Evaluation metrics integrate with:
- **Guarded rollouts**: Pause/revert when scores fall below threshold
- **Experiments**: Compare variations using evaluation metrics as goals

## Error Handling

| Status | Cause | Solution |
|--------|-------|----------|
| 404 | Config/variation not found | Verify keys exist |
| 400 | Invalid judge config | Check judgeConfigKey exists |
| 403 | Insufficient permissions | Reconnect the MCP server, or check the API token's permissions |
| 422 | Duplicate metric key | Cannot attach multiple judges with same metric key |

## Next Steps

After attaching judges:
1. **Set fallthrough** on judge configs to an enabled variation (required)
2. **Monitor results** in Monitoring tab
3. **Adjust sampling** based on cost/coverage needs
4. **Set up guarded rollouts** for automatic regression detection

## Related Skills

- `launchdarkly-configs-create` - Create configs and judges
- `launchdarkly-configs-targeting` - Configure targeting rules
- `launchdarkly-configs-variations` - Manage variations

## References

- [Online Evaluations](https://docs.launchdarkly.com/home/ai-configs/online-evaluations.md)
- [Custom Judges](https://docs.launchdarkly.com/home/ai-configs/custom-judges.md)

- [AI SDK reference for Python](https://launchdarkly.com/docs/sdk/ai/python)
- [AI SDK reference for Node.js](https://launchdarkly.com/docs/sdk/ai/node-js)
