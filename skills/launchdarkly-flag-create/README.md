# LaunchDarkly Flag Create Skill

An Agent Skill for introducing new feature flags into a codebase, matching existing patterns and conventions.

## Overview

This skill teaches agents how to:
- Explore a codebase to understand existing flag patterns and SDK usage
- Choose the right flag type and configuration
- Create the flag in LaunchDarkly
- Add flag evaluation code that matches codebase conventions
- Verify the flag is wired up correctly

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

Examples:

- **Generic**: copy `skills/feature-flags/launchdarkly-flag-create/` into your client's skills path

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment. The remote server provides higher-level, agent-optimized tools that orchestrate multiple API calls and return pruned, actionable responses.

## Usage

Once installed, the skill activates automatically when you ask about creating flags:

```
Create a feature flag for the new checkout flow
```

```
Wrap the dark mode feature in a LaunchDarkly flag
```

```
Add a feature toggle for the new pricing page
```

## Structure

```
launchdarkly-flag-create/
├── SKILL.md
├── marketplace.json
├── README.md
└── references/
    ├── flag-types.md
    └── sdk-evaluation-patterns.md
```

## Related

- [LaunchDarkly Flag Targeting](../launchdarkly-flag-targeting/): Control targeting after creating a flag
- [LaunchDarkly Flag Cleanup](../launchdarkly-flag-cleanup/): Remove flags when they're no longer needed
- [LaunchDarkly MCP Server](https://github.com/launchdarkly/mcp-server)
- [LaunchDarkly Docs](https://docs.launchdarkly.com)

## License

Apache-2.0
