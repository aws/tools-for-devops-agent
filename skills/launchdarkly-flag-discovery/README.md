# LaunchDarkly Flag Discovery Skill

An Agent Skill for auditing and understanding your LaunchDarkly feature flag landscape.

## Overview

This skill teaches agents how to:
- Survey the full feature flag inventory in a project
- Identify stale, inactive, or fully-launched flags
- Assess whether specific flags are ready for removal
- Provide prioritized, actionable recommendations

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

Examples:

- **Generic**: copy `skills/feature-flags/launchdarkly-flag-discovery/` into your client's skills path

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment. The remote server provides higher-level, agent-optimized tools that orchestrate multiple API calls and return pruned, actionable responses.

Refer to your LaunchDarkly account settings for instructions on connecting to the remotely hosted MCP server.

## Usage

Once installed, the skill activates automatically when you ask about flag health or inventory:

```
What's the state of our feature flags?
```

```
Which flags are stale and should be cleaned up?
```

```
Is the `dark-mode` flag ready to be removed?
```

## Structure

```
launchdarkly-flag-discovery/
├── SKILL.md
├── marketplace.json
├── README.md
└── references/
    ├── flag-health-signals.md
    └── removal-readiness-checklist.md
```

## Related

- [LaunchDarkly Flag Cleanup](../launchdarkly-flag-cleanup/): Remove flags from code after discovery identifies candidates
- [LaunchDarkly MCP Server](https://github.com/launchdarkly/mcp-server)
- [LaunchDarkly Docs](https://docs.launchdarkly.com)

## License

Apache-2.0
