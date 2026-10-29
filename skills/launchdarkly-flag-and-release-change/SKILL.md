---
name: launchdarkly-flag-and-release-change
description: "Drive a pull request's change end to end: decide it's flag-worthy, create the guarding flag, wire the new code path behind it on the PR branch, and record an automated release so the change ships safely when the PR merges. A portable orchestrator that composes launchdarkly-should-flag-change, launchdarkly-flag-create, and launchdarkly-flag-release. Keywords: flag a PR, wrap change in a flag, dark launch, kill switch, auto-release, automated rollout, end-to-end flag workflow."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server and a git CLI with access to the PR's repository
metadata:
  author: launchdarkly
  version: "0.1.0"
---

# Flag & Release a PR Change

You're using a skill that takes a pull request whose change should ship behind a feature flag and drives it end to end: decide it needs a flag, create the guarding flag, wire the new behavior behind it on the PR's branch, and record an **automated release** so the change ships safely once the PR merges.

**The deploy is not the release.** The merge ships the control path — the flag is created OFF, so deployment always serves the pre-change behavior. The *release* is the flag operation the automated rollout performs afterward, governed by the environment's policy. Creating the flag OFF and recording the release are deliberately separate things.

This skill is a **portable PR orchestrator**. It doesn't own the flag mechanics or the release mechanics — it composes three focused skills and adds the PR workflow (read the diff, work in a clone, push to the branch) plus the plan→implement sequencing:

| Step | Owned by | This skill's role |
|------|----------|-------------------|
| Decide *whether* to flag | [`launchdarkly-should-flag-change`](../launchdarkly-should-flag-change/SKILL.md) (advisory, read-only) | Act on a "yes"; make the call yourself if it wasn't run |
| Create the flag + wire the code | [`launchdarkly-flag-create`](../launchdarkly-flag-create/SKILL.md) | Invoke it against the change; don't re-teach flag creation or SDK patterns |
| Record the release | [`launchdarkly-flag-release`](../launchdarkly-flag-release/SKILL.md) | Hand off once the flag exists and the code is pushed; don't re-teach rollout mechanics |

Don't duplicate any composed skill's mechanics here. This skill's only unique content is the **PR wrapper** (clone, three-dot diff, commit/push to the branch) and the **plan→implement** flow that stitches the three together.

> **Automation note.** An orchestrating harness (e.g. a PR pipeline) can skip this skill and invoke the three composed skills directly — `launchdarkly-should-flag-change` → `launchdarkly-flag-create` → `launchdarkly-flag-release` — driving the git and sequencing itself. This skill is the portable, human-in-the-loop path for a developer working a PR by hand.

You work in two phases — **plan**, then **implement** — and you check in with the user in between. **Never create or modify anything during the plan phase.**

## Prerequisites

- The remotely hosted LaunchDarkly MCP server.
- A `git` CLI that can read and push to the PR's repository.
- The composed skills available: [`launchdarkly-flag-create`](../launchdarkly-flag-create/SKILL.md) (flag creation + code wiring) and [`launchdarkly-flag-release`](../launchdarkly-flag-release/SKILL.md) (recording the rollout). [`launchdarkly-should-flag-change`](../launchdarkly-should-flag-change/SKILL.md) is used if the flag decision hasn't been made.

MCP tools are used *via the composed skills* — `create-flag`/`get-flag` through flag-create, `match-release-policies`/`create-automated-rollout-config` through launchdarkly-flag-release. This skill calls none directly.

## Working With the Pull Request

Work from a clone so you can read the change and push the flag wiring back to its branch. Credentials are provided by the environment — never ask for, print, or store tokens.

```bash
git clone https://github.com/<owner>/<repo>.git && cd <repo>
git fetch origin pull/<pr_number>/head
git diff origin/HEAD...<head_sha>       # three-dot: change relative to the PR's base
```

The three-dot diff (`base...head`) shows exactly what the PR introduces. Read the changed files you need to understand the change and its risk. Stay in this clone through both phases — in implement you edit, commit, and push here. Full PR mechanics (clone, three-dot diff, commit/push to the branch): [references/pr-wiring.md](references/pr-wiring.md).

## Plan Phase

**Create nothing in this phase.**

1. **Confirm it should be flagged.** If [`launchdarkly-should-flag-change`](../launchdarkly-should-flag-change/SKILL.md) already ran, act on its verdict. Otherwise apply the same judgment: favor a flag for user-facing or risky changes; skip config-only, dependency-bump, infra, test-only, or docs changes. If a flag clearly isn't warranted, say so and stop.
2. **Understand the change and conventions.** Read the three-dot diff and changed files — what does it do, what's the blast radius? Then follow **flag-create's Step 1** to learn how this codebase already uses flags (SDK, wrapper, key constants, naming). Don't reinvent that exploration here.
3. **Design the flag.** Usually a single boolean kill-switch around the new path (flag-create's [flag-types](../launchdarkly-flag-create/references/flag-types.md) covers the choice). Don't propose more flags than the change needs. If Step 1 (or `launchdarkly-should-flag-change`) surfaced a **dependency on a parent flag/feature that isn't live yet**, note it — the release step can couple them with a prerequisite.
4. **Plan the release.** Follow [`launchdarkly-flag-release`](../launchdarkly-flag-release/SKILL.md)'s plan phase: pick target environments, preview each with `match-release-policies`, and capture the human's **release intent** (release on merge / hold / `notBefore` / segment / prerequisite). Don't re-derive the rollout model here — that's launchdarkly-flag-release's job.
5. **Present the combined plan and stop.** Summarize: the flag (`key`, `name`, boolean, tags) and why it gates *this* change; where in the code the guard goes; the per-environment release plan + captured intent (and anything to be *held*). Then wait. Revise on feedback; proceed only on clear approval. Ask a focused question if you're genuinely missing something (project key, environments, a missing policy) rather than guessing.

## Implement Phase

Only after approval:

1. **Create the flag and wire the code** using [`launchdarkly-flag-create`](../launchdarkly-flag-create/SKILL.md) (its Steps 3–4): flag created OFF with the agreed key/tags, guarding evaluation added with a safe default matching the codebase's pattern. **Fail closed on creation errors:** only an "already exists" result is success-via-reuse. Any *other* create-flag failure (auth, permissions, not-found, server error) is a hard stop — do **not** wire the code, record the release, or report success. A false "flag created" yields a green PR referencing a flag that doesn't exist, worse than an honest failure. Surface the error and stop.
2. **Add paired flag-on / flag-off tests.** If the repo has a test suite, add a test for each state of the wrapped path — flag ON serves the new behavior, flag OFF preserves the old — matching the repo's framework and flag-mocking convention. Run them and continue only once green. Scope the tests to the flagged path, not general coverage. If the repo has no tests, skip and say so.
3. **Commit and push to the PR branch.** Commit the wiring and push to the PR's existing branch so it lands in the same PR — don't open a new PR or touch the base branch. See [references/pr-wiring.md](references/pr-wiring.md).
4. **Record the release** by handing off to [`launchdarkly-flag-release`](../launchdarkly-flag-release/SKILL.md)'s implement phase: it records the automated rollout, honoring the captured intent (holding any environment the intent doesn't clear) and returns a `config_id`. Don't re-teach the rollout mechanics here.
5. **Report** the whole change: flag key + LaunchDarkly link (created OFF); the file(s)/code path wired; the tests added; the per-environment release plan + `config_id`; what was **held** (and why) versus what releases on merge. Report only what you verified.

## Edge Cases

| Situation | Action |
|-----------|--------|
| Change isn't flag-worthy | Explain why (config-only, dep bump, infra, test-only, docs) and stop. Don't create a flag. |
| Flag already exists | Reuse it — "already exists" is success. Wire the existing key; don't duplicate. |
| Flag creation fails for any other reason (auth, permissions, 5xx) | Hard stop. Don't wire code, record a release, or claim success — surface the error. |
| Codebase has no LaunchDarkly SDK | Wiring can't evaluate a flag — SDK install is separate ([onboarding/sdk-install](../../onboarding/sdk-install/SKILL.md)). |
| Guarding needs more than a boolean | Prefer a boolean kill-switch. Only go multivariate if the change serves distinct variants; see flag-create's [flag-types](../launchdarkly-flag-create/references/flag-types.md). |
| Release-specific cases (hold/`notBefore`, prerequisites, no matching policy, duplicate config, no useful metric) | Handled by [`launchdarkly-flag-release`](../launchdarkly-flag-release/SKILL.md) — see its edge cases. |

## What NOT to Do

- **Don't create anything in the plan phase.** Plan proposes; implement creates.
- **Don't re-document flag creation, SDK guarding, or rollout mechanics here** — those are [`launchdarkly-flag-create`](../launchdarkly-flag-create/SKILL.md) and [`launchdarkly-flag-release`](../launchdarkly-flag-release/SKILL.md). Link to them.
- **Don't turn the flag on yourself.** The recorded release owns that; creating the flag OFF is the point.
- **Don't over-flag.** One kill-switch beats several speculative flags.
- **Don't handle or print credentials.** Git access is injected.

## References

- [references/pr-wiring.md](references/pr-wiring.md): PR mechanics — clone, three-dot diff, committing to the PR branch. *(This skill's only unique reference.)*
- [`launchdarkly-should-flag-change`](../launchdarkly-should-flag-change/SKILL.md): the flag-worthiness decision.
- [`launchdarkly-flag-create`](../launchdarkly-flag-create/SKILL.md): flag creation + per-SDK guarding patterns.
- [`launchdarkly-flag-release`](../launchdarkly-flag-release/SKILL.md): recording the automated rollout (and its [auto-release.md](../launchdarkly-flag-release/references/auto-release.md) release model).
