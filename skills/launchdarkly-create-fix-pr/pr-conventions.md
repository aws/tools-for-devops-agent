# PR conventions

Load this file whenever you're about to create a commit or file a PR.

## Git identity

Use the repo's / your configured `git config` identity — don't override it. Commits and PRs land under your own identity, which is the correct behavior. If commits need to attribute to a specific identity to pass branch-protection rules, set it with your configured values:

```bash
git config user.email "<your-email>"
git config user.name "<your-name>"
```

## Branch naming

- `fix/<ticket-or-slug>` — general fixes and PR-driven work

Keep branch names kebab-case and under 60 chars.

## Commit + push

```bash
git checkout -b fix/<branch-name>
# stage only the files you changed
git add <specific paths>
git commit -m "<conventional commit message>"
git push -u origin fix/<branch-name>
```

`git push` uses your existing git/gh credentials.

**Commit message rules:**
- Follow Conventional Commits: `fix:`, `feat:`, `chore:`, `refactor:`, `docs:`, `test:`
- Imperative mood in the subject: "fix auth timeout" not "fixed auth timeout"
- Subject under 72 chars
- Body (optional) explains *why*, not *what* — the diff shows *what*
- Follow the repo's own commit conventions where they differ from the above

## Filing the PR

1. **Check for duplicates first.** Search for similar open PRs:
   - `gh pr list --search "<keywords>" --state open`

   If a similar PR exists, direct the user to it — do not file a duplicate.
2. **File the PR.** The branch must already be on the remote from your `git push` above.
   - `gh pr create --title "<title>" --body "<body>" --base <base-branch>`. Pass the body via heredoc to preserve formatting.

## PR body structure

```
## Summary

<1-2 sentences describing what changed and why>

## Root cause

<Short description of the root cause from your investigation. Cite specific evidence: trace ID, log timestamp, error group, file and line.>

## Approach

<Why this fix is the right one. What was considered and rejected. What's out of scope.>

## Verification

<How you verified the fix works. Tests added? Manual verification? Expected behavior change?>

## Related

- Error group: <id if applicable>
- Trace: <id if applicable>
```

Keep it tight. PR descriptions exist to give reviewers context, not to prove thoroughness.

## After filing

- **Monitor initial CI.** Get the PR's check status after a minute — `gh pr checks <pr-number>`. If something fails quickly (linting, formatting), surface it to the user so they can decide whether to fix in-thread or separately.
- **Don't push additional commits reflexively.** Wait for user direction or a specific failing check before editing further.

## Never do

- Push to `main` or any protected branch directly
- Force-push to a branch someone else is working on
- Create a PR without first searching for an existing open PR addressing the same issue
- Include access tokens, secrets, or credentials in commits, branch names, or PR bodies
