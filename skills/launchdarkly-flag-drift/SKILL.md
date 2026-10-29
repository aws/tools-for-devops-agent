---
name: launchdarkly-flag-drift
description: "Detect and reconcile drift between a feature flag's in-code SDK fallback default and its LaunchDarkly default rule (fallthrough). Use when a flag's default rule changed, when the user asks to detect flag drift, check whether a hardcoded default still matches LaunchDarkly, sync an in-code default, or open a PR reconciling a fallback value, without removing the flag or its evaluation."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "0.1.0"
---

# LaunchDarkly Flag Drift Detection

You're using a skill that will guide you through checking whether a feature flag's **in-code SDK fallback default** has drifted from its **LaunchDarkly default rule (fallthrough)**, and reconciling the code if it has. Your job is to determine the flag's current default rule value from LaunchDarkly, locate the default argument passed to every SDK evaluation in code, compare them, and, only when they differ, update the in-code default so it matches. You never remove the flag or change its evaluation logic.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `get-flag`: fetch the flag's configuration **in a specific environment** (fallthrough, variations, offVariation). Fallthrough is environment-specific, so call this **once per critical environment**.

**Optional MCP tools:**
- `list-flags`: find the flag key if the user only described the flag by name
- `get-environments`: enumerate the project's environments to determine which are critical
- `get-flag-status-across-envs`: quick snapshot of a flag's state across environments (a fast way to spot cross-environment differences before pulling each `get-flag`)

## Core Concept: The SDK Fallback Default Is Not the Off Variation

Every SDK evaluation call takes a **fallback default**: the value returned when LaunchDarkly is unreachable, the client is uninitialized, or the flag is unavailable. This is a code-side safety value, distinct from the flag's `offVariation` (served when the flag is toggled off) and from its `fallthrough` (the default rule served when no targeting rule matches).

This skill treats one specific invariant as "correct": **the in-code fallback default should match the current default rule (fallthrough) value**. When they diverge, that's *drift*. Reconciling it keeps the value returned during an outage consistent with what most users would otherwise receive.

## Core Concept: One In-Code Default, Many Environments

The in-code fallback default is a **single value compiled into the deployed code**. The flag's fallthrough, however, is configured **per environment** and can differ between them (e.g. `production`, `eu-production`, and `federal` may each serve a different default rule). So the fallthrough must be resolved in **every critical environment the code runs against**, not just one.

- When the critical environments **agree** on the fallthrough, that shared value is the expected default. Reconcile as normal.
- When they **disagree** (e.g. EU serves `true` but Federal serves `false`), a single in-code default *cannot* match all of them. That divergence is itself a finding: surface it and confirm which environment is authoritative for this build rather than silently reconciling to one. See Edge Cases.

Checking only one environment is the most common way this skill produces a wrong or misleading result, so always establish the full set of critical environments first.

Some teams intentionally keep the fallback as a conservative/off value instead. Treat a mismatch as a finding to surface, not always an automatic edit. See Edge Cases.

## Workflow

### Step 1: Identify the Flag and the Critical Environments

1. **Get the flag key.** If the user described the flag by name, use `list-flags` to resolve the key. Confirm before proceeding.
2. **Establish the critical environments.** The fallthrough is environment-specific, and the same in-code default has to stand in for every environment the deployed code serves. Determine that full set before comparing:
   - If one build serves **multiple** production-grade environments (e.g. `production`, `eu-production`, `federal`), **all** of them are critical.
   - If the build is scoped to **one** environment (a region- or tenant-specific deployment, e.g. a Federal-only build), that single environment is the only critical one.
   - Look for signals in the repo (deploy config, environment names in CI, SDK key wiring) and confirm with the user. Use `get-environments` to enumerate what exists if the set is unclear. Do not assume a single `production`.

### Step 2: Determine the Expected Default from LaunchDarkly

Call `get-flag` **once per critical environment**. For each environment, read:
- `fallthrough`: the default rule. If it points to a single `variation` (an index), that's the resolved value. If it's a percentage `rollout`, there is **no single default value**, so stop and handle as an edge case.
- `variations`: map `fallthrough.variation` (the index) to `variations[index].value`. This resolved value is that environment's expected default.
- `offVariation` and flag type: useful context for the comparison and for spotting type mismatches.

Then reconcile across environments:

| Across critical environments | Expected default |
|------------------------------|------------------|
| All resolve to the **same** value | That shared value is the expected default. Continue to Step 3. |
| They resolve to **different** values | **Cross-environment divergence.** One in-code default cannot satisfy all of them. Do **not** auto-pick. Report the per-environment values and confirm which environment is authoritative for this build (or that the divergence should be resolved in LaunchDarkly first). See Edge Cases. |

(`get-flag-status-across-envs` can give a fast heads-up on whether environments differ, but always resolve the actual fallthrough value with `get-flag` before editing.)

Never guess the fallthrough value. Always resolve it from `get-flag`.

### Step 3: Locate Every In-Code Default

Find every place the flag is evaluated in code and, critically, the **default/fallback argument** passed to the SDK call. Search for the flag key across the codebase, then identify the default in each hit.

- The default is typically the **last positional argument** to `variation(...)` / `*Variation(...)` calls (e.g. `boolVariation("<key>", context, <default>)`).
- Teams often wrap the SDK. Check wrapper/registry/config layers that declare a default once per flag, annotation- or struct-tag-based defaults, and generated default files.

See [SDK Default Patterns](references/sdk-default-patterns.md) for the full set of patterns by language and abstraction, and how to distinguish the default argument from the context argument.

### Step 4: Compare and Decide

Normalize both sides before comparing (see Edge Cases for JSON/number/type notes), then:

| Result | Action |
|--------|--------|
| Critical environments **disagree** on the fallthrough | **Stop — no single expected default exists.** Report the per-environment values and confirm which environment is authoritative for this build before editing (or resolve the divergence in LaunchDarkly first). Do not auto-reconcile to one environment. |
| In-code default **matches** the expected default (in every critical environment) | **No drift.** Report `drift_detected: false` and stop. Do not open a PR. |
| In-code default **differs** | **Drift detected.** Proceed to Step 5 to reconcile. |
| Multiple evaluations with **different** in-code defaults | Drift. Reconcile all of them to the expected value and note the prior inconsistency. |

### Step 5: Reconcile the In-Code Default

Update **only** the default/fallback argument so it matches the expected value.

- Do **not** change evaluation logic, branching, or off-path behavior.
- Do **not** remove the flag or its evaluation.
- If the default lives in a **generated file**, do not hand-edit it. Update the source of truth (the constructor/registry/annotation) and regenerate using the project's codegen command. Note `requires_generation: true` in your summary.

**Example (before then after), expected default = `true`:**

```typescript
// Before: outage returns false even though the default rule now serves true
const enabled = await ldClient.variation('new-checkout-flow', context, false);

// After: fallback default reconciled to match the fallthrough
const enabled = await ldClient.variation('new-checkout-flow', context, true);
```

The surrounding `if (enabled) { ... } else { ... }` branching is left untouched.

### Step 6: Validate Before Committing

Run the project's configured checks scoped to the changed files. Discover them from `package.json` scripts, a `Makefile`, `AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md`, or the CI config. Typically: format, lint, type-check, build, and the relevant tests.

**Hard stop:** if any check fails and you cannot fix it, do not commit or push. Narrow your change instead. Never ship code that fails format/lint/type-check/build/test.

### Step 7: Open the Pull Request

Only after validation passes. Use [references/pr-template.md](references/pr-template.md). The description must state: the flag key, the critical environments checked and their resolved fallthrough values, the old vs new in-code default, and that **only** the SDK fallback default changed (the flag and its evaluation are preserved).

- Follow the repository's contribution conventions (branch naming, commit style). Check `AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md` first.
- A clear default: branch `fix/flag-default-drift-<flag-key>`, commit `fix: sync in-code default for <flag-key> to match fallthrough`.

### Step 8: Report a Structured Summary

Produce a concise summary with these fields:

```
flag_key:              <key>
environments_checked:  [<env>: <resolved fallthrough value>, ...]
environments_diverge:  true | false
drift_detected:        true | false
old_default:           <in-code value before, or n/a>
new_default:           <expected value / value written, or n/a>
files_modified:        [<paths>]
pr_url:                <url or null>
requires_generation:   true | false
notes:                 <anything the reviewer should know, incl. any cross-environment divergence>
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Fallthrough is a **percentage rollout** | There is no single default value. Report the split, do not auto-edit, and ask the user which value the fallback should represent. |
| Fallback appears **intentionally conservative** (matches `offVariation` or a safe value) | Surface the mismatch and confirm intent before changing. Some teams keep the fallback as a safe value on purpose. |
| In-code default lives in a **generated file** | Edit the source of truth and regenerate; never hand-edit generated output. Set `requires_generation: true`. |
| **Type mismatch** between code default and the variation's type | Flag as a bug in the PR/summary; the default and variation types should agree. |
| **JSON / object / float** defaults | Compare by normalized value, not string form (`{"a":1}` == `{ "a": 1 }`, `0` == `0.0`). |
| Flag **not found** or wrong environment | Inform the user; check for typos in the key and confirm the environment. |
| **Dynamic flag keys** (`flag-${id}`) | Automated detection may be incomplete; flag for manual review. |
| Critical environments **disagree** on the fallthrough (e.g. `eu-production` serves `true`, `federal` serves `false`) | A single in-code default cannot match all of them. If the build is scoped to **one** environment, reconcile to that environment's value and note the others. If the build serves **several** divergent environments, do not silently pick one — surface every per-environment value and confirm which environment is authoritative, or recommend resolving the divergence in LaunchDarkly first. |
| Build targets a **single environment** (region- or tenant-specific deployment) | Treat that environment as the sole critical one; other environments' fallthroughs are not relevant to this build's default. |
| Flag spans **multiple repositories** | This skill operates on the current repo. Note other repos that also reference the key so they can be reconciled separately. |

## What NOT to Do

- Don't remove the flag or its evaluation; this skill only touches the default argument.
- Don't change evaluation logic, branching, or off-path behavior beyond the fallback default.
- Don't check only one environment; resolve the fallthrough in every critical environment the build serves.
- Don't reconcile to one environment's fallthrough when critical environments disagree — a single default can't satisfy divergent environments, so surface the divergence and confirm the authoritative environment first.
- Don't hand-edit generated files; regenerate from the source of truth.
- Don't open a PR when there is no drift.
- Don't guess the fallthrough value; resolve it from `get-flag`.
- Don't ship code that fails format, lint, type-check, build, or tests.

## References

- [SDK Default Patterns](references/sdk-default-patterns.md): Where the fallback default lives by language, wrapper, annotation, and generated-file pattern; how to find it
- [PR Template](references/pr-template.md): Structured PR description for a drift reconciliation
- [Flag Cleanup](../launchdarkly-flag-cleanup/SKILL.md): If the goal is to remove the flag entirely, not reconcile its default
- [Flag Targeting](../launchdarkly-flag-targeting/SKILL.md): If the goal is to change the default rule in LaunchDarkly instead of the code
