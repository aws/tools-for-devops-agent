# Flag Types and Patterns

A reference for choosing the right flag type and configuring it properly.

## Flag Kinds

### Boolean Flags

The most common type. Two variations: `true` and `false`.

**When to use:**
- Feature toggles (show/hide a feature)
- Kill switches (disable a feature in emergencies)
- Gradual rollouts (serve `true` to a percentage of traffic)
- Simple A/B tests (control vs treatment)

**Configuration:**
```json
{
  "kind": "boolean",
  "variations": [
    {"value": true},
    {"value": false}
  ]
}
```

**Convention:** Variation 0 is `true` (the new/enabled behavior), variation 1 is `false` (the old/disabled behavior). The `offVariation` should point to `false`.

### Multivariate Flags (String)

Multiple string values. Use for text variants, feature versions, or named configurations.

**When to use:**
- A/B/C tests with different copy or UI variants
- Feature version selection ("v1", "v2", "v3")
- Named configuration modes ("basic", "advanced", "enterprise")

**Configuration:**
```json
{
  "kind": "multivariate",
  "variations": [
    {"value": "control", "name": "Control"},
    {"value": "variant-a", "name": "Variant A"},
    {"value": "variant-b", "name": "Variant B"}
  ]
}
```

### Multivariate Flags (Number)

Numeric values. Use for thresholds, limits, or quantities.

**When to use:**
- Rate limits
- Timeout durations
- Feature limits (max items, max size)
- Numeric configuration that varies by audience

**Configuration:**
```json
{
  "kind": "multivariate",
  "variations": [
    {"value": 10, "name": "Default"},
    {"value": 50, "name": "Increased"},
    {"value": 100, "name": "Maximum"}
  ]
}
```

### Multivariate Flags (JSON)

Complex objects. Use for structured configuration.

**When to use:**
- Configuration objects with multiple fields
- UI layout configurations
- Feature bundles (multiple settings in one flag)

**Configuration:**
```json
{
  "kind": "multivariate",
  "variations": [
    {"value": {"theme": "light", "density": "comfortable"}, "name": "Default"},
    {"value": {"theme": "dark", "density": "compact"}, "name": "Dark Compact"}
  ]
}
```

## Naming Conventions

### Flag Keys

Flag keys are immutable identifiers. Choose carefully.

**Common conventions:**
| Convention | Example | When used |
|-----------|---------|-----------|
| `kebab-case` | `new-checkout-flow` | Most common, LaunchDarkly default |
| `snake_case` | `new_checkout_flow` | Common in Python/Ruby codebases |
| `camelCase` | `newCheckoutFlow` | Sometimes in JS/TS codebases |
| `dot.notation` | `checkout.new-flow` | Hierarchical organization |

**Always check the existing codebase** for which convention is in use before creating a new flag.

**Good key practices:**
- Descriptive but concise: `new-checkout-flow` not `the-new-checkout-flow-feature`
- Feature-oriented: `dark-mode` not `jira-1234`
- Avoid dates: `new-pricing` not `new-pricing-2025`

### Flag Names

The human-readable display name in the LaunchDarkly UI. Can be changed later (unlike keys).

**Good name practices:**
- Use title case: "New Checkout Flow"
- Be descriptive: "Dark Mode Toggle" not "DM"
- Include context: "Checkout V2 (Q1 Experiment)" can be helpful

## Temporary vs Permanent

### Temporary Flags (default)
- Expected to be removed after the feature is fully rolled out
- LaunchDarkly tracks these for cleanup reminders
- Most feature toggles and release flags are temporary

### Permanent Flags
- Long-lived configuration that should NOT be cleaned up
- Kill switches, ops toggles, plan-based feature gating
- Only mark as permanent when the user explicitly says the flag is long-lived

## Tags

Tags help organize flags in LaunchDarkly. Suggest tags based on:

| Category | Example tags |
|----------|-------------|
| Team | `team-checkout`, `team-platform` |
| Feature area | `payments`, `onboarding`, `search` |
| Flag purpose | `experiment`, `release`, `ops` |
| Lifecycle | `q1-2025`, `migration` |

## Best Practices for Variations

### Boolean Flags
- Name variations: `true` -> "Enabled" / "New behavior", `false` -> "Disabled" / "Old behavior"
- Set `offVariation` to `false` (index 1)

### Multivariate Flags
- Always include a "control" or "default" variation
- Give every variation a descriptive `name`
- Consider what the `offVariation` should be: typically the control/default
- Order variations with the default/control first

### Default Values in Code
- The default value (fallback) in your code should ALWAYS be the safe/existing behavior
- For boolean flags: default to `false` (feature off) unless the feature is already live
- For multivariate: default to the control/existing variation
- This ensures graceful degradation if LaunchDarkly is unreachable
