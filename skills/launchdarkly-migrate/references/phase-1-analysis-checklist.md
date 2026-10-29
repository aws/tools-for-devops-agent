# Phase 1 Analysis Checklist

A read-only audit the skill runs in **Step 1** before touching any code. Do not write files, install packages, or create LaunchDarkly resources during this phase. Produce a structured summary and stop for user confirmation.

## What to scan

### 1. Dependency manifests (most reliable signal)

Check the top-level files for the target service:

| Language | Files |
|----------|-------|
| Python | `pyproject.toml`, `requirements.txt`, `setup.py`, `Pipfile`, `uv.lock` |
| TypeScript / JavaScript | `package.json`, `pnpm-lock.yaml`, `yarn.lock` |
| Go | `go.mod`, `go.sum` |
| Ruby | `Gemfile`, `Gemfile.lock` |
| .NET | `*.csproj`, `packages.config` |

Extract: language, package manager, and any LLM provider SDKs already installed.

### 2. Provider imports

Grep the source tree for provider SDK imports so you know which one the app actually uses (dependencies can be unused):

| Provider | Python grep | TypeScript/JS grep |
|----------|-------------|---------------------|
| OpenAI | `from openai`, `import openai` | `from 'openai'`, `require('openai')` |
| Anthropic | `from anthropic`, `import anthropic` | `from '@anthropic-ai/sdk'` |
| Bedrock | `import boto3`, `bedrock-runtime` | `@aws-sdk/client-bedrock-runtime` |
| Gemini | `from google import genai`, `google.generativeai` | `@google/generative-ai` |
| LangChain | `from langchain`, `langchain_openai`, `langchain_anthropic` | `langchain`, `@langchain/openai` |
| LangGraph | `from langgraph`, `from langchain.agents import create_agent`, `create_react_agent` (deprecated) | `@langchain/langgraph`, `createReactAgent` |
| CrewAI | `from crewai` | — |

### 3. Hardcoded model configs

Look for the three things that need to move into the config:

1. **Model name** — grep for string literals:
   - `"gpt-4o"`, `"gpt-4o-mini"`, `"gpt-4-turbo"`, `"o1"`, `"o1-mini"`
   - `"claude-opus-"`, `"claude-sonnet-"`, `"claude-haiku-"`, `"claude-3-"`
   - `"gemini-"`, `"mistral-"`, `"meta.llama"`, `"anthropic.claude-"`
2. **Parameters** — grep for keys: `temperature=`, `max_tokens=`, `maxTokens:`, `top_p=`, `topP:`, `top_k=`, `stop_sequences=`
3. **System prompts / instructions** — grep for:
   - `"role": "system"` (OpenAI/Anthropic completion)
   - `system="` or `system:` (Anthropic top-level system)
   - `instructions="` (agent frameworks, CrewAI, LangGraph Python `create_agent(system_prompt=)` or legacy `create_react_agent(prompt=)`, LangGraph.js `createReactAgent({ prompt })`)
   - Long triple-quoted strings above provider calls

For each hit, record the file path, line number, and current value.

### 4. External prompt files & registries

Prompts often live outside `.py` / `.ts` source. **Open every plausible config file and read it before declaring the audit complete** — code-only grep will miss prompts loaded from YAML, prompt-template registries, or framework-specific manifests, and the resulting config will not cover the real prompt surface area.

**File-extension scan targets** (run from repo root):

- `**/*.yaml`, `**/*.yml`
- `**/*.json` (exclude `package.json`, `package-lock.json`, `tsconfig.json`, `*.lock`)
- `**/*.toml` (exclude `pyproject.toml` already covered in §1)
- `**/*.md` under `prompts/`, `templates/`, `agents/`, `personas/`
- `**/*.prompt`, `**/*.prompty`, `**/*.j2`, `**/*.jinja`, `**/*.tmpl`

**Content signals to grep inside those files**:

- Keys named `system`, `system_prompt`, `instructions`, `prompt`, `template`, `role`, `goal`, `backstory`, `persona`, `messages`
- Mustache (`{{ }}`) or Jinja (`{% %}`) blocks suggesting a prompt template
- Long multi-line string values (>200 chars) under any of those keys

**Framework-specific shapes to call out by name**:

| Framework | Where prompts live |
|-----------|---------------------|
| **CrewAI** | `agents.yaml` and `tasks.yaml` carry `role` / `goal` / `backstory` / `description` / `expected_output` per agent or task |
| **LangChain** | `.prompt` files (Promptfile format); any `langchain.hub.pull("name/key")` call — pulled prompts are remote and must either be inlined into the config or replaced with a `messages` array sourced from the hub at audit time |
| **LangSmith** | `client.pull_prompt(...)` calls referencing a remote prompt repo |
| **Pydantic / Settings** | classes with `prompt_*` fields backed by env vars or YAML overlays (Hydra / OmegaConf / Dynaconf) |
| **Helm / k8s ConfigMap** | prompts stored as values overrides — search `values*.yaml` and `templates/*configmap*.yaml` |

**For each hit, record**: file path, line range, the key holding the prompt, the loader call site that reads it, and any template placeholder syntax (Mustache vs Jinja vs Python `.format()`). The placeholder rewrite in Stage 2 sub-step 5 needs to know the source syntax to convert it to Mustache.

If a fallback file is already in use (see [fallback-defaults-pattern.md](fallback-defaults-pattern.md) — JSON/YAML loaded at startup), distinguish it from prompts that flow into the provider call. The fallback path is intentional infrastructure; only the latter migrates into the config.

### 5. Template placeholders in prompts

Anything the app currently interpolates into a prompt at runtime must be rewritten to Mustache `{{ variable }}` syntax in Stage 2 so the fallback path renders identically to the LD-served path. Grep for:

| Shape | Example | Grep |
|-------|---------|------|
| Python `.format()` | `PROMPT.format(system_time=now)` | `\.format(` on lines near prompt constants |
| Python f-string in a prompt constant | `f"You are... {system_time}."` | `f"` at the start of prompt literals |
| Python printf-style | `"%(topic)s"` / `"%s"` with `%` substitution | `%(` in prompt strings |
| JS/TS template literals in prompt strings | `` `You are... ${var}.` `` | backtick-wrapped prompt constants |
| Hand-rolled `str.replace` | `PROMPT.replace("__VAR__", value)` | `\.replace(` on prompt strings |

Record placeholder name + where the runtime value comes from (env var, function arg, `datetime.now()`, etc.). These get routed through `variables={...}` on `completion_config` / `agent_config` calls in Stage 2, and the literal prompt string gets rewritten to `{{ placeholder }}`. Leaving a non-Mustache placeholder in the fallback is a silent regression mode: LaunchDarkly-served prompts interpolate correctly, the fallback ships unrendered.

### 6. Hardcoded app-scoped knobs

Configuration that governs *tool* or *app* behavior rather than *model* behavior — easy to miss in an audit because it looks like ordinary application config. Common shapes:

- `Context` / `Settings` dataclass fields referenced by tools (`max_search_results`, `chunk_size`, `retry_budget`, `timeout_ms`, `enable_reranking`)
- Environment variables read inside tool implementations
- Constants declared in `tools.py` or a config module that a tool reads at call time

If a value changes agent behavior between variations — it belongs in the config. Stage 2 sub-step 5 (fallback) puts these in `ModelConfig(custom={...})`, **not** `parameters` (which is forwarded to the provider SDK and will crash on unknown kwargs). Tools read them via `ai_config.model.get_custom("key")`.

### 7. Existing LaunchDarkly SDK usage

If `LDClient` / `ldclient` is already initialized in the codebase, **reuse it** — do not create a second base client in Stage 2. Grep for:

- Python: `import ldclient`, `ldclient.set_config`, `ldclient.get()`
- TypeScript/JS: `@launchdarkly/node-server-sdk`, `init(LD_SDK_KEY)`, `@launchdarkly/react-client-sdk`
- Environment variables: `LD_SDK_KEY`, `LAUNCHDARKLY_SDK_KEY`, `LAUNCHDARKLY_API_KEY`

### 8. Mode decision: completion or agent

Walk the decision tree once per call site, using the call shape as the primary signal:

| Call shape | Mode |
|------------|------|
| Direct provider call with `messages=[...]` (OpenAI, Anthropic, Bedrock Converse) | **completion** |
| `create_agent(llm, tools, system_prompt=...)` (Python, `langchain.agents`) or `create_react_agent(llm, tools, prompt=...)` (Python, deprecated) | **agent** |
| `createReactAgent({ llm, tools, prompt })` (Node, `@langchain/langgraph/prebuilt`) | **agent** |
| CrewAI `Agent(role=..., goal=..., backstory=...)` | **agent** |
| Custom react loop: LLM-call → tool-call → LLM-call | **agent** |

**Default to completion mode** when unclear — it is more flexible and is the only mode that supports judges attached via the LaunchDarkly UI (Stage 5).

### 9. Monorepo / multi-service scope

If the repo contains multiple services, **ask the user which service to instrument**. Do not migrate every service in one pass.

## SDK routing table

Feeds into Stage 2 (install + wrap). Quoted from the `ai-configs-relaunch-guides/AGENT-SETUP-PROMPT.md` SDK routing table.

| Language | Base SDK | AI SDK | Docs |
|----------|----------|--------|------|
| Node.js / TypeScript | `@launchdarkly/node-server-sdk` | `@launchdarkly/server-sdk-ai` | https://docs.launchdarkly.com/sdk/ai/node-js |
| Python | `launchdarkly-server-sdk` | `launchdarkly-server-sdk-ai` | https://docs.launchdarkly.com/sdk/ai/python |
| Go | `github.com/launchdarkly/go-server-sdk/v7` | `github.com/launchdarkly/go-server-sdk-ai` | https://docs.launchdarkly.com/sdk/ai/go |
| Ruby | `launchdarkly-server-sdk` | `launchdarkly-server-sdk-ai` | https://docs.launchdarkly.com/sdk/ai/ruby |
| .NET | `LaunchDarkly.ServerSdk` | `LaunchDarkly.ServerSdk.Ai` | https://docs.launchdarkly.com/sdk/ai/dotnet |

**Node.js provider-specific helper packages** (optional, for auto-tracking in Stage 4):

| Provider | Package | Helper |
|----------|---------|--------|
| OpenAI | `@launchdarkly/server-sdk-ai-openai` | `getAIMetricsFromResponse` + `trackMetricsOf` |
| LangChain / LangGraph | `@launchdarkly/server-sdk-ai-langchain` | `createLangChainModel(config)` (forwards all variation parameters and handles provider-name mapping) + `getAIMetricsFromResponse` with `trackMetricsOf` |
| Vercel AI SDK | `@launchdarkly/server-sdk-ai-vercel` | `getAIMetricsFromResponse` + `trackMetricsOf`, or `VercelRunnerFactory.createVercelModel(aiConfig)` for a managed runner |

Python currently ships helper packages for OpenAI (`ldai_openai`) and LangChain (`ldai_langchain`). The LangChain Python package exposes `create_langchain_model(config)` (builds a LangChain chat model from the config, forwarding every variation parameter and mapping LD provider names to LangChain equivalents), `convert_messages_to_langchain`, and `get_ai_metrics_from_response` — the same package covers LangGraph. Use `create_langchain_model(config)` + `track_metrics_of_async(get_ai_metrics_from_response, lambda: llm.ainvoke(messages))` as the canonical single-call pattern. See [langchain-tracking.md](../../launchdarkly-built-in-metrics/references/langchain-tracking.md) for both LangChain and LangGraph patterns and [sdk-ai-tracker-patterns.md](sdk-ai-tracker-patterns.md) for the full tracker-method matrix.

## Phase 1 output format

Return this shape to the user, then **stop and wait for confirmation**:

```
Service:             <service name / path>
Language:            <Python 3.12 / Node.js 20 / Go 1.22 / ...>
Package manager:     <uv / poetry / pnpm / go mod / ...>
LLM provider:        <OpenAI / Anthropic / Bedrock / LangChain + OpenAI / ...>
Existing LD SDK:     <none / launchdarkly-server-sdk already initialized at src/ld.py:12>
Target mode:         <completion / agent>

Hardcoded migration targets:
  - <file>:<line>   model="gpt-4o"
  - <file>:<line>   temperature=0.7, max_tokens=2000
  - <file>:<line>   system="You are... {system_time}"  (27 lines, Python .format placeholder)

Externalized prompt files:   <none / 3 files: prompts/agents.yaml (CrewAI), prompts/system.md, config/prompts.json>
Prompt-template registries:  <none / langchain.hub.pull("rlm/rag-prompt") at app.py:14>
Template placeholders:       [{system_time} (Python .format, source=datetime.now().isoformat())]
App-scoped knobs:            [Context.max_search_results=10 (tools.py:24, reads from runtime.context)]
Tools detected:              <none / ['search', 'calculator'] at file.py:LN>
Retry wrapper:               <none / @retry(3) at file.py:LN>
Scope:                       <single service / monorepo: picked "service-x">

Coverage totals:             N hardcoded code targets · M externalized prompt files · K registry pulls

Proposed plan:
  Stage 1 (Audit):    Read-only manifest of hardcoded targets; flag placeholders for Mustache rewrite and knobs for model.custom
  Stage 2 (Wrap):     Install SDK, create config 'chat-assistant', inline fallback mirrors current values (Mustache syntax), rewrite the call site
  Stage 3 (Tools):    Skipped (no function calling) / Attach 2 tools via tools
  Stage 4 (Tracking): Inline tracker wiring (track_duration + track_tokens + track_success/error) — run-scoped tracker for agent loops
  Stage 5 (Evals):    Attach built-in 'accuracy' judge at 0.25 sampling via launchdarkly-online-evals
```

## STOP

Do not proceed to Stage 2 until the user confirms all of:

1. The service boundary is right
2. The hardcoded targets list is complete
3. The mode choice matches their intent
4. The stage plan is acceptable (e.g. skip tools? skip evals for now?)
5. **Coverage check.** State the totals out loud: "I scanned the repo and found **N** hardcoded code targets, **M** externalized prompt files, and **K** registry pulls. If you expected more (e.g. you know there's a `prompts/` directory, a CrewAI `agents.yaml`, or a config service I didn't reach), tell me where to look before we proceed." A number the user can react to surfaces under-detection that a yes/no on a list cannot.

**Reply with one of:**

- **`confirm`** — the audit looks complete; proceed to Stage 2.
- **`add: <files or paths>`** — I missed something; here's where to look. (Re-run the audit with the new locations and present an updated summary.)
- **`fix: <correction>`** — a target in the list is wrong (provider, mode, prompt content, etc.). (Update the summary and ask again.)
- **`stop`** — pause the migration here.

Do not interpret any other word — including `skip`, `next`, `go`, `ok`, `proceed` — as confirmation. If the reply doesn't match one of the four forms above, ask the user to pick one. Do not proceed under ambiguity.
