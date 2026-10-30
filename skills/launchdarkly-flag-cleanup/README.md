# LaunchDarkly Flag Cleanup Skill

An Agent Skill for safely automating feature flag cleanup workflows using LaunchDarkly as the source of truth.

## Overview

This skill teaches agents how to:
- Determine if a feature flag is ready for removal
- Calculate the correct forward value to preserve production behavior
- Safely remove flag references from code
- Create well-documented pull requests

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

Examples:

- **Generic**: copy `skills/feature-flags/launchdarkly-flag-cleanup/` into your client's skills path

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment. The remote server provides higher-level, agent-optimized tools that orchestrate multiple API calls and return pruned, actionable responses.

Refer to your LaunchDarkly account settings for instructions on connecting to the remotely hosted MCP server.

## Usage

Once installed, the skill activates automatically when you ask about flag cleanup:

```
Remove the `new-checkout-flow` feature flag
```

```
Is the `dark-mode` flag ready to be cleaned up?
```

```
Clean up stale feature flags in this codebase
```

## Structure

```
launchdarkly-flag-cleanup/
├── SKILL.md
├── marketplace.json
├── README.md
└── references/
    ├── pr-template.md
    └── sdk-patterns.md
```

## Related

- [LaunchDarkly MCP Server](https://github.com/launchdarkly/mcp-server)
- [LaunchDarkly Docs](https://docs.launchdarkly.com)
- [Agent Skills Specification](https://agentskills.io/specification)

## License

Apache-2.0
