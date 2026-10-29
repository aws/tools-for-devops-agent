---
name: launchdarkly-experiment-guide
description: "Guide a developer from 'I don't know what to test' to a ready-to-create LaunchDarkly experiment. Use when someone wants to run an experiment or A/B test but doesn't have a metric, a flag, or a hypothesis yet, or isn't sure what to measure. Scans the codebase and the connected LaunchDarkly account, proposes a hypothesis and metric from real context, wires up the flag and tracking code, then drafts the experiment and offers to create it. Built for engineers without a data-science or product-analytics background."
license: Apache-2.0
compatibility: "Uses the LaunchDarkly MCP server when it is configured; otherwise falls back to the LaunchDarkly REST API (needs a LaunchDarkly API token). Reads the local codebase and git history."
metadata:
  author: launchdarkly
  version: "0.1.0-experimental"
---

# LaunchDarkly Experiment Guide

You're using a skill that turns a vague "I should probably A/B test this" into a
concrete, ready-to-create LaunchDarkly experiment. Your user is likely a
developer who has never designed an experiment: they may not know what a metric
is, what a hypothesis should look like, or which of their features is worth
testing. Your job is to do the thinking *with* them — infer what their product
is from the code, look at what already exists in their LaunchDarkly account,
propose a sensible experiment grounded in that context, wire up the code they
need, and hand them a draft they can create with one confirmation.

Do the heavy lifting. Suggest, default, and explain. Never make them supply
something you could reasonably infer, and never dump jargon on them.

## Prerequisites

- A local codebase (this skill reads files and `git log`).
- A connection to LaunchDarkly that can **create metrics and experiments** —
  **either** an LD MCP server that exposes those tools, **or** a LaunchDarkly API
  token in the environment (`LD_API_KEY` / `LAUNCHDARKLY_ACCESS_TOKEN`) for REST
  calls. A flags-only MCP is not enough: it can scan and draft but not create.
  **Step 0 checks the specific capabilities and fails fast** if the create path
  is missing, offering a draft-only plan instead of grinding through the whole
  flow to a dead end.

This skill orchestrates several focused skills rather than reimplementing them.
When a step calls for one, use it:

| Job | Delegate skill |
|-----|----------------|
| Pick the right metric / primary metric / guardrails | `launchdarkly-metric-choose` |
| Create a metric (and instrument the event) | `launchdarkly-metric-create` |
| Add the `track()` call in code | `launchdarkly-metric-instrument` |
| Create / wrap a flag to match the codebase | `launchdarkly-flag-create` |
| Assemble, start, and stop the experiment | `launchdarkly-experiment-setup` |

## Core Principles

1. **Infer, then confirm.** Propose what the product is, what to test, and what
   to measure from real evidence in the repo and account. Show the user your
   read and let them correct it before you build on it.
2. **Reuse before you create.** Always check for an existing flag or metric that
   fits before making a new one. Duplicates are the #1 way experiments get messy.
3. **One hypothesis, one primary metric, one change.** Keep the first experiment
   small and legible. Guardrail metrics are fine; a second "primary" is not.
4. **Explain in their language.** Say "the thing you're hoping to improve"
   before you say "primary metric." Define a term the first time you use it.
5. **Draft, then ask.** Never create anything in LaunchDarkly without showing the
   full draft and getting an explicit yes. Writes are the user's call.

## Workflow

### Step 0: Check the LaunchDarkly connection (fail fast)

Before any work, confirm you can actually reach LaunchDarkly. This decides what
the skill can do and avoids a dead end after the user has invested time.

Check **capabilities, not just "is an MCP connected."** The flow needs three
things — confirm each is actually available before you rely on it, so you don't
discover a missing tool only at the create step:

- **Account read** — list flags, metrics, environments (Step 2 reuse).
- **Metric create** — create a metric and its event (Step 5, if none fits).
- **Experiment create + start** — create the experiment (Step 8) and, later, start its iteration.

Resolve a path, in precedence order:

1. **An LD MCP that exposes the experiment + metric tools** (`create-experiment`,
   `start-experiment-iteration`, `create-metric`, `list-metrics`, …) → full
   **MCP path**. Preferred.
2. **Else a LaunchDarkly API token** (`LD_API_KEY` / `LAUNCHDARKLY_ACCESS_TOKEN`)
   → full path via the **REST API**.
3. **Partial — an LD MCP is connected for flags/environments but has no
   experiment/metric tools, and there's no API token.** You *can* read the
   account (so the Step 2 scan still works), but you **cannot create the metric
   or experiment**. Scan and draft as normal, then stop before any write — see
   "Act on the outcome" below. This is **not** "no connection."
4. **No LD access at all** → you can't even read the account. **Stop at Step
   0.** Don't start Step 1: no reading project files, no `git log`, no guess at
   what the product is.

> Verify the *specific* create tools exist at Step 0 — "an LD MCP is connected"
> does **not** mean you can create an experiment. A flags-only MCP will let you
> scan and draft, then fail at Step 8; catching that now is the whole point of
> the preflight.

**Act on the outcome:**

- **Full (1 or 2):** proceed through the whole workflow.
- **Partial (3):** you can reach the account, so **still run the Step 2 scan** and
  reuse what fits, then produce the draft. At **Step 8, stop before any write**
  and tell the user you can't create from here — offer to connect a create-capable
  path (an experiment-capable LD MCP or an `LD_API_KEY` token) and re-run, or take
  the draft + ready-to-run commands and finish in the UI or via
  `launchdarkly-experiment-setup`. Don't tell them LaunchDarkly is unreachable —
  it isn't; you just can't create from here.
- **No access (4):** stop now. Your entire reply is the message below — no
  product read, no summary of the code, nothing from later steps — and then wait
  for the user. The user decides whether to connect before any discovery work
  happens, not after. Only if they say **draft-only** do you continue, starting
  at Step 1 (no account scan, no writes — working only from the codebase):
  > "I can read your code, but I can't reach your LaunchDarkly account — so I
  > can't see your existing flags/metrics or create the experiment. Connect the
  > LaunchDarkly MCP server (setup guide:
  > https://launchdarkly.com/docs/home/getting-started/mcp-hosted) or set an
  > `LD_API_KEY` token in your shell and restart this session, then re-run.
  > Or say **'draft only'** and I'll produce the hypothesis, metric/flag plan,
  > code snippets, and exact API calls — without touching your account."

**Capabilities by connection:**

| Connection | Scan account | Create metric + experiment | Notes |
|------------|:---:|:---:|-------|
| LD MCP w/ experiment + metric tools | ✅ | ✅ | Preferred — higher-level tools, pruned responses |
| LD API token (REST) | ✅ | ✅ | Full CRUD via `/api/v2` (experiments have no delete) |
| Both | ✅ | ✅ | MCP used; REST as fallback |
| LD MCP, flags/env only (no experiment/metric tools) | ✅ flags/env | ❌ | **Partial.** Scan + draft, then stop before create; connect a create-capable path to finish |
| No LD access | ❌ | ❌ | **Fail fast**; draft-only (no scan, no create) |

### Step 1: Understand the product (lightweight scan)

Start this step only once Step 0 found access (full or partial) or the user
chose draft-only.

Build a quick mental model of what this app *is* and who uses it. Keep it cheap
— you are not auditing the whole codebase.

Look at:
- `README*`, the package manifest (`package.json`, `pyproject.toml`, `go.mod`,
  `Gemfile`, etc.) — name, description, dependencies, frameworks.
- Top-level directories and entrypoints — is this a web app, an API, a mobile
  app, a CLI? What are the major surfaces (checkout, onboarding, search, feed)?
- `git log --oneline -n 30` and recent diffs — what has the team been building
  lately? Recent features are prime experiment candidates because the team
  already cares about them.

Then **state your read back in one or two sentences and confirm it**, e.g.
"Looks like a React e-commerce storefront; recent work has been on a redesigned
checkout and a new product-recommendation widget. Is that right?" Correct course
on their answer before continuing. See
[Discovery guide](references/discovery.md) for what to grep for per stack.

### Step 2: See what's already in LaunchDarkly

Scan the connected account so you reuse instead of duplicate and so your
suggestions match their conventions. (Requires the Step 0 connection — in
draft-only mode, skip this scan and tell the user you're proposing without
visibility into their existing flags and metrics.)

- **Flags** — list existing flags (MCP `list-flags` / REST
  `GET /api/v2/flags/{projectKey}`). Note naming conventions, tags, and whether
  any flag already gates the feature you're thinking about testing.
- **Metrics** — list existing metrics (MCP `list-metrics` / REST
  `GET /api/v2/metrics/{projectKey}`). If a relevant metric already exists (e.g.
  `checkout-completed`), prefer it as the experiment's primary metric.
- **Environments** — list the project's environments (MCP `get-project`, or
  `get-environment` for one environment's details) so you target the right one
  and know the environment key.
- **Project and environment** — if the account has more than one project, ask
  the user which one this app uses instead of guessing. Run the experiment in
  the environment the app connects to: match the app's client-side ID to the
  environments `get-project` returns, and ask when there's no match or the app
  uses a server SDK key.

Summarize what you found that's relevant: "You already have a
`checkout-completed` conversion metric and a `new-checkout` flag — we can build
the experiment on those instead of creating anything new."

### Step 3: Choose what to experiment on

Combine Steps 1–2 into a short list of candidate experiments and let the user
pick. Lead with the strongest candidate (usually a recent feature that has, or
could have, a flag). Present as a structured choice, for example:

- **Redesigned checkout** — test the new flow vs. the current one. *(recommended
  — recent work, directly tied to revenue)*
- **Recommendation widget** — test showing it vs. hiding it on product pages.
- **Something else** — describe it.

If nothing obvious stands out, ask what outcome they care about most
(sign-ups, conversion, retention, latency) and work backward to a feature.

### Step 4: Form the hypothesis

Most users freeze here. Do not ask for a hypothesis cold. Instead:

1. **Generate 1–2 candidates** from the chosen feature, in the standard shape:
   *"Changing **X** will improve **metric** for **audience**, because **reason**."*
   e.g. "Showing the redesigned checkout will increase checkout completion for
   logged-in shoppers, because it removes two form steps."
2. **Show a worked example** alongside so they see the shape.
3. Let them **pick, edit, or write their own.**

A good hypothesis names the change, the metric it should move, the direction,
and (ideally) a rough size. See [Hypothesis guide](references/hypothesis-guide.md)
for templates, examples by product type, and how to turn a fuzzy goal into a
testable statement.

### Step 5: Line up the metric

The hypothesis names what you're hoping to improve — that becomes the **primary
metric** (the single number that decides the experiment).

- If a fitting metric already exists (Step 2), use it. Confirm the key.
- If not, delegate to `launchdarkly-metric-choose` to pick the right kind
  (conversion vs. numeric, which event), then `launchdarkly-metric-create` to
  create it. If the event isn't emitted from the code yet,
  `launchdarkly-metric-instrument` adds the `track()` call.
- Offer 0–2 **guardrail metrics** (things that shouldn't get worse, e.g. error
  rate, latency) — but keep exactly one primary.

Give the user the **tracking code snippet** they need to paste in, matched to
their SDK.

### Step 6: Line up the flag

The experiment needs a flag with at least two variations to split traffic
between (control vs. treatment).

- If a flag already gates the feature, reuse it; confirm it has the right
  variations and find its targeting rule.
- If not, delegate to `launchdarkly-flag-create` to create one that matches the
  codebase's existing flag patterns, and to wrap the feature in it. Give the
  user the **flag-evaluation snippet** for their SDK.
- If the app uses a browser or mobile SDK, create the flag with client-side
  availability on (`clientSideAvailability.usingEnvironmentId`, or
  `usingMobileKey` for mobile), or the app can't read the flag.

You'll need the flag key, the variation IDs, and the targeting `ruleId` +
current `flagConfigVersion` for the rule that will drive the experiment (the
fallthrough rule's id is the string `"fallthrough"`).

### Step 7: Draft the experiment and confirm

Assemble everything into a plain-language draft **and** the concrete payload,
then ask before creating anything.

Present the draft like this:

> **Experiment: Redesigned checkout**
> - **Hypothesis:** the redesigned checkout will lift completion ~3% for logged-in shoppers.
> - **Flag:** `new-checkout` — Control (current) 50% vs. New checkout 50%.
> - **Primary metric:** `checkout-completed` (conversion).
> - **Guardrail:** `checkout-error-rate` (should not increase).
> - **Environment:** `production` · **Methodology:** Frequentist (LaunchDarkly's default).
> - **What I'll create:** 1 metric (already exists → reuse), experiment + first iteration.

Then **ask for explicit confirmation** with clear options: *Create it* /
*Change something* / *Just give me the steps, I'll do it myself*. Ask it as a
structured question when your agent supports one, so the yes is unambiguous.

### Step 8: Create (only after yes)

Create through whichever path is available — this is a single logical step with
two implementations. See [Create the experiment](references/create-experiment.md)
for the exact MCP calls and REST payloads.

- **MCP path (preferred):** create any missing metric, then call
  `create-experiment` with the nested first iteration. (Delegating to
  `launchdarkly-experiment-setup` handles the field details and lifecycle.)
- **REST fallback:** `POST /api/v2/metrics/{projectKey}` for a new metric, then
  `POST /api/v2/projects/{projectKey}/environments/{envKey}/experiments` with the
  iteration body.
- **Draft-only mode (no connection):** you already flagged this at Step 0 — do
  not attempt any write. Present the draft plus the exact ready-to-run API calls
  from the reference, and point them at `launchdarkly-experiment-setup` to finish
  once they're connected.

Create the experiment as a draft. Start it only after the flag and tracking
code are deployed and the user says yes again. Starting needs the flag on; if
the environment requires approval to change it, start only after the approval
request is approved.

After creating, verify (MCP `get-experiment` / REST `GET …/experiments/{key}`)
and report: what was created, that it's a draft that isn't collecting data yet,
the flag/metric it's wired to, and the one thing they should do next (deploy the
code, then tell you to start it).

## Edge Cases

| Situation | Action |
|-----------|--------|
| No git history / brand-new repo | Skip the recent-features scan; lean on the README and manifest, and ask what they're working on. |
| Can't tell what the product is | State your best guess and ask — don't silently pick. |
| No LaunchDarkly access (no MCP, no token) | Caught at Step 0 — fail fast: stop and offer to connect (MCP server or `LD_API_KEY`), or explicit draft-only mode (no account scan, no create). Don't grind through the flow to a dead end. |
| A flag or metric already fits | Reuse it. Say so explicitly and skip creation for that piece. |
| User has no idea what to measure | Start from the outcome (revenue, sign-ups, retention, speed) and map backward to a metric and feature. |
| Feature isn't behind a flag yet | Delegate to `launchdarkly-flag-create` first; an experiment needs a flag to split traffic. |
| User wants to test more than one change at once | Push back gently: one change per experiment for a clean result; offer to queue follow-ups. |
| Event for the metric isn't emitted in code | Delegate to `launchdarkly-metric-instrument` and give the `track()` snippet before creating the metric. |

## What NOT to Do

- Don't ask the user for a hypothesis, metric, or flag without first offering a
  concrete, context-derived suggestion.
- Don't create anything in LaunchDarkly before showing the draft and getting an
  explicit yes.
- Don't run the discovery/hypothesis/draft flow without a LaunchDarkly connection
  — check at Step 0 and fail fast, offering to connect or go draft-only.
- Don't create a new flag or metric when a suitable one already exists.
- Don't set up two primary metrics, or test multiple changes in one experiment.
- Don't drown the user in terminology — define terms in plain language as you go.
- Don't do a deep, slow codebase audit; this is a lightweight scan with a
  confirmation.
- Don't guess the product or the target feature silently — state and confirm.

## References

- [Discovery guide](references/discovery.md): what to read/grep per stack to
  infer the product and surface recent features.
- [Hypothesis guide](references/hypothesis-guide.md): templates, worked
  examples by product type, turning a fuzzy goal into a testable statement.
- [Create the experiment](references/create-experiment.md): the abstracted
  create step — MCP calls and REST payloads, with the exact fields.
