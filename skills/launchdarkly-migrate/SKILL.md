---
name: launchdarkly-migrate
description: "Migrate an application with hardcoded LLM prompts to a full LaunchDarkly AgentControl implementation in five stages: audit the code, wrap the call, move the tools, add tracking, attach evaluators. Use when the user wants to externalize model/prompt configuration, move from direct provider calls (OpenAI, Anthropic, Bedrock, Gemini, Strands) to a managed config, or stage a full hardcoded-to-LaunchDarkly migration."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "0.1.0"
---

# Migrate to AgentControl

You're using a skill that will guide you through migrating an application from hardcoded LLM prompts to a full LaunchDarkly AgentControl implementation. Your job is to run the migration in **five stages**, stopping at each stage for the user to confirm:

1. **Audit the code** — read-only scan that produces a structured list of everything hardcoded (prompt, model, parameters, tools, app-scoped knobs).
2. **Wrap the call** — install the SDK, create the config in LaunchDarkly with a fallback that mirrors the hardcoded values, and rewrite the call site to fetch the config fresh on every request.
3. **Move the tools** — extract each tool's JSON schema, attach it to the config, and swap every call site that references the old tool list.
4. **Add tracking** — wire the per-request tracker (duration, tokens, success/error) around the provider call.
5. **Attach evaluators** — either offline evals via the Playground + Datasets, or online judges that score sampled traffic automatically.

> **⚠️ Three first-run failure modes to avoid.**
>
> 1. **Tracker in the wrong scope.** For an agent with a loop, mint `create_tracker()` once per user turn in a `setup_run` entry node — not inside `call_model`. Per-iteration factory calls produce N `runId`s and trip the at-most-once guards. See [agent-mode-frameworks.md § Custom `StateGraph`](references/agent-mode-frameworks.md).
> 2. **`load_chat_model` wrapper reuse.** Templates like `langchain-ai/react-agent` ship a `load_chat_model(f"{provider}/{name}")` helper that wraps `init_chat_model(...)` and silently drops every variation parameter. **Delete it** (don't just avoid using it) and replace call sites with `create_langchain_model(ai_config)`.
> 3. **Fallthrough not flipped after `/launchdarkly-configs-create`.** A freshly-created config's fallthrough points at an auto-generated disabled variation, so the SDK returns `enabled=False` until `/launchdarkly-configs-targeting` runs. Flip it before Stage 2 verification.

## Coverage — which shapes are well-trodden vs require extrapolation

The skill is optimized for Python and Node.js / TypeScript; other languages are install-only. Within Python and Node the coverage tiers are:

| Shape | Python | Node.js | Reference |
|-------|--------|---------|-----------|
| One-shot completion (direct OpenAI / Anthropic / Bedrock / Gemini call) | ✅ Worked example | ✅ Worked example | [before-after-examples.md](references/before-after-examples.md), per-provider docs in `launchdarkly-built-in-metrics/references/` |
| Chat loop via managed runner (`ManagedModel`) | ✅ Tier 1 pattern | ✅ Tier 1 pattern | [launchdarkly-built-in-metrics SKILL.md](../launchdarkly-built-in-metrics/SKILL.md) |
| LangChain single-call | ✅ Worked example | ✅ Worked example | [langchain-tracking.md](../launchdarkly-built-in-metrics/references/langchain-tracking.md) |
| LangGraph prebuilt agent (Python `langchain.agents.create_agent`, Node `createReactAgent`) | ✅ Worked example | ✅ Worked example | [agent-mode-frameworks.md § LangGraph](references/agent-mode-frameworks.md) |
| LangGraph custom `StateGraph` with run-scoped tracker (setup_run + call_model + finalize) | ✅ Deep worked example | ⚠️ Mentioned — translate from Python | [agent-mode-frameworks.md § Custom `StateGraph`](references/agent-mode-frameworks.md) |
| CrewAI `Agent` | ✅ Worked example | — (not a Node framework) | [agent-mode-frameworks.md § CrewAI](references/agent-mode-frameworks.md) |
| Strands `Agent` | ✅ Worked example | ⚠️ BedrockModel + OpenAIModel only (no Anthropic) | [agent-mode-frameworks.md § Strands](references/agent-mode-frameworks.md) |
| Custom ReAct loop (hand-rolled, any framework or none) | ✅ Worked example | ⚠️ Apply framework-agnostic invariants; translate from Python | [agent-mode-frameworks.md § Custom ReAct loop](references/agent-mode-frameworks.md) |
| Vercel AI SDK (`generateText` / `streamText`) | — (not a Python framework) | ⚠️ Provider package exists; no worked example in skill | `launchdarkly-built-in-metrics` provider-package matrix |
| Streaming (SSE / WebSocket) | ⚠️ Delegated to `launchdarkly-built-in-metrics` streaming doc | ⚠️ Same — use `trackStreamMetricsOf` + manual TTFT | [streaming-tracking.md](../launchdarkly-built-in-metrics/references/streaming-tracking.md) |
| Multi-agent graph (supervisor + workers) | ⚠️ Out of main scope; see reference | ⚠️ Out of main scope; see reference | [agent-graph-reference.md](references/agent-graph-reference.md) |
| Non-LangGraph agent frameworks (Pydantic AI, DSPy, AutoGen, Haystack, LlamaIndex agents, Semantic Kernel) | ⚠️ Apply the three invariants; no framework-specific example | ⚠️ Same | [agent-mode-frameworks.md § Framework-agnostic invariants](references/agent-mode-frameworks.md) |
| Go, Ruby, .NET | ℹ️ Install commands only | ℹ️ Install commands only | [phase-1-analysis-checklist.md § SDK routing table](references/phase-1-analysis-checklist.md) |

**Reading the key:** ✅ = follow the skill verbatim; ⚠️ = the architecture applies but you'll translate idioms or cross-reference another skill; ℹ️ = skill doesn't go past the install step.

If the target app is in the ⚠️ column, start by reading [agent-mode-frameworks.md § Framework-agnostic invariants](references/agent-mode-frameworks.md) — those three rules (one `agent_config` per turn, one tracker per turn, at-most-once methods fire once at turn end) apply regardless of framework, and every code snippet in this skill is an instantiation of them. Translate the Python example's shape onto the target framework's primitives.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment, and an application that already calls an LLM provider with hardcoded model, prompt, and parameter values.

**Required environment:**
- `LD_SDK_KEY` — server-side SDK key (starts with `sdk-`) from the target LaunchDarkly project

**MCP tools used directly by this skill:** none — every LaunchDarkly write happens in a focused sibling skill.

**Check the SDK CHANGELOG before applying any pattern.** The API surface described throughout this skill targets the SDK behavior at the time of the skill's last update; SDK releases can rename, remove, or split methods after that. Before you start, fetch the latest CHANGELOG for the SDK(s) you'll target and skim for anything that contradicts the pattern you're about to apply:

- Python: https://github.com/launchdarkly/python-server-sdk-ai/blob/main/packages/sdk/server-ai/CHANGELOG.md (and per-provider CHANGELOGs under `packages/ai-providers/server-ai-{openai,langchain}/CHANGELOG.md`)
- Node: https://github.com/launchdarkly/js-core/blob/main/packages/sdk/server-ai/CHANGELOG.md (and per-provider CHANGELOGs under `packages/ai-providers/server-ai-{openai,langchain,vercel}/CHANGELOG.md`)

If a CHANGELOG entry post-dates this skill and changes an API you're about to use, the CHANGELOG wins — and the skill should be updated.

**Hand-off model.** This skill does **not** auto-invoke other skills. At each stage that needs a LaunchDarkly write, this skill prepares the inputs (config key, mode, model, prompt, tool schemas, judge keys) and then **tells the user to run the next slash-command themselves**. After the user finishes that sibling skill, return to the next step here. Treat the "Delegate" lines below as next-step instructions, not auto-handoffs.

**Sibling skills the user runs at each stage:**
- `launchdarkly-projects` — pre-Stage 2, only if no project exists yet
- `launchdarkly-configs-create` — Stage 2 (creates the config and first variation)
- `launchdarkly-tools` — Stage 3 (creates tool definitions and attaches them)
- `launchdarkly-configs-targeting` — between Stage 2 and Stage 4 (promotes the new variation to fallthrough so the SDK actually serves it)
- `launchdarkly-online-evals` — Stage 5 (attaches judges, creates custom judges)

## Core Principles

1. **Inspect before you mutate.** Every stage begins with a read-only audit. Do not touch code until Step 1 is confirmed by the user.
2. **Replace config, not business logic.** The SDK call is a drop-in for the place where the model, parameters, and prompt are *defined* — not for the provider call itself. OpenAI/Anthropic/Bedrock calls stay where they are.
3. **Fallback mirrors current behavior.** The fallback passed to `completion_config` / `agent_config` must preserve the hardcoded values you removed, so the app is unchanged if LaunchDarkly is unreachable.
4. **Stages are ordered.** Wrap before you add tools. Add tools before you track. Track before you add evals. Skipping ahead produces configs without traffic, metrics without context, and judges with nothing to score.
5. **Hand off to focused skills, manually.** Each stage that needs a LaunchDarkly write tells the user to run a sibling slash-command (`/launchdarkly-configs-create`, `/launchdarkly-tools`, `/launchdarkly-configs-targeting`, `/launchdarkly-online-evals`) and waits for them to come back. This skill does **not** auto-invoke other skills.

## Workflow

### Minimum viable migration

Stages 1–4 (audit, wrap, tools, tracker) are independently shippable. **A migration that stops after Stage 4 is complete, production-ready, and delivers the core value** — externalized prompts and model config, targeting, variation A/B testing, and Monitoring-tab metrics. Stage 5 (evaluators) is a quality-of-life addition, not a gate. Do not block a Stage-4 rollout on evaluators; ship the run-scoped tracker path, verify metrics flow, then come back for Stage 5 when the team has time to curate a dataset.

That said, do not *skip* Stage 4. A migration without the tracker gives you externalized prompts but no visibility, which is most of the payoff left on the floor.

### Step 1: Audit the codebase (Stage 1)

This is the first stage. It is **read-only** — no code writes, no LaunchDarkly resources created. The goal is to scan the repo and produce a structured manifest of every hardcoded value that needs to move, then hand the manifest back to the user for confirmation before any code is touched in Stage 2.

Use [phase-1-analysis-checklist.md](references/phase-1-analysis-checklist.md) to scan:

1. **Language and package manager** — Python (pip/poetry/uv), TypeScript/JavaScript (npm/pnpm/yarn), Go, Ruby, .NET
2. **LLM provider** — OpenAI, Anthropic, Bedrock, Gemini, LangChain, LangGraph, CrewAI, Strands
3. **Existing LaunchDarkly usage** — any pre-existing `LDClient` or `ldclient` initialization to reuse
4. **Hardcoded model configs** — model name string literals, temperature / max_tokens / top_p, system prompts, instruction strings
5. **Template placeholders in prompts** — `.format()` calls, f-strings in prompt constants, JS/TS template literals, `%(var)s`, hand-rolled `str.replace("__VAR__", ...)`. Flag each placeholder name and its runtime-value source; all get rewritten to Mustache `{{ variable }}` in Stage 2.
6. **Externalized prompt files** — scan YAML / JSON / TOML / Markdown / `.prompt` / `.j2` files **and** prompt-template registries (`langchain.hub.pull(...)`, LangSmith `client.pull_prompt(...)`) for prompts loaded at runtime. Common shapes: CrewAI `agents.yaml` / `tasks.yaml`, LangChain Promptfiles, k8s ConfigMap overlays, Pydantic Settings classes with `prompt_*` fields. Same Mustache rewrite (sub-step 5 of Stage 2) applies if the placeholder syntax differs. See [phase-1-analysis-checklist.md § 4](references/phase-1-analysis-checklist.md).
7. **Hardcoded app-scoped knobs** — search-result limits, retry budgets, tool-timeout overrides, feature toggles, any config-dataclass field that isn't a prompt or model parameter but still governs agent behavior. These belong in `model.custom` on the variation (not `model.parameters`, which is forwarded to the provider SDK and will crash on unknown kwargs).
8. **Mode decision** — completion mode (chat messages array) or agent mode (single instructions string). Completion mode is the default and the only mode that supports judges attached in the UI.

For each hardcoded target the audit finds, record:

- File path and line range
- Current value (model name, full prompt text, parameter dict)
- Target config field (`model.name`, `model.parameters.temperature`, `messages[].content`, `instructions`)
- Whether the surrounding call uses function calling / tools (drives Stage 3)
- Whether the surrounding call has retry logic (affects where Stage 4 tracker calls go)

This manifest is the contract for the next four stages.

**Stage 1 output** (return to user as a structured summary):

```
Language: Python 3.12
Package manager: uv
LLM provider: OpenAI
Existing LD SDK: none
Target mode: completion
Hardcoded targets:
  - src/chat.py:42   model="gpt-4o"
  - src/chat.py:43   temperature=0.7, max_tokens=2000
  - src/chat.py:45   system="You are a helpful assistant..."
Externalized prompt files: none (or e.g. "prompts/agents.yaml — CrewAI role/goal/backstory")
Prompt-template registries: none (or e.g. langchain.hub.pull("rlm/rag-prompt") at app.py:14)
Coverage totals: 3 hardcoded code targets · 0 externalized prompt files · 0 registry pulls
Proposed plan: single config key `chat-assistant`, mirror fallback, Stage 3 (tools) skipped (no function calling), Stage 4 (tracking) inline, Stage 5 (evals) attach built-in accuracy judge.
```

**STOP.** Present this summary, state the coverage totals out loud (e.g. "I found **N** hardcoded code targets and **M** externalized prompt files — does that match what you expected?"), and wait for the user to reply with one of four explicit forms:

- **`confirm`** — proceed to Stage 2.
- **`add: <files or paths>`** — re-run the audit with the new locations and present an updated summary.
- **`fix: <correction>`** — update a target in the list (provider, mode, prompt content, etc.) and ask again.
- **`stop`** — pause the migration here.

Do not interpret any other word — including `skip`, `next`, `go`, `ok`, `proceed` — as confirmation; ask the user to pick one of the four forms. **This is the most important checkpoint in the workflow** — if the audit is wrong, every stage after this will be wrong. The user should cross-check the hardcoded-targets list against what they know is in the code before giving the go-ahead.

### Step 2: Wrap the call in the AI SDK (Stage 2)

This is the first stage that writes code. It has nine sub-steps.

1. **Delete any hand-rolled model / tool wrappers the audit flagged.** Do this *before* installing the new SDK so the replacement lands in a repo without confusing fallback imports. The two shapes the Stage 1 audit should have surfaced:
   - **`load_chat_model(f"{provider}/{name}")` or any `init_chat_model(...)` wrapper.** Ships with `langchain-ai/react-agent` and many derivative repos. Delete the function and its module; the replacement is `create_langchain_model(ai_config)` (installed in the next sub-step). Leaving the wrapper in place means the next edit in this repo will import the familiar helper and silently drop variation parameters.
   - **Hand-rolled `resolve_tools` / `TOOL_REGISTRY` / `ALL_TOOLS` helpers that hard-code a static tool list.** Delete them; `ldai_langchain.langchain_helper.build_structured_tools(ai_config, TOOL_REGISTRY_DICT)` is the canonical replacement and gets wired in Stage 3. If you leave the hand-rolled version, both shapes will live side-by-side and the next contributor will pick the familiar one.

   Commit the deletion separately from the SDK install if the repo's review process benefits from it — otherwise bundle with sub-step 2.

2. **Install the AI SDK.** Detect the package manager from Step 1, then install:
   - Python: `launchdarkly-server-sdk` + `launchdarkly-server-sdk-ai>=0.20.0`
   - Node.js/TypeScript: `@launchdarkly/node-server-sdk` + `@launchdarkly/server-sdk-ai@^0.20.0`
   - Go: `github.com/launchdarkly/go-server-sdk/v7` + `github.com/launchdarkly/go-server-sdk-ai`

   Tier-2 provider packages (install in Stage 4, only if you're using the matching provider):
   - OpenAI: `launchdarkly-server-sdk-ai-openai>=0.4.0` (Python) / `@launchdarkly/server-sdk-ai-openai@^0.5.5` (Node)
   - LangChain / LangGraph: `launchdarkly-server-sdk-ai-langchain>=0.5.0` (Python) / `@launchdarkly/server-sdk-ai-langchain@^0.5.5` (Node)
   - Vercel AI SDK (Node only): `@launchdarkly/server-sdk-ai-vercel@^0.5.5`
   - Anthropic, Gemini, Bedrock — no provider package published; use Tier-3 custom extractor (see `launchdarkly-built-in-metrics`)

3. **Initialize `LDAIClient` once at startup.** Reuse any existing `LDClient` — do not create a second base client. Place the initialization in the same module that owns existing app config.

   **Python:**
   ```python
   import os
   import ldclient
   from ldclient.config import Config
   from ldai.client import LDAIClient

   # Order matters: ldclient.get() raises if called before ldclient.set_config().
   # The set_config call is what initializes the singleton; .get() just returns it.
   sdk_key = os.environ.get("LD_SDK_KEY")
   if sdk_key:
       ldclient.set_config(Config(sdk_key))
   else:
       # Missing key: init in offline mode so the app still starts and the fallback
       # path runs on every call. Never raise at import time for a missing env var —
       # that turns a config gap into a boot failure.
       import logging
       logging.getLogger(__name__).warning(
           "LD_SDK_KEY not set; configs will use fallback values only."
       )
       ldclient.set_config(Config("", offline=True))

   ai_client = LDAIClient(ldclient.get())
   ```

   **Node.js/TypeScript:**
   ```typescript
   import { init } from '@launchdarkly/node-server-sdk';
   import { initAi } from '@launchdarkly/server-sdk-ai';

   // The Node SDK does not have an explicit offline mode — a missing or invalid
   // key fails fast during waitForInitialization, and every agent_config /
   // completion_config call returns the fallback. Log a warning; do not throw.
   if (!process.env.LD_SDK_KEY) {
     console.warn('LD_SDK_KEY not set; configs will use fallback values only.');
   }
   const ldClient = init(process.env.LD_SDK_KEY ?? 'sdk-offline');
   await ldClient.waitForInitialization({ timeout: 10 }).catch(() => {
     // Swallow init failures in offline mode; fallback path runs.
   });
   const aiClient = initAi(ldClient);
   ```

4. **Hand off to `launchdarkly-configs-create`.** Print the extracted model, prompt/instructions, parameters, and mode from the Stage 1 manifest, then tell the user: *"Run `/launchdarkly-configs-create` with these inputs, then come back here."* Supply the config key you want the code to call (e.g. `chat-assistant`). Do not attempt to auto-invoke the sibling skill — wait for the user to finish it before continuing.

   **After `launchdarkly-configs-create` finishes, the user must also run `/launchdarkly-configs-targeting` to promote the new variation to fallthrough.** A freshly created variation returns `enabled=False` to every consumer until targeting is updated. Skip this and Stage 2 verification (sub-step 9 below) will silently take the fallback path on every request.

5. **Rewrite template placeholders to Mustache syntax.** If the hardcoded prompt interpolates runtime values with Python `.format()`, f-strings, JS template literals, or any other non-Mustache syntax (e.g. `{system_time}`, `${userName}`, `%(topic)s`), rewrite every placeholder to `{{ variable }}` Mustache form. Do this in **both** the file you're about to send to `/launchdarkly-configs-create` *and* the fallback string you'll write in sub-step 6. The AI SDK interpolates variables through a Mustache renderer on the LD-served path *and* the fallback path using the fourth-argument `variables` dict to `completion_config(...)` / `completionConfig(...)`. Leaving a Python-style `{system_time}` literal in the fallback ships a silent regression when LaunchDarkly is unreachable — the renderer won't match the single-brace form and the literal `{system_time}` goes to the provider as part of the prompt.

   **Before:**
   ```python
   SYSTEM_PROMPT = "You are a helpful assistant. The time is {system_time}."
   prompt = SYSTEM_PROMPT.format(system_time=datetime.now().isoformat())
   ```

   **After (in source):**
   ```python
   SYSTEM_PROMPT = "You are a helpful assistant. The time is {{ system_time }}."
   # .format() is removed at the call site — the SDK interpolates via `variables`
   config = ai_client.completion_config(
       CONFIG_KEY,
       context,
       fallback,
       variables={"system_time": datetime.now().isoformat()},
   )
   ```

   Common shapes to rewrite:
   - Python `"{var}"` / `"{var!s}"` / `"%(var)s"` → `"{{ var }}"`
   - JS/TS `` `${var}` `` template literals inside prompt strings → `"{{ var }}"`
   - Any hand-rolled `str.replace("__VAR__", value)` scheme → `"{{ var }}"`

   See [fallback-defaults-pattern.md § Template placeholders](references/fallback-defaults-pattern.md) for the fallback-specific variant.

6. **Build the fallback.** Mirror the hardcoded values you extracted. Use `AICompletionConfigDefault` / `AIAgentConfigDefault` in Python, plain object literals in Node. See [fallback-defaults-pattern.md](references/fallback-defaults-pattern.md) for inline, file-backed, and bootstrap-generated patterns.

   **Python fallback (completion mode):**
   ```python
   from ldai.client import AICompletionConfigDefault, ModelConfig, ProviderConfig, LDMessage

   fallback = AICompletionConfigDefault(
       enabled=True,
       model=ModelConfig(name="gpt-4o", parameters={"temperature": 0.7, "max_tokens": 2000}),
       provider=ProviderConfig(name="openai"),
       messages=[LDMessage(role="system", content="You are a helpful assistant...")],
   )
   ```

7. **Replace the hardcoded call site.** Swap the hardcoded model/prompt/params for a `completion_config` / `completionConfig` (or `agent_config` / `agentConfig`) call, then read the returned fields into the existing provider call. Keep the provider call intact.

   **Python — before:**
   ```python
   response = openai_client.chat.completions.create(
       model="gpt-4o",
       temperature=0.7,
       max_tokens=2000,
       messages=[
           {"role": "system", "content": "You are a helpful assistant..."},
           {"role": "user", "content": user_input},
       ],
   )
   ```

   **Python — after:**
   ```python
   context = Context.builder(user_id).set("email", user.email).build()
   config = ai_client.completion_config("chat-assistant", context, fallback)

   if not config.enabled:
       return disabled_response()

   params = config.model.parameters or {}
   response = openai_client.chat.completions.create(
       model=config.model.name,
       temperature=params.get("temperature"),
       max_tokens=params.get("max_tokens"),
       messages=[m.to_dict() for m in (config.messages or [])] + [
           {"role": "user", "content": user_input},
       ],
   )
   ```

   **Python — after (agent mode)** — for LangGraph, CrewAI, or any framework that takes a goal/instructions string:

   ```python
   context = Context.builder(user_id).kind("user").build()
   config = ai_client.agent_config("support-agent", context, FALLBACK)

   if not config.enabled:
       return disabled_response()

   # config is a single AIAgentConfig object — NOT a (config, tracker) tuple.
   # Obtain the tracker once per execution via the factory: tracker = config.create_tracker()
   model_name = f"{config.provider.name}/{config.model.name}"
   instructions = config.instructions
   params = config.model.parameters or {}

   # Pass model_name + instructions into your framework's agent constructor.
   # Example: LangGraph prebuilt agent (Python — `from langchain.agents import create_agent`;
   # this replaces `langgraph.prebuilt.create_react_agent`, deprecated in LangGraph 1.0
   # and removed in 2.0. Same return shape; `prompt=` was renamed to `system_prompt=`.)
   # agent = create_agent(
   #     create_langchain_model(config),  # forwards every variation parameter
   #     TOOLS,                            # Stage 3 will replace this with a config.tools loader
   #     system_prompt=instructions,
   # )
   ```

   See [before-after-examples.md](references/before-after-examples.md) for full Python OpenAI, Node Anthropic, and LangGraph agent-mode paired snippets.

8. **Check `config.enabled`.** If it returns `False`, handle the disabled path without crashing and without calling the provider. The check is required — not optional.

9. **Verify.** Run the app with a valid `LD_SDK_KEY`; confirm the call succeeds and the response matches pre-migration output. Then temporarily set `LD_SDK_KEY=sdk-invalid` (or unset it) and confirm the fallback path runs without error. Both paths must work before moving to Stage 3.

Delegate: **`launchdarkly-configs-create`** (sub-step 4).

### Step 3: Move tools into the config (Stage 3)

Skip this step if the audited app has no function calling / tools. Otherwise:

1. **Enumerate the tools currently registered.** Common shapes to look for:

   - `openai.chat.completions.create(tools=[...])` — OpenAI direct
   - `anthropic.messages.create(tools=[...])` — Anthropic direct
   - `create_agent(llm, tools=[...], system_prompt=...)` — LangGraph prebuilt (Python, `langchain.agents`; replaces deprecated `langgraph.prebuilt.create_react_agent`)
   - `createReactAgent({ llm, tools: [...] })` — LangGraph.js prebuilt (Node, `@langchain/langgraph/prebuilt`)
   - `Agent(tools=[...])` — CrewAI
   - `Agent(tools=[...])` — Strands (Python `@tool`-decorated callables passed through the constructor; TS SDK uses Zod-schema tools)
   - **Custom `StateGraph`** — module-level `TOOLS = [...]` list referenced in **both** `model.bind_tools(TOOLS)` and `ToolNode(TOOLS)`. This is the `langchain-ai/react-agent` template shape; the list is usually in a `tools.py` module. Grep for `bind_tools(` and `ToolNode(` together — they will point at the same list.

   Record each tool's name, description, and JSON schema.

   For LangChain/LangGraph tools defined with `@tool`, extract the schema via `tool.args_schema.model_json_schema()` (or the equivalent Pydantic `model_json_schema()` call). For plain async callables used as tools (common in custom StateGraph shapes), LangChain infers the schema from the function signature at bind time — extract it via `StructuredTool.from_function(fn).args_schema.model_json_schema()`. Do not hand-write the schema.

2. **Hand off to `launchdarkly-tools`.** Print the extracted tool names, descriptions, and schemas, then tell the user: *"Run `/launchdarkly-tools` with these tools and the variation key, then come back here."* The sibling skill creates tool definitions (`create-ai-tool`) and attaches them to the variation (`update-ai-config-variation`). Wait for the user to finish before proceeding to sub-step 3. Do not auto-invoke.

3. **Replace the hardcoded tools array at the call site** with a read from `config.tools` (or the SDK equivalent for your language). Load the actual implementation functions dynamically from the tool names — see [agent-mode-frameworks.md](references/agent-mode-frameworks.md) for the dynamic-tool-factory pattern from the devrel agents tutorial.

   **For custom `StateGraph` shapes**, you must update **both** call sites: `.bind_tools(TOOLS)` and `ToolNode(TOOLS)` must both read from the same `config.tools`-derived list. Forgetting one leaves the LLM seeing the new tools but the executor still running the old ones, or vice versa.

4. **Verify.** Run the app; confirm the tool flows still execute correctly. `get-ai-config` (via the delegate) confirms the tools are attached server-side.

Delegate: **`launchdarkly-tools`** (sub-step 2).

### Step 4: Instrument the tracker (Stage 4)

Delegate: **`launchdarkly-built-in-metrics`** wires the per-request `tracker.track_*` calls (duration, tokens, success/error, feedback) around the provider call. Use **`launchdarkly-custom-metrics`** alongside it if the app needs business metrics beyond the built-in agent ones. Note: do not confuse this with `launchdarkly-metric-instrument`, which is for `ldClient.track()` feature metrics — a different API. See [sdk-ai-tracker-patterns.md](references/sdk-ai-tracker-patterns.md) for the full per-method Python + Node matrix that the delegate skill draws on.

Hand off: print the config key, variation key, provider, and whether the call is streaming, then tell the user: *"Run `/launchdarkly-built-in-metrics` with these inputs, then come back here."* Do not auto-invoke. Return here for sub-step 5 (verify) once they're done.

1. **Create the tracker.** Obtain a per-execution tracker via the factory on the config returned in Stage 2: `tracker = config.create_tracker()` (Python) or `const tracker = aiConfig.createTracker();` (Node). Call the factory **once per user turn** and reuse the returned `tracker` for every tracking call in that turn — each call mints a fresh `runId` that tags every event emitted from the turn so they can be correlated via exported events or downstream queries. (The Monitoring tab aggregates today; run-level grouping is a downstream concern — but the `runId` is also what the SDK's at-most-once guards are keyed on, so minting a new one mid-turn breaks the guard semantics regardless of where the events end up.)

   **Where to call the factory depends on the call shape:**

   - **Completion mode / one-shot provider call:** mint the tracker right after `completion_config(...)` returns, in the same function that handles the request.
   - **Agent mode with a ReAct loop (LangGraph, LangChain, custom):** mint the tracker in a dedicated `setup_run` entry node that executes **once** before the loop, stash it on graph state, and read it from state in `call_model` / tool handlers / a terminal `finalize` node. Emitting `track_duration` / `track_tokens` / `track_success` inside the loop body will trip the at-most-once guards. See [agent-mode-frameworks.md § Custom `StateGraph` (run-scoped architecture)](references/agent-mode-frameworks.md) for the full `setup_run` + `call_model` + `finalize` pattern.
   - **Managed runner (Tier 1):** skip this step entirely. `ManagedModel` mints the tracker internally per `run()` / `invoke()`. Move to sub-step 4 if that's what the app uses.

2. **Pick a tier from the four-tier ladder.** See [sdk-ai-tracker-patterns.md § Tier decision table](references/sdk-ai-tracker-patterns.md) for the full table (chat loop → Tier 1; provider-package call → Tier 2; custom extractor → Tier 3; streaming/manual → Tier 4).

3. **Wire the chosen tier.** The delegate skill has full Python + Node examples for each tier plus per-provider files. A condensed Tier 2/3 example for reference — OpenAI via the provider package:

   **Python:**
   ```python
   from ldai_openai import get_ai_metrics_from_response
   import openai

   client = openai.OpenAI()

   tracker = config.create_tracker()

   def call_openai():
       return client.chat.completions.create(
           model=config.model.name,
           messages=[{"role": "system", "content": config.messages[0].content},
                     {"role": "user", "content": user_prompt}],
       )

   # Exceptions are tracked automatically — track_metrics_of catches
   # exceptions, records tracker.track_error(), and re-raises. Wrap your
   # own try/except only for local handling (logging, fallback).
   response = tracker.track_metrics_of(get_ai_metrics_from_response, call_openai)
   ```

   **Node:**
   ```typescript
   import { getAIMetricsFromResponse } from '@launchdarkly/server-sdk-ai-openai';

   const tracker = aiConfig.createTracker();
   // Exceptions are tracked automatically — trackMetricsOf catches
   // exceptions, records tracker.trackError(), and re-throws.
   const response = await tracker.trackMetricsOf(
     getAIMetricsFromResponse,
     () => openaiClient.chat.completions.create({
       model: aiConfig.model!.name,
       messages: [...aiConfig.messages, { role: 'user', content: userPrompt }],
     }),
   );
   ```

   For Anthropic direct, Bedrock (no provider package), Gemini, and custom HTTP, write a small extractor returning `LDAIMetrics` — see the delegate skill's [anthropic-tracking.md](../launchdarkly-built-in-metrics/references/anthropic-tracking.md), [bedrock-tracking.md](../launchdarkly-built-in-metrics/references/bedrock-tracking.md), and [gemini-tracking.md](../launchdarkly-built-in-metrics/references/gemini-tracking.md). LangChain single-node and LangGraph go through the `launchdarkly-server-sdk-ai-langchain` / `@launchdarkly/server-sdk-ai-langchain` provider package. Build the model with `create_langchain_model(config)` (Python) / `createLangChainModel(config)` (Node) — both forward all variation parameters — and track with `get_ai_metrics_from_response` / `getAIMetricsFromResponse`. See [langchain-tracking.md](../launchdarkly-built-in-metrics/references/langchain-tracking.md).

4. **Wire feedback tracking if the app has thumbs-up/down UI.** Both SDKs expose `trackFeedback` with a `{kind}` argument.

   **Python:**
   ```python
   from ldai.tracker import FeedbackKind
   tracker.track_feedback({"kind": FeedbackKind.Positive})
   ```

   **Node:**
   ```typescript
   import { LDFeedbackKind } from '@launchdarkly/server-sdk-ai';
   tracker.trackFeedback({ kind: LDFeedbackKind.Positive });
   ```

   **Deferred feedback across processes.** If the thumbs-up UI fires in a different process than the one that produced the response, do **not** call `create_tracker()` again in the consumer — that mints a new `runId`. Persist the tracker's resumption token (`tracker.resumption_token` in Python, `tracker.resumptionToken` in Node) alongside the message, then rehydrate the tracker with `LDAIConfigTracker.from_resumption_token(...)` (Python) or `aiClient.createTracker(token, context)` (Node) in the feedback handler.

5. **Verify.** Hit the wrapped endpoint in staging, then open the config in LaunchDarkly → Monitoring tab. Duration, token, and generation counts should appear within 1–2 minutes. If nothing shows up, walk the checklist in [sdk-ai-tracker-patterns.md](references/sdk-ai-tracker-patterns.md) under "Troubleshooting."

### Step 5: Attach evaluations (Stage 5)

1. **Decide between three evaluation paths.** This is the most commonly misunderstood stage — there are **three** paths, not two, and the right default for a migration context is often the one people skip.

   | Path | When to use | Supports agent mode? |
   |------|-------------|---------------------|
   | **Offline eval** (recommended default for migration) | Pre-ship regression: run a fixed dataset through the new variation in the LD Playground and score against baseline. Best fit for migration because you want to prove the new config behaves at least as well as the hardcoded version before shipping. | Yes — all modes |
   | **UI-attached auto judges** | Attach one or more judges to a variation in the LD UI; judges run on sampled live requests automatically. Zero code changes. | Completion mode only (the UI widget is completion-only today) |
   | **Programmatic direct-judge** | Call `ai_client.create_judge(...)` inside the request handler and `judge.evaluate(input, output)` on each call. Adds per-request cost and code complexity. Best for continuous live scoring of workflows where sampled auto-judges aren't enough. | Yes — all modes (the SDK handles both identically) |

   **Most migration users should start with offline eval**, then add programmatic direct-judge only if they need continuous live scoring after the rollout is stable.

2. **For agent-mode migrations, default to offline eval.** UI-attached auto judges are completion-mode only today. The documented path for agent mode is either (a) **offline regression** via the LD Playground + Datasets (works for all modes), or (b) **programmatic direct-judge** wired into the call site. Generate a starter dataset CSV from the audit manifest (one representative input per row) and point the user at the [Offline Evals guide](https://docs.launchdarkly.com/guides/ai-configs/offline-evaluations) for the Playground walkthrough. Only wire programmatic direct-judge into production code if the user explicitly asks for continuous live scoring.

   **Recommended offline-eval shape for a migration:**
   - Run the `default` variation (or whichever variation mirrors the pre-migration hardcoded behavior) against the dataset first — this is the baseline.
   - Clone it into a second variation pointing at a **different model family** (e.g., if the baseline is `anthropic/claude-sonnet-4-5`, clone to `openai/gpt-4o` or `openai/gpt-4o-mini`). The comparison is most informative across families, not across siblings.
   - Attach the built-in **Accuracy** judge with a pass threshold of **0.85**, and run both variations against the same dataset.
   - Promote the winner to fallthrough via `/launchdarkly-configs-targeting` only if it beats the baseline on Accuracy and does not regress on Relevance or Toxicity.

   Write this shape into the project's `datasets/README.md` (or equivalent) so the comparison pattern is reproducible after the migration ships.

3. **Hand off to `launchdarkly-online-evals`** — only for UI-attached judges (completion mode) or to create custom judge configs that will be referenced by the programmatic path. Tell the user: *"Run `/launchdarkly-online-evals` with these inputs, then come back here."* Do not auto-invoke. Pass:
   - The parent config key and variation key
   - A list of built-in judges (Accuracy, Relevance, Toxicity) or custom judge keys to create/attach
   - Target environment

   The delegate handles creating custom judge configs, attaching them via the variation PATCH endpoint, and setting fallthrough on each judge config. Offline eval does **not** go through this delegate — it's a Playground workflow, not an API write.

4. **For programmatic direct-judge: wire `create_judge` + `evaluate` + `track_judge_result`.** This is the only path at Stage 5 that writes code. The Python shape:

   ```python
   from ldai.client import AIJudgeConfigDefault

   judge = ai_client.create_judge(
       judge_key,                               # judge config key in LD
       ld_context,
       AIJudgeConfigDefault(enabled=False),     # fallback: skip eval on SDK miss
   )

   if judge and judge.enabled:
       result = await judge.evaluate(
           input_text,
           output_text,
           sampling_rate=0.25,                  # optional; default 1.0 (always eval)
       )
       if result.sampled:
           tracker.track_judge_result(result)
   ```

   Four rules:
   - **`create_judge` returns `Optional[Judge]`.** Always guard with `if judge and judge.enabled:` — it returns `None` if the judge config is disabled for the context or the provider is missing. A direct `.evaluate()` on a `None` return will raise `AttributeError`.
   - **Pass `AIJudgeConfigDefault`**, not `AICompletionConfigDefault`. The `create_judge` `default` parameter is typed `Optional[AIJudgeConfigDefault]`; passing the completion type will not type-check and is a doc-level bug in some older examples.
   - **`sampling_rate` is a parameter on `evaluate()`**, not on `create_judge`. It defaults to `1.0` (evaluate every call). For live paths, pass something lower (0.1–0.25) to control cost.
   - **`evaluate()` returns a `JudgeResult`** (never `None`). Check `result.sampled` to know whether the evaluation actually ran, and call `track_judge_result(result)`. Node uses `trackJudgeResult(result)` and `LDJudgeResult` with the same `sampled` field.

   **Ask the user which judge config key to use.** LaunchDarkly ships three built-in judges — Accuracy, Relevance, Toxicity — but the actual config **keys** for the built-ins are not canonical SDK constants and aren't documented. Have the user open **AgentControl > Library** in the LD UI and copy the key of the judge they want to reference, or create a custom judge config via `launchdarkly-configs-create` first.

5. **Verify.**
   - **UI-attached auto judges:** trigger a request in staging, open the Monitoring tab → "Evaluator metrics" dropdown. Scores appear within 1–2 minutes at the configured sampling rate.
   - **Programmatic direct-judge:** hit the wrapped endpoint and confirm `track_judge_result` lands on the parent config's Monitoring tab.
   - **Offline eval:** run the dataset through the LD Playground, compare baseline vs new-variation scores side by side. No runtime wiring required.

Delegate: **`launchdarkly-online-evals`** (sub-step 3, optional — only for UI-attached judges or custom-judge creation; offline eval doesn't delegate).

## Edge Cases

| Situation | Action |
|-----------|--------|
| App already initializes `LDClient` for feature flags | Reuse it — pass the existing client to `LDAIClient()` / `initAi()`, do not create a second client |
| App uses LangChain `ChatOpenAI(model=...)` | Replace the hand-rolled model construction with `create_langchain_model(config)` (Python) or `createLangChainModel(config)` (Node). Do not read `config.model.name` and pass it to `ChatOpenAI(model=...)` by hand — that pattern drops every variation parameter except the ones you explicitly name |
| Retry wrapper around the provider call | The tracker is minted once at the top of the user turn; the retry loop is inside that scope. Every retry attempt shares the same `runId`. Tracker calls (`track_duration` / `track_tokens` / `track_success` / `track_error`) live *outside* the retry body — one call at the end of the turn, on the success path or the final-failure path |
| App has no tools — Stage 3 skipped | Move directly from Stage 2 verification to Stage 4 (tracking) |
| Mode mismatch: user said agent, audit shows one-shot chat | Choose completion mode unless the app uses a LangGraph prebuilt agent (`langchain.agents.create_agent` in Python or `createReactAgent` in Node), CrewAI `Agent`, Strands `Agent`, or a similar goal-driven framework |
| App uses Strands Agents (Python) | Agent mode. Build a `create_strands_model` dispatcher keyed on `agent_config.provider.name` that returns `AnthropicModel(model_id=..., max_tokens=...)` or `OpenAIModel(model_id=..., params=...)`. Drop `parameters.tools` before passing params to the model class — Strands receives tools via `Agent(tools=[...])`. Tracking is Tier 3: wrap `invoke_async` with `tracker.track_duration_of(...)` and record tokens from `result.metrics.accumulated_usage`. See [agent-mode-frameworks.md § Strands Agent](references/agent-mode-frameworks.md) and [strands-tracking.md](../launchdarkly-built-in-metrics/references/strands-tracking.md) |
| Strands app on TypeScript | TS SDK ships `BedrockModel` and `OpenAIModel` only — cannot serve Anthropic-backed variations. Use the Python SDK if multi-provider variations are required |
| TypeScript app using Anthropic SDK | No `trackAnthropicMetrics` helper exists. Use Tier 3: `trackMetricsOf` with a small custom extractor that reads `response.usage.input_tokens` / `response.usage.output_tokens` and returns `LDAIMetrics`. See [anthropic-tracking.md](../launchdarkly-built-in-metrics/references/anthropic-tracking.md) in the `launchdarkly-built-in-metrics` skill for the exact extractor |
| Fallback would silently crash because `LD_SDK_KEY` is missing | Log a startup warning; proceed with the fallback. Never raise at import time |
| Multi-agent graph (supervisor + workers) | Stop after migrating a single agent. Agent Graph Definitions are available in **both** SDKs — Python via `launchdarkly-server-sdk-ai.agent_graph` and Node via the graph API in `@launchdarkly/server-sdk-ai`. Read [agent-graph-reference.md](references/agent-graph-reference.md) for the graph-level migration path — it is deliberately out of this skill's main scope |
| Single-agent (ReAct, tool loop) + agent mode | Default to offline eval via the LD Playground + Datasets for Stage 5. UI-attached judges are completion-only today, and programmatic direct-judge adds per-call cost that is usually not worth it until after the migration is live and stable. Point at the [Offline Evals guide](https://docs.launchdarkly.com/guides/ai-configs/offline-evaluations) |
| Tool with a Pydantic `args_schema` (LangChain `@tool`) | Extract the schema via `tool.args_schema.model_json_schema()`; do not hand-write the JSON schema for the delegate |
| Custom `StateGraph` with module-level `TOOLS` list bound via `.bind_tools(TOOLS)` and run through `ToolNode(TOOLS)` (e.g. the `langchain-ai/react-agent` template) | Find the `TOOLS` list (usually in a separate `tools.py` module). Extract schemas the same way. Swap **both** call sites — `.bind_tools(...)` and `ToolNode(...)` — to read from the same `config.tools`-derived list |
| App has already externalized config into a `Context` dataclass with env-var fallback (e.g. `react-agent` template's `context.py`) | Replace the consumers of `runtime.context.model` / `runtime.context.system_prompt` with `ai_client.agent_config(...)` and read from the returned `AIAgentConfig`. **Empty the dataclass** rather than keeping it as the fallback shape — the canonical fallback is `FALLBACK = AIAgentConfigDefault(...)` in Python (a top-level constant near the `agent_config` call), not a parallel Python dataclass. Two sources of truth for fallback values drift. An empty `Context` is a placeholder satisfying LangGraph's `context_schema` requirement only; `thread_id` and any other per-request plumbing comes through `config: RunnableConfig` instead (see [agent-mode-frameworks.md § Custom `StateGraph`](references/agent-mode-frameworks.md)) |

## What NOT to Do

These are ordered by how likely they are to show up as a first-run failure. The first three rules — about tracker and config lifetime — account for most of the "migration looks done but the Monitoring tab is fragmented / wrong" reports.

### Tracker and config lifetime (most common failure mode)

- **Don't call `create_tracker()` / `createTracker()` more than once per user turn.** One turn = the full request/response cycle including every ReAct iteration, tool call, and retry. See Stage 4 Step 1 for the canonical placement in each app shape (completion / agent loop / managed runner).
- **Don't call `track_duration` / `track_tokens` / `track_success` / `track_error` / `track_time_to_first_token` inside a loop body.** These are at-most-once per tracker; second calls are dropped. Accumulate inside the loop, emit once in a terminal/finalize node. Per-event methods (`track_tool_call`, `track_tool_calls`, `track_feedback`, `track_judge_result`) are safe to call repeatedly. Full matrix: [sdk-ai-tracker-patterns.md § At-most-once guards](references/sdk-ai-tracker-patterns.md).
- **Don't call `agent_config()` / `completion_config()` more than once per user turn.** Each call is a flag evaluation and emits a `$ld:ai:agent:config` event. Re-fetching inside a loop step or a tool body inflates agent-config counts on the Monitoring tab and lets a mid-turn targeting change swap the variation between LLM calls in a single turn. Resolve once at the top, stash on state, and have every subsequent consumer read from state. Tools that need variation-scoped knobs should use the tool-factory pattern (`make_search(ai_config)` that closes over the knob at setup time) — see [agent-mode-frameworks.md § Getting knobs into tools](references/agent-mode-frameworks.md).
- Don't cache the config object *across* requests — resolve once per turn, yes, but still resolve once per turn. Caching at module scope defeats the targeting-change mechanism entirely.
- Don't delete the fallback once LaunchDarkly is wired up. It is required for the `enabled=False` and SDK-unreachable paths.
- Don't tuple-unpack the return of `completion_config` / `agent_config` / `completionConfig` / `agentConfig`. They return a **single** config object (e.g. `AIAgentConfig`, `AICompletionConfig`), not `(config, tracker)`. Obtain the tracker by calling `config.create_tracker()` / `aiConfig.createTracker()`. LLMs hallucinate both the tuple shape and a `config.tracker` property — the actual API is a factory.

### LangChain / LangGraph patterns (second most common failure mode)

- **If the repo already contains a `load_chat_model(f"{provider}/{name}")` helper, delete it — don't just avoid using it.** This exact shape ships with `langchain-ai/react-agent` and is copied into dozens of derivative repos; look for `utils.load_chat_model`, `utils.build_model`, or any one-arg `init_chat_model` wrapper that splits a `"provider/model"` string. Re-using it is the first-run failure mode: every variation parameter (temperature, max_tokens, top_p, stop sequences) silently drops on the floor because `init_chat_model` only receives the name and provider. `create_langchain_model(ai_config)` is a one-for-one replacement that forwards the whole `model.parameters` dict. Replace every call site, then delete the wrapper file-side so the next reader can't reach for it.
- **Same rule applies to hand-rolled `resolve_tools` / `TOOL_REGISTRY` / `ALL_TOOLS` helpers.** If the template already has a `resolve_tools(tool_keys)` or an `ALL_TOOLS` module-level list, import `build_structured_tools` from `ldai_langchain.langchain_helper` and delete the hand-rolled version. `build_structured_tools(ai_config, TOOL_REGISTRY_DICT)` reads `ai_config.model.parameters.tools` and wraps the matching callables as LangChain `StructuredTool`s with the LD tool key as the `StructuredTool.name` — so `ToolNode` lookup works without a second mapping. Don't leave both in the repo.
- Don't put app-scoped knobs directly in `model.parameters`. `create_langchain_model` forwards every key in `parameters` to the provider SDK via `init_chat_model`, so a `max_search_results` / `retry_budget` / `feature_toggle` entry will crash the provider with an unexpected-keyword-argument error. The correct home is `model.custom`, which the provider helpers ignore and the app reads via `ai_config.model.get_custom("key")`. The MCP `update-ai-config-variation` tool does not currently expose top-level `custom`, so pick one of two paths: (a) PATCH the variation via the REST API to set `model.custom` directly, or (b) set it via MCP inside `parameters.custom` (as a nested dict) and use a defensive accessor that reads both locations. Full walk-through with code samples in [langchain-tracking.md § MCP caveat](../launchdarkly-built-in-metrics/references/langchain-tracking.md).
- Don't re-encode tool schemas inside the fallback. When LaunchDarkly is unreachable the fallback should run without tools (or with whatever minimal provider-bound parameters the app needs to keep operating). Building a `_FALLBACK_TOOLS` array that duplicates the config's tool schema re-introduces the hardcoded config the migration was supposed to move out of code.
- Don't import `LaunchDarklyCallbackHandler` from `ldai.langchain` — neither the class nor the dotted module path exists. The Python LangChain helper package is `ldai_langchain` (top-level module, underscore). Use `create_langchain_model(config)` + `track_metrics_of_async(get_ai_metrics_from_response, lambda: llm.ainvoke(messages))` as the canonical pattern.

### Stage / handoff discipline

- Don't skip Step 1 even when the user says "just wrap it." Without the audit, the fallback will drift from the hardcoded behavior.
- Don't delegate to `launchdarkly-configs-create` before extracting the prompt and model — the delegate needs them as inputs.
- Don't try to attach tools during initial `setup-ai-config`. Tool attachment is a separate step owned by `launchdarkly-tools`.
- Don't claim you "delegated to `launchdarkly-configs-create`" or any other sibling skill. This skill does not auto-invoke. At each handoff, print the inputs and tell the user to run the sibling slash-command, then wait. Anything else misleads the user about what just happened.
- Don't skip the `/launchdarkly-configs-targeting` step between Stage 2 and Stage 4. A freshly created variation returns `enabled=False` until targeting promotes it to fallthrough — Stage 2 verification will silently take the fallback path on every request.
- Don't attempt a multi-agent graph migration in one pass. Migrate a single agent first; use [agent-graph-reference.md](references/agent-graph-reference.md) as the next-step read.

### Stage 5 evaluations

- Don't wire evals before the tracker is in place. Judges score traffic; without Stage 4 traffic, there is nothing to judge.
- Don't frame Stage 5 as "either UI or programmatic." There are **three** paths: offline eval (recommended default for migration), UI-attached auto judges (completion-mode only), and programmatic direct-judge. Offline eval is the one most people skip and usually the right starting point.
- Don't pass `sampling_rate` to `create_judge` — it's a parameter on `Judge.evaluate()`, not `create_judge()`.
- Don't hardcode judge config keys (`"accuracy-judge"`, `"relevance-judge"`, etc). The built-in keys are not canonical SDK constants; ask the user to look them up in **AgentControl > Library** in the LD UI.
- Don't forget the `if judge and judge.enabled:` guard after `create_judge`. It returns `Optional[Judge]` and returns `None` when the judge config is disabled for the context.

### API surface gotchas

- Don't use `launchdarkly-metric-instrument` for Stage 4 (tracking). That skill is for `ldClient.track()` feature metrics, not agent `tracker.track_*` calls — they are different APIs.
- Don't use `track_request()` in Python — it does not exist in `launchdarkly-server-sdk-ai`. Use `track_metrics_of` with a provider-package or custom extractor, or drop to explicit `track_duration` + `track_tokens` + `track_success` / `track_error` if you're on the streaming path.
- Don't pass `graph_key=...` to `tracker.track_*()` methods in Python — it is not an accepted argument. Trackers obtained inside a graph traversal are automatically configured with the correct graph key.

## Related Skills

- `launchdarkly-configs-create` — called by Stage 2 to create the config
- `launchdarkly-tools` — called by Stage 3 to create and attach tool definitions
- `launchdarkly-online-evals` — called by Stage 5 to attach judges
- `launchdarkly-configs-variations` — add variations for A/B testing after migration is complete
- `launchdarkly-configs-targeting` — roll out new variations to users after migration is complete
- `launchdarkly-configs-update` — modify config properties as your app evolves
- `launchdarkly-metric-instrument` — for `ldClient.track()` feature metrics (NOT for agent tracker calls)

## References

- [phase-1-analysis-checklist.md](references/phase-1-analysis-checklist.md) — Step 1 audit checklist, grep patterns, SDK routing table, mode decision tree
- [before-after-examples.md](references/before-after-examples.md) — Paired hardcoded-to-wrapped snippets for Python OpenAI, Node Anthropic, Python LangGraph
- [sdk-ai-tracker-patterns.md](references/sdk-ai-tracker-patterns.md) — Every `tracker.track_*` method in Python and Node side by side, auto-helper matrix, and common gotchas
- [agent-mode-frameworks.md](references/agent-mode-frameworks.md) — How to wire `agent_config` into LangGraph, CrewAI, and custom react loops; dynamic tool loading pattern
- [fallback-defaults-pattern.md](references/fallback-defaults-pattern.md) — Three fallback patterns (inline, file-backed, bootstrap-generated) and when to use each
- [agent-graph-reference.md](references/agent-graph-reference.md) — Out-of-scope pointer doc for multi-agent migrations
