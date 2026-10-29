---
name: launchdarkly-configs-targeting
description: Configure config targeting rules to control which variations serve to different users. Enable percentage rollouts, attribute-based rules, segment targeting, and guarded rollouts.
compatibility: Requires LaunchDarkly API access token with ai-configs:write permission.
metadata:
  author: launchdarkly
  version: "0.1.0"
---

# Config Targeting

Configure targeting rules for configs to control which variations serve to different contexts. Works the same for both completion and agent mode.

## Prerequisites

- LaunchDarkly account with AgentControl enabled
- API access token with write permissions
- Project key and environment key
- Existing config with variations (use `launchdarkly-configs-create` skill)

## API Access

Prefer the LaunchDarkly MCP server tools: they authenticate via OAuth and need no token. If a step has no MCP equivalent and you must call the REST API directly, ask the user to paste an API access token for this session and substitute it for `{api_token}` in the examples below. Do not search environment variables, `.env` files, or agent/MCP config files for credentials.

## Core Concepts

### Evaluation Order

Targeting rules evaluate in this order (same as feature flags):

1. **Individual targets** - Specific context keys (highest priority)
2. **Segment rules** - Pre-defined segments
3. **Custom rules** - Attribute-based conditions (evaluated in order)
4. **Default rule** - Fallthrough for all others
5. **Off variation** - When targeting is disabled

### Semantic Patch API

config targeting uses semantic patch instructions:

```
PATCH /api/v2/projects/{projectKey}/ai-configs/{configKey}/targeting
Content-Type: application/json; domain-model=launchdarkly.semanticpatch
```

### Key Concepts

- **variationId**: UUIDs, not keys. Always fetch targeting first to get IDs.
- **Weights**: Thousandths (50000 = 50%, 100000 = 100%)
- **Clause logic**: Multiple clauses = AND, multiple values = OR
- **Null attributes**: Rules with null/missing attributes are skipped

## Workflow

### Step 1: Get Targeting (with Variation IDs)

```bash
curl -X GET "https://app.launchdarkly.com/api/v2/projects/{projectKey}/ai-configs/{configKey}/targeting" \
  -H "Authorization: {api_token}" \
  -H "LD-API-Version: beta"
```

Response includes `variations` array with `_id` (UUID) for each variation.

### Step 2: Edit the Default Rule

Edit the default rule to serve the variation you created.

> **Important:** The `turnTargetingOn` instruction does not work for configs. Use `updateFallthroughVariationOrRollout` instead.

```bash
# First, get variation IDs from Step 1 response
# Then set fallthrough to the enabled variation (e.g., "Default" variation)
curl -X PATCH "https://app.launchdarkly.com/api/v2/projects/{projectKey}/ai-configs/{configKey}/targeting" \
  -H "Authorization: {api_token}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -H "LD-API-Version: beta" \
  -d '{
    "environmentKey": "production",
    "instructions": [{
      "kind": "updateFallthroughVariationOrRollout",
      "variationId": "your-enabled-variation-uuid"
    }]
  }'
```

### Step 3: Add Targeting Rules

**Attribute-based rule:**

```bash
curl -X PATCH "https://app.launchdarkly.com/api/v2/projects/{projectKey}/ai-configs/{configKey}/targeting" \
  -H "Authorization: {api_token}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -H "LD-API-Version: beta" \
  -d '{
    "environmentKey": "production",
    "instructions": [{
      "kind": "addRule",
      "clauses": [{
        "contextKind": "user",
        "attribute": "selectedModel",
        "op": "contains",
        "values": ["sonnet"],
        "negate": false
      }],
      "variation": 0
    }]
  }'
```

**Percentage rollout:**

```bash
curl -X PATCH "..." \
  -d '{
    "environmentKey": "production",
    "instructions": [{
      "kind": "addRule",
      "clauses": [{
        "contextKind": "user",
        "attribute": "tier",
        "op": "in",
        "values": ["premium"],
        "negate": false
      }],
      "percentageRolloutConfig": {
        "contextKind": "user",
        "bucketBy": "key",
        "variations": [
          {"variation": 0, "weight": 60000},
          {"variation": 1, "weight": 40000}
        ]
      }
    }]
  }'
```

**Set fallthrough (default rule):**

```bash
curl -X PATCH "..." \
  -d '{
    "environmentKey": "production",
    "instructions": [{
      "kind": "updateFallthroughVariationOrRollout",
      "variationId": "fallback-variation-uuid"
    }]
  }'
```

## Python Implementation

```python
import requests
import os
from typing import Dict, List, Optional

class AIConfigTargeting:
    """Manager for config targeting rules"""

    def __init__(self, api_token: str, project_key: str):
        self.api_token = api_token
        self.project_key = project_key
        self.base_url = "https://app.launchdarkly.com/api/v2"

    def get_targeting(self, config_key: str) -> Optional[Dict]:
        """Get current targeting with variation IDs."""
        url = f"{self.base_url}/projects/{self.project_key}/ai-configs/{config_key}/targeting"

        response = requests.get(url, headers={
            "Authorization": self.api_token,
            "LD-API-Version": "beta"
        })

        if response.status_code == 200:
            return response.json()
        print(f"[ERROR] {response.status_code}: {response.text}")
        return None

    def get_variation_id(self, config_key: str, variation_key: str) -> Optional[str]:
        """Look up variation UUID from key or name."""
        targeting = self.get_targeting(config_key)
        if targeting:
            for var in targeting.get("variations", []):
                if var.get("key") == variation_key or var.get("name") == variation_key:
                    return var.get("_id")
        return None

    def update_targeting(self, config_key: str, environment: str,
                         instructions: List[Dict], comment: str = "") -> Optional[Dict]:
        """Send semantic patch instructions."""
        url = f"{self.base_url}/projects/{self.project_key}/ai-configs/{config_key}/targeting"

        payload = {"environmentKey": environment, "instructions": instructions}
        if comment:
            payload["comment"] = comment

        response = requests.patch(url, headers={
            "Authorization": self.api_token,
            "Content-Type": "application/json; domain-model=launchdarkly.semanticpatch",
            "LD-API-Version": "beta"
        }, json=payload)

        if response.status_code == 200:
            return response.json()
        print(f"[ERROR] {response.status_code}: {response.text}")
        return None

    def enable_config(self, config_key: str, environment: str,
                      variation_key: str = "default") -> bool:
        """
        Enable a config by setting fallthrough to an enabled variation.

        Note: turnTargetingOn doesn't work for configs. Instead, set the
        fallthrough from the disabled variation (index 0) to an enabled one.
        """
        variation_id = self.get_variation_id(config_key, variation_key)
        if not variation_id:
            print(f"[ERROR] Variation '{variation_key}' not found")
            return False
        return self.set_fallthrough(config_key, environment, variation_id)

    def add_rule(self, config_key: str, environment: str,
                 clauses: List[Dict], variation: int,
                 description: str = "") -> bool:
        """Add targeting rule serving a specific variation index."""
        instruction = {
            "kind": "addRule",
            "clauses": clauses,
            "variation": variation
        }
        if description:
            instruction["description"] = description

        result = self.update_targeting(config_key, environment,
            [instruction], f"Add rule: {description}")
        if result:
            print(f"[OK] Rule added")
            return True
        return False

    def add_rollout_rule(self, config_key: str, environment: str,
                         clauses: List[Dict],
                         weights: List[Dict],
                         bucket_by: str = "key") -> bool:
        """
        Add percentage rollout rule.

        weights: [{"variation": 0, "weight": 50000}, {"variation": 1, "weight": 50000}]
        """
        result = self.update_targeting(config_key, environment, [{
            "kind": "addRule",
            "clauses": clauses,
            "percentageRolloutConfig": {
                "contextKind": "user",
                "bucketBy": bucket_by,
                "variations": weights
            }
        }], "Add percentage rollout")
        if result:
            print(f"[OK] Rollout rule added")
            return True
        return False

    def set_fallthrough(self, config_key: str, environment: str,
                        variation_id: str) -> bool:
        """Set default (fallthrough) variation by UUID."""
        result = self.update_targeting(config_key, environment, [{
            "kind": "updateFallthroughVariationOrRollout",
            "variationId": variation_id
        }], "Set fallthrough")
        if result:
            print(f"[OK] Fallthrough set")
            return True
        return False

    def target_individuals(self, config_key: str, environment: str,
                          context_keys: List[str], variation: int,
                          context_kind: str = "user") -> bool:
        """Target specific context keys."""
        result = self.update_targeting(config_key, environment, [{
            "kind": "addTargets",
            "variation": variation,
            "contextKind": context_kind,
            "values": context_keys
        }], f"Target {len(context_keys)} individuals")
        if result:
            print(f"[OK] Individual targets added")
            return True
        return False

    def target_segment(self, config_key: str, environment: str,
                      segment_keys: List[str], variation: int) -> bool:
        """Target a segment."""
        result = self.update_targeting(config_key, environment, [{
            "kind": "addRule",
            "clauses": [{
                "attribute": "segmentMatch",
                "contextKind": "",  # Leave blank for segments
                "op": "segmentMatch",
                "values": segment_keys,
                "negate": False
            }],
            "variation": variation
        }], f"Target segments: {segment_keys}")
        if result:
            print(f"[OK] Segment targeting added")
            return True
        return False

    def clear_rules(self, config_key: str, environment: str) -> bool:
        """Remove all targeting rules."""
        result = self.update_targeting(config_key, environment,
            [{"kind": "replaceRules", "rules": []}], "Clear all rules")
        if result:
            print(f"[OK] All rules cleared")
            return True
        return False
```

## Instruction Reference

> **Note:** `turnTargetingOn` and `turnTargetingOff` do not work for configs. Configs have targeting enabled by default. To "enable" a config, set the fallthrough to an enabled variation using `updateFallthroughVariationOrRollout`.

### Rules
| Kind | Description |
|------|-------------|
| `addRule` | Add rule with clauses and variation/rollout |
| `removeRule` | Remove by ruleId |
| `replaceRules` | Replace all rules |
| `reorderRules` | Change evaluation order |
| `updateRuleVariationOrRollout` | Update what a rule serves |

### Fallthrough
| Kind | Description |
|------|-------------|
| `updateFallthroughVariationOrRollout` | Set default variation or rollout |

### Individual Targets
| Kind | Description |
|------|-------------|
| `addTargets` | Target specific context keys |
| `removeTargets` | Remove specific targets |
| `replaceTargets` | Replace all targets |

## Operators Reference

| Operator | Description | Example |
|----------|-------------|---------|
| `in` | Value in list | `["premium", "enterprise"]` |
| `contains` | String contains | `["sonnet"]` |
| `startsWith` | String prefix | `["user-"]` |
| `endsWith` | String suffix | `[".edu"]` |
| `matches` | Regex match | `["^user-\\d+$"]` |
| `greaterThan` / `lessThan` | Numeric comparison | `[100]` |
| `before` / `after` | Date comparison | `["2024-12-31T00:00:00Z"]` |
| `semVerEqual` / `semVerGreaterThan` | Version comparison | `["2.0.0"]` |
| `segmentMatch` | Segment membership | `["beta-testers"]` |

## Clause Structure

```json
{
  "contextKind": "user",
  "attribute": "email",
  "op": "endsWith",
  "values": [".edu"],
  "negate": false
}
```

- Multiple clauses = AND (all must match)
- Multiple values = OR (any can match)
- `negate: true` inverts the operator

## Rollout Types

### Manual Percentage Rollout
```json
{
  "percentageRolloutConfig": {
    "contextKind": "user",
    "bucketBy": "key",
    "variations": [
      {"variation": 0, "weight": 50000},
      {"variation": 1, "weight": 50000}
    ]
  }
}
```

### Progressive Rollout
```json
{
  "progressiveRolloutConfig": {
    "contextKind": "user",
    "controlVariation": 1,
    "endVariation": 0,
    "steps": [
      {"rolloutWeight": 1000, "duration": {"quantity": 4, "unit": "hour"}},
      {"rolloutWeight": 5000, "duration": {"quantity": 4, "unit": "hour"}},
      {"rolloutWeight": 10000, "duration": {"quantity": 4, "unit": "hour"}}
    ]
  }
}
```

### Guarded Rollout
```json
{
  "guardedRolloutConfig": {
    "randomizationUnit": "user",
    "stages": [
      {"rolloutWeight": 1000, "monitoringWindowMilliseconds": 17280000},
      {"rolloutWeight": 5000, "monitoringWindowMilliseconds": 17280000}
    ],
    "metrics": [{
      "metricKey": "error-rate",
      "onRegression": {"rollback": true},
      "regressionThreshold": 0.01
    }]
  }
}
```

## Common Patterns

### Model Routing by Attribute
```python
# Route based on selectedModel context attribute
targeting.add_rule(
    config_key="model-selector",
    environment="production",
    clauses=[{
        "contextKind": "user",
        "attribute": "selectedModel",
        "op": "contains",
        "values": ["sonnet"],
        "negate": False
    }],
    variation=0,  # Sonnet variation index
    description="Route sonnet requests"
)
```

### Tier-Based Variation
```python
targeting.add_rule(
    config_key="chat-assistant",
    environment="production",
    clauses=[{
        "contextKind": "user",
        "attribute": "tier",
        "op": "in",
        "values": ["premium", "enterprise"],
        "negate": False
    }],
    variation=0  # Premium model variation
)
```

### Segment Targeting
```python
targeting.target_segment(
    config_key="chat-assistant",
    environment="production",
    segment_keys=["beta-testers"],
    variation=1  # Experimental variation
)
```

## Error Handling

| Status | Cause | Solution |
|--------|-------|----------|
| 400 | Invalid semantic patch | Check instruction format, ops must be lowercase |
| 403 | Insufficient permissions | Check API token |
| 404 | Config not found | Verify projectKey and configKey |
| 422 | Invalid variation | Use index (0, 1, 2...) or UUID from targeting response |

## Next Steps

After configuring targeting:
1. **Provide config URL:**
   ```
   https://app.launchdarkly.com/projects/{projectKey}/ai-configs/{configKey}
   ```
2. **Monitor performance** with `launchdarkly-built-in-metrics`
3. **Attach judges** with `launchdarkly-online-evals`
4. **Set up guarded rollouts** for automatic regression detection

## Related Skills

- `launchdarkly-configs-create` - Create configs with variations
- `launchdarkly-configs-variations` - Manage variations
- `launchdarkly-online-evals` - Attach judges
- `segments` - Create segments for targeting

## Other Resources

- [Target with AgentControl](https://docs.launchdarkly.com/home/ai-configs/target.md)
- [Targeting Rules](https://docs.launchdarkly.com/home/flags/target-rules.md)
- [JSON Targeting](https://docs.launchdarkly.com/home/flags/json-targeting.md)
- [Guarded Rollouts](https://docs.launchdarkly.com/home/releases/guarded-rollouts.md)
