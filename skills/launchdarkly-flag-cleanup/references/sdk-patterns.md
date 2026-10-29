# SDK Patterns Reference

Common flag evaluation patterns by SDK and language. Search for these patterns when finding flag references.

## JavaScript/TypeScript (Node.js)

```typescript
// Standard evaluation
ldClient.variation('flag-key', context, defaultValue);
ldClient.boolVariation('flag-key', context, false);
ldClient.stringVariation('flag-key', context, 'default');
ldClient.numberVariation('flag-key', context, 0);
ldClient.jsonVariation('flag-key', context, {});

// With details (includes reason)
ldClient.variationDetail('flag-key', context, defaultValue);
ldClient.boolVariationDetail('flag-key', context, false);

// All flags
ldClient.allFlagsState(context);
```

## JavaScript/TypeScript (Browser/React)

```typescript
// React SDK hooks
const { flags } = useFlags();
const flagValue = flags['flag-key'];
const flagValue = flags.flagKey; // camelCase access

// useLDClient hook
const ldClient = useLDClient();
ldClient.variation('flag-key', defaultValue);

// withLDConsumer HOC
this.props.flags['flag-key']
this.props.ldClient.variation('flag-key', defaultValue);

// Direct client usage
LDClient.variation('flag-key', defaultValue);
```

## Python

```python
# Standard evaluation
ld_client.variation('flag-key', context, default_value)
ld_client.bool_variation('flag-key', context, False)
ld_client.string_variation('flag-key', context, 'default')
ld_client.int_variation('flag-key', context, 0)
ld_client.float_variation('flag-key', context, 0.0)
ld_client.json_variation('flag-key', context, {})

# With details
ld_client.variation_detail('flag-key', context, default_value)
ld_client.bool_variation_detail('flag-key', context, False)

# All flags
ld_client.all_flags_state(context)
```

## Go

```go
// Standard evaluation
ldClient.BoolVariation("flag-key", context, false)
ldClient.StringVariation("flag-key", context, "default")
ldClient.IntVariation("flag-key", context, 0)
ldClient.Float64Variation("flag-key", context, 0.0)
ldClient.JSONVariation("flag-key", context, ldvalue.Null())

// With details
ldClient.BoolVariationDetail("flag-key", context, false)
ldClient.StringVariationDetail("flag-key", context, "default")

// All flags
ldClient.AllFlagsState(context)
```

## Java/Kotlin

```java
// Standard evaluation
ldClient.boolVariation("flag-key", context, false);
ldClient.stringVariation("flag-key", context, "default");
ldClient.intVariation("flag-key", context, 0);
ldClient.doubleVariation("flag-key", context, 0.0);
ldClient.jsonValueVariation("flag-key", context, LDValue.ofNull());

// With details
ldClient.boolVariationDetail("flag-key", context, false);
ldClient.stringVariationDetail("flag-key", context, "default");

// All flags
ldClient.allFlagsState(context);
```

## Ruby

```ruby
# Standard evaluation
ld_client.variation('flag-key', context, default_value)
ld_client.bool_variation('flag-key', context, false)
ld_client.string_variation('flag-key', context, 'default')
ld_client.number_variation('flag-key', context, 0)
ld_client.json_variation('flag-key', context, {})

# With details
ld_client.variation_detail('flag-key', context, default_value)

# All flags
ld_client.all_flags_state(context)
```

## .NET (C#)

```csharp
// Standard evaluation
ldClient.BoolVariation("flag-key", context, false);
ldClient.StringVariation("flag-key", context, "default");
ldClient.IntVariation("flag-key", context, 0);
ldClient.FloatVariation("flag-key", context, 0.0f);
ldClient.DoubleVariation("flag-key", context, 0.0);
ldClient.JsonVariation("flag-key", context, LdValue.Null);

// With details
ldClient.BoolVariationDetail("flag-key", context, false);
ldClient.StringVariationDetail("flag-key", context, "default");

// All flags
ldClient.AllFlagsState(context);
```

## Common Wrapper Patterns

Many teams create abstraction layers. Search for these patterns too:

```typescript
// Service wrappers
featureFlagService.isEnabled('flag-key');
featureFlagService.getValue('flag-key');
featureFlagService.getFlag('flag-key');
FeatureFlags.isEnabled('flag-key');

// Constants/enums
FLAGS.NEW_CHECKOUT_FLOW
FeatureFlag.NEW_CHECKOUT_FLOW
FEATURE_FLAGS['flag-key']

// Decorator patterns (Python/Java)
@feature_flag('flag-key')
@FeatureFlag("flag-key")

// Configuration files
feature_flags:
  flag-key: true
```

## Search Strategies

When searching for flag references, use multiple patterns:

```bash
# Exact string match
grep -r "'flag-key'" .
grep -r '"flag-key"' .

# Case variations (kebab-case to camelCase)
grep -r "flagKey" .

# Partial matches for wrapper usage
grep -r "flag-key\|flagKey\|FLAG_KEY" .

# Check constants files
grep -r "flag-key" . --include="*.constants.*"
grep -r "flag-key" . --include="*flags*"
```

## Removal Patterns

### Boolean flag (forward value = true)

```typescript
// Before
if (ldClient.variation('flag-key', user, false)) {
  doNewThing();
} else {
  doOldThing();
}

// After
doNewThing();
```

### Boolean flag (forward value = false)

```typescript
// Before
if (ldClient.variation('flag-key', user, false)) {
  doNewThing();
} else {
  doOldThing();
}

// After
doOldThing();
```

### String/multivariate flag

```typescript
// Before
const variant = ldClient.variation('flag-key', user, 'control');
switch (variant) {
  case 'new':
    return renderNew();
  case 'experimental':
    return renderExperimental();
  default:
    return renderControl();
}

// After (forward value = 'new')
return renderNew();
```

### Early return pattern

```typescript
// Before
const enabled = ldClient.variation('flag-key', user, false);
if (!enabled) {
  return null;
}
return <NewFeature />;

// After (forward value = true)
return <NewFeature />;

// After (forward value = false)
return null;
```
