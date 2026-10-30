# Fallback Defaults Pattern

Every `completion_config` / `agent_config` call takes a fallback. The fallback runs when LaunchDarkly is unreachable, the SDK is disabled, or the returned config has `enabled=False`. **It must mirror the hardcoded values you removed** so behavior is unchanged if LaunchDarkly is unavailable.

This doc covers three patterns in order of sophistication. Pick the one that matches the size of the app and the number of configs it uses.

## Pattern 1: Inline fallback (start here)

One config key, one fallback constant. Best for apps with a handful of configs or a single call site.

### Python — completion mode

```python
from ldai.client import (
    AICompletionConfigDefault,
    ModelConfig,
    ProviderConfig,
    LDMessage,
)

CHAT_FALLBACK = AICompletionConfigDefault(
    enabled=True,
    model=ModelConfig(
        name="gpt-4o",
        parameters={"temperature": 0.7, "max_tokens": 2000},
    ),
    provider=ProviderConfig(name="openai"),
    messages=[
        LDMessage(role="system", content="You are a helpful assistant. Answer concisely."),
    ],
)

# Later in the request handler:
config = ai_client.completion_config("chat-assistant", context, CHAT_FALLBACK)
```

### Python — agent mode

```python
from ldai.client import (
    AIAgentConfigDefault,
    ModelConfig,
    ProviderConfig,
)

SUPPORT_AGENT_FALLBACK = AIAgentConfigDefault(
    enabled=True,
    model=ModelConfig(
        name="gpt-4o",
        parameters={"temperature": 0.3},
    ),
    provider=ProviderConfig(name="openai"),
    instructions=(
        "You are a technical support assistant. Use the search_kb tool to look up "
        "documentation, and the calculator tool for math. Always cite sources."
    ),
)

# Later in the request handler:
config = ai_client.agent_config("support-agent", context, SUPPORT_AGENT_FALLBACK)
```

### Node — completion mode

```typescript
import { LDAICompletionConfigDefault } from '@launchdarkly/server-sdk-ai';

const CHAT_FALLBACK: LDAICompletionConfigDefault = {
  enabled: true,
  model: {
    name: 'gpt-4o',
    parameters: { temperature: 0.7, max_tokens: 2000 },
  },
  provider: { name: 'openai' },
  messages: [
    { role: 'system', content: 'You are a helpful assistant. Answer concisely.' },
  ],
};

const aiConfig = await aiClient.completionConfig('chat-assistant', context, CHAT_FALLBACK);
```

### Node — agent mode

```typescript
import { LDAIAgentConfigDefault } from '@launchdarkly/server-sdk-ai';

const SUPPORT_AGENT_FALLBACK: LDAIAgentConfigDefault = {
  enabled: true,
  model: {
    name: 'gpt-4o',
    parameters: { temperature: 0.3 },
  },
  provider: { name: 'openai' },
  instructions:
    'You are a technical support assistant. Use the search_kb tool to look up documentation, and the calculator tool for math. Always cite sources.',
};

const agent = await aiClient.agentConfig('support-agent', context, SUPPORT_AGENT_FALLBACK);
```

### When to use inline

- Fewer than ~5 configs in the app
- Fallback values don't change often (or change in lockstep with code deploys)
- You want every fallback visible in a single source file for easy review

## Pattern 2: File-backed defaults

A JSON/YAML file holds every config's fallback; a loader at startup builds the default objects. Best for apps with many configs or where the fallback needs to be environment-specific.

### File shape

```json
{
  "_metadata": {
    "environment": "production",
    "generated_at": "2026-04-14"
  },
  "configs": {
    "chat-assistant": {
      "mode": "completion",
      "enabled": true,
      "model": {
        "name": "gpt-4o",
        "parameters": { "temperature": 0.7, "max_tokens": 2000 }
      },
      "provider": { "name": "openai" },
      "messages": [
        { "role": "system", "content": "You are a helpful assistant. Answer concisely." }
      ]
    },
    "support-agent": {
      "mode": "agent",
      "enabled": true,
      "model": {
        "name": "gpt-4o",
        "parameters": { "temperature": 0.3 }
      },
      "provider": { "name": "openai" },
      "instructions": "You are a technical support assistant. Use the search_kb tool..."
    }
  }
}
```

### Python loader

Adapted from `devrel-agents-tutorial/config_manager.py`:

```python
import json
from pathlib import Path
from ldai.client import (
    AICompletionConfigDefault,
    AIAgentConfigDefault,
    ModelConfig,
    ProviderConfig,
    LDMessage,
)


class FallbackLoader:
    def __init__(self, path: str = ".ai_config_defaults.json"):
        data = json.loads(Path(path).read_text())
        self.configs = data.get("configs", {})

    def get(self, config_key: str):
        if config_key not in self.configs:
            raise ValueError(
                f"Fallback for '{config_key}' not found in defaults file. "
                f"Available: {list(self.configs.keys())}"
            )
        entry = self.configs[config_key]
        mode = entry.get("mode", "completion")

        common = dict(
            enabled=entry.get("enabled", True),
            model=ModelConfig(
                name=entry["model"]["name"],
                parameters=entry["model"].get("parameters", {}),
            ),
            provider=ProviderConfig(name=entry["provider"]["name"]),
        )

        if mode == "agent":
            return AIAgentConfigDefault(
                **common,
                instructions=entry.get("instructions", ""),
            )
        else:
            return AICompletionConfigDefault(
                **common,
                messages=[LDMessage(**m) for m in entry.get("messages", [])],
            )


# Usage
fallbacks = FallbackLoader()
config = ai_client.completion_config(
    "chat-assistant",
    context,
    fallbacks.get("chat-assistant"),
)
```

### When to use file-backed

- 5+ configs, each with its own fallback
- Fallback values are derived from the current LaunchDarkly state (see Pattern 3 for generation)
- You want a single commit to update all fallbacks at once
- You want different default files per environment (dev vs staging vs prod)

## Pattern 3: Bootstrap-generated defaults

A script fetches the current state of every config from LaunchDarkly and writes the file used by Pattern 2. Best for large apps where keeping fallbacks in sync by hand is a maintenance burden.

The devrel-agents-tutorial has a `bootstrap/create_configs.py` script that does this end-to-end: it creates the configs in LaunchDarkly from a YAML manifest, then writes the `.ai_config_defaults.json` file that the app loads at startup. Use it as prior art — do not reproduce it inline.

### Sketch

```python
# bootstrap/generate_defaults.py
import json
from launchdarkly_api import ApiClient  # or use the MCP server tools

def dump_defaults(api_token: str, project_key: str, environment: str) -> dict:
    client = ApiClient(api_token)
    configs = client.list_ai_configs(project_key)

    out = {
        "_metadata": {"environment": environment, "generated_at": today()},
        "configs": {},
    }
    for cfg in configs:
        variation = pick_default_variation(cfg, environment)
        out["configs"][cfg.key] = {
            "mode": cfg.mode,
            "enabled": variation.enabled,
            "model": {"name": variation.model.name, "parameters": variation.model.parameters},
            "provider": {"name": variation.provider.name},
            "instructions": variation.instructions if cfg.mode == "agent" else None,
            "messages": variation.messages if cfg.mode == "completion" else None,
        }

    return out
```

### Hooks

- Run the script in CI on every merge to main, commit the updated file
- Or run it on deploy to bake the file into the container image
- Or run it manually when you know a config has changed meaningfully

### When to use bootstrap-generated

- 20+ configs
- You want fallbacks to track production state automatically
- You have CI capacity to run the generator and commit the file

### Trade-off

Fallback drift is a feature, not a bug. If you regenerate on every deploy, a stale fallback (one that missed a recent production change) only shows up when LaunchDarkly is unreachable — an already-degraded path. If you would rather the fallback be *exactly* the last-shipped production value, regenerate on deploy. If you would rather the fallback be *exactly* the original hardcoded value, use Pattern 1 or commit the file once and never regenerate.

## Template placeholders: Mustache in the fallback, not Python `.format()`

If the instructions or system message in the fallback contains a runtime-interpolated variable, it **must** be in Mustache `{{ variable }}` form — the same form the LaunchDarkly UI stores — and the interpolation must go through the SDK's `variables` argument, not `str.format()` or template-literal substitution.

**Wrong** (silent regression when LaunchDarkly is unreachable):

```python
SYSTEM_PROMPT = "You are a helpful assistant. The time is {system_time}."

FALLBACK = AIAgentConfigDefault(
    enabled=True,
    model=ModelConfig(name="gpt-4o"),
    provider=ProviderConfig(name="openai"),
    instructions=SYSTEM_PROMPT.format(system_time=datetime.now().isoformat()),
    # ^^^^^^^^^^^^^^^^^^^^^^^ This resolves `{system_time}` at import time, so the fallback
    # always ships a stale value. When LaunchDarkly serves the variation it's resolved
    # correctly via Mustache; when the fallback runs it isn't — behavior diverges.
)
```

**Right**:

```python
SYSTEM_PROMPT = "You are a helpful assistant. The time is {{ system_time }}."

FALLBACK = AIAgentConfigDefault(
    enabled=True,
    model=ModelConfig(name="gpt-4o"),
    provider=ProviderConfig(name="openai"),
    instructions=SYSTEM_PROMPT,   # Mustache literal; interpolation happens per-request
)

# Per-request — LD-served and fallback both interpolate through the 4th argument
config = ai_client.agent_config(
    AGENT_CONFIG_KEY,
    context,
    FALLBACK,
    variables={"system_time": datetime.now().isoformat()},
)
```

The SDK runs both paths through the same Mustache renderer. Leaving a Python-style `{var}` literal in the fallback ships a silent regression: LaunchDarkly serves correctly-interpolated output; the fallback ships the unrendered literal, or (worse) a value frozen at import time.

Same rule applies to JS template literals and any other non-Mustache scheme — rewrite to `{{ variable }}` before handing off to `/launchdarkly-configs-create`.

## Critical rules (apply to all three patterns)

1. **Fallback mirrors pre-migration behavior.** If the hardcoded model was `gpt-4o`, the fallback model is `gpt-4o`. If the hardcoded temperature was `0.7`, the fallback temperature is `0.7`. The fallback is the contract that says "app behavior doesn't change if LaunchDarkly is unreachable."
2. **Always set `enabled=True` in the fallback.** If the fallback has `enabled=False`, the disabled path runs every time LaunchDarkly is unreachable — an outage escalates into a full service outage. Make the fallback a real, working config unless the feature is explicitly off-by-default.
3. **Fallback is optional — but if you pass one, specify it fully.** Omitting the fallback argument is valid; the SDK returns a disabled config when LaunchDarkly is unreachable, and your `if not config.enabled:` branch handles the disabled path. Pass a fallback when you want the app to keep serving traffic on LaunchDarkly unreachable — in that case it must be a fully-specified `AICompletionConfigDefault` / `AIAgentConfigDefault` with `model`, `provider`, and `messages`/`instructions`. Do not pass `AICompletionConfigDefault(enabled=False)` as a "placeholder" — it collapses into the disabled path and gives you nothing the omitted-fallback case wouldn't.
4. **Do not delete the fallback after migration.** It is required for the `enabled=False` path and for SDK-unreachable scenarios. Treat it as load-bearing production code, not scaffolding.
5. **Keep fallback type imports stable.** `AICompletionConfigDefault` is for completion mode; `AIAgentConfigDefault` is for agent mode. Using the wrong one will fail at runtime when the SDK tries to coerce the fallback.
