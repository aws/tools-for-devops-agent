# Targeting Patterns

Reference for all targeting operations available through the LaunchDarkly API semantic patch system.

## Toggle Flag On/Off

The simplest targeting change.

```json
{"kind": "turnFlagOn"}
```

```json
{"kind": "turnFlagOff"}
```

**Notes:**
- Turning a flag OFF makes it serve the `offVariation` to everyone, regardless of rules or targets.
- Turning a flag ON activates the full targeting evaluation (individual targets -> rules -> default rule).

## Percentage Rollouts (Default Rule)

The default rule (fallthrough) is what applies when no individual targets or custom rules match.

### Serve a single variation to everyone

```json
{
  "kind": "updateFallthroughVariationOrRollout",
  "variationId": "<variation-id>"
}
```

Or by index:

```json
{
  "kind": "updateFallthroughVariationOrRollout",
  "variationId": "<variation-id-of-index-0>"
}
```

### Percentage rollout

```json
{
  "kind": "updateFallthroughVariationOrRollout",
  "rolloutWeights": {
    "<variation-id-0>": 25000,
    "<variation-id-1>": 75000
  }
}
```

**Note on weights:** The API uses weights scaled by 1000. So:
- 25% = 25000
- 50% = 50000
- 75% = 75000
- 100% = 100000

Weights must sum to 100000.

### Common rollout patterns

| Goal | Weights (variation 0 / variation 1) |
|------|-------------------------------------|
| 1% canary | 1000 / 99000 |
| 10% canary | 10000 / 90000 |
| 25% rollout | 25000 / 75000 |
| 50/50 A/B test | 50000 / 50000 |
| Full rollout (100%) | Use single variation instead of rollout |
| Kill switch | Turn flag OFF instead of changing rollout |

## Custom Targeting Rules

Rules let you target specific segments of users based on context attributes.

### Add a rule

```json
{
  "kind": "addRule",
  "clauses": [
    {
      "contextKind": "user",
      "attribute": "email",
      "op": "endsWith",
      "values": ["@company.com"],
      "negate": false
    }
  ],
  "variationId": "<variation-id>",
  "description": "Internal users"
}
```

### Rule clause operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `in` | Exact match (any value in list) | `attribute: "country", values: ["US", "CA"]` |
| `endsWith` | String ends with | `attribute: "email", values: ["@company.com"]` |
| `startsWith` | String starts with | `attribute: "name", values: ["test-"]` |
| `matches` | Regex match | `attribute: "email", values: [".*@company\\.com"]` |
| `contains` | String contains | `attribute: "plan", values: ["enterprise"]` |
| `lessThan` | Numeric less than | `attribute: "age", values: [18]` |
| `greaterThan` | Numeric greater than | `attribute: "score", values: [100]` |
| `semVerEqual` | Semantic version equals | `attribute: "version", values: ["2.0.0"]` |
| `semVerGreaterThan` | Semver greater than | `attribute: "version", values: ["1.5.0"]` |
| `semVerLessThan` | Semver less than | `attribute: "version", values: ["3.0.0"]` |

### Multiple clauses (AND logic)

Clauses within a single rule are ANDed. All must match for the rule to apply:

```json
{
  "kind": "addRule",
  "clauses": [
    {
      "contextKind": "user",
      "attribute": "plan",
      "op": "in",
      "values": ["enterprise"]
    },
    {
      "contextKind": "user",
      "attribute": "country",
      "op": "in",
      "values": ["US"]
    }
  ],
  "variationId": "<variation-id>",
  "description": "US enterprise users"
}
```

### Rule with percentage rollout

Instead of serving a single variation, a rule can do a percentage rollout:

```json
{
  "kind": "addRule",
  "clauses": [
    {
      "contextKind": "user",
      "attribute": "beta",
      "op": "in",
      "values": [true]
    }
  ],
  "rolloutWeights": {
    "<variation-id-0>": 50000,
    "<variation-id-1>": 50000
  },
  "description": "50/50 for beta users"
}
```

### Remove a rule

```json
{
  "kind": "removeRule",
  "ruleId": "<rule-id>"
}
```

The `ruleId` (also shown as `_id`) can be found in the flag's current configuration.

### Reorder rules

```json
{
  "kind": "reorderRules",
  "ruleIds": ["<rule-id-1>", "<rule-id-2>", "<rule-id-3>"]
}
```

Rule order matters: rules evaluate top to bottom, first match wins.

### Update a rule's variation

```json
{
  "kind": "updateRuleVariationOrRollout",
  "ruleId": "<rule-id>",
  "variationId": "<variation-id>"
}
```

### Add/remove clauses on a rule

```json
{
  "kind": "addClauses",
  "ruleId": "<rule-id>",
  "clauses": [
    {
      "contextKind": "user",
      "attribute": "country",
      "op": "in",
      "values": ["UK"]
    }
  ]
}
```

```json
{
  "kind": "removeClauses",
  "ruleId": "<rule-id>",
  "clauseIds": ["<clause-id>"]
}
```

## Individual Targets

Individual targets are the highest priority: they override all rules.

### Add users to a variation

```json
{
  "kind": "addTargets",
  "variationId": "<variation-id>",
  "values": ["user-key-1", "user-key-2"]
}
```

### Remove users from a variation

```json
{
  "kind": "removeTargets",
  "variationId": "<variation-id>",
  "values": ["user-key-1"]
}
```

### Context-kind targets (non-user)

For custom context kinds (device, organization, etc.):

```json
{
  "kind": "addContextTargets",
  "contextKind": "organization",
  "variationId": "<variation-id>",
  "values": ["org-123", "org-456"]
}
```

```json
{
  "kind": "removeContextTargets",
  "contextKind": "organization",
  "variationId": "<variation-id>",
  "values": ["org-123"]
}
```

### Replace all targets for a variation

```json
{
  "kind": "replaceTargets",
  "variationId": "<variation-id>",
  "values": ["user-key-1", "user-key-2"]
}
```

**Warning:** This replaces ALL targets for the variation, not just adds to them.

## Cross-Environment Config Copying

Copy targeting configuration from one environment to another.

This is a separate API call (not a semantic patch). Use the flag copy endpoint:

- **Source:** The environment to copy from
- **Target:** The environment to copy to
- **Included actions:** Selectively copy `updateOn` (toggle state), `updateRules`, `updateFallthrough`, `updateOffVariation`, `updatePrerequisites`, `updateTargets`

### Common use case: promote staging to production

Copy the full targeting config from staging after testing:

```
source: "staging"
target: "production"
includedActions: ["updateOn", "updateRules", "updateFallthrough", "updateOffVariation", "updateTargets"]
```

**Note:** The target environment may have approval requirements. If so, the copy operation creates an approval request instead of applying immediately.

## Batching Instructions

Multiple instructions can be batched. For example, turning on and setting a rollout in one call to `toggle-flag` and `update-rollout`, or sending multiple rule changes to `update-targeting-rules`:

```json
{
  "environmentKey": "production",
  "instructions": [
    {"kind": "turnFlagOn"},
    {
      "kind": "updateFallthroughVariationOrRollout",
      "rolloutWeights": {
        "<variation-id-0>": 10000,
        "<variation-id-1>": 90000
      }
    }
  ],
  "comment": "Turning on with 10% rollout"
}
```

This is preferred over multiple separate calls: it's atomic (all changes apply together or none do).
