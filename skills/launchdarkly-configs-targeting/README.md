# LaunchDarkly Config Targeting Skill

An Agent Skill for configuring config targeting rules through the LaunchDarkly MCP server.

## Overview

This skill teaches agents how to:
- Set fallthrough (default) variations
- Split default traffic by percentage for A/B testing
- Add attribute-based targeting rules
- Target individual contexts or segments
- Roll a config back to an earlier variation

## Installation (Local)

Copy `skills/agentcontrol/configs-targeting/` into your agent client's skills path.

## Prerequisites

- The LaunchDarkly MCP server, connected as a member who can change config targeting
- Existing config with variations (use `launchdarkly-configs-create` skill)

## Usage

```
Set up targeting rules for model-selector: route sonnet requests to the Sonnet variation, mistral to Mistral, and default to Opus
```

```
Add a percentage rollout: 60% to variation A, 40% to variation B for premium users
```

## Structure

```
launchdarkly-configs-targeting/
├── SKILL.md
└── README.md
```

## Related

- [config Create](../launchdarkly-configs-create/) - Create configs first
- [config Variations](../launchdarkly-configs-variations/) - Create variations to target
- [config Online Evals](../launchdarkly-online-evals/) - Attach judges
- [Targeting Docs](https://docs.launchdarkly.com/home/ai-configs/target)

## License

Apache-2.0
