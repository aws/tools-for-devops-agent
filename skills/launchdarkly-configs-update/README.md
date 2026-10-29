# LaunchDarkly Config Update Skill

An Agent Skill for updating, archiving, and deleting configs and their variations.

## Overview

This skill teaches agents how to:
- Assess config health using `get-ai-config-health` before making changes
- Update config metadata (name, description, tags) via `update-ai-config`
- Modify variation instructions, messages, models, and parameters via `update-ai-config-variation`
- Archive configs (reversible) or delete them (permanent, irreversible)
- Verify changes via `get-ai-config`

## Installation (Local)

Copy `skills/agentcontrol/configs-update/` into your agent client's skills path.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

## Usage

```
Update the instructions for our support agent config
```

```
Switch the content writer config to use Claude instead of GPT-4
```

```
Archive the old chatbot config
```

## Structure

```
launchdarkly-configs-update/
├── SKILL.md
└── README.md
```

## Related

- [config Create](../launchdarkly-configs-create/): Create configs
- [config Variations](../launchdarkly-configs-variations/): Add or test variations
- [LaunchDarkly AgentControl Docs](https://docs.launchdarkly.com/home/ai-configs)

## License

Apache-2.0
