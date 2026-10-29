---
name: launchdarkly-release-autopilot-settings
description: "Configure LaunchDarkly Release Autopilot settings (GitHub App auto-flagging and auto-releasing) via the hosted MCP, or diagnose why a pull request was not classified / auto-flagged. Use when the user wants to turn on auto-flagging, map a GitHub repo to a LaunchDarkly project, change Release Autopilot account defaults, unmap a repo, or asks why Release Autopilot did not classify their PR."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.3.0-experimental"
---

# LaunchDarkly Release Autopilot Settings

You're using a skill that configures Release Autopilot (GitHub App code automation) through the LaunchDarkly MCP, or explains why a PR was not classified. Release Autopilot can open and change pull requests (auto-flagging) and can drive auto-releasing. Treat every write as production automation with a blast radius.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server.

**Required MCP tools:**
- `get-release-autopilot-settings` / `update-release-autopilot-settings`
- `list-release-autopilot-github-repos` (GitHub App install — mappable repos)
- `list-release-autopilot-repo-settings` (already mapped)
- `update-release-autopilot-repo-settings` / `get-release-autopilot-repo-settings` / `delete-release-autopilot-repo-settings`

If these tools are missing, stop. Do not invent REST calls, numeric GitHub ids, or "fixes" by guessing settings.

Release Autopilot settings are in alpha: the underlying endpoints are gated by an alpha feature flag. If every Release Autopilot tool returns 404, the account is not in the alpha — tell the user rather than retrying or falling back to REST.

## Core Principles

1. **Fail closed.** Diagnosis is read-only. Never change settings to "make classification work" unless the user confirmed that exact write after seeing current vs proposed state.
2. **Account settings are the master gate.** A mapped repo cannot enable a capability the account has off. Turning a capability **off** at the account level turns it off for every mapped repo. Turning it **on** at the account level allows every mapped repo that inherits (no override off) to start automating PRs.
3. **Confirm before every Release Autopilot write.** Account PATCH, mapping, repo overrides, and unmap all use [Confirm before write](#confirm-before-write). Only touch repos the user named.
4. **Least privilege.** Never enable auto-releasing unless the user explicitly asked to auto-release (that can ship code). Never turn `approvalRequired` off unless they explicitly asked to drop the approval gate. Never map or unmap repos they did not name. Never iterate the install list and map everything.
5. **Discover, then map.** Pass `owner/name`. Never ask for a numeric GitHub id. Prefer `git remote` of the current workspace when they say "this repo" / "this PR"; if remotes disagree (fork vs upstream), ask which one. `owner/name` resolves against the GitHub App install list only — a repo outside the install cannot be resolved or acted on, because Release Autopilot works through the App. A 404 saying the repo is not on the install, or that the App is not installed, is the answer; do not retry with other spellings or look the repo up elsewhere.
6. **`projectKey` on first map.** Required when creating a mapping; later updates can omit it.
7. **Omit `autoCleanup`.** Not part of Release Autopilot settings yet. Never send it; never copy it from a response into a PATCH.
8. **GitHub connect is a browser link.** If `list-release-autopilot-github-repos` returns `githubConnectUrl`, give the user that exact URL and wait until they say they finished. Then call `list-release-autopilot-github-repos` again. Do not install or authorize GitHub yourself. `flow=install` is Install GitHub App. `flow=authorize` is Authorize GitHub. Both are the same pages as the integration drawer. The user must already be logged into LaunchDarkly in that browser.

## Confirm before write

**STOP.** Do not call `update-release-autopilot-settings`, `update-release-autopilot-repo-settings`, or `delete-release-autopilot-repo-settings` until the user has answered yes to the proposal in this turn. A yes from an earlier turn, or a vague "fix it" / "go ahead" that does not name the setting, is not enough.

1. Read current state first (`get-release-autopilot-settings`, and repo get/list if the change is repo-scoped).
2. State **now** vs **proposed**, in one or two sentences. Include blast radius. For a map, state inherited auto-flagging **and** auto-releasing from the account (read `get-release-autopilot-settings` first).
3. Wait. Do not batch the write in the same tool round as the question.

**Account change** (any field on `update-release-autopilot-settings`, including turning things on):

> Auto-flagging is ON for this account. Turn it OFF for all mapped repos? Auto-flagging pull requests will stop until it is turned back on.

> Auto-flagging is OFF for this account. Turn it ON for the account? Mapped repos that inherit this setting can start getting auto-flagging pull requests.

> Auto-flagging approvalRequired is ON. Turn it OFF? Auto-flagging PRs would no longer require that approval gate.

Same pattern for auto-releasing, and say that auto-releasing can ship.

**Map or change one repo** (`update-release-autopilot-repo-settings`):

Always name **both** inherited account capabilities in the proposal. Omitted overrides inherit auto-flagging **and** auto-releasing; do not confirm a map that only mentions auto-flagging.

> `launchdarkly/gonfalon` is not mapped. Map it to project `default`, inheriting account auto-flagging (ON) and auto-releasing (OFF)? Release Autopilot can start classifying and opening auto-flagging PRs in that repo. Auto-releasing will stay off unless the account (or a repo override) turns it on.

> `launchdarkly/gonfalon` is not mapped. Map it to project `default`, inheriting account auto-flagging (ON) and auto-releasing (ON)? Release Autopilot can start auto-flagging PRs in that repo **and** auto-releasing, which can ship.

> `launchdarkly/gonfalon` is mapped to `default` with auto-flagging effective ON and auto-releasing effective OFF. Set a repo override turning auto-flagging OFF for this repo only? Auto-releasing stays inherited (OFF).

**Unmap** (`delete-release-autopilot-repo-settings`):

> `launchdarkly/gonfalon` is mapped to project `default` with auto-flagging effective ON and auto-releasing effective OFF. Unmap it? Release Autopilot will stop auto-flagging and auto-releasing that repo until it is mapped again.

After they confirm, apply **only** the fields in the proposal. Then verify (do not use verify as the safety check).

## Choose a workflow

- **"Why didn't Release Autopilot classify / auto-flag my PR?"** (or similar) → [Why didn't my PR get classified?](#why-didnt-my-pr-get-classified) first. Do not write settings in that workflow.
- Configure / map / turn on / unmap → [Configure settings](#configure-settings).

## Why didn't my PR get classified?

Use this when the user asks why a PR was not classified, not auto-flagged, or Release Autopilot ignored the PR. **Read-only.** Check in this order. Stop at the first failure and tell them how to fix it (then [Confirm before write](#confirm-before-write) if they ask you to apply the fix).

Identify the GitHub repo (`owner/name`) from the PR URL, `git remote`, or the name they gave. If you cannot identify one repo, ask. Do not diagnose a different repo.

1. **Is auto-flagging on for the account?** `get-release-autopilot-settings`. If `autoFlagging.enabled` is false, that is the answer: account gate is off, so no repo can auto-flag. Stop.
2. **Is this repo mapped to a project?** `get-release-autopilot-repo-settings` with `repo: "owner/name"` (or `list-release-autopilot-repo-settings` and find it). If the error or `list-release-autopilot-github-repos` includes `githubConnectUrl`, read `flow`:
   - `flow=install`: the GitHub App is not installed, so Release Autopilot never sees the PR. That is the answer. Give the user the link and stop.
   - `flow=authorize`: this member has not authorized GitHub, so `owner/name` cannot be looked up. That is not why Release Autopilot skipped the PR. Say so, give the user the link, and resume at this step after they finish. Do not report it as the fix.

   A repo that is on the install but unmapped is a different answer. Unmapped install repos do not run Release Autopilot. Stop.
3. **Does this repo override auto-flagging off?** On the repo payload, if auto-flagging `enabled` is false, or `enabledOverride` is true while `enabled` is false, the repo is opted out even if the account is on. Stop.

If all three look fine (account on, repo mapped, repo auto-flagging effective on):

- Do **not** flip settings to "try something."
- Point them at the Release Autopilot runbooks. These are internal LaunchDarkly Confluence pages (PD space) while Release Autopilot is in alpha; there is no public docs URL yet. Classification can still fail for reasons this MCP surface cannot see (GitHub App install on the wrong org, PR not in an installed repo, workflow/app permissions, classifier skip rules).
  - [Flag Classification (ODD) Runbook](https://launchdarkly.atlassian.net/wiki/spaces/PD/pages/5377097848/WIP+Flag+Classification+ODD+Runbook) — the classifier itself: verdicts (`not-suited`, `already-flagged`), escalations, and the per-PR ledger that records why a PR got the verdict it did.
  - [GitHub App Runbook](https://launchdarkly.atlassian.net/wiki/spaces/PD/pages/5157388373/GitHub+App+Runbook) — the PR event never reaching Release Autopilot: install scope, permissions, webhooks.
- Optional reads: `list-release-autopilot-github-repos` to confirm the repo is on the install list; `autoFlagging.approvalRequired` if they expected a PR and one exists but is waiting on approval.

## Configure settings

### Step 1: Read current settings

1. `get-release-autopilot-settings`
2. `list-release-autopilot-repo-settings`
3. `list-release-autopilot-github-repos` (optional `projectKey`; install is account-wide)

If `githubConnectUrl` is present, give the user that link and stop this turn. Do not map until a later call omits the URL.

### Step 2: Account defaults (if needed)

If an account PATCH is needed, follow [Confirm before write](#confirm-before-write), then `update-release-autopilot-settings` with **only** the confirmed fields:

- `autoFlagging.enabled` / `autoFlagging.approvalRequired` (approval is only valid here)
- `autoReleasing.enabled`

Do not send `autoCleanup`. Requires permission to update account Release Autopilot settings.

### Step 3: Map or override a repository

Only for repos the user named. Follow [Confirm before write](#confirm-before-write), then `update-release-autopilot-repo-settings`:

1. Prefer `repo: "owner/name"`.
2. Include `projectKey` when creating a mapping.
3. Optional repo-level `autoFlagging` / `autoReleasing` overrides. Omitted capabilities inherit the account setting. A repo cannot enable a capability the account has off.

Requires permission to update Release Autopilot repo settings on the mapped project.

### Step 4: Verify (after a confirmed write)

- `get-release-autopilot-repo-settings` / `get-release-autopilot-settings` as appropriate.
- Effective `enabled` must match the proposal (account off ⇒ repo cannot be on).
- Mapped repos appear in `list-release-autopilot-repo-settings`.

To unmap: [Confirm before write](#confirm-before-write), then `delete-release-autopilot-repo-settings`.

## Out of scope

- Auto-cleanup
- Completing GitHub OAuth inside the tool. Hand the user `githubConnectUrl` instead.
- Vega BYOK
- Observability MCP (`github_repositories`) — do not require a second MCP server just to map a repo
- Changing classification rules, GitHub App permissions, or org install scope via this skill
