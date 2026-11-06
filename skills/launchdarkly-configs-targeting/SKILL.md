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
| `get-agent-configs` with `configKey`, `section: "targeting"` and `env` | Read the variations, individual targets, rules, default rule and off variation in one environment (read-only) |
| `get-agent-configs` with `configKey` | Read variation keys and what each variation contains (read-only) |
| `get-agent-configs` with `configKey` and `section: "status"` | See where the config is active before you change it (read-only) |
| `update-agent-config` with `resource: "targeting"` | Change one environment's targeting in one write: turn it on or off (`on`), set the default rule (`fallthrough`), and change rules and individual targets (`targetingInstructions`) |
| `create-agent-config-approval` | Submit a change for review when the environment requires approval |
| `get-agent-config-approvals` | Check whether a submitted change was approved (read-only) |
| `apply-agent-config-approval` | Apply a change after a person approved it |
| `search-members` | Find a reviewer's member ID (read-only) |
| `search-change-history` | Find earlier targeting changes, with `resourceKind: "aiconfig"` (read-only) |

`update-agent-config` with `resource: "targeting"` changes what live traffic receives and requires `confirm: true`. Before calling it, tell the user what the config serves now and what will change, and pass `confirm: true` only after they agree.

## Core Concepts

### Evaluation Order

Targeting rules evaluate in this order (same as feature flags):

1. **Individual targets** - Specific context keys (highest priority)
2. **Custom rules** - Attribute or segment conditions, top to bottom; the first match wins
3. **Default rule** - Fallthrough for all others

When an environment's targeting is off (`on: false`), every context gets the off variation instead. A new config's default rule serves an auto-generated disabled variation, so to start serving a variation, change the default rule. The `turnTargetingOn` instruction does not work for configs; use the `on` field.

### Key Concepts

- **variationKey**: `fallthrough` and `targetingInstructions` take a `variationKey`: a variation key or name from `get-agent-configs`. You don't need variation UUIDs or indexes.
- **Percentages**: a `fallthrough` split takes whole percentages that sum to 100.
- **Clause logic**: Multiple clauses = AND, multiple values = OR
- **Null attributes**: Rules with null/missing attributes are skipped
- **Approvals**: When the environment requires approval, `update-agent-config` makes no change and returns `requiresApproval: true` with the instructions to submit (Step 5).

## Workflow

### Step 1: Read the Current Targeting

Call `get-agent-configs` with `projectKey`, `configKey`, `section: "targeting"` and `env`. Note the variation keys and names, each rule's `_id` and its clauses' `_id` values, the individual targets, and what the default rule serves. Call `get-agent-configs` with only `projectKey` and `configKey` to see what each variation contains.

### Step 2: Edit the Default Rule

Call `update-agent-config` with `resource: "targeting"` and a `fallthrough`:

```json
{
  "projectKey": "my-project",
  "configKey": "chat-assistant",
  "resource": "targeting",
  "env": "production",
  "fallthrough": {"variationKey": "v1-gpt4o"},
  "confirm": true
}
```

- To serve one variation to every context no rule matches: `"fallthrough": {"variationKey": "v1-gpt4o"}`.
- To split that traffic: `"fallthrough": {"weights": [{"variationKey": "v1-gpt4o", "percent": 80}, {"variationKey": "v2-claude", "percent": 20}]}`.

> **Important:** A new config's default rule serves an auto-generated disabled variation. Until you point the default rule at a real variation, the SDK returns `enabled=False` to every context.

Tell the user what the default rule served before (from Step 1) and what it serves now, so they can undo the change.

### Step 3: Add Targeting Rules

Call `update-agent-config` with `resource: "targeting"` and one or more `targetingInstructions`. The rule kinds are `addRule`, `removeRule`, `addClauses`, `removeClauses`, `reorderRules`, `replaceRules`, `updateRuleDescription`, `addValuesToClause`, `removeValuesFromClause` and `updateClause`. Take `ruleId` and `clauseId` from the `_id` values in Step 1.

**Attribute-based rule:**

```json
{
  "projectKey": "my-project",
  "configKey": "model-selector",
  "resource": "targeting",
  "env": "production",
  "targetingInstructions": [{
    "kind": "addRule",
    "variationKey": "sonnet",
    "clauses": [{
      "contextKind": "user",
      "attribute": "selectedModel",
      "op": "contains",
      "values": ["sonnet"],
      "negate": false
    }]
  }],
  "confirm": true
}
```

**Segment rule** (the instruction only):

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

Use `targetingInstructions` with `addTargets`, `removeTargets`, `clearTargets` or `replaceTargets`. `addTargets` and `removeTargets` require `contextKind` and `values`:

```json
{
  "projectKey": "my-project",
  "configKey": "chat-assistant",
  "resource": "targeting",
  "env": "production",
  "targetingInstructions": [{
    "kind": "addTargets",
    "variationKey": "v1-gpt4o",
    "contextKind": "user",
    "values": ["user-key-1"]
  }],
  "confirm": true
}
```

Individual targets override every rule.

### Step 5: Submit for Approval When Required

If `update-agent-config` returns `requiresApproval: true`, the change wasn't made. Ask the user who should review it; if they name a person, find their member ID with `search-members`. Then call `create-agent-config-approval` with the environment, at least one reviewer in `notifyMemberIds` or `notifyTeamKeys`, and the returned instructions. Show the user the request's `approvalRequest.url`: a person approves or declines it in LaunchDarkly, and you can't. When the user says it has been reviewed, check it once with `get-agent-config-approvals` and the request's `id`. Only when `reviewStatus` is `approved`, apply it with `apply-agent-config-approval` (`id` and `confirm: true`). If it is pending or declined, tell the user and don't apply it.

### Step 6: Verify

Call `get-agent-configs` with `section: "targeting"` again and confirm that the default rule, rules and individual targets match the request. `section: "status"` shows the config's status in every environment, and `section: "health"` reports missing variations, models, prompts and tool references.

## Roll Back a Config

When a variation misbehaves, for example after a model or prompt change:

1. Call `get-agent-configs` with `section: "targeting"` and the environment to find what serves the variation: individual targets, a rule or the default rule.
2. Find the variation that served before with `search-change-history` (`resourceKind: "aiconfig"`, `resourceKey` set to the config key, and the environment). If the history doesn't show it, ask the user which variation to restore.
3. If the default rule serves it, call `update-agent-config` with `resource: "targeting"` and `"fallthrough": {"variationKey": "<earlier variation>"}`. If a rule or individual targets serve it, change that rule (Step 3) or those targets (Step 4). If no earlier variation is safe to serve, turning targeting off with `on: false` serves the off variation to every context in that environment.
4. Verify as in Step 6, and tell the user what you changed.

If the variation itself was edited (its prompt or model changed, not which variation serves), restore its earlier version as described in `launchdarkly-configs-update`.

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
| 404 | Config not found | Verify projectKey and configKey: `get-agent-configs` without `configKey` lists the project's configs |
| Unknown variation | `variationKey` matches no variation | Use a variation key or name from `get-agent-configs` |

## Next Steps

After configuring targeting:
1. **Provide config URL:**
   ```
   https://app.launchdarkly.com/projects/{projectKey}/ai-configs/{configKey}
   ```
2. **Check health** with `get-agent-configs` and `section: "health"`
3. **Attach judges** with `launchdarkly-online-evals`

## Related Skills

- `launchdarkly-configs-create` - Create configs with variations
- `launchdarkly-configs-variations` - Manage variations
- `launchdarkly-configs-update` - Restore an earlier version of a variation
- `launchdarkly-online-evals` - Attach judges

## Other Resources

- [Target with AgentControl](https://docs.launchdarkly.com/home/ai-configs/target.md)
- [Targeting Rules](https://docs.launchdarkly.com/home/flags/target-rules.md)
