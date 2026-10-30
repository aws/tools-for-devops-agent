---
name: launchdarkly-tools
description: "Give your agents capabilities through tools (function calling). Helps you identify what your agent needs to do, create tool definitions, and attach them to config variations."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0"
---

# Config Tools

You're using a skill that will guide you through adding capabilities to your agents through tools (function calling). Your job is to identify what your agent needs to do, create tool definitions, attach them to variations, and verify they work.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `create-ai-tool` -- create a new tool definition with a schema
- `update-ai-config-variation` -- attach tools to a config variation
- `get-ai-config` -- verify tools are attached to the variation

**Optional MCP tools:**
- `list-ai-tools` -- browse existing tools in the project
- `get-ai-tool` -- inspect a specific tool's schema

## Core Principles

1. **Start with Capabilities**: Think about what your agent needs to do before creating tools
2. **Framework Matters**: LangGraph/CrewAI often auto-generate schemas; OpenAI SDK needs manual schemas
3. **Create Before Attach**: Tools must exist before you can attach them to variations
4. **Verify**: The agent fetches the config to confirm attachment
5. **Complete the Full Workflow**: Listing existing tools is a discovery step, not the end goal. After listing, always proceed to create the requested tool, attach it, and verify. Do not stop after exploration.

## Workflow

### Step 1: Identify Needed Capabilities

What should the agent be able to do?
- Query databases, call APIs, perform calculations, send notifications
- Check what exists in the codebase (API clients, functions)
- Consider framework: LangGraph/LangChain auto-generate schemas; direct SDK needs manual schemas

If the user asks to check existing tools first, or you have no codebase context about what tools exist, follow this exact order:
1. `list-ai-tools` -- explore what exists
2. `create-ai-tool` -- create the new tool (with a key different from existing ones)
3. `update-ai-config-variation` -- attach it
4. `get-ai-config` -- verify

Call `list-ai-tools` as your **first** tool call before any creation. Never stop after listing alone -- always proceed through all four steps.

### Step 2: Create Tools

Use `create-ai-tool` with:
- `key` -- unique identifier for the tool
- `description` -- clear description (the LLM uses this to decide when to call the tool)
- `schema` -- raw JSON Schema (do NOT use the OpenAI function calling wrapper):

```json
{
  "type": "object",
  "properties": {
    "query": {"type": "string", "description": "Search query"},
    "limit": {"type": "integer", "default": 10}
  },
  "required": ["query"]
}
```

### Step 3: Attach to Variation

Use `update-ai-config-variation` to attach tools. **Pass only the `tools` field.** Do not bundle `instructions`, `messages`, `model`, or `parameters` into this PATCH unless the user has explicitly asked you to also update those fields. Those fields may have been edited in the LaunchDarkly UI since the variation was created, and including them in a tool-attachment PATCH will silently clobber the UI edits.

```json
{
  "projectKey": "my-project",
  "configKey": "support-chatbot",
  "variationKey": "default",
  "tools": [
    {"key": "search-knowledge-base", "version": 1}
  ]
}
```

If you observe a UI-clear bug where attaching tools wipes other fields, **do not work around it by re-sending those fields from the previous `get-ai-config` response** — that masks the bug and can resurrect stale values that the user has since edited. Report the bug instead.

### Step 4: Verify

1. Use `get-ai-tool` to confirm the tool exists with a valid schema
2. Use `get-ai-config` to confirm the tool is attached to the variation (check `tools` in the variation's output)

**Report results:**
- Tool created with valid schema
- Tool attached to variation
- Flag any issues

## Per-provider schema at the call site

LaunchDarkly stores the tool schema once — the flat `{type, name, description, parameters}` shape you passed to `create-ai-tool`. Your application reads it back via `config.model.parameters.tools` (completion mode) or `agent_config.model.parameters.tools` (agent mode), then converts to the shape the provider SDK expects. LaunchDarkly never makes the provider call; your code does. The handlers that implement each tool also stay in application code — LaunchDarkly stores the schema, your application owns the behavior.

| Provider / framework | Target shape | Where it goes on the call |
|---|---|---|
| OpenAI Chat Completions (direct SDK) | `{type: "function", function: {name, description, parameters}}` | top-level `tools=[...]` |
| Anthropic direct SDK | `{name, description, input_schema}` — rename `parameters` → `input_schema` | top-level `tools=[...]` |
| Bedrock Converse | `{toolSpec: {name, description, inputSchema: {json: parameters}}}` | inside `toolConfig.tools=[...]` |
| Gemini (`google-genai`) | `{function_declarations: [{name, description, parameters}]}` (Python) / `{functionDeclarations: [...]}` (Node) | `GenerateContentConfig.tools=[...]` |
| OpenAI Responses API | LaunchDarkly's flat shape passes through unchanged | top-level `tools=[...]` |
| LangChain / LangGraph | `createLangChainModel(config)` (Node) / `create_langchain_model(config)` (Python) and pass `ai_config.tools` (or your own `StructuredTool` list) into `bind_tools(...)` / `create_react_agent(tools=[...])` | framework-native; no per-call conversion |
| Strands Agents | LaunchDarkly's flat shape; drop `parameters.tools` before passing params to the Strands model class (`AnthropicModel`, `OpenAIModel`) — Python `@tool`-decorated callables stay in code | `Agent(tools=[...])` constructor; no per-call conversion |

Minimal conversion snippets (Python):

```python
ld_tools = (ai_config.model.to_dict().get("parameters") or {}).get("tools", []) or []

# OpenAI Chat Completions
openai_tools = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("parameters", {"type": "object", "properties": {}}),
        },
    }
    for t in ld_tools
]

# Anthropic
anthropic_tools = [
    {
        "name": t["name"],
        "description": t.get("description", ""),
        "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
    }
    for t in ld_tools
]

# Bedrock Converse
bedrock_tool_config = {
    "tools": [
        {
            "toolSpec": {
                "name": t["name"],
                "description": t.get("description", ""),
                "inputSchema": {"json": t.get("parameters", {"type": "object", "properties": {}})},
            }
        }
        for t in ld_tools
    ]
}

# Gemini
gemini_tools = [
    {
        "function_declarations": [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in ld_tools
        ]
    }
] if ld_tools else []
```

## Agent loop with tool calls

An agent that uses tools runs a short loop: call the provider, dispatch any tool calls, loop again, stop when the provider returns a final answer. Three rules apply regardless of provider:

1. **Bound the loop.** `MAX_STEPS = 5` is a safe default. A runaway tool loop is almost always a prompt or schema bug, not a case that needs 50 iterations.
2. **Track every tool invocation.** Call `tracker.track_tool_call(tool_name)` / `tracker.trackToolCall(toolName)` for each tool the agent actually executes. This is what the Monitoring tab counts as tool usage.
3. **Break on the provider's "no more tool calls" signal.** The exact signal differs per provider: OpenAI Chat Completions → `choice.finish_reason != "tool_calls"`; Anthropic → `response.stop_reason != "tool_use"`; Bedrock Converse → `response["stopReason"] != "tool_use"`; Gemini → `response.function_calls` empty; OpenAI Responses API → no `function_call` items in `response.output`.

Skeleton (Python, Anthropic — the other providers follow the same shape with their own stop-reason check and tool-result formatting):

```python
messages = [{"role": "user", "content": initial_input}]
MAX_STEPS = 5
for _ in range(MAX_STEPS):
    response = tracker.track_metrics_of(
        anthropic_metrics,
        lambda: anthropic_client.messages.create(
            model=agent.model.name,
            system=agent.instructions,
            messages=messages,
            tools=anthropic_tools,
            **params,
        ),
    )
    if response.stop_reason != "tool_use":
        break

    messages.append({"role": "assistant", "content": response.content})

    tool_results = []
    for block in response.content:
        if block.type != "tool_use":
            continue
        if block.name not in tool_handlers:
            raise ValueError(f"Unknown tool: {block.name}")
        result = tool_handlers[block.name](**block.input)
        tracker.track_tool_call(block.name)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": result,
        })
    messages.append({"role": "user", "content": tool_results})
```

Per-provider tool-call payload shapes live in the `launchdarkly-built-in-metrics` references:

- [openai-tracking.md](../launchdarkly-built-in-metrics/references/openai-tracking.md) — Chat Completions + Responses API
- [anthropic-tracking.md](../launchdarkly-built-in-metrics/references/anthropic-tracking.md) — `tool_use` blocks and `tool_result` payloads
- [bedrock-tracking.md](../launchdarkly-built-in-metrics/references/bedrock-tracking.md) — `toolUse` / `toolResult` Converse format
- [gemini-tracking.md](../launchdarkly-built-in-metrics/references/gemini-tracking.md) — `functionCalls` / `functionResponse` parts
- [langchain-tracking.md](../launchdarkly-built-in-metrics/references/langchain-tracking.md) — LangGraph tool loop inherits from `create_react_agent`

## Orchestrator Note

LangGraph, CrewAI, and AutoGen often generate schemas from function definitions. You still need to create tools in LaunchDarkly and attach keys to variations so the SDK knows what's available.

## Edge Cases

| Situation | Action |
|-----------|--------|
| Tool already exists (409) | Use existing or create with different key |
| Schema invalid | Use raw JSON Schema format (type: object, properties, required) |
| Wrong endpoint assumed | The tools use `/ai-tools`, not `/ai-configs/tools` |

## What NOT to Do

- Don't try to attach tools during config creation -- update the variation afterward
- Don't skip clear tool descriptions (LLM needs them to decide when to call)
- Don't forget to verify attachment after updating the variation
- Don't bundle `instructions`, `messages`, `model`, or `parameters` into the tool-attachment PATCH. Send `tools` alone unless the user explicitly asked for a multi-field update — bundled PATCHes silently clobber UI edits to the other fields.

## Related Skills

- `launchdarkly-configs-create` -- Create config before attaching tools
- `launchdarkly-configs-variations` -- Manage variations with different tool sets
