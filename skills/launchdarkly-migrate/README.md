# LaunchDarkly Config Migrate Skill

An Agent Skill for migrating an application with hardcoded LLM prompts to a full LaunchDarkly AgentControl implementation in five stages: extract, wrap, tools, tracking, evals.

## Overview

This skill orchestrates the full migration journey from hardcoded `openai.chat.completions.create(model="gpt-4o", ...)` (or equivalent in any provider SDK) to a managed config with tools, tracking, and judges. It delegates each stage to a focused skill and covers the tracker wiring inline — since no existing skill owns `tracker.track_*` calls.

The five stages:

1. **Extract** hardcoded model names, prompts, and parameters (read-only)
2. **Wrap** the call site in `completion_config` / `completionConfig` with a safe fallback — delegates the config creation to `launchdarkly-configs-create`
3. **Tools** — move function-calling schemas into LaunchDarkly — delegates to `launchdarkly-tools`
4. **Tracking** — wire `track_duration`, `track_tokens`, `track_success`/`track_error`, optional `track_feedback` — inline, with a reference doc covering every SDK method in Python and Node side by side
5. **Evals** — attach judges for LLM-as-a-judge scoring — delegates to `launchdarkly-online-evals`

## Installation (Local)

Copy `skills/agentcontrol/migrate/` into your agent client's skills path.

## Prerequisites

- Remotely hosted LaunchDarkly MCP server
- `LD_SDK_KEY` environment variable (server-side SDK key, starts with `sdk-`)
- An application with hardcoded LLM calls (OpenAI, Anthropic, Bedrock, Gemini, LangChain, LangGraph, CrewAI, or Strands)

## Usage

```
Migrate our chat service from hardcoded OpenAI prompts to LaunchDarkly AgentControl
```

```
Our LangGraph agent has its model and instructions baked in — walk me through wrapping it in a config
```

```
Wire up the agent tracker and attach accuracy + relevance judges to our existing config
```

## Structure

```
launchdarkly-migrate/
├── SKILL.md
├── README.md
└── references/
    ├── phase-1-analysis-checklist.md
    ├── before-after-examples.md
    ├── sdk-ai-tracker-patterns.md
    ├── agent-mode-frameworks.md
    ├── fallback-defaults-pattern.md
    └── agent-graph-reference.md
```

## Related

- [config Create](../launchdarkly-configs-create/): Delegated to by Stage 2 (wrap)
- [config Tools](../launchdarkly-tools/): Delegated to by Stage 3 (tools)
- [config Online Evals](../launchdarkly-online-evals/): Delegated to by Stage 5 (evals)
- [config Variations](../launchdarkly-configs-variations/): Next step after migration for A/B testing
- [config Targeting](../launchdarkly-configs-targeting/): Next step after migration for rollout control
- [LaunchDarkly AgentControl Docs](https://docs.launchdarkly.com/home/ai-configs)

## License

Apache-2.0
