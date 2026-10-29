---
name: launchdarkly-metric-instrument
description: "Instrument a LaunchDarkly metric event in a codebase by adding a track() call. Use when the user wants to wire up an event, instrument an action for a metric, add tracking to a feature, or confirm that an event is flowing to LaunchDarkly."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0-experimental"
---

# LaunchDarkly Metric Instrument

You're using a skill that will guide you through adding a `track()` call to a codebase so a LaunchDarkly metric can measure it. Your job is to detect the SDK in use, find the right place in code to add the call, write it correctly, and verify that events are reaching LaunchDarkly.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `list-metric-events` — verify events are flowing after instrumentation

**Optional MCP tools (enhance workflow):**
- `get-project` — retrieve the SDK key for the right environment when SDK initialization is needed

## Workflow

### Step 1: Detect the SDK

Before writing any code, understand the LaunchDarkly setup already in this codebase.

1. **Search for existing `track()` calls.** This is the fastest signal:
   - Look for `ldClient.track(`, `.track(`, `ld.track(`
   - If any exist, they tell you the SDK type, call signature, and context pattern in one shot — mirror those exactly.

2. **Search for SDK imports and initialization** if no `track()` calls exist:
   - Check `package.json`, `requirements.txt`, `go.mod`, `Gemfile`, `*.csproj` for an LD SDK dependency
   - Look for `LDClient`, `ldclient`, `launchdarkly-server-sdk`, `launchdarkly-node-server-sdk`, `launchdarkly-react-client-sdk`, etc.
   - Find the initialization block to understand how the client is accessed across the codebase

3. **Determine client-side or server-side.** This is the most critical distinction — it determines the `track()` signature:

   | SDK type | `track()` signature | Notes |
   |----------|---------------------|-------|
   | Server-side (Node, Python, Go, Java, Ruby, .NET) | `ldClient.track(eventKey, context, data?, metricValue?)` | Context required per call |
   | Client-side (React, browser JS) | `ldClient.track(eventKey, data?, metricValue?)` | Context set at init, not per call |

   See [SDK Track Patterns](references/sdk-track-patterns.md) for full examples by language.

### Step 2: Install & Initialize (if SDK not present)

Skip this step if the SDK is already in the codebase.

1. **Detect the package manager** from lockfiles: `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml` → npm/yarn/pnpm; `Pipfile.lock` / `poetry.lock` → pip/poetry; `go.sum` → go modules; `Gemfile.lock` → bundler.

2. **Install the appropriate SDK** using the detected package manager. See [SDK Track Patterns](references/sdk-track-patterns.md) for the right package name per language.

3. **Get the SDK key** using `get-project` — fetch the project and choose the key for the environment the user wants to instrument (typically `production` or `staging` for initial testing).

4. **Add SDK initialization** following the patterns already in this codebase. If there's a central config or service layer, add the LD client there. See [SDK Track Patterns](references/sdk-track-patterns.md) for initialization examples.

### Step 3: Find the Right Placement

Locate where in the code the user action or event occurs.

1. **Ask if you're not sure** where the action happens. Don't guess at placement — a `track()` call in the wrong location (e.g. a render method instead of a submit handler) produces misleading data.

2. **Look for signals of the right location:**
   - Form submissions, button click handlers, API route completions, mutation hooks
   - Existing analytics calls (`segment.track()`, `mixpanel.track()`, `gtag()`) — these are often co-located with where LD track calls should go
   - Comments like `// TODO: track this`

3. **Show the candidate location** to the user before writing anything:
   ```
   I'll add the track() call here, in the checkout submit handler (src/checkout/CheckoutForm.tsx, line 47).
   Does that look right?
   ```

4. **Proceed once confirmed** (or if you're confident enough from codebase signals).

### Step 4: Write the `track()` Call

Write the call following the patterns found in Step 1.

**Server-side SDKs** — context is required:
```typescript
ldClient.track('checkout-completed', context);
```

**Client-side SDKs** — context is implicit:
```typescript
ldClient.track('checkout-completed');
```

**For `value` metrics** — include `metricValue` with the numeric measurement:
```typescript
// Server-side: latency metric (ms)
ldClient.track('api-response-time', context, null, responseTimeMs);

// Client-side: revenue metric
ldClient.track('purchase-completed', { orderId }, purchaseAmountUSD);
```

**Key rules:**
- **Match the existing context.** Don't construct a new context inline. Find where the codebase already builds its context/user object (used for `variation()` calls) and use the same one. This is how LD correlates the event to the right experiment participant.
- **`metricValue` only for `value` metrics.** For `count` and `occurrence` metrics, omit `metricValue` entirely.
- **Respect wrapper patterns.** If the codebase wraps LD calls behind a utility (`featureFlags.track()`, `analytics.ldTrack()`), add the new call through that wrapper — not by calling `ldClient` directly.
- **Match the event key exactly.** `track()` event keys are case-sensitive. Use the exact string that the metric was created with.

See [SDK Track Patterns](references/sdk-track-patterns.md) for full per-language examples.

### Step 5: Verify

**Guide the user to trigger the action** in their local or staging environment. Then use `list-metric-events` to confirm the event key appears:

```
list-metric-events(projectKey, environmentKey)
```

**If the event key appears:** confirm success and show a summary.

**If the event key is absent after triggering**, work through this checklist:

| Problem | Check |
|---------|-------|
| Wrong event key casing | Does the `track()` call match the metric's event key exactly? |
| SDK not initialized | Is `ldClient` initialized before the `track()` call runs? |
| Server-side: wrong context | Is the context passed to `track()` the same context used for `variation()` calls? |
| Client-side: no flag evaluation first | Has the SDK initialized and identified the user before `track()` is called? |
| Wrong environment | Is `list-metric-events` querying the same environment where the action was triggered? |
| Data delay | `list-metric-events` shows the last 90 days with up to ~5 min delay — try again in a moment |

Surface a summary once verified:

```
✓ Event flowing: checkout-completed
  Seen in: production
  
Next: this event is now ready to back a metric. Use the metric-create skill to set one up,
or attach an existing metric to your experiment.
```

## Important Context

- **`track()` calls only count in experiments when a flag is evaluated first.** The event is correlated to an experiment participant because LD saw a `variation()` call from that context. If the user triggers the action without evaluating any flag, the event may still be ingested but won't appear in experiment results.
- **Client-side SDKs flush events on an interval** (default ~30 seconds) or on page unload. In tests, you may need to call `ldClient.flush()` explicitly to see events appear immediately.
- **Server-side SDKs also buffer events.** Calling `ldClient.flush()` after `track()` in development ensures the event is sent before the process exits or the test ends.
- **`metricValue` units must match the metric definition.** If the metric was created with unit `ms`, pass milliseconds. Passing seconds into a milliseconds metric will produce silently wrong results.
- **The `data` parameter is for custom metadata, not the metric value.** Pass extra context (order ID, category, etc.) in `data`. Pass the numeric measurement in `metricValue`.

## References

- [SDK Track Patterns](references/sdk-track-patterns.md) — `track()` call syntax, initialization, and package names for every supported SDK
