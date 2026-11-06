# LaunchDarkly Config Update Skill

An Agent Skill for updating, retiring, and deleting configs and their variations.

## Overview

This skill teaches agents how to:
- Assess config health using `get-agent-configs` with `section: "health"` before making changes
- Update config metadata (name, description, tags) via `update-agent-config` (`resource: "config"`)
- Modify variation instructions, messages, models, and parameters via `update-agent-config` (`resource: "variation"`)
- Retire configs by turning targeting off (reversible) or delete them (permanent, irreversible)
- Verify changes via `get-agent-configs`

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
Retire the old chatbot config
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
