# LaunchDarkly Config Create Skill

An Agent Skill for creating configs in LaunchDarkly. Guides choosing agent vs completion mode, creating the config and variations, and verifying the result.

## Overview

This skill teaches agents how to:
- Understand the use case and choose agent vs completion mode
- Create configs using MCP tools (`create-agent-config` with `resource: "config"` and a first variation for one-step, or a config alone followed by `resource: "variation"` for more control)
- Set up model configuration with the correct `modelConfigKey` format
- Verify creation via the tool response or `get-agent-configs`

## Installation (Local)

Copy `skills/agentcontrol/configs-create/` into your agent client's skills path.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

## Usage

```
Create a config for our customer support agent
```

```
Set up a config for content generation using Claude
```

## Structure

```
launchdarkly-configs-create/
├── SKILL.md
└── README.md
```

## Related

- [config Tools](../launchdarkly-tools/): Add tools after creating config
- [config Variations](../launchdarkly-configs-variations/): Add more variations for experimentation
- [LaunchDarkly AgentControl Docs](https://docs.launchdarkly.com/home/ai-configs)

## License

Apache-2.0
