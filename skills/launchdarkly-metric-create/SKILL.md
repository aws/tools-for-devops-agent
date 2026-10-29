---
name: launchdarkly-metric-create
description: "Create a LaunchDarkly metric that measures what matters for an experiment or rollout. Use when the user wants to create a metric, track an event, measure page views, button clicks, conversion, latency, error rate, or any custom numeric or binary outcome. Instruments the event first when needed (including SDK setup and .env), then creates and verifies the metric."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.4.0-experimental"
---

# LaunchDarkly Metric Create

You're using a skill that will guide you through creating a LaunchDarkly metric. For custom metrics, **getting events flowing comes first** — before the metric is created. Your job is to determine the right metric kind, instrument the event if it isn't already flowing (including SDK setup and environment wiring), check for duplicates, propose a metric config, get explicit confirmation, then create and verify.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `create-metric` — create the metric
- `get-metric` — verify it after creation
- `get-environment` — fetch the client-side SDK key when instrumenting

**Optional MCP tools (enhance workflow):**
- `list-metrics` — check for existing metrics with the same event key and understand naming conventions
- `list-metric-events` — discover which event keys have recent activity before committing to one (custom metrics only)

## Two Different "Projects" — Never Confuse Them

Users work with two completely separate things that both get called "project." You must keep these distinct at all times:

| | What it is | How the user refers to it | What you do with it |
|---|---|---|---|
| **LaunchDarkly project** | The project inside the user's LD account where the metric will be created | Usually sounds like an environment or team name: `my-app`, `anthony-agent-dev-5000`, `production` | Pass as `projectKey` to all MCP tool calls |
| **Local codebase** | The developer's application on disk that you'll instrument with a `track()` call | Often a folder name, repo name, or app name: `checkout_proj`, `frontend`, `my-react-app` | Use to find and edit source files |

**Rules for resolving these from user input:**

- If the user says *"my application at X"* or *"my codebase"* or *"my repo"* → they mean the **local codebase**. `X` is a folder path or project name, not a LaunchDarkly key.
- If the user says *"add it to X"* or *"in LaunchDarkly"* or *"my LD project"* → they mean the **LaunchDarkly project**. `X` is the `projectKey` for API calls.
- A user can name their local codebase `checkout_proj` while their LaunchDarkly project is `anthony-agent-dev-5000`. These are unrelated.
- **Never assume the local codebase name is a LaunchDarkly project key.** If you're unsure which is which, ask directly: *"Just to confirm — what's your LaunchDarkly project key? (This is different from your local app name — you can find it in the LD UI under Account Settings > Projects.)"*

When both are needed (e.g. for a custom metric with instrumentation), confirm each explicitly before proceeding.

## Workflow

### Step 1: Determine the Metric Kind

LaunchDarkly has three metric kinds. **Choose the right one before anything else.**

| Kind | How events are collected | Requires |
|------|--------------------------|----------|
| `custom` | Developer calls `ldClient.track(eventKey)` in code | `eventKey` |
| `pageview` | Fires automatically when a user visits a matching URL — **no SDK call needed** | `urls` (URL match rules) |
| `click` | Fires automatically when a user clicks a CSS selector on a matching URL — **no SDK call needed** | `urls` + `selector` |

**Decision rules:**
- User says "track when someone views a page / visits a URL" → **`pageview`** (preferred — no instrumentation required)
- User says "track when someone clicks a button / link" → **`click`**
- User says "track a custom event" or references a `track()` call → **`custom`**

When `pageview` or `click` would work, suggest it over `custom` — it requires no code changes.

### Step 2: Resolve the Data Source

**For `pageview` and `click` metrics:**
- Ask for the URL(s) to match. Confirm the `kind` of URL match rule:
  - `substring` — URL contains this string (most common)
  - `exact` — URL must match exactly
  - `canonical` — matches the canonical URL
  - `regex` — full regex pattern
- For `click` metrics, also ask for the CSS selector (e.g. `.checkout-btn`, `#submit`).
- Skip `list-metric-events` — these metrics don't use event keys.
- Skip to Step 3.

**For `custom` metrics — check events first, instrument if needed:**

Call `list-metric-events` immediately to see which event keys are already flowing:

```
list-metric-events(projectKey, environmentKey?)
```

**Case A — the event key is already in the list:** Confirm the key with the user and proceed to Step 3. No instrumentation needed.

**Case B — the event key is NOT in the list:** The metric can't measure anything without events. **Instrument the event now before creating the metric.** Do not simply warn and ask whether to proceed — treat instrumentation as the default next action.

Follow the instrumentation sub-workflow below, then re-check `list-metric-events` to confirm events are flowing before moving to Step 3. Only skip instrumentation if the user explicitly says they want to create the metric first and wire the event up later — in that case, remind them at the end that the metric will produce no data until the event is tracked.

### Step 2b: Instrument the Event (when events aren't flowing)

This sub-workflow gets a `track()` call into the codebase and connects the app to the right LaunchDarkly environment. Complete all steps before returning to the main workflow.

**1. Find the right place in the codebase.**
Locate the function or handler where the event naturally occurs (e.g. a checkout submit handler, a form submission callback). Read the relevant source files to understand the existing structure before making changes.

**2. Determine the event key.**
If the user hasn't specified one, propose a descriptive kebab-case key that matches what the code is doing (e.g. `checkout-completed`, `signup-submitted`). Confirm with the user before using it.

**3. Fetch the client-side SDK key.**
Ask the user which environment they want to connect to (e.g. "test", "production", "staging") — just the environment name. Then call:

```
get-environment(projectKey, environmentKey)
```

Use the `clientSideId` from the response.

**4. Write the environment file.**
Check whether a `.env` file (or equivalent — `.env.local`, `.env.development`, etc.) already exists.

- If the file **does not exist**, create it.
- If the file **exists and already contains the key** (e.g. `VITE_LD_CLIENT_SIDE_ID`), compare the stored value to the `clientSideId` returned by `get-environment`. If they differ, surface the discrepancy to the user:
  > "Your `.env` already has `VITE_LD_CLIENT_SIDE_ID=<old>`, but `get-environment` returned `<new>` for the `<env>` environment. Should I update it?"
  Do not silently keep the old value — a mismatched client-side ID means events will be sent to the wrong project or environment.
- If the file exists but the key is absent, add it without touching other values.

Use the variable name appropriate to the project's build tool (e.g. `VITE_LD_CLIENT_SIDE_ID` for Vite, `REACT_APP_LD_CLIENT_SIDE_ID` for CRA, `NEXT_PUBLIC_LD_CLIENT_SIDE_ID` for Next.js).

**4b. Set the SDK base URL if the user is not on app.launchdarkly.com.**
The SDK defaults to `app.launchdarkly.com` for all traffic. If the user is on a different LaunchDarkly deployment (e.g. an internal staging environment like catamorphic, or a dedicated instance), events and flag evaluations will silently go to the wrong host.

Detect this by inspecting any `_links` or UI URLs in MCP API responses — if they point to a host other than `app.launchdarkly.com`, you are on a non-production deployment. When in doubt, ask:
> "Are you connecting to app.launchdarkly.com or a different LaunchDarkly instance? (e.g. an internal or staging environment)"

If they are on a non-standard host, add three additional variables to the `.env` file:

```
VITE_LD_BASE_URL=https://<their-host>
VITE_LD_STREAM_URL=https://clientstream.<their-host-domain>
VITE_LD_EVENTS_URL=https://events.<their-host-domain>
```

And pass them to the SDK `options` at init time:

```js
asyncWithLDProvider({
  clientSideID,
  context: { kind: 'user', anonymous: true },
  options: {
    baseUrl: import.meta.env.VITE_LD_BASE_URL,
    streamUrl: import.meta.env.VITE_LD_STREAM_URL,
    eventsUrl: import.meta.env.VITE_LD_EVENTS_URL,
  },
})
```

Omit the `options` block entirely if they are on `app.launchdarkly.com` — the defaults are correct and no extra config is needed.

**5. Install and initialize the SDK** if it isn't already present.
Check `package.json` (or the equivalent dependency file) for an existing LD SDK. If none is found, install the right one for the project's stack:
- React → `launchdarkly-react-client-sdk`
- Browser JS → `launchdarkly-js-client-sdk`
- Node.js server → `@launchdarkly/node-server-sdk`

Initialize the SDK at the app's entry point (e.g. wrap the React root with `LDProvider`, configure `LDClient.init()` in the server entry, etc.). Pass the client-side ID from the env file. Use an anonymous user/context as the default unless the app already manages user context.

**6. Add the `track()` call.**
In the location identified in step 1, add the call immediately before or after the action completes:

- Count / occurrence metric: `ldClient.track('event-key')`
- Value metric: `ldClient.track('event-key', null, numericValue)`

Use optional chaining (`ldClient?.track(...)`) in client-side code where the client may not yet be initialized.

**7. Verify events are flowing.**
After the instrumentation changes are made, remind the user to run the app and trigger the event at least once. Then call `list-metric-events` again to confirm the key appears before proceeding to metric creation.

### Step 3: Check for Existing Metrics

Before creating anything, use `list-metrics` to scan the project:

1. **Check for duplicates.** Search for metrics with the same event key, URL pattern, or similar names. Avoid creating a second metric that measures the same thing — instead, flag the existing metric and ask the user if they want to reuse it.
2. **Learn the naming convention.** Are metric keys `kebab-case` or `snake_case`? Are there common tag patterns? Match what already exists.
3. **Understand the tag taxonomy.** Tags like `team:growth`, `area:checkout`, or `type:guardrail` may already exist. Suggest relevant tags based on what the user describes.

### Step 4: Propose the Metric Configuration

Before calling any API, surface a proposed configuration in plain language for the user to confirm or edit.

**Determine measure type.** The right choice depends on what the user is trying to learn and how they'll use the metric — in an experiment, a guarded rollout, or a release policy. **Do not assume.** When the event is something a user can do repeatedly (click, add to cart, view page, etc.), always ask before proposing:

> "Are you trying to measure **how many times** this event happens in total (`count`), or **what percentage of users** triggered it at least once (`occurrence`)?"

Tie the question to their context:
- **Experiments** — occurrence is common for conversion goals (did the treatment cause more users to do X?); count is better for engagement or volume goals (did the treatment cause more total actions?)
- **Guarded rollouts / release policies** — occurrence is typical for error rate guardrails (what fraction of users hit an error?); count suits absolute volume guardrails (total error events)
- **If the user explicitly says "percent of users" or "conversion rate"** → `occurrence`
- **If the user explicitly says "number of times" or "total events"** → `count`

Only skip asking if the intent is unambiguous from context (e.g. "API latency" → `value`, "error rate" → `count`, "signup conversion" → `occurrence`).

| What the user wants to measure | Measure type | Means |
|-------------------------------|-------------|-------|
| Total times the event occurred | `count` | Raw event count per analysis unit |
| Whether each user triggered the event at all | `occurrence` | Conversion / binary (did it happen?) |
| A numeric value attached to the event | `value` | Latency, revenue, score, etc. |

**Determine success criteria:**

- **Higher is better** → `HigherThanBaseline` (conversion rate, revenue, engagement)
- **Lower is better** → `LowerThanBaseline` (latency, error rate, bounce rate)

**Use common templates as defaults** when the user's intent is clear:

| User intent | kind | measure type | success criteria | unit |
|-------------|------|-------------|-----------------|------|
| Page visit / view rate | `pageview` | `occurrence` | `HigherThanBaseline` | — |
| Button / link click rate | `click` | `occurrence` | `HigherThanBaseline` | — |
| API latency / page load time | `custom` | `value` (average) | `LowerThanBaseline` | `ms` |
| Signup / conversion rate | `custom` | `occurrence` | `HigherThanBaseline` | — |
| Error count / rate | `custom` | `count` | `LowerThanBaseline` | — |
| Revenue per user | `custom` | `value` (sum) | `HigherThanBaseline` | `USD` |

**Present the proposed config** before creating — don't silently fire the API:

```
Proposed metric:
  Key:              checkout-page-viewed
  Name:             Checkout Page Viewed
  Kind:             pageview (fires automatically on URL visit — no code change needed)
  URLs:             substring match on "/checkout"
  Measure type:     occurrence (did each user visit the page?)
  Success criteria: HigherThanBaseline

Proceed, or would you like to change anything?
```

**STOP HERE.** Do not call any API. Do not proceed to Step 5. Wait for the user to explicitly confirm before doing anything else. The user must respond with an approval (e.g. "yes", "looks good", "proceed") before you call `create-metric`. If there is any ambiguity in the proposed config — such as a choice between `sum` vs `average`, or the event key name — ask that question as part of the proposal and wait for the answer before continuing.

### Step 5: Create the Metric

**Only proceed once the user has explicitly confirmed the proposed config in Step 4.** If you have not yet received a confirmation, go back and wait.

Once the user confirms, call `create-metric`. The tool handles the translation from `measureType` to the underlying API fields — you never need to pass `isNumeric` or `unitAggregationType` directly.

```
create-metric(
  projectKey,
  key,
  name,
  kind,              // "custom" | "pageview" | "click"
  eventKey?,         // only for kind="custom"
  urls?,             // only for kind="pageview" or "click": [{ kind, url }]
  selector?,         // only for kind="click": CSS selector string
  measureType,       // "count" | "occurrence" | "value"
  successCriteria,   // "HigherThanBaseline" | "LowerThanBaseline"
  valueAggregation?, // only for measureType="value": "average" (default) or "sum"
  unit?,             // display label: "ms", "USD", etc.
  description?,
  tags?
)
```

### Step 6: Verify

Use `get-metric` to confirm the metric was created with the right configuration:

1. **Key and name match** what was requested.
2. **kind is correct** — `custom`, `pageview`, or `click`.
3. **measureType is correct** — double-check by reading back the `measureType` field, not just `isNumeric`.
4. **eventKey / urls / selector** are set to the intended values.
5. **successCriteria** is correct.

Surface a summary to the user:

```
✓ Metric created: checkout-page-viewed
  Kind:     pageview (auto-tracked on URL visit)
  URLs:     substring "/checkout"
  Measures: occurrence (conversion rate)
  Goal:     Higher is better

View in LaunchDarkly: {_links.ui from the create-metric response}
```

The `create-metric` tool returns a `_links.ui` field with the correct URL for the environment being used. Always use that value — never hard-code `app.launchdarkly.com`.

## Measure Type Reference

The `create-metric` tool translates `measureType` to the LD API fields internally. You never need to set `isNumeric` or `unitAggregationType` directly.

| measureType | isNumeric | unitAggregationType | Use for |
|-------------|-----------|---------------------|---------|
| `count` | false | sum | Raw event counts — error rate, click count |
| `occurrence` | false | average | Conversion — did the user do the thing? |
| `value` (average) | true | average | Per-user mean — average latency, average session length |
| `value` (sum) | true | sum | Per-user total — total revenue, total items purchased |

For `value` metrics, `valueAggregation` defaults to `"average"`. Pass `valueAggregation: "sum"` for revenue or cumulative totals.

## Important Context

- **Prefer `pageview` and `click` over `custom` when possible.** They require no SDK instrumentation and work automatically in browser environments.
- **Event keys are case-sensitive.** `checkout-completed` and `Checkout-Completed` are different events. Match the key exactly as it appears in your `track()` calls.
- **Custom metrics without events produce no data.** A custom metric is only useful once its event key is actively being tracked in production (or the relevant environment). If you created the metric before instrumenting the event, remind the user.
- **Metric keys are immutable.** Once created, a metric's key cannot be changed. Choose carefully.
- **Metrics are project-scoped.** A metric created in one project is not visible in another. Make sure `projectKey` matches where the experiment or flag lives.
- **One primary metric per experiment.** When attaching this metric to an experiment, clarify whether it's the primary metric (the one that determines success or failure) or a secondary metric (a guardrail or supporting signal). See the LaunchDarkly docs for experiment setup.
