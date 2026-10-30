# LaunchDarkly Flag Targeting Skill

An Agent Skill for controlling feature flag targeting, rollouts, and rules in LaunchDarkly.

## Overview

This skill teaches agents how to:
- Understand current flag targeting state before making changes
- Toggle flags on/off safely
- Set up percentage rollouts
- Add and manage targeting rules
- Manage individual user/context targets
- Copy targeting config between environments
- Follow safety practices for production changes

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

Examples:

- **Generic**: copy `skills/feature-flags/launchdarkly-flag-targeting/` into your client's skills path

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment. The remote server provides higher-level, agent-optimized tools that orchestrate multiple API calls and return pruned, actionable responses.

Refer to your LaunchDarkly account settings for instructions on connecting to the remotely hosted MCP server.

## Usage

Once installed, the skill activates automatically when you ask about flag targeting:

```
Turn on the new-checkout flag in staging
```

```
Roll out dark-mode to 25% of users in production
```

```
Target beta users for the new-pricing feature
```

```
Copy the staging config for checkout-v2 to production
```

## Structure

```
launchdarkly-flag-targeting/
├── SKILL.md
├── marketplace.json
├── README.md
└── references/
    ├── targeting-patterns.md
    └── safety-checklist.md
```

## Related

- [LaunchDarkly Flag Create](../launchdarkly-flag-create/): Create flags before targeting them
- [LaunchDarkly Flag Discovery](../launchdarkly-flag-discovery/): Audit flags and understand the landscape
- [LaunchDarkly MCP Server](https://github.com/launchdarkly/mcp-server)
- [LaunchDarkly Docs](https://docs.launchdarkly.com)

## License

Apache-2.0
