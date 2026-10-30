# LaunchDarkly Config Online Evaluations Skill

An Agent Skill for attaching judges to config variations for automatic LLM-as-a-judge evaluation.

## Overview

This skill teaches agents how to:
- Create custom judge configs with evaluation criteria
- Attach judges to config variations via API
- Configure sampling rates for cost control
- Monitor evaluation results in the dashboard

## Installation (Local)

Copy `skills/agentcontrol/online-evals/` into your agent client's skills path.

## Prerequisites

- LaunchDarkly API access token with `ai-configs:write` permission
- Existing config with variations (use `launchdarkly-configs-create` skill)
- For custom judges: understanding of LLM-as-a-judge methodology

## Usage

```
Attach security and API contract judges to the model-selector config at 100% sampling
```

```
Create a custom judge that checks for scope creep in code changes
```

## Structure

```
launchdarkly-online-evals/
├── SKILL.md
└── README.md
```

## Related

- [config Create](../launchdarkly-configs-create/) - Create configs first
- [config Targeting](../launchdarkly-configs-targeting/) - Enable targeting on judges
- [config Variations](../launchdarkly-configs-variations/) - Manage variations
- [Online Evaluations Docs](https://docs.launchdarkly.com/home/ai-configs/online-evaluations)

## License

Apache-2.0
