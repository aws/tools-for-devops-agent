# Agent-Mode Frameworks

How to wire a config in **agent mode** into the frameworks that take a goal/instructions string: LangGraph, CrewAI, Strands, and custom ReAct loops. Also covers the **dynamic tool loading** pattern from the devrel-agents-tutorial — how to extract tool names from `config.tools` at runtime and instantiate the actual tool implementations without hardcoding.

## When to pick agent mode

Completion mode is the default and covers direct provider calls (OpenAI, Anthropic, Bedrock) where the app assembles a `messages` array. Pick **agent mode** when:

| Signal | Framework | Example |
|--------|-----------|---------|
| Takes a `system_prompt` / `prompt` / `instructions` string as a single argument | LangGraph prebuilt agent | Python: `create_agent(llm, tools, system_prompt="You are...")` (`langchain.agents`); Node: `createReactAgent({ llm, tools, prompt: "You are..." })` (`@langchain/langgraph/prebuilt`) |
| Takes `role`, `goal`, `backstory` | CrewAI `Agent` | `Agent(role="researcher", goal="...", backstory="...")` |
| Custom ReAct loop with a system instruction separated from messages | hand-rolled | `system = "You can use search..."; while not done: ...` |
| Multi-step tool use with persistent instructions across turns | LangGraph / LangChain `AgentExecutor` | The system prompt stays stable across a long interaction |
| Provider-agnostic agent with `@tool` decorators and `invoke_async` | Strands `Agent` | `Agent(model=OpenAIModel(...), system_prompt="You are...", tools=[search])` |

Agent mode returns an `instructions` string. Completion mode returns a `messages` array. Both modes support tools, parameters, and the same tracker — the only difference is the input shape the SDK returns to you.

**Caveat:** judges cannot be attached to agent-mode variations via the LaunchDarkly UI. Agent mode evaluations must go through the programmatic judge API (`create_judge(...).evaluate(input, output)`). See `launchdarkly-online-evals` for the programmatic path.

**Model construction for LangChain / LangGraph.** When the framework runs on top of LangChain (which includes LangGraph's prebuilt agent and most custom graphs), build the chat model with `create_langchain_model(ai_config)` (Python) or `createLangChainModel(aiConfig)` (Node). These helpers forward every variation parameter (`temperature`, `max_tokens`, `top_p`, …) and handle LaunchDarkly→LangChain provider-name mapping internally. Do not hand-roll `init_chat_model(model=..., model_provider=...)` — it silently drops every variation parameter. See [langchain-tracking.md](../../launchdarkly-built-in-metrics/references/langchain-tracking.md) for the canonical single-model and LangGraph patterns, including the SDK helpers `sum_token_usage_from_messages` / `get_tool_calls_from_response` (Python, `ldai_langchain`) used inside the `track_metrics_of_async` / `trackMetricsOf` extractor.

## Framework-agnostic invariants for the run-scoped pattern

The concrete examples below use specific frameworks (LangGraph, CrewAI, Strands) and specific node names (`setup_run`, `call_model`, `finalize`). Treat those as incidentals. The three invariants below apply to **any** agent framework — DSPy, AutoGen, Pydantic AI, Haystack, LlamaIndex agents, or a hand-rolled tool loop in pure Python/TypeScript. If the framework has its own idioms, translate these three rules onto them:

1. **Resolve `agent_config()` / `agentConfig()` once per user turn.** Every call is a flag evaluation and emits a `$ld:ai:agent:config` event. Re-fetching inside a loop step or a tool body amplifies the event count per turn and lets a mid-turn targeting change swap the variation between LLM calls. Do the resolve at the highest scope that corresponds to "one user-input-to-final-response cycle" — a handler function, a LangGraph entry node, a CrewAI `kickoff`, whatever the framework exposes.
2. **Mint one tracker via `create_tracker()` / `createTracker()` per user turn.** Same scope as the `agent_config` call. The `runId` ties every event from one turn together; per-step factory calls fragment the correlation and reset the SDK's at-most-once guards. If the framework has a multi-turn session (chat thread), each turn inside the session still gets its own fresh tracker — sessions share a `thread_id`, not a `runId`.
3. **Emit the five at-most-once methods once at the end of the turn.** `track_duration` / `track_tokens` / `track_success` / `track_error` / `track_time_to_first_token` each fire at most once per tracker. Accumulate inside the loop body (sum token usage across steps, stash a `perf_counter_ns` timer up top), emit once after the loop exits or in a dedicated finalize node. `track_tool_calls` / `track_feedback` / `track_judge_result` are per-event — call them as many times as the agent does those things.

What "one user turn" means differs by app shape:

| App shape | "One turn" = |
|-----------|--------------|
| Request/response HTTP handler | One request |
| Chat loop (one session across many user inputs) | One user input (not the whole session) |
| LangGraph `app.ainvoke(...)` / `create_agent().invoke(...)` (Python) / `createReactAgent().invoke(...)` (Node) | One call to `ainvoke` / `invoke` |
| Custom ReAct loop with its own `for` iteration | The full loop run, not one iteration |
| Batch job / dataset walk | One row — each sample is its own run |
| Streaming response (SSE / WebSocket) | The full stream (open → last chunk), not one chunk |

If you can answer "what's the smallest unit at which I'd want to see a single 'execution' in the Monitoring tab?" — that's the turn. Mint exactly one tracker there.

## Tool-scoped and app-scoped knobs go in `model.custom`

If the Stage 1 audit identified configuration that isn't a native model parameter — the kind of thing a provider SDK will reject with `unexpected keyword argument` if you forward it — these fields belong in `ModelConfig(custom={...})`, **not** `ModelConfig(parameters={...})`. Typical examples:

- `max_search_results` (tool behavior — how many hits the search tool returns)
- `chunk_size` / `chunk_overlap` (RAG preprocessing knobs)
- `retry_budget` / `retry_backoff` (app-level retry policy)
- `enable_reranking`, `use_cache`, any boolean feature toggle the agent consumes
- any value that governs **tool behavior** or **app behavior** rather than **model behavior**

`create_langchain_model` (Python) / `createLangChainModel` (Node) forwards every key in `parameters` wholesale to the provider SDK. Anthropic, OpenAI, and Gemini all raise on unknown kwargs — a `max_search_results` entry in `parameters` crashes the request with `AsyncMessages.create() got an unexpected keyword argument 'max_search_results'`. Put the same field in `custom` and the helper leaves it alone; the app reads it where it's needed.

```python
# Fallback: mirror the hardcoded knob shape using custom
FALLBACK = AIAgentConfigDefault(
    enabled=True,
    model=ModelConfig(
        name="claude-sonnet-4-5-20250929",
        parameters={"temperature": 0.3, "max_tokens": 2000},  # provider-bound
        custom={"max_search_results": 10},                    # app-scoped
    ),
    provider=ProviderConfig(name="anthropic"),
    instructions="You are a helpful assistant.",
)

# In the tool or app code that needs the knob:
def search(query: str) -> dict:
    ai_config = get_current_agent_config()
    max_results = ai_config.model.get_custom("max_search_results") or 10
    return TavilySearch(max_results=max_results).invoke({"query": query})
```

Mirror the same shape on the LaunchDarkly variation. **MCP caveat.** The `update-ai-config-variation` MCP tool does not currently expose the `custom` field — to populate `model.custom` on an existing variation, PATCH it through the REST API directly:

```bash
curl -X PATCH \
  "https://app.launchdarkly.com/api/v2/projects/$PROJECT/ai-configs/$CONFIG_KEY/variations/$VARIATION_ID" \
  -H "Authorization: {api_token}" \
  -H "Content-Type: application/json" \
  -d '{"patch":[{"op":"add","path":"/model/custom","value":{"max_search_results":10}}]}'
```

### Getting knobs into tools: tool factories that close over per-run config (default)

Tools need read access to `model.custom` at call time. The correct pattern is a **tool factory** that takes the per-run `ai_config` resolved in `setup_run` (or at the top of a custom ReAct loop) and returns a tool callable that closes over whatever knobs it needs:

```python
# tools.py
def make_search(ai_config) -> Callable[..., Any]:
    max_results = ai_config.model.get_custom("max_search_results") or 10

    async def search(query: str) -> dict:
        """Search the web for current information on a given topic."""
        return await TavilySearch(max_results=max_results).ainvoke({"query": query})

    return search

TOOL_FACTORIES = {"search": make_search}

# graph.py setup_run
built = {name: fn(ai_config) for name, fn in TOOL_FACTORIES.items()}
tools = build_structured_tools(ai_config, built)
```

This is the default because it has three properties nothing else preserves all at once:

1. **Turn-level atomicity.** A mid-turn flag change doesn't swap `max_search_results` between the first tool call and the second — the factory captured it once, at `setup_run`.
2. **No extra LD evaluations.** `agent_config()` is a flag evaluation *and* an emitted event. Calling it from a tool once per user turn is fine; calling it per tool invocation on a chatty agent inflates `$ld:ai:agent:config` counts by a factor of however many tool calls run per turn.
3. **Tools don't take a dependency on LD.** The tool function is a plain callable. Testing is substitution, not monkeypatching `get_agent_config`.

**Do not call `get_agent_config()` (or `ai_client.agent_config(...)`) from inside a tool body.** The alternatives — re-resolving from inside the tool, or reaching into `runtime.context` from inside the tool — either break turn atomicity or require plumbing LangGraph's context through every tool signature. Tool factories sidestep both problems and are also how `ldai_langchain.langchain_helper.build_structured_tools` expects its registry to be shaped (a dict of `{name: Callable}` ready to bind).

The only legitimate reason to re-fetch inside a tool is if the tool's behavior needs to follow a flag change *within* a single turn. That's vanishingly rare; default to factories and treat re-fetch as an exception that requires a concrete reason.

## Wiring `agent_config` into each framework

### LangGraph prebuilt agent (Python — `langchain.agents.create_agent`)

> **API note.** Use `from langchain.agents import create_agent`. The earlier `from langgraph.prebuilt import create_react_agent` is deprecated in LangGraph 1.0 and removed in 2.0. Same return shape; the only call-site rename is `prompt=` → `system_prompt=`. Node.js still uses `createReactAgent` from `@langchain/langgraph/prebuilt`.

```python
from langchain.agents import create_agent
from ldai_langchain import create_langchain_model
from ldai.client import LDAIClient, AIAgentConfigDefault, ModelConfig, ProviderConfig

FALLBACK = AIAgentConfigDefault(
    enabled=True,
    model=ModelConfig(name="gpt-4o", parameters={"temperature": 0.3}),
    provider=ProviderConfig(name="openai"),
    instructions="You are a helpful assistant.",
)

def build_agent(ai_client: LDAIClient, user_id: str, tools: list):
    context = Context.builder(user_id).kind("user").build()
    config = ai_client.agent_config("support-agent", context, FALLBACK)

    if not config.enabled:
        return None, None

    # create_langchain_model forwards every variation parameter — do NOT hand-roll
    # ChatOpenAI(model=..., temperature=...). It silently drops unnamed parameters.
    llm = create_langchain_model(config)

    agent = create_agent(
        llm,
        tools,
        system_prompt=config.instructions,
    )
    return agent, config.create_tracker()
```

**Key points:**
- `system_prompt=config.instructions` — the instructions string replaces the hardcoded prompt
- Model + parameters come from `create_langchain_model(config)` — forwards the whole `model.parameters` dict
- A fresh tracker is minted via `config.create_tracker()` and returned alongside the agent so the caller can wire Stage 4 tracking around `agent.invoke(...)`. Each call to `create_tracker()` produces a new `runId`; the caller should treat the returned tracker as owning the execution.

### CrewAI `Agent`

```python
from crewai import Agent
from ldai.client import LDAIClient, AIAgentConfigDefault

def build_crew_agent(ai_client, user_id: str):
    context = Context.builder(user_id).kind("user").build()
    config = ai_client.agent_config("researcher-agent", context, FALLBACK)

    if not config.enabled:
        return None

    # CrewAI expects role/goal/backstory — split the instructions or store them
    # in the Config as three variables and pipe them in at runtime.
    return Agent(
        role="Research Analyst",
        goal="Produce a summary of recent config adoption patterns.",
        backstory=config.instructions,
        llm=config.model.name,  # CrewAI accepts a string or a LangChain model
    )
```

**Pattern note:** CrewAI's `Agent` takes three separate fields. If you want to drive all three from LaunchDarkly, either:
- Use prompt **variables** on the config (`{{role}}`, `{{goal}}`, `{{backstory}}`) and pass them as the `variables` argument to `agent_config(...)`
- Or store a structured JSON blob in `instructions` and parse it in the app

Prompt variables are cleaner and keep the config human-readable in the UI.

### Strands `Agent`

Strands is a provider-agnostic, async-first agent SDK. The same `Agent` class runs against Anthropic, OpenAI, and Bedrock by swapping the `model` argument; tools are plain `@tool`-decorated Python functions passed through the constructor; and `SlidingWindowConversationManager` keeps short-term memory across `invoke_async` turns without external state. Agent-mode `instructions` maps directly to `Agent(system_prompt=...)`.

Strands does not ship a first-party LaunchDarkly provider package. To serve multiple providers from a single config key, dispatch on `agent_config.provider.name` and construct the matching Strands model class.

**Provider dispatcher.** Drop `parameters.tools` before passing params into the Strands model class — LaunchDarkly surfaces attached tools via a flat `parameters.tools` shape in the variation payload, but Strands receives tools via the `Agent` constructor. Passing `tools` through a second time via model `params` is an error.

```python
from strands.models.anthropic import AnthropicModel
from strands.models.openai import OpenAIModel


def create_strands_model(agent_config):
    """Map an LDAIAgentConfig to the matching Strands model class by provider."""
    provider = (agent_config.provider.name if agent_config.provider else "").lower()
    model_id = agent_config.model.name
    params = dict(agent_config.model.to_dict().get("parameters") or {})
    # LD surfaces attached tools via parameters.tools; Strands takes tools via
    # Agent(tools=[...]). Drop the key before passing params to the model class.
    params.pop("tools", None)

    if provider == "anthropic":
        # AnthropicModel requires max_tokens as a kwarg, not inside params.
        max_tokens = int(
            params.pop("max_tokens", None) or params.pop("maxTokens", None) or 1024
        )
        return AnthropicModel(model_id=model_id, max_tokens=max_tokens, params=params or None)
    if provider == "openai":
        # Pass parameters through as-is — gpt-5 wants max_completion_tokens,
        # gpt-4o wants max_tokens. Keep that choice in the LD variation.
        return OpenAIModel(model_id=model_id, params=params)
    raise ValueError(f"Unsupported provider for Strands: {provider!r}")
```

**Call site.** Build the agent once per request, pull the tracker off the config, and wrap `invoke_async` with `track_duration_of` — Strands is Tier 3 (custom extractor) because there is no provider package.

```python
from strands import Agent, tool
from strands.agent.conversation_manager.sliding_window_conversation_manager import (
    SlidingWindowConversationManager,
)
from ldai.client import AIAgentConfigDefault, ModelConfig, ProviderConfig
from ldai.tracker import TokenUsage
from ldclient import Context


@tool
def get_order_status(order_id: str) -> str:
    """Look up the status of a customer order by order ID."""
    ...


FALLBACK = AIAgentConfigDefault(
    enabled=True,
    model=ModelConfig(name="gpt-5", parameters={"max_completion_tokens": 2000}),
    provider=ProviderConfig(name="openai"),
    instructions="You are a helpful assistant.",
)


def track_strands_metrics(tracker, result):
    """Record token usage from a Strands AgentResult on the LD tracker.

    accumulated_usage aggregates tokens across every provider call in the turn,
    including tool-calling round trips — unlike the single-response shape from
    Anthropic or OpenAI direct.
    """
    usage = getattr(result.metrics, "accumulated_usage", {}) or {}
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    total = usage.get("totalTokens", 0) or (input_tokens + output_tokens)
    if total > 0:
        tracker.track_tokens(TokenUsage(input=input_tokens, output=output_tokens, total=total))


async def run_turn(ai_client, user_id: str, user_input: str):
    context = Context.builder(user_id).kind("user").build()
    agent_config = ai_client.agent_config("strands-agent", context, FALLBACK)

    if not agent_config.enabled:
        return disabled_response()

    agent = Agent(
        name="order-assistant",
        model=create_strands_model(agent_config),
        system_prompt=agent_config.instructions,
        tools=[get_order_status],
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )
    tracker = agent_config.create_tracker()

    try:
        result = await tracker.track_duration_of(lambda: agent.invoke_async(user_input))
        tracker.track_success()
        track_strands_metrics(tracker, result)
        return result.message["content"][0]["text"]
    except Exception:
        tracker.track_error()
        raise
```

**Key points:**
- `system_prompt=agent_config.instructions` — the instructions string replaces the hardcoded system prompt.
- `create_strands_model(agent_config)` is the provider-dispatch seam. Add a branch per provider the variation can serve.
- The tracker is Tier 3: `tracker.track_duration_of(...)` + an explicit `track_tokens` call fed by `track_strands_metrics`. See [strands-tracking.md](../../launchdarkly-built-in-metrics/references/strands-tracking.md) for the single-call `track_metrics_of_async` variant and the per-field breakdown of `accumulated_usage`.
- Always `ldclient.get().flush()` before process exit in short-lived scripts — trailing events can otherwise be lost.

**TypeScript caveat.** The Strands TypeScript SDK ships `BedrockModel` and `OpenAIModel` only — it cannot run Anthropic-backed variations. If the app needs to serve both OpenAI and Anthropic from a single config, use the Python SDK.

### Custom `StateGraph` (bind_tools + ToolNode)

The most common LangGraph pattern in the wild is not the prebuilt agent — it's a custom `StateGraph` with a `call_model` node that does `model.bind_tools(TOOLS)`, a separate `"tools"` node that runs `ToolNode(TOOLS)`, and a conditional edge between them. This is the shape of the `langchain-ai/react-agent` template.

Two things make it different from the prebuilt `create_agent`:

1. **Tools appear in two places** — `bind_tools(TOOLS)` (so the LLM knows which tools exist) and `ToolNode(TOOLS)` (so the executor knows how to run them). Both must read from the same source.
2. **The system prompt is injected manually** in the `call_model` node body (usually as the first message in the `ainvoke([{"role": "system", ...}, *state.messages])` call), not passed as a constructor argument.

Before — the typical template shape (`src/react_agent/graph.py`, `src/react_agent/tools.py`, `src/react_agent/context.py`):

```python
# tools.py
TOOLS: List[Callable[..., Any]] = [search]

# context.py
@dataclass(kw_only=True)
class Context:
    system_prompt: str = field(default=prompts.SYSTEM_PROMPT)
    model: str = field(default="anthropic/claude-sonnet-4-5-20250929")

# graph.py
from .tools import TOOLS

async def call_model(state: State, runtime: Runtime[Context]):
    model = load_chat_model(runtime.context.model).bind_tools(TOOLS)
    system_message = runtime.context.system_prompt.format(system_time=now_iso())
    response = await model.ainvoke(
        [{"role": "system", "content": system_message}, *state.messages]
    )
    return {"messages": [response]}

builder = StateGraph(State, context_schema=Context)
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge("__start__", "call_model")
builder.add_conditional_edges("call_model", route_model_output)
builder.add_edge("tools", "call_model")
graph = builder.compile()
```

After — **run-scoped** architecture. The critical shape for the tracker factory is that **one user turn = one `runId` = one tracker**, not one LLM call = one tracker. A ReAct loop that calls `call_model` three times in a single turn must not mint three trackers, or billing and the Monitoring tab will treat the turn as three separate executions. The fix is to resolve the config and mint the tracker once, in a dedicated entry node, and thread both through graph state for every subsequent node.

Three nodes, in order:

1. **`setup_run`** (entry) — resolves `agent_config`, mints the tracker with `create_tracker()`, builds `model` with `create_langchain_model(ai_config)`, builds tools via the factory pattern below, starts a `perf_counter_ns()` timer, and stashes all of it on `State`. Runs exactly once per turn.
2. **`call_model`** — reads model / tools / tracker / accumulator from `State`, runs `model.ainvoke(...)`, accumulates token usage, calls `tracker.track_tool_calls([...])` per step. **Does not** call `track_metrics_of_async` here — that wrapper records duration + success on every invocation and would fire once per iteration. On exception: call `tracker.track_duration` + `tracker.track_error` and re-raise (the finalize node will not run).
3. **`finalize`** (terminal) — runs exactly once at the end of the turn on the success path. Calls `tracker.track_duration(elapsed_ms)` + `tracker.track_tokens(accumulated)` + `tracker.track_success()`. Each of these fires exactly once per run, which is what the at-most-once guards enforce.

```python
# tools.py — tool factories close over per-run config, so tools never re-fetch
from typing import Any, Callable, Dict
from langchain_core.tools import StructuredTool
from langchain_tavily import TavilySearch

def make_search(ai_config) -> Callable[..., Any]:
    """Closure: capture `max_search_results` once at setup_run time."""
    max_results = ai_config.model.get_custom("max_search_results") or 10

    async def search(query: str) -> dict:
        """Search the web for current information on a given topic."""
        return await TavilySearch(max_results=max_results).ainvoke({"query": query})

    return search

# Registry of factories keyed by LD tool name. Each factory takes the
# per-run ai_config and returns a ready-to-bind callable. This decouples
# the Config (tool metadata) from the app (implementations) and
# means tools never call get_agent_config() themselves.
TOOL_FACTORIES: Dict[str, Callable[[Any], Callable[..., Any]]] = {
    "search": make_search,
}


# graph.py
import time
from typing import Any, Dict, List, TypedDict
from uuid import uuid4
from ldai_langchain import create_langchain_model, get_ai_metrics_from_response
from ldai_langchain.langchain_helper import build_structured_tools
from ldai.tracker import TokenUsage
from ldclient import Context as LDContext
from langchain_core.runnables import RunnableConfig
from .tools import TOOL_FACTORIES


# Run-scoped State. Fields below messages[] are non-serializable and only
# meaningful inside one turn — if you add a LangGraph checkpointer, exclude
# them from the checkpoint.
class State(TypedDict, total=False):
    messages: List[Any]                 # standard LangGraph messages reducer applies
    tracker: Any                        # LDAIConfigTracker, minted in setup_run
    model: Any                          # Bound chat model with per-run tools
    tools: List[Any]                    # StructuredTool list for this turn
    start_perf_ns: int                  # time.perf_counter_ns() at setup_run
    token_accumulator: TokenUsage       # Sum of usage_metadata across loop iterations
    disabled_message: str               # Set iff ai_config.enabled is False

# If the repo's State is a @dataclass (e.g., langchain-ai/react-agent),
# attribute access works the same — `state.tools` instead of `state["tools"]`.
# Same field set, same reducers (wrap the messages field with
# `Annotated[List[Any], add_messages]`). Don't convert during migration.


async def setup_run(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Runs once per user turn. Resolves the config, mints the tracker,
    builds the model and tools, and stashes everything on state.

    Node signature takes `config: RunnableConfig` rather than
    `runtime: Runtime[Context]` so the example works with an empty Context
    dataclass and reads `thread_id` from LangGraph's standard
    `config["configurable"]["thread_id"]` plumbing. If your app has a typed
    Context schema with fields beyond thread_id, use the Runtime[Context]
    signature instead and keep those fields on Context.
    """
    configurable = config.get("configurable") or {}
    ld_key = configurable.get("thread_id") or f"anon-{uuid4()}"
    ld_context = LDContext.builder(ld_key).kind("user").build()
    ai_config = get_ai_client().agent_config(
        "react-agent",
        ld_context,
        FALLBACK,
    )

    if not ai_config.enabled:
        # Return BOTH a flag the router can short-circuit on AND an AIMessage
        # appended to state["messages"]. Downstream consumers (UI, tests, the
        # caller that invoked the graph) read the last message — setting only
        # `disabled_message` without touching `messages` produces a graph
        # whose last-message shape depends on state entry, which surprises
        # readers. Every node return should leave `messages` in a valid shape.
        return {
            "disabled_message": "Feature is currently unavailable.",
            "messages": [AIMessage(content="Feature is currently unavailable.")],
        }

    # Three-tier tool-registry contract. Don't conflate these:
    #   1. TOOL_FACTORIES          — {name: factory}   at module scope (static, never changes)
    #   2. built_callables         — {name: callable}  per-run (factories applied to ai_config)
    #   3. tools (StructuredTool)  — per-run list, ready for bind_tools + ToolNode dispatch
    # build_structured_tools reads ai_config.model.parameters.tools to decide
    # which entries from built_callables to wrap — the LLM only sees the subset
    # the variation attached, even if the registry has more callables.
    built_callables = {name: fn(ai_config) for name, fn in TOOL_FACTORIES.items()}
    tools = build_structured_tools(ai_config, built_callables)

    return {
        "tracker": ai_config.create_tracker(),
        "model": create_langchain_model(ai_config).bind_tools(tools),
        "tools": tools,
        "start_perf_ns": time.perf_counter_ns(),
        "token_accumulator": TokenUsage(input=0, output=0, total=0),
        # Cache instructions so call_model doesn't touch ai_config again.
        "instructions": ai_config.instructions or "",
    }


async def call_model(state: State) -> Dict[str, Any]:
    """Reads model / tracker / tools from state. No LD access, no config fetch."""
    tracker = state["tracker"]
    model = state["model"]
    messages = [{"role": "system", "content": state["instructions"]}, *state["messages"]]

    try:
        response = cast(AIMessage, await model.ainvoke(messages))
    except Exception:
        elapsed_ms = (time.perf_counter_ns() - state["start_perf_ns"]) // 1_000_000
        tracker.track_duration(elapsed_ms)
        tracker.track_error()
        raise

    # Accumulate token usage across loop iterations; finalize emits the sum.
    acc = state["token_accumulator"]
    if getattr(response, "usage_metadata", None):
        um = response.usage_metadata
        state["token_accumulator"] = TokenUsage(
            input=acc.input + um.get("input_tokens", 0),
            output=acc.output + um.get("output_tokens", 0),
            total=acc.total + um.get("total_tokens", 0),
        )

    if response.tool_calls:
        tracker.track_tool_calls([call["name"] for call in response.tool_calls])

    return {"messages": [response]}


async def finalize(state: State) -> Dict[str, Any]:
    """Runs exactly once at the end of a successful turn. Emits the three
    once-per-run tracker events: duration, tokens, success."""
    tracker = state["tracker"]
    elapsed_ms = (time.perf_counter_ns() - state["start_perf_ns"]) // 1_000_000
    tracker.track_duration(elapsed_ms)
    acc = state["token_accumulator"]
    if acc.total > 0:
        tracker.track_tokens(acc)
    tracker.track_success()
    return {}


def route_after_setup(state: State) -> Literal["call_model", "__end__"]:
    return "__end__" if "disabled_message" in state else "call_model"


def route_model_output(state: State) -> Literal["tools", "finalize"]:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else "finalize"


async def tools_node(state: State) -> Dict[str, Any]:
    """Dynamic ToolNode wrapper — rebuilds dispatch per invocation.

    `ToolNode` builds its `{name: callable}` dispatch dict at construction
    time, so `ToolNode([])` cannot execute anything (dispatch returns
    "Error: <tool> is not a valid tool, try one of []." verbatim). Because
    our tool callables close over per-run `ai_config` (see TOOL_FACTORIES),
    we cannot pre-build the ToolNode at compile time — the concrete
    callables differ each turn. Construct a fresh ToolNode from
    state["tools"] per invocation.

    Two things to get right in the body:
    - Use `ainvoke`, not `invoke` — the enclosing nodes in this example
      are async and LangGraph will raise if a sync node is awaited.
    - Pass an explicit `{"messages": [...]}` payload rather than the full
      State dict — ToolNode's contract is that input shape, and passing
      extra fields has surprised users on some LangGraph versions.
    """
    return await ToolNode(list(state["tools"])).ainvoke(
        {"messages": list(state["messages"])}
    )


# No context_schema=Context here — Context can be empty or dropped entirely.
# thread_id and any other per-invocation plumbing flows through RunnableConfig
# via config["configurable"] (see setup_run). Add context_schema=Context only
# if your app truly has typed per-request context fields beyond thread_id.
builder = StateGraph(State)
builder.add_node(setup_run)
builder.add_node(call_model)
builder.add_node("tools", tools_node)  # NOT ToolNode([]) — see tools_node docstring
builder.add_node(finalize)
builder.add_edge("__start__", "setup_run")
builder.add_conditional_edges("setup_run", route_after_setup)
builder.add_conditional_edges("call_model", route_model_output)
builder.add_edge("tools", "call_model")
builder.add_edge("finalize", "__end__")
graph = builder.compile()
```

**Why this shape:**

- **One `create_tracker()` per turn** — `setup_run` is the only caller. Each factory call mints a fresh `runId`; per-iteration calls fragment the run downstream and reset the at-most-once guards.
- **One `agent_config(...)` per turn** — `setup_run` resolves once. Re-fetching in a loop step inflates agent-config event counts and lets a mid-turn targeting change swap variations between LLM calls.
- **`track_duration` / `track_tokens` / `track_success` fire in `finalize`, not `call_model`** — these are at-most-once; per-iteration calls are silently dropped.
- **`track_tool_calls` in `call_model` is fine** — it's per-event metadata, not at-most-once.
- **Tools close over per-run config** — `make_search(ai_config)` captures `max_search_results` at setup time. A mid-turn variation change doesn't affect the in-flight turn; the next turn picks up the new value.
- **`tools` node uses the `tools_node` wrapper, not `ToolNode([])`** — `ToolNode` builds its dispatch dict at construction, so an empty list produces empty dispatch and every tool call fails with `is not a valid tool`. The wrapper rebuilds per invocation from state.
- **Fallback instructions use Mustache** (`"...{{ system_time }}"`), not `.format()` — the SDK's Mustache renderer runs on both the LD-served path and the fallback path; single-brace placeholders ship a stale literal.

**Gotchas:**

- **Never call `track_metrics_of_async` in a loop node.** `trackMetricsOf` is designed for single-call shapes (one provider call, one `success` event). In a ReAct loop it would re-fire `track_success` per iteration and trip the at-most-once guard. Use manual `track_tool_calls` per step and explicit `track_duration` + `track_tokens` + `track_success` in `finalize`.
- **Lazy-init the `ai_client`.** Avoid `ai_client = LDAIClient(...)` at module import time — it couples test collection to LD initialization and makes the per-turn runId story harder to mock. Wrap with `def get_ai_client(): ...` and cache on first use.
- **Per-run `LDContext` keys — and their MAU cost.** A shared literal like `"anonymous"` collapses every request into one targeting/billing segment, which breaks experimentation and per-run segmentation. The obvious fix is to use the LangGraph `thread_id` if present and fall back to `uuid4()` per `setup_run`. **Before doing this in production, check the MAU impact:** LaunchDarkly bills by distinct context keys per month, so a production agent serving 100k anonymous runs/day will register 3M+ MAU even though there's no real user. Three shapes, pick the one that fits:
  1. **Known user identity (preferred).** If the caller knows who the user is (session cookie, auth token, SSO ID), use that as the context key. No anonymous keys at all. Targeting, segmentation, and MAU all work correctly.
  2. **Session-scoped key.** Use the LangGraph `thread_id`, or the chat-session ID, or whatever the longest-lived identifier is below "real user." MAU scales with session count, not turn count.
  3. **Per-turn `uuid4()`.** Only in demos, or if you genuinely need per-run isolation for experiment targeting and are willing to pay the MAU. Document the decision in the repo README so the next migrator doesn't swap it out without reading the tradeoff.
- **State field serialization.** If you add a LangGraph `checkpointer`, exclude the run-scoped fields (`tracker`, `model`, `tools`, `start_perf_ns`) from the checkpoint — they're non-serializable and only meaningful inside one turn anyway.

### Node.js — LangGraph.js `createReactAgent` (prebuilt)

For apps built on `@langchain/langgraph`'s prebuilt `createReactAgent`, the loop happens inside one `agent.invoke(...)` call — you don't own the nodes. That makes the run-scoped pattern simpler than the Python custom-`StateGraph` shape above: resolve `agentConfig` once, mint the tracker once, wrap the whole `agent.invoke` in one `tracker.trackMetricsOf(...)` call per user turn.

```typescript
import { init } from '@launchdarkly/node-server-sdk';
import { initAi, type LDAIAgentConfig, type LDAIMetrics } from '@launchdarkly/server-sdk-ai';
import { createLangChainModel } from '@launchdarkly/server-sdk-ai-langchain';
import { createReactAgent } from '@langchain/langgraph/prebuilt';
import { MemorySaver } from '@langchain/langgraph';

const ldClient = init(process.env.LD_SDK_KEY!);
await ldClient.waitForInitialization({ timeout: 10 });
const aiClient = initAi(ldClient);

// Sum token usage across every message the agent produced in one turn.
// Multiple fallback field names cover the provider variation LangChain
// normalizes over (OpenAI, Anthropic, Bedrock, Gemini, …).
function langgraphMetrics(result: any): LDAIMetrics {
  let input = 0, output = 0, total = 0;
  for (const msg of result.messages ?? []) {
    const usage = msg.response_metadata?.token_usage ?? msg.usage_metadata;
    if (!usage) continue;
    input += usage.input_tokens ?? usage.prompt_tokens ?? usage.promptTokens ?? 0;
    output += usage.output_tokens ?? usage.completion_tokens ?? usage.completionTokens ?? 0;
    total += usage.total_tokens ?? usage.totalTokens ?? 0;
  }
  if (total === 0) total = input + output;
  return { success: true, tokens: total > 0 ? { input, output, total } : undefined };
}

async function runTurn(userInput: string, threadId: string): Promise<string | null> {
  const context = { kind: 'user' as const, key: threadId };
  const agentConfig: LDAIAgentConfig = await aiClient.agentConfig(
    'react-agent',
    context,
    FALLBACK,                            // LDAIAgentConfigDefault literal
  );

  if (!agentConfig.enabled) return null;

  // Build everything once per user turn.
  const llm = await createLangChainModel(agentConfig);
  const agent = createReactAgent({
    llm,
    tools: buildTools(agentConfig),      // factory pattern — see below
    prompt: agentConfig.instructions,
    checkpointer: new MemorySaver(),     // reuse across turns if you want chat memory
  });

  // One tracker per user turn. Fresh runId. At-most-once guards reset.
  const tracker = agentConfig.createTracker();

  // Exceptions are tracked automatically — trackMetricsOf catches
  // exceptions, records tracker.trackError(), and re-throws.
  const result = await tracker.trackMetricsOf(
    langgraphMetrics,
    () => agent.invoke(
      { messages: [{ role: 'user', content: userInput }] },
      { configurable: { thread_id: threadId } },
    ),
  );
  const messages = result.messages ?? [];
  return messages.length ? String(messages[messages.length - 1].content) : null;
}
```

**Tool factories in TypeScript.** The same pattern as Python — a record of `(agentConfig) => tool` factories, applied per-turn so each tool closes over the live variation's `model.custom` knobs:

```typescript
import { tool } from '@langchain/core/tools';
import { z } from 'zod';

type ToolFactory = (agentConfig: LDAIAgentConfig) => ReturnType<typeof tool>;

function makeSearch(agentConfig: LDAIAgentConfig) {
  const maxResults =
    (agentConfig.model?.custom?.max_search_results as number | undefined) ?? 10;
  return tool(
    async ({ query }: { query: string }) => {
      const res = await fetch(`https://api.tavily.com/search?q=${encodeURIComponent(query)}&n=${maxResults}`);
      return await res.json();
    },
    {
      name: 'search',
      description: 'Search the web for current information on a given topic.',
      schema: z.object({ query: z.string() }),
    },
  );
}

const TOOL_FACTORIES: Record<string, ToolFactory> = {
  search: makeSearch,
};

function buildTools(agentConfig: LDAIAgentConfig) {
  const attached = ((agentConfig.model?.parameters?.tools as Array<{ name: string }>) ?? [])
    .map((t) => t.name);
  return attached
    .filter((name) => name in TOOL_FACTORIES)
    .map((name) => TOOL_FACTORIES[name](agentConfig));
}
```

**Key differences from Python custom-`StateGraph`:**

- Because LangGraph.js's `createReactAgent` is prebuilt, you don't write a `setup_run` / `call_model` / `finalize` graph — `agent.invoke(...)` is the single call that represents the turn, so wrapping it in one `trackMetricsOf` call is sufficient. The at-most-once guards are naturally satisfied by the single wrapping call.
- No dynamic `ToolNode` wrapper needed. `createReactAgent` takes a tool list at construction; construct the agent per-turn (inside `runTurn`) so the tools can close over the current `agentConfig`.
- Multi-turn chat: if you want `runTurn` to be called three times in a row for one session (shared `threadId` / `MemorySaver`), each call still mints its own tracker inside `runTurn`. The `threadId` threads conversation memory through `checkpointer`; the `runId` identifies each turn independently.

**Custom `StateGraph` in Node.js.** If the app uses a hand-rolled `StateGraph` with its own `call_model` / tool nodes (uncommon in Node compared to Python, but possible), the same run-scoped architecture from the Python section above applies — `setup_run` as an entry node, `tools_node` wrapper around `new ToolNode(state.tools).invoke(...)`, `finalize` as a terminal node. The TypeScript syntax differs but the node responsibilities are identical. Prefer `createReactAgent` unless the app genuinely needs graph-level control.

### Custom ReAct loop

The same run-scoped shape applies: one config fetch + one `create_tracker()` at the top of the turn, accumulate tokens across the loop, emit `track_duration` / `track_tokens` / `track_success` exactly once after the loop exits.

```python
import time
from ldai.tracker import TokenUsage

def run_turn(ai_client, user_id: str, user_input: str):
    context = Context.builder(user_id).kind("user").build()
    config = ai_client.agent_config("custom-react", context, FALLBACK)

    if not config.enabled:
        return disabled_response()

    # Resolve everything needed for the turn once, up top.
    system_prompt = config.instructions
    model_name = config.model.name
    tracker = config.create_tracker()
    tool_callables = build_tools_from_config(config)  # closes over config
    start_ns = time.perf_counter_ns()
    acc = TokenUsage(input=0, output=0, total=0)

    try:
        history = [{"role": "user", "content": user_input}]
        for step in range(MAX_TURNS):
            response = my_provider.complete(
                model=model_name,
                system=system_prompt,
                messages=history,
                tools=config.model.get_parameter("tools") or [],
            )

            # Accumulate token usage across the loop; finalize emits the sum.
            usage = extract_tokens(response)  # returns TokenUsage
            acc = TokenUsage(
                input=acc.input + usage.input,
                output=acc.output + usage.output,
                total=acc.total + usage.total,
            )

            tool_calls = extract_tool_calls(response)
            if tool_calls:
                tracker.track_tool_calls([c["name"] for c in tool_calls])
                history.extend(run_tools(tool_calls, tool_callables))
                continue

            # Done — fall through to the success emit block.
            break

        elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
        tracker.track_duration(elapsed_ms)
        if acc.total > 0:
            tracker.track_tokens(acc)
        tracker.track_success()
        return response
    except Exception:
        elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
        tracker.track_duration(elapsed_ms)
        tracker.track_error()
        raise
```

The call site stays in your control; the config just delivers `instructions`, `model.name`, `model.parameters`, and `tools`. Everything that's stable across the turn (model name, instructions, tool bindings, tracker) is hoisted out of the loop body — the loop itself only does message passing and tool dispatch.

**Do not** call `track_duration` / `track_tokens` / `track_success` inside the `for` body. The at-most-once guards will warn and drop the second-and-later calls on the same tracker, so per-step tracker calls will silently lose data. Accumulate inside the loop, emit once after.

## Dynamic tool loading — the "tools factory" pattern

The devrel-agents-tutorial uses a **dynamic tool factory** that reads tool names from `config.tools` and instantiates the actual tool implementations at runtime. This decouples the config (which holds tool metadata) from the application (which holds the executable code).

### The pattern

```python
# tools_impl/dynamic_tool_factory.py — adapted from devrel-agents-tutorial

def extract_tool_names(config) -> list[str]:
    """Read the list of tool names from the config."""
    if not hasattr(config, "tools") or not config.tools:
        return []
    return [tool.name if hasattr(tool, "name") else tool.get("name") for tool in config.tools]


def create_dynamic_tools_from_launchdarkly(config) -> list:
    """Instantiate tool implementations for every tool name on the config."""
    tool_names = extract_tool_names(config)
    instances = []
    for name in tool_names:
        tool = _create_tool_instance(name)
        if tool is not None:
            instances.append(tool)
    return instances


def _create_tool_instance(tool_name: str):
    """Map a tool name to an actual implementation. Add one branch per tool."""
    if tool_name == "search_kb":
        from my_tools.search import SearchKBTool
        return SearchKBTool()
    elif tool_name == "calculator":
        from my_tools.calc import CalculatorTool
        return CalculatorTool()
    # ... etc
    return None
```

Then at the call site:

```python
config = ai_client.agent_config("support-agent", context, FALLBACK)
tools = create_dynamic_tools_from_launchdarkly(config)

agent = create_agent(
    build_llm(config),
    tools,
    system_prompt=config.instructions,
)
```

**What this gives you:**

- Toggle a tool on/off by editing the config in LaunchDarkly — no redeploy needed to remove a tool from production
- Roll out a new tool to 5% of users by editing targeting rules (combined with `launchdarkly-configs-targeting`)
- Keep the actual tool implementation code in the repo; only metadata lives in LaunchDarkly

### Extracting schemas from existing hardcoded tools

If your tools are defined with LangChain `@tool` or Pydantic `BaseModel` schemas, extract the JSON schema programmatically to pass to `launchdarkly-tools` during Stage 3:

```python
from my_tools import search_kb  # a @tool-decorated function

schema = search_kb.args_schema.model_json_schema()
# schema is a dict ready to pass as the tool's parameters field
```

Do not hand-write the schema — LangChain already generated it from the function signature, and Pydantic will keep it in sync. The `launchdarkly-tools` delegate accepts raw JSON Schema for the parameters field.

### Dynamic schemas from LaunchDarkly

The devrel tutorial also shows the reverse: reading a JSON schema **from** the config and constructing a Pydantic model at runtime:

```python
from pydantic import BaseModel, Field, create_model

def _create_dynamic_tool_input(tool_config: dict) -> type[BaseModel]:
    """Build a Pydantic input schema from a config tool's parameters."""
    properties = tool_config.get("properties", {})
    fields = {}
    for name, cfg in properties.items():
        py_type = {"string": str, "number": float, "integer": int, "boolean": bool}.get(
            cfg.get("type"), str
        )
        default = ... if name in tool_config.get("required", []) else None
        fields[name] = (py_type, Field(default=default, description=cfg.get("description", "")))
    return create_model("DynamicToolInput", **fields)
```

This lets LaunchDarkly change a tool's parameter schema without redeploying the app. Use it when the tool implementation is generic enough to accept any parameter shape (e.g. a proxy that forwards requests to an external API). For most tools, a static Pydantic schema in the repo is simpler.

## Routing / multi-node hint

If the framework needs to pick between multiple downstream agents (e.g. a supervisor that routes to a security agent or a support agent based on the user input), do **not** roll your own routing. Use LaunchDarkly agent graphs — the graph's edges carry the routing contract, and the supervisor's `instructions` can be auto-injected with the valid routes.

The devrel tutorial's `generic_agent.py` shows a minimal version of this:

```python
# If this node has outgoing edges with routes, inject them into instructions
if self.valid_routes:
    route_instruction = (
        f"\n\nYou must select one of these routes: {self.valid_routes}. "
        f'Return your choice in JSON format: {{"route": "<selected_route>"}}'
    )
    instructions = instructions + route_instruction
```

For the full graph pattern, read [agent-graph-reference.md](agent-graph-reference.md) — but again, single-agent migration comes first, and agent graphs are currently **Python-only** in the SDK.

## Keep the provider call in the repo

One rule that applies across all three frameworks: the **provider SDK call** (OpenAI, Anthropic, Bedrock) stays in your code. The config only changes the inputs to that call — model name, instructions, parameters, tool list. It does not replace the provider SDK. That means:

- You keep full control of error handling, retries, timeouts, custom headers
- You keep full control of streaming logic and backpressure
- You keep full control of authentication (API keys, IAM roles, Bedrock Converse sessions)
- The config is additive — removing it gets you back to the original hardcoded app, provided the fallback mirrors the old values
