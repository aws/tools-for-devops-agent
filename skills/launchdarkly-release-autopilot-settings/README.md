# LaunchDarkly Release Autopilot Settings Skill

An Agent Skill for configuring Release Autopilot (GitHub App auto-flagging and auto-releasing) through the LaunchDarkly MCP, and for diagnosing why a PR was not classified.

## Overview

This skill teaches agents how to:

- Diagnose "why didn't Release Autopilot classify my PR?" (account gate → mapped repo → repo override) before changing anything
- Read account-wide Release Autopilot defaults
- Confirm every write (account, map, repo override, unmap) before calling MCP
- List GitHub App install repos as `owner/name`

## Installation (Local)

- **Generic**: copy `skills/release-autopilot/launchdarkly-release-autopilot-settings/` into your client's skills path

## Prerequisites

The remotely hosted LaunchDarkly MCP server must expose the Release Autopilot settings tools (`get-release-autopilot-settings`, `list-release-autopilot-github-repos`, `update-release-autopilot-repo-settings`, and siblings). If `list-release-autopilot-github-repos` returns `githubConnectUrl`, give the user that link. This skill does not complete GitHub OAuth itself.

Release Autopilot settings are in alpha. The endpoints behind these tools are gated by an alpha feature flag, so accounts outside the alpha get 404s.

## Usage

```
Why didn't Release Autopilot classify my pull request?
```

```
Turn on auto-flagging and map launchdarkly/gonfalon to project default
```

```
Which GitHub repos are mapped for Release Autopilot, and which can I map?
```

## Related

- [LaunchDarkly Flag Create](../../feature-flags/launchdarkly-flag-create/): Create flags after Release Autopilot is mapped
- [LaunchDarkly MCP Server](https://github.com/launchdarkly/mcp-server)
- [LaunchDarkly Docs](https://docs.launchdarkly.com)

## License

Apache-2.0
