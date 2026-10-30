# Flag Release Skill

An Agent Skill that records an automated rollout for an **existing** LaunchDarkly flag guarding a pull request's change, so the change releases safely when the PR merges.

## Overview

This skill teaches agents how to:
- Confirm the guarding flag exists and is OFF
- Preview each environment's release policy with `match-release-policies` (immediate / progressive / guarded)
- Capture the human's **release intent** (release on merge / hold / `notBefore` / segment / prerequisite) and honor it — recording only the environments the intent clears, holding the rest
- Record the rollout with `create-automated-rollout-config`

It operates entirely through the LaunchDarkly MCP tools: it never creates flags or edits code. It's the **release step** of the PR flag workflow — after [`launchdarkly-flag-create`](../launchdarkly-flag-create/) has created and wired the flag.

## Installation (Local)

Copy `skills/feature-flags/flag-release/` into your client's skills path.

## Prerequisites

- The remotely hosted LaunchDarkly MCP server.
- The guarding flag already exists (created OFF).
- A pull-request reference (`repoFullName` + `prNumber`, or `prUrl`).

## Usage

```
Record the automated release for flag `new-checkout-flow` on PR acme/storefront#482:
staging on merge, hold production until legal signs off.
```

## Structure

```
launchdarkly-flag-release/
├── SKILL.md
├── marketplace.json
├── README.md
└── references/
    └── auto-release.md
```

## Related

- [Should Flag Change](../launchdarkly-should-flag-change/): Decide whether a change needs a flag
- [LaunchDarkly Flag Create](../launchdarkly-flag-create/): Create + wire the flag
- [Flag & Release a PR Change](../launchdarkly-flag-and-release-change/): The end-to-end orchestrator that composes this skill
- [LaunchDarkly Guarded Rollout](../launchdarkly-guarded-rollout/): Drive a bespoke rollout by hand
- [LaunchDarkly Docs](https://docs.launchdarkly.com)

## License

Apache-2.0
