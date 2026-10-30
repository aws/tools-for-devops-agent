# SDK Track Patterns

How to call `track()` in each LaunchDarkly SDK. Use this reference to match the patterns already in use in the codebase — and to add the right call when starting fresh.

The key distinction across all SDKs: **server-side SDKs require a context per call; client-side SDKs do not.**

---

## JavaScript / TypeScript — Node.js (Server-side)

**Package:** `@launchdarkly/node-server-sdk` (v9+) or `launchdarkly-node-server-sdk` (v6–v8)

```bash
npm install @launchdarkly/node-server-sdk
```

```typescript
import * as ld from '@launchdarkly/node-server-sdk';

const client = ld.init(process.env.LD_SDK_KEY!);
await client.waitForInitialization();

// Count / occurrence metric (no metricValue)
client.track('checkout-completed', context);

// Value metric — pass the measurement as metricValue
client.track('api-response-time', context, null, responseTimeMs);

// With custom data payload
client.track('item-purchased', context, { itemId: 'abc123', category: 'apparel' }, purchaseAmount);

// Flush explicitly in tests / short-lived processes
await client.flush();
```

---

## JavaScript / TypeScript — Browser (Client-side)

**Package:** `launchdarkly-js-client-sdk`

```bash
npm install launchdarkly-js-client-sdk
```

```typescript
import * as ld from 'launchdarkly-js-client-sdk';

const client = ld.initialize(clientSideId, context);
await client.waitForInitialization();

// Count / occurrence metric — no context, no metricValue
client.track('signup-completed');

// Value metric
client.track('page-load-time', null, performanceMs);

// With custom data
client.track('item-added-to-cart', { itemId: 'abc123' }, itemPrice);

// Flush (useful in tests or before navigating away)
await client.flush();
```

---

## React (Client-side)

**Package:** `launchdarkly-react-client-sdk`

```bash
npm install launchdarkly-react-client-sdk
```

```tsx
import { useLDClient } from 'launchdarkly-react-client-sdk';

function CheckoutButton() {
  const ldClient = useLDClient();

  const handleSubmit = async () => {
    await processCheckout();

    // Count / occurrence metric
    ldClient?.track('checkout-completed');

    // Value metric
    ldClient?.track('checkout-revenue', null, orderTotal);
  };

  return <button onClick={handleSubmit}>Complete Order</button>;
}
```

**Initialization** (typically in the app root via `LDProvider` or `asyncWithLDProvider`):

```tsx
import { LDProvider } from 'launchdarkly-react-client-sdk';

// Wrap your app — context is set here, not in each track() call
<LDProvider clientSideID={clientSideId} context={userContext}>
  <App />
</LDProvider>
```

---

## Python (Server-side)

**Package:** `launchdarkly-server-sdk`

```bash
pip install launchdarkly-server-sdk
```

```python
import ldclient
from ldclient.config import Config

ldclient.set_config(Config(sdk_key))
client = ldclient.get()

# Count / occurrence metric
client.track('checkout-completed', context)

# Value metric
client.track('api-response-time', context, None, response_time_ms)

# With data payload
client.track('item-purchased', context, {'item_id': 'abc123'}, purchase_amount)

# Flush
client.flush()
```

---

## Go (Server-side)

**Package:** `github.com/launchdarkly/go-server-sdk/v7`

```bash
go get github.com/launchdarkly/go-server-sdk/v7
```

```go
import (
    ld "github.com/launchdarkly/go-server-sdk/v7"
    "github.com/launchdarkly/go-server-sdk/v7/ldcontext"
)

client, _ := ld.MakeClient(sdkKey, 5*time.Second)
defer client.Close()

// Count / occurrence metric
client.TrackEvent("checkout-completed", context)

// Value metric
client.TrackMetric("api-response-time", context, responseTimeMs, nil)

// With data payload
data := ldvalue.BuildObject().Set("itemId", ldvalue.String("abc123")).Build()
client.TrackData("item-purchased", context, data)
```

---

## Java (Server-side)

**Package:** `com.launchdarkly:launchdarkly-java-server-sdk`

```xml
<!-- Maven -->
<dependency>
  <groupId>com.launchdarkly</groupId>
  <artifactId>launchdarkly-java-server-sdk</artifactId>
  <version>7.x.x</version>
</dependency>
```

```java
LDClient client = new LDClient(sdkKey);

// Count / occurrence metric
client.track("checkout-completed", context);

// Value metric
client.trackMetric("api-response-time", context, responseTimeMs);

// With data payload
LDValue data = LDValue.buildObject().put("itemId", "abc123").build();
client.trackData("item-purchased", context, data);
client.trackMetric("item-purchased", context, purchaseAmount);

// Flush
client.flush();
client.close();
```

---

## Ruby (Server-side)

**Package:** `launchdarkly-server-sdk`

```bash
gem install launchdarkly-server-sdk
```

```ruby
require 'ldclient-rb'

client = LaunchDarkly::LDClient.new(sdk_key)

# Count / occurrence metric
client.track('checkout-completed', context)

# Value metric
client.track('api-response-time', context, nil, response_time_ms)

# With data payload
client.track('item-purchased', context, { item_id: 'abc123' }, purchase_amount)

# Flush
client.flush
```

---

## .NET / C# (Server-side)

**Package:** `LaunchDarkly.ServerSdk`

```bash
dotnet add package LaunchDarkly.ServerSdk
```

```csharp
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

var client = new LdClient(sdkKey);

// Count / occurrence metric
client.Track("checkout-completed", context);

// Value metric
client.Track("api-response-time", context, LdValue.Null, responseTimeMs);

// With data payload
var data = LdValue.BuildObject().Add("itemId", "abc123").Build();
client.Track("item-purchased", context, data, purchaseAmount);

// Flush
client.Flush();
```

---

## iOS / Swift (Client-side)

**Package:** `LaunchDarkly` via Swift Package Manager or CocoaPods

```swift
import LaunchDarkly

// Context set during LDClient.start() — not required per track call

// Count / occurrence metric
LDClient.get()!.trackEvent(key: "checkout-completed")

// Value metric
LDClient.get()!.trackEvent(key: "api-response-time", metricValue: responseTimeMs)

// With data payload
LDClient.get()!.trackEvent(key: "item-purchased", data: ["itemId": "abc123"], metricValue: purchaseAmount)

// Flush
LDClient.get()!.flush()
```

---

## Android / Kotlin (Client-side)

**Package:** `com.launchdarkly:launchdarkly-android-client-sdk`

```kotlin
// Context set during LDClient.init() — not required per track call
val client = LDClient.get()

// Count / occurrence metric
client.trackEvent("checkout-completed")

// Value metric
client.trackMetric("api-response-time", null, responseTimeMs)

// With data payload
val data = LDValue.buildObject().put("itemId", "abc123").build()
client.trackData("item-purchased", data, purchaseAmount)

// Flush
client.flush()
```

---

## Common Wrapper Patterns

Many teams abstract LaunchDarkly calls behind a service or utility. Search for these patterns before adding a raw `ldClient.track()` call:

```typescript
// Service wrappers
analyticsService.track('event-key');
featureFlagService.trackEvent('event-key', context);
tracking.record('event-key', metricValue);

// Module-level wrappers
import { trackEvent } from '../lib/launchdarkly';
trackEvent('event-key', context, metricValue);

// Class-based
this.ldService.track('event-key');
LDWrapper.getInstance().track('event-key');
```

If any of these exist, add the new call through the same wrapper — don't bypass it.

---

## `metricValue` Quick Reference

| Metric type | Pass `metricValue`? | Example |
|-------------|---------------------|---------|
| `count` | No — omit it | `client.track('button-clicked', context)` |
| `occurrence` | No — omit it | `client.track('signup-completed', context)` |
| `value` (average) | Yes — the measurement | `client.track('page-load', context, null, 342)` |
| `value` (sum) | Yes — the per-event amount | `client.track('revenue', context, null, 49.99)` |

The `data` parameter (before `metricValue`) is for arbitrary metadata — order IDs, category names, etc. It does not affect metric calculations.
