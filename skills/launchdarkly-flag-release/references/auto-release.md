# Auto-release: automated rollout configs & release policies

This is the mechanism behind the "release" half of the skill. The goal: once the PR
merges and the guarding flag starts evaluating, the change rolls out **on its own**,
the way the team has decided similar changes should roll out — no human toggling a flag.

## The pieces

- **Flag** — the boolean gate you created (OFF everywhere). Nothing happens to users until a release turns it on.
- **Release policy** — a project-level rule that says *how* a matching flag should be released in a given environment: immediately, progressively (staged %), or as a guarded rollout with metrics and auto-rollback. Policies match on criteria like environment and flag tags, and can auto-attach the metrics a guarded rollout should watch.
- **Automated rollout config** — the per-flag, per-PR record (created by `create-automated-rollout-config`) that ties the flag to the merge and says, per environment, whether to release immediately or to defer to the environment's release policy (`releaseType: "policy"`).

## Immediate vs `policy`

`create-automated-rollout-config` takes an `environments` array; each entry has an
`environmentKey` and, for a policy release, `releaseType: "policy"`. `releaseType` accepts only
`override` and `policy`; there is no `simple`.

- **Immediate** (`{ environmentKey }`, no `releaseType` or `override`): serve `true` in that environment once the flag begins evaluating — the same trigger `policy` waits for, just with no policy resolution or stages. Use it for dev/staging environments you want fully enabled without ceremony.

- **`policy`** (`{ environmentKey, releaseType: "policy" }`): not a hold — it never waits for a date or a sign-off. Wait until the PR merges and the flag begins evaluating, then resolve that environment's configured release policy and perform the matching release — immediate, progressive, or guarded — automatically. Use it for production and any environment where you want a governed, monitored rollout with the safety net the team already defined.

A typical plan: `staging → immediate`, `production → policy`.

An operator can also pin a rollout with `releaseType: "override"` and an `override` object whose
`releaseMethod` is `immediate`, `progressive`, or `guarded`. Progressive and guarded need `stages`
(`allocation` and `durationMillis`, allocations strictly increasing; guarded caps each stage at
`50000` and needs `metricKeys` or `metricGroupKeys`). Never combine `override` with `policy`.

## Preview before you propose

Always call `match-release-policies` before recommending a `policy` environment, so you
(and the user) know what `policy` will actually do:

- **Before the flag exists** — pass `projectKey`, `environmentKey`, and the proposed `flagTags`. This does client-side matching against the project's policies and previews the winner.
- **After the flag exists** — pass `projectKey`, `environmentKey`, and `flagKey`. This hits the server-side release-settings endpoint and returns the authoritative resolved policy.

It returns `matchingPolicies`, the `winningPolicy` (null when nothing matches), and `warnings`. The winner's method is `winningPolicy.releaseMethod` (`immediate-release`, `progressive-release`, or `guarded-release`), and a guarded policy's metrics are `winningPolicy.guardedReleaseConfig.metricKeys` and `.metricGroupKeys`. Use `get-release-policies` to see every policy in the project and what each attaches.

**If nothing matches**, `policy` falls back to project defaults (often an immediate release). Tell the user — they may want an immediate release instead, or set up a release policy first.

**A guarded release is only as good as its metrics.** If a `policy` env resolves to a **guarded** method, check that `winningPolicy.guardedReleaseConfig.metricKeys` (or `.metricGroupKeys`) is non-empty and actually relevant to this change — a guarded rollout with no meaningful metric guards nothing. Watch for the **net-new path** case: when the flag-off control renders nothing, feature-specific before/after comparisons are "one-armed" and can't detect a regression, so a guarded release must lean on existing global/service metrics. If the attached metrics can't compare treatment vs. control for this change, say so and recommend an immediate release for that env (or point the user at metric setup) rather than presenting a guarded rollout that can't actually guard.

## Precedence

When a `policy` environment resolves what to do on merge, precedence is:

**human release intent → explicit overrides → matched release policy → project/demo defaults**

A human's stated intent — captured before recording (release now / hold / `notBefore` / segment /
prerequisite) — sits *above* the policy: if the user said "hold until August," you don't register a
plan that releases that env on merge, no matter what the policy would do. Below intent, an operator override
wins over the policy, and the policy wins over the fallback default. You generally don't set
overrides from this skill; you rely on the policy, which is why previewing it matters.

**Fail closed.** Intent is honored or explicitly held — never silently dropped. If you can't
express a piece of intent through the available tools (e.g. a `notBefore` date the rollout config
can't encode), leave the flag OFF for that env and report it as held with the reason, rather than
registering a release that ignores the constraint. An unclear intent should *prevent* a release,
never cause one.

## Registering the config

Call `create-automated-rollout-config` in the implement phase:

```json
{
  "projectKey": "default",
  "flagKey": "new-checkout-flow",
  "environments": [
    { "environmentKey": "staging" },
    { "environmentKey": "production", "releaseType": "policy" }
  ],
  "repoFullName": "acme/storefront",
  "prNumber": 482
}
```

The guarding flag must already exist. Provide the PR reference (`repoFullName` + `prNumber`,
or `prUrl`) so the rollout is bound to the right merge. The call returns `created`,
`config_id`, and the normalized per-environment plan — record `config_id` in your report.

## Coupling to a parent flag (prerequisites)

When the change depends on another feature that isn't live yet, don't leave the ordering as a
human note — make it structural with a LaunchDarkly **prerequisite**. The dependent flag lists
the parent as a prerequisite (parent must serve its "on" variation) so the dependent can be
turned on safely: while the parent is off, the dependent stays effectively off; when the parent
releases, the dependent goes live in lockstep. This is native LaunchDarkly behavior, so it's the
right way to express "this must not go live before X." Set it via the MCP surface if it exposes
prerequisite editing; if it doesn't, report the required prerequisite as a manual step and do not
register a rollout that could release this flag ahead of its parent.

## Relationship to guarded rollouts

When a `policy` environment resolves to a **guarded** release method, the merge triggers the
same kind of progressive, metric-monitored rollout described in the
[`launchdarkly-guarded-rollout`](../../launchdarkly-guarded-rollout/SKILL.md) skill — the
difference is that here it's driven automatically by the policy on merge, rather than started
by hand. If a change needs a *bespoke* rollout that no policy expresses, record that environment
as immediate here and drive the guarded rollout manually with that skill after merge.
