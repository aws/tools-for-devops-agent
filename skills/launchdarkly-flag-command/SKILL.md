---
name: launchdarkly-flag-command
description: "Resolve `/flag` style requests into the right LaunchDarkly flag lookup flow. Use when the user types `/flag`, asks to quickly find a flag by name/key, wants a direct flag detail summary, or needs fast disambiguation between similar flags."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0-experimental"
---

# LaunchDarkly Flag Command Router

You're using a skill that standardizes quick `/flag` requests. Your job is to parse the user intent, resolve the requested flag with minimal friction, return an actionable summary, and route to deeper workflows when needed.

## Scope Boundary

This skill is a **read-only lookup entrypoint**. It returns flag details and routes forward.

**Hard constraints — you MUST NOT:**

- Create, toggle, update, or delete flags
- Assess whether a flag is safe to remove, stale, or ready for cleanup
- Provide a "verdict", "safe to remove" conclusion, removal steps, or "before removing" advice
- Offer to archive or delete the flag

**When the user asks about removal or staleness**, your entire response for that part must be the flag summary table followed by this exact routing message (you may rephrase slightly but must keep the substance):

> This quick lookup can only show you the flag's current config. To assess whether it's safe to remove, you need the **flag discovery** or **flag cleanup** skill — they scan code references, check status across all environments, and analyze downstream dependencies.

That's it. No analysis. No bullet points. No verdict. The removal question is answered by the routing message, not by you.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `list-flags` — search and disambiguate flag candidates
- `get-flag` — fetch detailed configuration for a resolved flag

**Optional MCP tools:**
- `get-flag-status-across-envs` — compare lifecycle status across environments
- `get-flag-health` — quick health snapshot for a single flag

## Command Contract

Treat these forms as equivalent intents:

- `/flag <query>`
- `flag <query>`
- "find flag <query>"
- "show me <query> flag"

Use `production` as the default environment unless the user specifies another environment.

## Workflow

### Step 1: Parse and Normalize Input

1. Extract the query text after `/flag`.
2. If no query is provided, ask for one concise identifier (flag key, name fragment, or tag).
3. Capture optional hints from the request:
   - Environment (`staging`, `production`, etc.)
   - Project key
   - Preference for exact key vs fuzzy search

### Step 2: Resolve the Flag

Use `list-flags` first unless the user clearly provided an exact key and project.

1. Search with `list-flags` using the query.
2. If one clear exact match exists, resolve to that flag.
3. If multiple plausible matches exist, return a short disambiguation list (key + name + state) and ask the user to pick.
4. If no matches exist, tell the user and suggest one broader query.

### Step 3: Return a Useful Summary

For a resolved flag, call `get-flag` and return:

1. Flag key and name
2. Environment state (`on`/`off`)
3. Off variation and fallthrough behavior
4. Rule/target complexity (simple vs complex)
5. Direct LaunchDarkly URL for the flag (when project + key are known)

**If the user asked about removal, staleness, or cleanup** (e.g., "is this safe to remove?", "can I clean this up?", "is this stale?"):

Show ONLY the summary table above, then write:

> This quick lookup can only show you the flag's current config. To assess whether it's safe to remove, you need the **flag discovery** or **flag cleanup** skill — they scan code references, check status across all environments, and analyze downstream dependencies.

Do not add a verdict, bullet-point analysis, removal steps, "before removing" checklist, or an offer to archive/delete. The removal question is **fully answered by the routing message above**. Proceed to Step 4.

### Step 4: Route to the Right Follow-up Workflow

After returning the summary, check whether the user's request implies a deeper workflow. If it does, **name the skill and stop** — do not attempt the workflow yourself.

| User intent | Route to |
|---|---|
| Create or modify a flag | [flag create skill](../launchdarkly-flag-create/SKILL.md) |
| Change targeting or rollout | [flag targeting skill](../launchdarkly-flag-targeting/SKILL.md) |
| "Is this safe to remove?", "Is this stale?", cleanup | [flag discovery](../launchdarkly-flag-discovery/SKILL.md) / [flag cleanup](../launchdarkly-flag-cleanup/SKILL.md) |

For removal/staleness questions specifically: follow the Scope Boundary instructions above — summary table only, then route. No verdict.

## Output Style

Keep `/flag` responses brief and operational:

- Start with the resolved flag (or disambiguation list)
- Include only the minimum config details needed for the next action
- End with one clear next step question when user intent is ambiguous

## Important Context

- `/flag` is a fast entrypoint, not a full lifecycle workflow.
- Prefer disambiguation over guessing when multiple flags match.
- Treat project + environment as first-class context; avoid hidden assumptions.
- When sharing rollout percentages, always use human-readable percentages.
- **Never improvise removal, staleness, or cleanup analysis.** Always route to the dedicated skill.
