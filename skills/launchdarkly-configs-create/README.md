# LaunchDarkly Config Create Skill

An Agent Skill for creating configs in LaunchDarkly. Guides choosing agent vs completion mode, creating the config and variations, and verifying the result.

## Overview

This skill teaches agents how to:
- Understand the use case and choose agent vs completion mode
- Create configs using MCP tools (`setup-ai-config` for one-step, or `create-ai-config` + `create-ai-config-variation` for more control)
- Set up model configuration with the correct `modelConfigKey` format
- Verify creation via the tool response or `get-ai-config`

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

- [config Projects](../launchdarkly-projects/): Create projects first
- [config Tools](../launchdarkly-tools/): Add tools after creating config
- [config Variations](../launchdarkly-configs-variations/): Add more variations for experimentation
- [LaunchDarkly AgentControl Docs](https://docs.launchdarkly.com/home/ai-configs)

## License

Apache-2.0
