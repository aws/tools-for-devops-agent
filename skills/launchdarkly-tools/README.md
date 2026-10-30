# LaunchDarkly Config Tools Skill

An Agent Skill for creating tools (function calling) and attaching them to config variations. Guides identifying capabilities, creating tool schemas, and verifying attachment.

## Overview

This skill teaches agents how to:
- Identify what capabilities the agent needs
- Create tool definitions using the `create-ai-tool` MCP tool
- Attach tools to config variations via `update-ai-config-variation`
- Verify tools are properly connected via `get-ai-config`

## Installation (Local)

Copy `skills/agentcontrol/tools/` into your agent client's skills path.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

## Usage

```
Add a database search tool to our support agent config
```

```
Create tools for the content assistant to call our API
```

## Structure

```
launchdarkly-tools/
├── SKILL.md
└── README.md
```

## Related

- [config Create](../launchdarkly-configs-create/): Create the config before adding tools
- [config Variations](../launchdarkly-configs-variations/): Manage variations that tools attach to
- [LaunchDarkly AgentControl Docs](https://docs.launchdarkly.com/home/ai-configs)

## License

Apache-2.0
