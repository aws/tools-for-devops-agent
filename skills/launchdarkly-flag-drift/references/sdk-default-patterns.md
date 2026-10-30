# SDK Default Patterns Reference

How to find the **fallback default**: the value the SDK returns when LaunchDarkly is unreachable, uninitialized, or the flag is unavailable. This is the argument this skill compares against the flag's default rule (fallthrough) and, on drift, the only thing it changes.

## How to Spot the Default Argument

In a direct SDK evaluation, the arguments are usually: **flag key**, **context/user**, **default**. The default is almost always the **last positional argument**. Do not confuse it with the context.

```text
ldClient.<typed>Variation( "<flag-key>", <context>, <DEFAULT> )
                            ^ key         ^ context   ^ the value this skill checks
```

The default's type should match the flag's variation type (bool flag → boolean default, string flag → string default, etc.). A type mismatch is a bug worth flagging.

## Direct Evaluation by Language

### JavaScript / TypeScript (Node & client)

```typescript
ldClient.variation('flag-key', context, defaultValue);
ldClient.boolVariation('flag-key', context, false);      // default = false
ldClient.stringVariation('flag-key', context, 'control'); // default = 'control'
ldClient.numberVariation('flag-key', context, 0);
ldClient.jsonVariation('flag-key', context, {});
ldClient.variationDetail('flag-key', context, defaultValue);
```

React SDK note: `useFlags()` reads already-evaluated values and does not expose a per-call default. The default for those flags is set where `LDProvider` / `asyncWithLDProvider` is configured (`flags` bootstrap / default map). Check the provider setup, not the call site.

### Python

```python
ld_client.variation('flag-key', context, default_value)
ld_client.bool_variation('flag-key', context, False)
ld_client.string_variation('flag-key', context, 'control')
ld_client.int_variation('flag-key', context, 0)
ld_client.variation_detail('flag-key', context, default_value)
```

### Go

```go
ldClient.BoolVariation("flag-key", context, false)      // default = false
ldClient.StringVariation("flag-key", context, "control")
ldClient.IntVariation("flag-key", context, 0)
ldClient.JSONVariation("flag-key", context, ldvalue.Null())
ldClient.BoolVariationDetail("flag-key", context, false)
```

### Java / Kotlin

```java
ldClient.boolVariation("flag-key", context, false);
ldClient.stringVariation("flag-key", context, "control");
ldClient.intVariation("flag-key", context, 0);
ldClient.jsonValueVariation("flag-key", context, LDValue.ofNull());
```

### Ruby

```ruby
ld_client.variation('flag-key', context, default_value)
ld_client.bool_variation('flag-key', context, false)
ld_client.string_variation('flag-key', context, 'control')
```

### .NET (C#)

```csharp
ldClient.BoolVariation("flag-key", context, false);
ldClient.StringVariation("flag-key", context, "control");
ldClient.IntVariation("flag-key", context, 0);
ldClient.JsonVariation("flag-key", context, LdValue.Null);
```

## Abstraction Patterns (where the default is declared once)

Many teams don't call the SDK directly at each site. They declare the default in a central place, then read the flag by key elsewhere. When present, the default in these declarations is the value to check and reconcile.

### Wrapper / service method

```typescript
featureFlags.getBool('flag-key', false);   // default = false
featureFlags.getValue('flag-key', 'control');
```

Open the wrapper implementation to confirm how the passed value flows into the underlying `variation(...)` call.

### Registry / config map (one default per flag)

```typescript
// A central flag registry
const flags = {
  'new-checkout-flow': createFlag('new-checkout-flow', /* default */ false),
};
```

```yaml
# A config file of flag defaults
feature_flags:
  new-checkout-flow: false
```

### Annotation / struct-tag defaults

Some typed languages encode the default in metadata rather than an argument.

```go
type Flags struct {
    NewCheckoutFlow bool `ld:"new-checkout-flow,false"` // default = false
}
```

```java
@FeatureFlag(key = "new-checkout-flow", defaultValue = "false")
boolean newCheckoutFlow;
```

Reconcile the value inside the annotation/tag, not a downstream copy of it.

### Generated default files

When flag defaults are compiled into a generated file (e.g. an auto-generated defaults map or typed accessor), **do not hand-edit the generated output**. Change the source of truth (the registry, annotation, or codegen input) and re-run the project's generation step. Mark `requires_generation: true` in the summary.

## Search Strategy

Search for the flag key with several forms, since codebases mix conventions:

```bash
# Exact key, both quote styles
rg "'flag-key'" ; rg '"flag-key"'

# camelCase accessor (kebab keys often surface as camelCase in code)
rg "flagKey"

# Wrapper / registry / config usage and constants
rg "flag-key|flagKey|FLAG_KEY"

# Likely declaration sites
rg "flag-key" -g '*flags*' -g '*.constants.*' -g '*config*'
```

For each hit, decide whether it is: a direct evaluation (default = last arg), a declaration (default = the declared value), or a read of an already-declared flag (trace back to the declaration). Reconcile at the declaration; read sites need no change.
