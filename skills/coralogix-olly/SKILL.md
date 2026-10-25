---
name: coralogix-olly
description: '- Use when the user wants to investigate or analyze data in Coralogix, or explicitly asks to use Olly. Examples: "ask Olly", "why is my service slow", "what alerts fired", "investigate this incident", "analyze errors", "explain this spike".'
metadata:
  author: "coralogix"
  version: "1.0.0"
  tier: "partner-managed"
aws-devops-agent-skills:
  agent-types: "CHAT,INCIDENT_TRIAGE,INCIDENT_RCA,INCIDENT_MITIGATION"
---

# Olly Observability Agent Skill

Use this skill to interact with Coralogix's Observability Agent (Olly) via MCP tools. Olly can analyze your observability data, answer questions about alerts, metrics, logs, and generate artifacts like charts and reports.

When calling Olly via MCP, `agent_to_agent_mode` defaults to `true`. Olly acts as a **sub-agent** to you (the parent agent): it runs shorter, asks clarifying questions instead of guessing when context is missing, relies on your broader context, and skips charts/tables (returns previews, citations, and text instead).
Pass `false` if you don't have context to share (like quick access to source files) or if the created chat is only for human usage.

## MCP Tools

| Tool | Purpose | Key parameters |
|------|---------|----------------|
| `olly_ask` | Send a message to the Observability Agent | `message`, `chat_id`, `model`, `should_block`, `agent_to_agent_mode` |
| `olly_get_interaction` | Poll an interaction started in background | `chat_id`, `interaction_id` |
| `olly_list_chats` | List user's chat sessions | - |
| `olly_get_chat` | Get a chat with full history | `chat_id` |
| `olly_list_artifacts` | List all generated artifacts | `chat_id` (optional) |
| `olly_get_artifact` | Get artifact content by ID | `artifact_id` |

## Chat Commands

### Ask Olly (default: async)

`olly_ask` defaults to `should_block=False`: it returns immediately with `status=in_progress` instead of waiting. Use this for investigations and any non-trivial request, and poll with `olly_get_interaction` until terminal:

```python
result = olly_ask(message="Why is the checkout service showing high latency?")
chat_id, interaction_id = result["chat_id"], result["interaction_id"]

status = result["status"]
while status == "in_progress":
    time.sleep(30)  # pace polling; investigations can take a while
    result = olly_get_interaction(chat_id=chat_id, interaction_id=interaction_id)
    status = result["status"]

response = result["response"]
```

`chat_id` starts a new chat; pass an existing one to continue the conversation with context (e.g. `olly_ask(message="What changed in the last hour?", chat_id=chat_id)`).

For a short question you expect Olly to answer almost immediately, pass `should_block=True` instead to skip polling:

```python
olly_ask(message="What alerts fired today?", should_block=True)["response"]
```

### List previous chats

```python
olly_list_chats()
```

Returns all chat sessions for the current user. Use to find a previous conversation to continue.

### Get chat history

```python
olly_get_chat(chat_id="<chat-id>")
```

Returns the full conversation history including all messages and responses.

### Model selection

The `model` parameter is optional. If omitted, the Olly API uses its default.

To see currently supported models, ask Olly directly, for example:

```python
olly_ask(message="What models do you support?")
```

You can pass `model` on any `olly_ask` call when the user specifies one:

```python
olly_ask(message="Explain this error", model="<model-id>")
```

## Response format

### `olly_ask` / `olly_get_interaction` response

```json
{
  "chat_id": "chat-uuid-123",
  "interaction_id": "interaction-uuid-456",
  "status": "completed",
  "response": "Here are the results..."
}
```

| Field | Description |
|-------|-------------|
| `chat_id` | Unique chat session ID — **save this** for follow-up questions |
| `interaction_id` | This turn's interaction ID — **save this** to poll with `olly_get_interaction` |
| `status` | Interaction status (see table below) |
| `response` | Olly's text answer, or a user-facing fallback if no assistant text. Absent when async and still `in_progress` — a `note` field is present instead, telling you to poll |

### Status values

| Status | Meaning | Action |
|--------|---------|--------|
| `completed` | Success, response available | Use the response |
| `in_progress` | Still processing (expected right after an async `olly_ask` call) | Poll with `olly_get_interaction` until status is terminal |
| `error` | Failed | Check error message, retry with different query |
| `stopped` | Cancelled/interrupted | Retry if needed |

### `olly_list_artifacts` response

```json
[
  {
    "id": "artifact-123",
    "type": "coralogix_logs",
    "chat_id": "chat-456",
    "interaction_id": "interaction-789",
    "created_at": "2024-01-15T10:30:00Z",
    "chat_title": "Latency investigation"
  }
]
```

### `olly_get_artifact` response

```json
{
  "id": "artifact-123",
  "type": "coralogix_logs",
  "download_url": "https://storage.../presigned-url",
  "params": {
    "query": "source logs | filter ...",
    "description": "Error logs from checkout service"
  }
}
```

The `download_url` returns a link to the artifact in gzip-compressed JSON format.

## Artifacts

Olly can generate artifacts like query results, previews, and citations. Artifact IDs may appear in the response.

### List all artifacts

```python
olly_list_artifacts()
# Or filter by chat:
olly_list_artifacts(chat_id="<chat-id>")
```

### Get artifact content

```python
olly_get_artifact(artifact_id="<artifact-id>")
```

Returns:
- `download_url` — pre-signed link to the artifact in gzip-compressed JSON format
- `type` — artifact type (coralogix_logs, coralogix_spans, coralogix_metrics, etc.)
- `params` — query details (e.g., DataPrime query used)

### Artifact types

| Type | Description |
|------|-------------|
| `coralogix_logs` | DataPrime log query results |
| `coralogix_spans` | DataPrime span/trace query results |
| `coralogix_metrics` | PromQL metrics query results |
| `alert_watch_data` | Alert trigger data with associated query results |
| `kubernetes_query_results` | Kubernetes resource query results |

## Workflow Examples

### Investigate an issue

```python
# Start investigation and poll until terminal (see polling pattern above)
result = olly_ask(message="Why is the checkout service showing high latency? Check logs with `checkout:` strings and aws related metrics")
chat_id = result["chat_id"]
# ... poll olly_get_interaction until status != "in_progress" ...

# Follow up with context, then poll that interaction to terminal too
result = olly_ask(message="What changed in the last hour?", chat_id=chat_id)
# ... poll olly_get_interaction until status != "in_progress" ...

# Get any generated artifacts (safe now that both interactions are terminal)
for artifact in olly_list_artifacts(chat_id=chat_id):
    olly_get_artifact(artifact_id=artifact["id"])
```

### Get generated data

```python
# List recent artifacts
artifacts = olly_list_artifacts()

# Get the content of an artifact
artifact = olly_get_artifact(artifact_id="<id>")
# Use artifact["download_url"] to fetch the actual data
```

## When to use Olly vs direct tools

**Use `olly_ask` when:**
- User needs multi-step investigation across logs, metrics, alerts
- User doesn't know the exact DataPrime or PromQL syntax
- User wants AI-guided analysis with explanations

**Use direct tools when:**
- User provides a specific DataPrime query → use `query_dataprime`
- User asks about alerts or incidents → use `olly_ask`
- User asks about specific metrics with PromQL → use `query_promql_instant` or `query_promql_range`
- User needs raw log/span data with precise filters → use `query_dataprime`

To summarize: if the user is asking for simple data retrieval or straightforward information, use the other available tools instead of Olly.

Use Olly when the request requires investigation, analysis, or understanding what happened (for example, troubleshooting an issue, identifying root causes, or analyzing system behavior), or when the user explicitly asks to use Olly.

## Common pitfalls

- **Forgetting `chat_id`** — Always save the `chat_id` from the first response. Without it, follow-up questions lose context and start a new conversation.
- **Costly feature not enabled** — Olly tools are hidden unless the `x-allow-costly-use: true` header is set. If tools are missing, check this header.
- **403 errors** — Surface the API ``detail`` from the error to the user. You cannot verify API key scopes, quota, subscription status, or log/trace permissions from here.
- **Using Olly for specific queries** — Olly is for observability investigation, not for simple questions that can be answered with other tools (for example, when the user already provided exact DataPrime or PromQL). Use `query_dataprime`, `query_promql_instant`, or `query_promql_range` directly in those cases.
- **Empty assistant text** — If Olly returns no assistant text, `response` includes a short fallback (for example, error with retry guidance, stopped, or no response received).
- **Missing artifact data** — The artifact `download_url` returns a link to a gzip-compressed JSON file. Decompress it before parsing.

## Key principles

- **Async by default** — `olly_ask` defaults to `should_block=False`; poll with `olly_get_interaction` until the status is terminal. Only pass `should_block=True` for short questions you expect Olly to answer almost immediately — never for multi-step investigations.
- **Chat IDs enable context** — save the `chat_id` from responses to continue conversations
- **Artifact IDs are in responses** — look for artifact references when Olly generates data
- **Optional model parameter** — ask Olly which models are supported when the user needs a specific model
- **Check source code before asking** — Give Olly concrete context from the source code if available, such as which metric to start investigating from, before calling it.
- **Limit investigation scope** - Guide Olly to the correct limited scope. For example limit to just logs or to specific time ranges.

## Related skills

- **DataPrime queries** — `skill://coralogix-dataprime/SKILL.md`
- **Log querying** — `skill://coralogix-logs/SKILL.md`
- **Trace querying** — `skill://coralogix-spans/SKILL.md`
- **Metrics querying** — `skill://coralogix-metrics-query/SKILL.md`
- **RUM (Real User Monitoring)** — `skill://coralogix-rum/SKILL.md`
