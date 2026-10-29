# SDK Evaluation Patterns

How to evaluate feature flags in each LaunchDarkly SDK. Use this reference to match the patterns already in use in the codebase.

## JavaScript/TypeScript (Node.js Server SDK)

```typescript
// Standard boolean evaluation
const enabled = await ldClient.boolVariation('flag-key', context, false);

// Standard string evaluation
const variant = await ldClient.stringVariation('flag-key', context, 'default');

// Standard number evaluation
const limit = await ldClient.numberVariation('flag-key', context, 10);

// JSON evaluation
const config = await ldClient.jsonVariation('flag-key', context, {});

// Generic evaluation (returns any type)
const value = await ldClient.variation('flag-key', context, defaultValue);

// With evaluation details (includes reason for the variation served)
const detail = await ldClient.boolVariationDetail('flag-key', context, false);
// detail.value, detail.variationIndex, detail.reason

// All flags at once
const allFlags = await ldClient.allFlagsState(context);
```

## JavaScript/TypeScript (React SDK)

```tsx
// Hook-based (most common in React)
import { useFlags, useLDClient } from 'launchdarkly-react-client-sdk';

function MyComponent() {
  const { flagKey } = useFlags();         // camelCase access
  const flags = useFlags();
  const value = flags['flag-key'];        // bracket access for kebab-case keys

  // Direct client access when needed
  const ldClient = useLDClient();
  const variant = ldClient?.variation('flag-key', 'default');
}

// HOC pattern (older codebases)
import { withLDConsumer } from 'launchdarkly-react-client-sdk';

class MyComponent extends React.Component {
  render() {
    const enabled = this.props.flags['flag-key'];
    return enabled ? <NewFeature /> : <OldFeature />;
  }
}
export default withLDConsumer()(MyComponent);
```

## Python

```python
# Standard evaluation
enabled = ld_client.variation('flag-key', context, False)

# Typed evaluations
enabled = ld_client.bool_variation('flag-key', context, False)
variant = ld_client.string_variation('flag-key', context, 'default')
limit = ld_client.int_variation('flag-key', context, 10)
ratio = ld_client.float_variation('flag-key', context, 0.0)
config = ld_client.json_variation('flag-key', context, {})

# With details
detail = ld_client.variation_detail('flag-key', context, False)
# detail.value, detail.variation_index, detail.reason

# All flags
all_flags = ld_client.all_flags_state(context)
```

## Go

```go
// Typed evaluations
enabled, err := ldClient.BoolVariation("flag-key", context, false)
variant, err := ldClient.StringVariation("flag-key", context, "default")
limit, err := ldClient.IntVariation("flag-key", context, 10)
ratio, err := ldClient.Float64Variation("flag-key", context, 0.0)
config, err := ldClient.JSONVariation("flag-key", context, ldvalue.Null())

// With details
detail, err := ldClient.BoolVariationDetail("flag-key", context, false)
// detail.Value, detail.VariationIndex, detail.Reason

// All flags
allFlags := ldClient.AllFlagsState(context)
```

## Java/Kotlin

```java
// Typed evaluations
boolean enabled = ldClient.boolVariation("flag-key", context, false);
String variant = ldClient.stringVariation("flag-key", context, "default");
int limit = ldClient.intVariation("flag-key", context, 10);
double ratio = ldClient.doubleVariation("flag-key", context, 0.0);
LDValue config = ldClient.jsonValueVariation("flag-key", context, LDValue.ofNull());

// With details
EvaluationDetail<Boolean> detail = ldClient.boolVariationDetail("flag-key", context, false);
// detail.getValue(), detail.getVariationIndex(), detail.getReason()

// All flags
FeatureFlagsState allFlags = ldClient.allFlagsState(context);
```

## Ruby

```ruby
# Standard evaluation
enabled = ld_client.variation('flag-key', context, false)

# Typed evaluations
enabled = ld_client.bool_variation('flag-key', context, false)
variant = ld_client.string_variation('flag-key', context, 'default')
limit = ld_client.number_variation('flag-key', context, 10)
config = ld_client.json_variation('flag-key', context, {})

# With details
detail = ld_client.variation_detail('flag-key', context, false)
# detail.value, detail.variation_index, detail.reason

# All flags
all_flags = ld_client.all_flags_state(context)
```

## .NET (C#)

```csharp
// Typed evaluations
bool enabled = ldClient.BoolVariation("flag-key", context, false);
string variant = ldClient.StringVariation("flag-key", context, "default");
int limit = ldClient.IntVariation("flag-key", context, 10);
float ratio = ldClient.FloatVariation("flag-key", context, 0.0f);
double precise = ldClient.DoubleVariation("flag-key", context, 0.0);
LdValue config = ldClient.JsonVariation("flag-key", context, LdValue.Null);

// With details
EvaluationDetail<bool> detail = ldClient.BoolVariationDetail("flag-key", context, false);
// detail.Value, detail.VariationIndex, detail.Reason

// All flags
FeatureFlagsState allFlags = ldClient.AllFlagsState(context);
```

## Common Wrapper Patterns

Many teams build abstraction layers over the SDK. Search for these in addition to direct SDK calls:

```typescript
// Service/utility wrappers
featureFlagService.isEnabled('flag-key');
featureFlagService.getValue('flag-key');
FeatureFlags.isEnabled('flag-key');
flagsClient.check('flag-key');

// Constants/enums for flag keys
FLAGS.NEW_CHECKOUT_FLOW
FeatureFlag.NEW_CHECKOUT_FLOW
FEATURE_FLAGS['flag-key']
const FLAG_KEY = 'flag-key';

// Decorator patterns (Python/Java)
@feature_flag('flag-key')
@FeatureFlag("flag-key")

// React context/provider patterns
<FeatureFlagProvider flags={['flag-key']}>
  <ConditionalFeature flag="flag-key">
    <NewFeature />
  </ConditionalFeature>
</FeatureFlagProvider>

// Configuration files (YAML, JSON)
feature_flags:
  flag-key: true
```

## Adding a New Flag Evaluation

When adding flag evaluation code, follow this pattern:

1. **Import/access the client** the same way existing code does
2. **Define the flag key** following the project's convention (constants file, inline, etc.)
3. **Choose the right evaluation method** based on the flag type
4. **Set a safe default value**: the behavior when LaunchDarkly is unreachable
5. **Add the conditional logic** for each variation

### Example: Adding a boolean flag (Node.js)

```typescript
// If the codebase uses constants:
// In flags.ts / constants.ts
export const NEW_CHECKOUT_FLOW = 'new-checkout-flow';

// In the feature code:
import { NEW_CHECKOUT_FLOW } from '../flags';

const showNewCheckout = await ldClient.boolVariation(
  NEW_CHECKOUT_FLOW,
  context,
  false  // default: keep old behavior if LD is unreachable
);

if (showNewCheckout) {
  return renderNewCheckout();
} else {
  return renderOldCheckout();
}
```

### Example: Adding a boolean flag (React)

```tsx
import { useFlags } from 'launchdarkly-react-client-sdk';

function CheckoutPage() {
  const { newCheckoutFlow } = useFlags();

  if (newCheckoutFlow) {
    return <NewCheckout />;
  }
  return <OldCheckout />;
}
```
