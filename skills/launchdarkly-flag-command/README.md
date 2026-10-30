# LaunchDarkly Flag Command Skill

An Agent Skill for handling quick `/flag` lookups with fast resolution, disambiguation, and actionable summaries.

## Overview

This skill teaches agents how to:
- Parse `/flag` style user requests
- Resolve flag keys from fuzzy queries
- Disambiguate between similar flags safely
- Return concise flag detail summaries
- Route users into deeper create/targeting/cleanup workflows when needed

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

Examples:

- **Generic**: copy `skills/feature-flags/launchdarkly-flag-command/` into your client's skills path

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment. The remote server provides higher-level, agent-optimized tools that orchestrate multiple API calls and return pruned, actionable responses.

Refer to your LaunchDarkly account settings for instructions on connecting to the remotely hosted MCP server.

## Usage

Once installed, the skill activates automatically when you ask for quick flag lookups:

```
/flag dark mode
```

```
find flag checkout
```

```
show me the new-checkout flag in staging
```

## Structure

```
launchdarkly-flag-command/
├── SKILL.md
├── marketplace.json
└── README.md
```

## Related

- [LaunchDarkly Flag Discovery](../launchdarkly-flag-discovery/) — Audit and assess flag health
- [LaunchDarkly Flag Targeting](../launchdarkly-flag-targeting/) — Change rollouts and targeting
- [LaunchDarkly Flag Cleanup](../launchdarkly-flag-cleanup/) — Remove stale flags safely
- [LaunchDarkly MCP Server](https://github.com/launchdarkly/mcp-server)
- [LaunchDarkly Docs](https://docs.launchdarkly.com)

## License

Apache-2.0
