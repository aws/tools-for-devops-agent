# Flag & Release a PR Change Skill

A portable Agent Skill that drives a pull request's change end to end: decide it needs a flag, create the guarding flag, wire the new code path behind it on the PR branch, and record an automated release so the change ships safely when the PR merges.

## Overview

This skill is a **PR orchestrator**. It composes three focused skills and adds only the PR workflow (clone, three-dot diff, commit/push to the branch) and the plan→implement sequencing:

| Step | Owned by |
|------|----------|
| Decide *whether* to flag | [`launchdarkly-should-flag-change`](../launchdarkly-should-flag-change/) (advisory, read-only) |
| Create the flag + wire the code | [`launchdarkly-flag-create`](../launchdarkly-flag-create/) |
| Record the release | [`launchdarkly-flag-release`](../launchdarkly-flag-release/) |

**The deploy is not the release**: the merge ships the control path (flag OFF); the release is the flag operation the recorded rollout performs afterward. An automation harness can bypass this skill and invoke the three composed skills directly — this is the portable, human-in-the-loop path.

## Installation (Local)

Copy `skills/feature-flags/flag-and-release-change/` into your client's skills path, along with the composed skills it delegates to.

## Prerequisites

- The remotely hosted LaunchDarkly MCP server.
- A `git` CLI that can read and push to the PR's repository.
- The composed skills available: `launchdarkly-flag-create` and `launchdarkly-flag-release`.

## Usage

```
This PR should ship behind a flag — create it, wire it on the branch, and set up
the release. Hold production until next week.
```

## Structure

```
launchdarkly-flag-and-release-change/
├── SKILL.md
├── marketplace.json
├── README.md
└── references/
    └── pr-wiring.md
```

## Related

- [Should Flag Change](../launchdarkly-should-flag-change/): The flag-worthiness decision
- [LaunchDarkly Flag Create](../launchdarkly-flag-create/): Flag creation + SDK guarding patterns
- [Flag Release](../launchdarkly-flag-release/): Recording the automated rollout
- [LaunchDarkly Docs](https://docs.launchdarkly.com)

## License

Apache-2.0
