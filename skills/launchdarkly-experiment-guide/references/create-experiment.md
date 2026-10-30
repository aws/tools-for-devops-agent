# Create the experiment (abstracted: MCP or REST)

This is **one logical step with two implementations**. Detect what's available
and use it. Only run this after the user has confirmed the draft (Step 7).

Detection order (already confirmed up front by the skill's **Step 0** preflight,
which checks for the *specific* create tools — a flags-only MCP does not qualify):
1. **An LD MCP exposing the experiment + metric tools** (`create-experiment`,
   `create-metric`, `start-experiment-iteration`, …) → MCP path (preferred).
2. **Else a LaunchDarkly API token** (`LD_API_KEY` / `LAUNCHDARKLY_ACCESS_TOKEN`) → REST path.
3. **Both present** → use MCP; fall back to REST only for an operation MCP doesn't expose.
4. **No create capability** (flags-only MCP, or nothing) → you should never reach
   the create step: Step 0 fails fast. If the user chose **draft-only** mode,
   present these calls for them to run later and stop.

You need these values, gathered in earlier steps:
- `projectKey`, `environmentKey` (from `get-project`, or `get-environment` for one environment).
- Primary metric key (reused or newly created).
- Flag key, the variation IDs for control/treatment, the targeting `ruleId`
  (fallthrough rule id is the string `"fallthrough"`), and current
  `flagConfigVersion`.

> **Prefer delegating the mechanical details to `launchdarkly-experiment-setup`.**
> It owns the field-level rules (`mutableFieldsByStatus`, iteration lifecycle,
> stopping with a winner). This reference is the abstraction contract so this
> skill can complete the flow even when that skill isn't loaded.

---

## MCP path (preferred)

1. **Create any missing metric** — `create-metric` (or delegate to
   `launchdarkly-metric-create`). Skip if reusing an existing metric.
2. **Create the experiment with its first iteration** — `create-experiment`:

```json
{
  "projectKey": "my-project",
  "environmentKey": "production",
  "key": "redesigned-checkout-experiment",
  "name": "Redesigned Checkout Experiment",
  "description": "Test the redesigned checkout against the current flow.",
  "iteration": {
    "hypothesis": "The redesigned checkout will lift completion ~3% for logged-in shoppers.",
    "primarySingleMetricKey": "checkout-completed",
    "metrics": [
      { "key": "checkout-completed" },
      { "key": "checkout-error-rate" }
    ],
    "treatments": [
      { "name": "Control", "baseline": true, "allocationPercent": 50,
        "parameters": [{ "flagKey": "new-checkout", "variationId": "<control-variation-id>" }] },
      { "name": "New Checkout", "baseline": false, "allocationPercent": 50,
        "parameters": [{ "flagKey": "new-checkout", "variationId": "<treatment-variation-id>" }] }
    ],
    "flags": {
      "new-checkout": { "ruleId": "fallthrough", "flagConfigVersion": 7 }
    },
    "randomizationUnit": "user"
  }
}
```

3. **Verify** — `get-experiment`; confirm the experiment exists with a
   `not_started` iteration.

Create the experiment as a draft. Start it only after the flag and tracking
code are deployed and the user says yes again. Starting
(`start-experiment-iteration`) requires the flag to be on, a
`randomizationUnit`, and at least one non-zero allocation.

Rules that matter: exactly one treatment has `baseline: true`; allocations sum
to 100; the `iteration` object is required on create.

---

## REST fallback

Base URL `https://app.launchdarkly.com`. Header:
`Authorization: <token>` (plus `Content-Type: application/json`, and
`LD-API-Version: beta` for experiment endpoints).

**Create a metric** (skip if reusing):
```
POST /api/v2/metrics/{projectKey}
{
  "key": "checkout-completed",
  "name": "Checkout completed",
  "kind": "custom",
  "isNumeric": false,
  "eventKey": "checkout-completed",
  "successCriteria": "HigherThanBaseline"
}
```

**Create the experiment** (body mirrors the MCP `iteration`):
```
POST /api/v2/projects/{projectKey}/environments/{environmentKey}/experiments
{
  "key": "redesigned-checkout-experiment",
  "name": "Redesigned Checkout Experiment",
  "iteration": {
    "hypothesis": "The redesigned checkout will lift completion ~3% for logged-in shoppers.",
    "primarySingleMetricKey": "checkout-completed",
    "metrics": [{ "key": "checkout-completed" }, { "key": "checkout-error-rate" }],
    "treatments": [
      { "name": "Control", "baseline": true, "allocationPercent": 50,
        "parameters": [{ "flagKey": "new-checkout", "variationId": "<control-variation-id>" }] },
      { "name": "New Checkout", "baseline": false, "allocationPercent": 50,
        "parameters": [{ "flagKey": "new-checkout", "variationId": "<treatment-variation-id>" }] }
    ],
    "flags": { "new-checkout": { "ruleId": "fallthrough", "flagConfigVersion": 7 } },
    "randomizationUnit": "user"
  }
}
```

**Start the iteration** (only after the flag and tracking code are deployed and
the user says yes again): `create-experiment` already created a `not_started`
iteration — do **not** `POST .../iterations` to start it (that creates a second,
now-deprecated iteration). Start the existing draft with a semantic-patch `PATCH`
on the experiment:
```
PATCH /api/v2/projects/{projectKey}/environments/{environmentKey}/experiments/{experimentKey}
Content-Type: application/json; domain-model=launchdarkly.semanticpatch
{ "instructions": [{ "kind": "startIteration" }] }
```
Same preconditions as the MCP path: the flag must be on, the iteration needs a
`randomizationUnit`, and at least one treatment must have a non-zero allocation.

**Verify:**
```
GET /api/v2/projects/{projectKey}/environments/{environmentKey}/experiments/{experimentKey}
```

CRUD reality check: **metrics support full CRUD** (create/read/update/delete).
**Experiments support create/read/update + iterations, but no delete** — you
manage an experiment's life through its iterations, not by deleting it.

For exact request/response schemas, see the OpenAPI spec:
`https://launchdarkly.com/docs/api/other/get-openapi-spec` (tags: *Metrics*,
*Experiments*).

---

## No access at all

Present the draft plus the two `POST` calls above with the user's real values
filled in, and tell them they can either run them with an API token or open the
experiment in the LaunchDarkly UI. Point them at `launchdarkly-experiment-setup`
to finish and to run the iteration lifecycle.
