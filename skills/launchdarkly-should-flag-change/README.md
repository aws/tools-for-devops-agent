# Should Flag Change Skill

An advisory, read-only Agent Skill that decides whether a given code change should be released behind a LaunchDarkly feature flag.

## Overview

This skill teaches agents how to:
- Read a git diff (or in-progress change) and understand what it actually does
- Explore the surrounding code to judge blast radius and behavior impact
- Weigh the change against a decision framework (favoring flags for user-facing and risky changes)
- Emit a single structured verdict via the `recommend-flag` tool

It is **advisory and read-only**: it never creates, toggles, or modifies flags.

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

- **Generic**: copy `skills/feature-flags/should-flag-change/` into your client's skills path

## Prerequisites

None. This skill does not require the LaunchDarkly MCP server. It reads code with standard file tools and returns a structured recommendation via the `recommend-flag` tool.

## Usage

Ad hoc, while working on a change:

```
Should this change be behind a feature flag?
```

In CI on a pull request, the skill is fed the PR's git diff and reads the repository to assess it, then emits a `recommend-flag` verdict (`{ recommend, verdict, confidence, reasons }`) that a check can parse.

## Output

The skill ends by calling the `recommend-flag` tool:

```json
{
  "recommend": true,
  "verdict": "suggested",
  "confidence": "medium",
  "reasons": [
    "New public endpoint added in src/routes/export.ts — user-facing path with no existing gate"
  ]
}
```

`recommend` is the boolean a CI check keys on. `verdict` is the finer signal: `suggested` (a new flag is warranted), `reuse-existing` (gate the change behind an existing flag that already covers this feature — set `reuse_flag_key`, don't create a new one), `already-flagged` (protected by an existing / ancestor flag — covered, no action), or `not-suited` (genuinely nothing to flag). Keeping these outcomes distinct is what lets a dashboard track real flag coverage.

## Structure

```
launchdarkly-should-flag-change/
├── SKILL.md
├── marketplace.json
└── README.md
```

## Related

- [LaunchDarkly Flag Create](../launchdarkly-flag-create/): Create the flag once you've decided to
- [LaunchDarkly Flag Cleanup](../launchdarkly-flag-cleanup/): Remove flags when they're no longer needed
- [LaunchDarkly Docs](https://docs.launchdarkly.com)

## License

Apache-2.0
