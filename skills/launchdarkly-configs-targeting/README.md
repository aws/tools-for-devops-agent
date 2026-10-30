# LaunchDarkly Config Targeting Skill

An Agent Skill for configuring config targeting rules via the LaunchDarkly API.

## Overview

This skill teaches agents how to:
- Turn targeting on/off for configs
- Add attribute-based targeting rules
- Configure percentage rollouts for A/B testing
- Set fallthrough (default) variations
- Target individual contexts or segments

## Installation (Local)

Copy `skills/agentcontrol/configs-targeting/` into your agent client's skills path.

## Prerequisites

- LaunchDarkly API access token with `ai-configs:write` permission
- Existing config with variations (use `launchdarkly-configs-create` skill)
- Understanding of contexts (see `context-basic` skill)

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
