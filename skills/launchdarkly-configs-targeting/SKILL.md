---
name: launchdarkly-configs-targeting
description: Configure AgentControl config targeting to control which variation each context receives. Set the default rule or a percentage split, add attribute and segment rules, target individual contexts, and roll a config back to an earlier variation.
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: "nieblara"
  version: "1.0.0"
  summary: "Choose which AgentControl config variation each context gets: default rule, percentage split, rules and individual targets."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "INCIDENT_MITIGATION, CHAT"
---

# Config Targeting

Configure targeting rules for configs to control which variations serve to different contexts. Works the same for both completion and agent mode.

## Prerequisites

- LaunchDarkly account with AgentControl enabled
- The LaunchDarkly MCP server, connected as a member who can change config targeting in the environment
- Project key and environment key
- Existing config with variations (use `launchdarkly-configs-create` skill)

## API Access

Use the LaunchDarkly MCP server tools: they authenticate with the connection the customer set up. If a step has no MCP tool, tell the user which change to make in the LaunchDarkly UI instead. Never ask the user for an API access token.

## Tools

| Tool | Use it to |
|------|-----------|
| `get-agentcontrol-config-targeting` | Read the variations, individual targets, rules, default rule and off variation in one environment (read-only) |
| `get-agentcontrol-config` | Read variation keys and what each variation contains (read-only) |
| `get-agentcontrol-config-status-envs` | See where the config is active before you change it (read-only) |
| `update-agentcontrol-config-rollout` | Set the default rule: one variation, or a percentage split |
| `update-agentcontrol-config-targeting` | Add, remove, reorder or replace custom rules and their clauses |
| `update-agentcontrol-config-targets` | Add or remove individual contexts |
| `create-agentcontrol-config-approval` | Submit a change for review when the environment requires approval |
| `query-change-history` | Find earlier targeting changes, with `resourceKind: "aiconfig"` (read-only) |

The update tools change what live traffic receives. Before calling one, tell the user what the config serves now and what will change, and wait for their confirmation.

## Core Concepts

### Evaluation Order

Targeting rules evaluate in this order (same as feature flags):

1. **Individual targets** - Specific context keys (highest priority)
2. **Custom rules** - Attribute or segment conditions, top to bottom; the first match wins
3. **Default rule** - Fallthrough for all others

Targeting for a config is always on. `toggle-agentcontrol-config` and the `turnTargetingOn` instruction always fail; to start serving a variation, change the default rule.

### Key Concepts

- **variationKey**: Every update tool takes a variation key from `get-agentcontrol-config`, or a variation name from `get-agentcontrol-config-targeting`. You don't need variation UUIDs or indexes.
- **Percentages**: `update-agentcontrol-config-rollout` takes whole percentages that sum to 100.
- **Clause logic**: Multiple clauses = AND, multiple values = OR
- **Null attributes**: Rules with null/missing attributes are skipped
- **Approvals**: When the environment requires approval, an update tool makes no change and returns `requiresApproval: true` with the instructions to submit (Step 5).

## Workflow

### Step 1: Read the Current Targeting

Call `get-agentcontrol-config-targeting` with the project key, config key and environment key. Note the variation names, each rule's `ruleId` and `clauseId` values, and what the default rule serves. Call `get-agentcontrol-config` if you need variation keys.

### Step 2: Edit the Default Rule

Call `update-agentcontrol-config-rollout`:

- To serve one variation to every context no rule matches: `rolloutType: "variation"` and `variationKey`.
- To split that traffic: `rolloutType: "percentage"` with weights, for example `[{ "variationKey": "v1-gpt4o", "percent": 80 }, { "variationKey": "v2-claude", "percent": 20 }]`.

> **Important:** A new config's default rule serves an auto-generated disabled variation. Until you point the default rule at a real variation, the SDK returns `enabled=False` to every context.

The response returns the stored default rule and `previousFallthrough`. Tell the user both, so they can undo the change.

### Step 3: Add Targeting Rules

Call `update-agentcontrol-config-targeting` with one or more instructions. The kinds are `addRule`, `removeRule`, `addClauses`, `removeClauses`, `reorderRules`, `replaceRules`, `updateRuleDescription`, `addValuesToClause`, `removeValuesFromClause` and `updateClause`. Take `ruleId` and `clauseId` from Step 1.

**Attribute-based rule:**

```json
{
  "kind": "addRule",
  "variationKey": "sonnet",
  "clauses": [{
    "contextKind": "user",
    "attribute": "selectedModel",
    "op": "contains",
    "values": ["sonnet"],
    "negate": false
  }]
}
```

**Segment rule:**

```json
{
  "kind": "addRule",
  "variationKey": "experimental",
  "clauses": [{
    "contextKind": "",
    "attribute": "segmentMatch",
    "op": "segmentMatch",
    "values": ["beta-testers"],
    "negate": false
  }]
}
```

Leave `contextKind` blank for segment clauses.

To change which variation an existing rule serves, send `replaceRules` with every rule in order, each with its `variationKey` and clauses. `replaceRules` overwrites all rules, so build the list from the rules Step 1 returned.

Each rule serves one variation. For a percentage split inside a rule, or a progressive or guarded rollout of a config, tell the user to make the change in the LaunchDarkly UI.

### Step 4: Target Individual Contexts

Call `update-agentcontrol-config-targets`. The kinds are `addTargets`, `removeTargets`, `clearTargets` and `replaceTargets`:

```json
{
  "kind": "addTargets",
  "variationKey": "v1-gpt4o",
  "contextKind": "user",
  "values": ["user-key-1"]
}
```

Individual targets override every rule.

### Step 5: Submit for Approval When Required

If an update tool returns `requiresApproval: true`, the change wasn't made. Ask the user who should review it; if they name a person, find their member ID with `find-members`. Then call `create-agentcontrol-config-approval` with the environment key, the reviewers and the returned instructions. A person approves the request in LaunchDarkly; once it's approved, `apply-agentcontrol-config-approval` applies it. `list-agentcontrol-config-approvals` shows its progress.

### Step 6: Verify

Call `get-agentcontrol-config-targeting` again and confirm that the default rule, rules and individual targets match the request. `get-agentcontrol-config-health` reports, for each environment, whether the config serves a variation that isn't disabled.

## Roll Back a Config

When a variation misbehaves, for example after a model or prompt change:

1. Call `get-agentcontrol-config-targeting` to find what serves the variation: individual targets, a rule or the default rule.
2. Find the variation that served before with `query-change-history` (`resourceKind: "aiconfig"`, `resourceKey` set to the config key, and the environment). If the history doesn't show it, ask the user which variation to restore.
3. If the default rule serves it, call `update-agentcontrol-config-rollout` with `rolloutType: "variation"` and the earlier variation's key. If a rule or individual targets serve it, change that rule (Step 3) or those targets (Step 4).
4. Verify as in Step 6, and tell the user what you changed.

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

## Error Handling

| Result | Cause | Solution |
|--------|-------|----------|
| `requiresApproval: true` | The environment requires approval | Submit the change for review (Step 5) |
| 400 | Invalid instruction | Check the instruction kind and the clause `op`, which is case-sensitive |
| 403 | The connected member can't change this config's targeting | Ask the user to reconnect the LaunchDarkly connector as a member with that access |
| 404 | Config not found | Verify projectKey and configKey with `list-agentcontrol-configs` |
| Unknown variation | `variationKey` matches no variation | Use a key from `get-agentcontrol-config` or a name from `get-agentcontrol-config-targeting` |

## Next Steps

After configuring targeting:
1. **Provide config URL:**
   ```
   https://app.launchdarkly.com/projects/{projectKey}/ai-configs/{configKey}
   ```
2. **Check health** with `get-agentcontrol-config-health`
3. **Attach judges** with `launchdarkly-online-evals`

## Related Skills

- `launchdarkly-configs-create` - Create configs with variations
- `launchdarkly-configs-variations` - Manage variations
- `launchdarkly-online-evals` - Attach judges

## Other Resources

- [Target with AgentControl](https://docs.launchdarkly.com/home/ai-configs/target.md)
- [Targeting Rules](https://docs.launchdarkly.com/home/flags/target-rules.md)
