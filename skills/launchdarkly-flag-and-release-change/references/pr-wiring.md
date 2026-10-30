# PR wiring: reading the change and pushing to the branch

This covers only what's specific to operating on a **pull request**: reading exactly what the
PR changes, and pushing the flag wiring back to its branch so it lands in the same PR.

How to actually guard the new path in code — SDK calls, wrapper patterns, safe defaults, per
language — is **not** here. That's owned by
[`launchdarkly-flag-create`](../../launchdarkly-flag-create/SKILL.md) and its
[SDK Evaluation Patterns](../../launchdarkly-flag-create/references/sdk-evaluation-patterns.md).
Use those; don't reinvent them.

## Clone and read the change

Credentials are injected by the environment — never ask for, print, or store tokens.

```bash
git clone https://github.com/<owner>/<repo>.git && cd <repo>
git fetch origin pull/<pr_number>/head
git diff origin/HEAD...<head_sha>      # three-dot: change relative to the PR's base
```

Use the **three-dot** form (`base...head`). It shows only what this PR introduces, not
unrelated commits that landed on the base since the branch forked. Read the changed source
files (not just the diff) so you pick a clean seam to guard.

Stay in this same clone for both phases. In the implement phase you commit and push here.

## Guard the change (delegated)

Follow flag-create's Step 4 and its SDK patterns to wrap the new behavior behind the flag.
The one principle worth repeating because it's a release-safety invariant: **the in-code
default must be the safe, pre-change behavior**, so an unreachable LaunchDarkly leaves users on
the old path. Concretely, **the flag-off path must not invoke any of the new code** — no new
function calls on the control branch — so a flag that never turns on leaves users exactly where
they were. Wrap at the smallest scope that isolates the change (the handler/component logic, not
route registration). Prefer a single branch point around the new path over scattered flag checks,
and don't delete the old path — the kill-switch needs something to fall back to.

## Commit and push to the PR branch

```bash
git add -A
git commit -m "Gate <change> behind LaunchDarkly flag <flag-key>"
git push origin HEAD:<pr_branch>
```

Push to the PR's existing branch so the wiring appears in the same PR. Don't open a new PR,
force-push, or touch the base branch.

## After wiring

Once the flag exists and the wiring is pushed, hand off to
[`launchdarkly-flag-release`](../../launchdarkly-flag-release/SKILL.md) to record the automated release so the merge
triggers the rollout. Then verify the code compiles/lints and `get-flag` shows the flag
created and OFF before reporting.
