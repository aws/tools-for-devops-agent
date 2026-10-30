---
name: launchdarkly-create-fix-pr
description: "Investigates a root cause and files a minimal fix PR for a reported bug or observability finding."
license: Apache-2.0
compatibility: Requires git and the GitHub CLI (gh); pairs with the investigate skill
metadata:
  author: launchdarkly
  version: "1.0.0"
---

# Create a fix PR

## Overview

You are investigating a problem and filing a pull request that resolves it. This builds on the `launchdarkly-investigate` skill — do the investigation properly first, don't jump to a fix without evidence.

Use the `gh` CLI for all GitHub operations (auth comes from your `gh` login) and standard `Bash` / `Edit` / `Read` / `Grep` for everything else.

## Workflow

1. **Investigate.** Use the `launchdarkly-investigate` skill to find the root cause. Cite the exact trace ID, log line, error group, and code location that pins the problem.
2. **Confirm there isn't already a PR open.** Before filing anything, search GitHub for an existing open PR addressing the same issue — `gh pr list --search "<keywords>" --state open`. If one exists, direct the user to it — do not create a duplicate.
3. **Judge whether a PR is the right tool.** If the fix requires a config change, a flag flip, or a change outside the code you can access, describe the solution instead of filing a PR.
4. **Get the repo.** Clone it if you don't already have it locally — `gh repo clone <owner>/<repo>`.
5. **Check for repo conventions.** Read `agents.md` or `CLAUDE.md` at the repo root — these describe repo-specific rules your fix needs to respect.
6. **Make the change.** Minimal diff. Don't refactor surrounding code, don't add features, don't fix unrelated bugs you happen to notice. One PR, one fix.
7. **Set git identity** before committing — see `pr-conventions.md`.
8. **Commit, push, and file the PR.** See `pr-conventions.md` for branch naming and PR body rules.

## What's a good fix

- Changes the smallest possible number of lines
- Preserves current production behavior unless the bug IS the current behavior
- Doesn't depend on assumptions you can't verify from the evidence
- Would pass a `code-review` skill's check if one existed

## What isn't

- Sweeping refactors unrelated to the reported problem
- Speculative null checks or error handling added "while you're in there"
- Changes to tests that hide the underlying bug
- Bumping dependency versions to fix a symptom

## Restricted tools

If `gh` isn't installed or `gh auth status` shows no auth, surface the error to the user and stop — don't try alternative auth schemes.

## Never include in a PR

- GitHub access tokens or any other secrets or credentials.
- Debugging logs or print statements you added during investigation.

Follow the repo's own commit and PR conventions for everything else.
