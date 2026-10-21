---
name: ai-center
description: Coralogix AI Center — observe, evaluate, and guard GenAI/LLM applications and agents. Use for questions or actions about the user's AI/GenAI applications or agents — their behavior, prompts/responses, chats, quality, hallucinations, guardrails, cost/tokens, evaluations/policies, model pricing or comparing or tracking agents over time. Combines GenAI span queries (via `query_dataprime`) with the `ai_center_*` / `manage_ai_*` configuration tools. Only load this skill when you have an indication that GenAI is related.
metadata:
  author: coralogix
  version: 1.0.0
---

# AI Center — analyzing GenAI interactions, quality & platform health

## Background

**AI Center is Coralogix's native generative-AI observability and security platform.** It captures every LLM interaction as OpenTelemetry GenAI spans and gives full-stack visibility into AI applications — what users ask, how well the AI answers, where it hallucinates, token usage and cost, latency, errors, security risks, and guardrail/evaluation outcomes. It exists because GenAI apps are black boxes by default: teams can't see hallucinations, cost overruns, prompt-injection/PII risks, or quality regressions. AI Center closes that gap.

Capabilities you support (a question may span several of these):
- **Monitoring / Observability** — interactions, cost, tokens, latency, errors, usage per app/model/user.
- **Evaluations** — automatically score interaction quality/security/compliance against policies (results land on spans as tags).
- **Guardrails** — real-time blocking of harmful/non-compliant prompts or responses via the `cx-guardrails` SDK.
- **AI‑SPM (AI Security Posture Management)** — discover AI usage across code (GitHub scan), security posture score, risky users.

Two data sources:
- **Telemetry** — GenAI spans, queried with **`query_dataprime`** (`source spans`). Use for content, cost, tokens, latency, errors, usage, and issues over time. See the **`coralogix-spans`** (`skill://coralogix-spans/SKILL.md`) and **`dataprime`** (`skill://dataprime/SKILL.md`) skills for span querying and DataPrime syntax.
- **Configuration** — the **`ai_center_*`** (read) and **`manage_ai_*`** (write) tools. Use for the AI app inventory, configured evaluations/policies, custom evaluations, and model pricing — none of which live in spans.

## Objectives
- Answer from **real telemetry**: for content/quality questions read the actual interactions (report coverage — see Golden rule); for everything else compute from tags/aggregations.
- **Compose your own minimal scoped query for exactly what's asked.** The widget reference below teaches how each widget query is built — use it as your inspiration: when a question maps to a widget logic, adapt that widget's DataPrime query; when it doesn't, build your own query, and be helped and inspired with the logic of the closest/related widgets to compose the query. Always apply the GenAI filter and inject the user's params (timeframe, app, model, user).
- Back findings with **evidence** — quoted messages, traceIDs, concrete counts, etc. (a trend is an insight you draw, not evidence) — and suggest next steps. Cite the `traceID` of any interaction you reference.

## Golden rule: read the interactions, not just the verdicts

Each interaction's **GenAI spans** carry the **conversation** plus model, tokens, cost, latency, errors, and tool calls. Two conventions store the conversation — current (`gen_ai.input.messages` / `gen_ai.output.messages`) and older indexed (`gen_ai.prompt.<n>` / `gen_ai.completion.<n>`), depending on the app's instrumentation; see the two-conventions note below for each one's exact shape and how to read it. Evaluations, when configured, add **optional** verdict tags on the GenAI span; guardrails are **optional** too and live on **separate** guardrail spans (`otel.library.name == 'cx_guardrails.client'`). **Match the data to the question:** for **content** questions (quality, hallucination, sentiment, frustration, satisfaction, topics) read the conversation and reason about it; for everything else use the relevant tags/attributes. For plain dialogue read the **`user`**/**`assistant`** turns, but the **`system`**/**`tool`** turns matter too when you're debugging an agent or sub-agent (the tool calls it made and the task it was given). The system prompt lives in the `gen_ai.system_instructions` tag **or** the `role:'system'` turn: the first `role:'system'` message inside `gen_ai.input.messages` (current) / `gen_ai.prompt.0.content` when `gen_ai.prompt.0.role == 'system'` (indexed). Check both places.

**Reading conversation content:** read the interactions the question needs. The query result tells you how many matched vs. how many you read; **always report both to the user** (e.g. "312 interactions matched; I read 100").

**Cap the volume first — sample, don't read them all.** When the answer comes from **reading the conversations** (satisfaction, sentiment, topics, quality, "read the last day and tell me if X", summaries), never run the heavy query over *all* of an app's interactions — cap to **≤150** (100 default; 50–150 when each unit is large) and run the heavy query over that sample only.

**Do NOT sample in two cases:**
1. **An exact metric** — the user wants a precise number: `count`/`distinct_count`, sums (cost, tokens), error/issue rates, percentiles, "how many…". Compute over *all* matching data (still scoped by a tight time window + indexed filters); a sample would give a wrong number.
2. **A specific target or a needle** — a given `traceID`, one user's session, "the last 5 traces", or "does **any** interaction do X / find the one where…". Filter **directly** to the target (for a needle, filter on the condition itself and read/count the matches) — sampling could miss it.
- **Trace-level questions** (read one interaction at a time — satisfaction, sentiment, topics, per-session content): do it in **two steps**. *Step 1* — get the capped distinct trace IDs (cheap, IDs only) by placing `| distinct $d.traceID | limit <N>` right after the GenAI filter:
```dataprime
source spans
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))
| filter tags['gen_ai.input.messages'] != null || tags['gen_ai.output.messages'] != null || tags['gen_ai.prompt.0.role'] != null   // only if the question needs the conversation (covers both conventions)
| distinct $d.traceID
| limit 100
```
*Step 2* — paste the returned IDs into an `arrayContains` filter, then run the requested (heavy) query over **only** those traces:
```dataprime
source spans
| filter ['TRACE_1','TRACE_2', … ].arrayContains($d.traceID)   // the IDs from step 1
| … the requested query …
```
- **Span-level questions** (work per span, no per-interaction grouping): skip the ID round-trip — add `| limit <N>` (≤150) right after the GenAI spans filter, then run the heavy query over that capped set.

(The same two-step cap applies to the indexed convention below — cap the trace IDs first, then read.)

**These are skeleton examples, not copy-paste queries.** Keep the GenAI filter and add the question's own scope to the sampling query — time window, app (`$l.applicationName`/`$l.subsystemName`), user/model — match the message filter to the app's convention (current `gen_ai.input.messages` / `gen_ai.output.messages` or older indexed `gen_ai.prompt.<n>`). Step 2 inherits the scope through the trace IDs.

Aggregations (counts, cost, error/issue rates, score distributions), inventory, and the `ai_center_*` / evaluation / model queries return **all matching data** within the query window. `query_dataprime` defaults to the **last 1 hour** when you don't pass a range — set a wider window (e.g. the last 1 day) when the question needs more history, and only if the user hasn't asked for a specific window.

**Scope before you scan.**
- **Anchor on indexed fields first.** Lead with the indexed labels/metadata (`$l.subsystemName`, `$l.applicationName`, `$m.timestamp`) plus the GenAI filter so the engine narrows the set *before* you match or read un-indexed `$d.*` payload fields; a query that filters only on deep `$d.*` paths scans everything in the window.
- **Discover an unknown field cheaply — don't guess it with full scans.** When you don't know which field holds a value (a company/team/user name, an id), run one cheap discovery step — `search_for_fields` (scoped to `source spans`, see the `coralogix-spans` skill) or a tiny `limit 5` sample over a small window — and read the keys, instead of re-running wide scans one candidate field at a time.

**Listing one row per trace/interaction** (e.g. "the last 5 traces"): use a **projection** — `… | choose … | dedupeby trace_id keep 1 orderby <ts> desc` — **not** `groupby … aggregate max_by(...)`. A trace listing is a set of rows, not an aggregation; aggregating collapses to one row per group and mangles the message-content columns. Keep message fields as plain `choose` string columns (`… :string as input_messages`).

You usually **won't know the exact `applicationName`/`subsystemName` up front** — call `ai_center_list_applications` first to get the exact pairs. The app filter is **optional**: keep it to scope to one app, **drop it** for org-wide questions, or **group by** `$l.applicationName, $l.subsystemName` for comparative ones (e.g. "which region is most active").

Example — reading a conversation (just a template — keep, drop, or add lines as the question needs; e.g. drop the app/subsystem filter for a global/org-wide question like overall satisfaction):
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'   // scope to one app (the pair); optional — drop for global/org-wide questions
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))   // the GenAI filter (OTel semconv); exclude coding-agent services
| filter tags['gen_ai.input.messages'] != null   // spans that carry the conversation (no :string cast — don't drop a structured value)
| choose $m.timestamp as ts, $d.traceID as trace_id,
         $l.applicationName as application, $l.subsystemName as subsystem,
         tags['gen_ai.conversation.id']:string as conversation,
         tags['gen_ai.request.model']:string as model,
         tags['gen_ai.input.messages']:string as input_messages,
         tags['gen_ai.output.messages']:string as output_messages
| orderby ts desc
```

## How AI Center data is stored

**Granularity (span vs. interaction):** an **AI span** = one AI operation (e.g. an LLM call, embeddings, a retrieval/agent/tool/workflow step, or a Guardrails SDK invocation). An **interaction** = the multiple spans under one `traceID` — one exchange (user input → [tool calls / guardrails / evals] → response) plus the surrounding spans and operations. "Interactions" = trace-level; "AI spans" = span-level.

**The count widgets are span-level — this matches the UI.** The Overview/Drilldown count widgets (**AI Spans**, **Errors**, **Guardrail Actions**) and the tool counts (Q10) use `count()`/`count_if()` over **spans**, exactly as the AI Center UI computes them (it counts spans, not deduplicated traces) — so a trace with several GenAI spans contributes several, by design. The only trace-level rate is **Issue Rate (Q9)**. If the user explicitly wants a deduplicated *interaction* count, use `distinct_count(traceID)` and say that's what you're reporting. For very high-cardinality counts, use `approx_count_distinct(traceID)` to avoid memory blowups when an exact number isn't needed.

**Find GenAI spans.** Query `source spans` and apply the GenAI filter — the same filter the AI Center UI runs (OTel GenAI semantic conventions, excluding coding-agent services, which AI Center reports separately):
```dataprime
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))
```
This matches AI Center's own counts. For views that also include guardrail spans (the **AI Spans** count, Issue-rate / Guardrail widgets), use the GenAI **+ guardrails** filter:
```dataprime
| filter ((tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))) || tags['otel.library.name']:string == 'cx_guardrails.client'
```
Guardrail spans are marked by `tags['otel.library.name'] == 'cx_guardrails.client'`; from there filter by whatever the question needs — `tags['guardrails.triggered'] == 'true'` for **triggered** guardrails, `== 'false'` for ones that **passed**, or the per-policy `gen_ai.{prompt|response}.guardrails.{policy}.triggered` tags for a specific guardrail.

> **Always scope to GenAI spans — every AI Center query.** AI Center is *only* about GenAI/AI applications. The GenAI filter above is **mandatory on every query** (one exception: **root-cause** analysis — pull the whole trace, including sibling non-GenAI spans; see Root cause), including org-wide "which app…?" questions. `source spans` also contains ordinary APM spans (lambdas, databases, HTTP services); if you omit the GenAI filter you'll compute AI Center metrics over non-AI traffic and return wrong answers — e.g. a non-AI service topping "highest error rate", or inflated counts/cost. An **AI application** is a GenAI (`$l.applicationName`,`$l.subsystemName`) pair — the apps returned by `ai_center_list_applications` and the GenAI filter — **not** every `applicationName` in spans. **AI error rate** = `otel.status_code == 'ERROR'` on **GenAI** spans (not generic `error=true`/HTTP 5xx across all spans). When unsure which apps are AI apps, get them from `ai_center_list_applications` and restrict to those.

**Scoping to an application.** An app is the **pair** (`$l.applicationName`, `$l.subsystemName`). A name may live in either field — if a filter returns nothing, try the other field, or run `search_for_fields` (scoped to `source spans`, see the `coralogix-spans` skill) with the name to find which field holds it and its exact value. Time = `$m.timestamp` (`roundTime($m.timestamp, <interval>ms)` for series); duration = `$m.duration` (µs).

**End-user identity** (for "who's using"/per-user):
```dataprime
| create user from firstNonNull(tags['gen_ai.request.user'], tags['enduser.id'], tags['user.id'], tags['traceloop.association.properties.user_id'], tags['langsmith.metadata.user_id'])
```

**Message formats.** `gen_ai.input.messages` / `gen_ai.output.messages` are JSON arrays of messages shaped `{role, parts:[{type, content}]}` (part `type` = `text`, `tool_call`, `tool_call_response`, and others — e.g. `reasoning` for the model's thinking, `blob`/`file`/`uri` for multimodal input). **Roles:** `user` = the end user's turn (has a `text` part); `assistant` = the model's turn (may carry `tool_call` parts requesting a tool); `tool` = a tool's output fed back to the model (`tool_call_response` parts — this lives under `role:'tool'`, **not** `role:'user'`); `system` = the system prompt (usually index 0). To read what the **user** asked, take the `text` parts of `role:'user'` messages; skip `tool`/`system`/`assistant` turns. The system prompt may live here **or** in `gen_ai.system_instructions` (check both) — skip it when reading dialogue, read it only for system-prompt questions.

**Extracting the conversation text.** The `…messages` value is a JSON string of `{role, parts:[{type, content}]}` objects. Parse it with the **`jsonobject`** extractor and keep only the `user`/`assistant` **`text`** turns — this structurally drops the system prompt and tool traffic (roles filtered to `user`/`assistant`, parts to `type:"text"`), so a `tool_call`/`tool_call_response` part is never mistaken for spoken text, and it's robust to escaping and turn order. **Cap first** (Step 1 in *Cap the volume first* — it samples trace IDs across both conventions), then extract the transcripts for those IDs with the query matching the app's convention. **Current convention** (`gen_ai.input.messages` / `gen_ai.output.messages`) — one clean transcript per span:
```dataprime
source spans
| filter ['TRACE_1','TRACE_2', … ].arrayContains($d.traceID)   // ← the IDs returned by step 1
| filter tags['gen_ai.input.messages'] != null || tags['gen_ai.output.messages'] != null
| create input_json from concat('{"messages":', firstNonNull(tags['gen_ai.input.messages'], '[]'), '}')
| create output_json from concat('{"messages":', firstNonNull(tags['gen_ai.output.messages'], '[]'), '}')
| extract input_json into input_parsed using jsonobject()
| extract output_json into output_parsed using jsonobject()
| create all_messages from arrayConcat(input_parsed.messages, output_parsed.messages)
| explode all_messages into message original preserve
| filter ['user','assistant'].arrayContains(message.role)
| explode message.parts into part original preserve
| filter part.type == 'text' && trim(firstNonNull(part.content, '')) != ''
| create line from concat(message.role, ': ', part.content)
| groupby $d.traceID as trace_id, $d.spanID as span_id aggregate collect(line) as lines
| create conversation_text from arrayJoin(lines, '\n')
| choose trace_id, span_id, conversation_text
```
Assistant `reasoning`/`<thinking>` arrives as a `text` part and is included — that's expected. For a full transcript **including** tool calls/results and exact structure, `choose` the raw `tags['gen_ai.input.messages']` / `tags['gen_ai.output.messages']` string and read it directly.

Aggregate instead of read (e.g. top user questions): keep only `message.role == 'user'` before the parts explode, then `| groupby part.content aggregate count() as times | orderby times desc`.
> **Two conventions carry the conversation — handle both.** Current: `gen_ai.input.messages` / `gen_ai.output.messages` (one JSON blob with all turns). Older **indexed**: one tag *per message*, numbered from 0 — `gen_ai.prompt.<n>.role` / `gen_ai.prompt.<n>.content` for each input message (`n = 0,1,2,…` in order) and `gen_ai.completion.<n>.role` / `gen_ai.completion.<n>.content` for the output(s); so `gen_ai.prompt.0.content` is only the **first** message and the whole conversation spans `prompt.0, prompt.1, …` / `completion.0, …`. Different SDKs emit one or the other — **pick by which tags exist: run the current-convention query above when `gen_ai.input.messages` or `gen_ai.output.messages` is present, the indexed-convention query below when `gen_ai.prompt.0.role` is present**.
>
> **Indexed convention** (`gen_ai.prompt.<n>` / `gen_ai.completion.<n>`) — over the same sampled IDs. DataPrime can't iterate the numbered keys directly (there's no key enumeration), so read it by serializing the span with `$d:string` and `multi_regexp`-ing all role/content pairs at once, then re-pairing by index — same `user`/`assistant` + non-empty filter, so system and tool turns are excluded:
```dataprime
source spans
| filter ['TRACE_1','TRACE_2', … ].arrayContains($d.traceID)   // the IDs from Cap the volume first, Step 1
| filter tags['gen_ai.prompt.0.role'] != null
| create doc_json from $d:string
| extract doc_json into matches using multi_regexp(e=/"gen_ai\.(prompt|completion)\.(\d+)\.(role|content)":"((?:[^"\\]|\\.)*)"/)
| explode matches into m original preserve
| extract m into p using regexp(e=/"gen_ai\.(?<grp>prompt|completion)\.(?<idx>\d+)\.(?<kind>role|content)":"(?<value>(?:[^"\\]|\\.)*)"/)
| groupby $d.traceID as trace_id, $d.spanID as span_id, p.grp:string as grp, p.idx:number as idx
    aggregate any_value(if(p.kind == 'role', p.value:string, null)) as role,
              any_value(if(p.kind == 'content', p.value:string, null)) as content
| filter (role == 'user' || role == 'assistant') && content != null && trim(content) != ''
| create line from concat(if(grp == 'prompt', '0', '1'), ':', padLeft(idx:string, 5, '0'), ':::', role, ': ', content)
| groupby trace_id, span_id aggregate arrayJoin(arraySort(collect(line)), '\n') as conversation_text
| redact conversation_text matching /[01]:\d{5}:::/ to ''
| choose trace_id, span_id, conversation_text
```
The `grp`/`idx` sort prefix orders prompt-before-completion and by index; `redact` then strips it. (Regexing the string-serialized span keeps in-message newlines/escapes literal — text complete and correctly ordered, just cosmetically escaped vs. the current convention.)

**Span attributes — be aware of all of these** (GenAI spans; use `search_for_fields` for customer-specific fields beyond these. For the conversation itself, read `gen_ai.input.messages` / `gen_ai.output.messages` (current convention) or the indexed `gen_ai.prompt.<n>.*` / `gen_ai.completion.<n>.*` keys — whichever convention the app's instrumentation emits; see the two-conventions note above).

*Span kind* — `gen_ai.operation.name`: `chat` (LLM inference; also `generate_content`, `text_completion`), `embeddings`, `retrieval` (RAG), `create_agent`, `invoke_agent` (agentic turn), `invoke_workflow` (multi-agent), `execute_tool`.

| Attribute | Meaning |
| --- | --- |
| `gen_ai.provider.name` (or deprecated `gen_ai.system`) | Provider — prefer `gen_ai.provider.name`; the filters above still match `gen_ai.system` for legacy data |
| `otel.status_code` (`ERROR`) / `error.type` | Failure status / low-cardinality error class |
| `otel.library.name` | `cx_guardrails.client` marks a guardrail span (GenAI spans are identified by the `gen_ai.*` filter above, not by this tag) |
| `gen_ai.agent.{id,name,description,version}` / `gen_ai.workflow.name` | Agent / workflow identity |
| `gen_ai.request.model` / `gen_ai.response.model` / `gen_ai.response.id` | Requested / actual model; completion id |
| `gen_ai.conversation.id` | Conversation/session/thread id |
| `enduser.id` / `user.id` (+ fallbacks `gen_ai.request.user` [non-standard, not in OTel], `traceloop.association.properties.user_id`, `langsmith.metadata.user_id`) | End user |
| `gen_ai.data_source.id` | Grounding source (RAG/vector store) |
| `gen_ai.output.type` | `text`/`json`/`image`/`speech` |
| `gen_ai.request.{choice.count,seed,stream,max_tokens,temperature,top_p,top_k,frequency_penalty,presence_penalty,stop_sequences,encoding_formats}` | Request params |
| `gen_ai.response.finish_reasons` | Stop reason (`~ 'length'`=truncated; `~ 'tool_'`=tool call — values seen: tool_call/tool_calls/tool_use) |
| `gen_ai.response.time_to_first_chunk` | TTFB (s) for streaming |
| `gen_ai.usage.{input_tokens,output_tokens,reasoning.output_tokens,cache_read.input_tokens,cache_creation.input_tokens}` | Token usage |
| `gen_ai.embeddings.dimension.count` | Embedding dimensions |
| `server.address` / `server.port` | GenAI server host/port |
| `gen_ai.input.messages` / `gen_ai.output.messages` | Conversation transcript — input = full chat history (system/user/assistant/tool turns) sent to the model, output = the model's response (opt-in; **read these** for content) |
| `gen_ai.system_instructions` | System prompt — often large; **skip** when reading dialogue. May instead sit as the `role:'system'` message in `gen_ai.input.messages`; for a system-prompt question check both |
| `gen_ai.tool.definitions` / `gen_ai.tool.{name,call.id,description,type,call.arguments,call.result}` | Tools advertised / executed (`tool.type`: `function`/`extension`/`datastore`) |
| `gen_ai.retrieval.documents` / `gen_ai.retrieval.query.text` | Retrieved docs (id+score) / query (opt-in) |
| Coralogix: `gen_ai.prompt_price`,`gen_ai.response_price`,`gen_ai.read_cache_price`,`gen_ai.write_cache_price` | Cost (USD) — see Cost below |
| Coralogix: `gen_ai.{target}.evaluations.{type}.{score,label,version,details}`, `…evaluations.custom.{0..9}.{…}`, `guardrails.triggered`, `gen_ai.{target}.guardrails.{policy}.triggered` | Eval/guardrail results — see Evaluations below |

`m`/`l`/`d` prefixes: `$m.timestamp`,`$m.duration`; `$l.applicationName`,`$l.subsystemName`,`$l.serviceName`,`$l.operationName`; `$d.traceID`,`$d.spanID`.

**Cost (Coralogix tags, USD):** total = `firstNonNull(gen_ai.prompt_price,0)+firstNonNull(gen_ai.response_price,0)+firstNonNull(gen_ai.read_cache_price,0)+firstNonNull(gen_ai.write_cache_price,0)` — prompt + response + cache-read + cache-write. **Cache token accounting differs by provider:** OpenAI-style — `cache_read` ⊂ `input_tokens` (hit rate = cache_read/input); Anthropic-style — input/cache_read/cache_creation are disjoint. **Custom model pricing** is configured per-model in a Cost section ("Configure model pricing"); it's **team-wide and applies to new data only** (read it via the `ai_center_get_model_pricing` tool; price tags already reflect it).

**Model-switch / cost-saving questions** ("how much would we save by switching from model X to model Y?"): take the app's **current token volume** for the source model (Q5/Q6), **re-price** it at the target model's rate, and report the savings (absolute + %). If the named model isn't in the telemetry, say which models you actually see and which you mapped it to. **Always add the quality caveat** — a cheaper/smaller model can reduce answer quality, so recommend validating the switch with an evaluation or a sampled quality comparison before acting (it's a quality–cost tradeoff, not just a price cut).

## Evaluations, Guardrails & Policies

A **policy** is a configurable check. The same policy can act as an **evaluation** (post-hoc scoring/flagging) and/or a **guardrail** (real-time block). UI evaluation categories: **Hallucinations, Security, Toxicity, Topics, User experience, Compliance**, plus **Custom** (typed Quality or Security).

**Evaluations** run automatically on spans (no added latency); the target is **prompt** or **response** (the backend supports only these two — ignore the unused `conversation` enum value). Results are written back as span tags:
- Built-in: `gen_ai.{prompt|response}.evaluations.{eval_type}.{score|label|version|details}`. **`label == 'p1'` marks a flagged issue** (UI severity High/Low).
- Custom: `gen_ai.{target}.evaluations.custom.{0..9}.{name,target,category,triggered,score,label}` (`triggered` is the string `"true"`/`"false"`).
- Eval types — Hallucinations: `hallucination_context_adherence|context_relevance|completeness|correctness|task_adherence`, `sql_hallucination`; Security: `prompt_injection`, `pii`, `sql_read_only|sql_load|sql_restricted_tables|sql_allowed_tables`; Toxicity: `toxicity`, `sexism`; Topics: `restricted_topics`, `allowed_topics`, `competition`; User experience: `language_mismatch`.
- **Issue class:** Security category = `prompt_injection`, `pii`, `sql_*`; everything else = Quality.

**Guardrails** act in real time via the `cx-guardrails` SDK: check a prompt before the LLM or a response before the user, and **block** on violation. Each invocation is a span (`otel.library.name == 'cx_guardrails.client'`) with `tags['guardrails.triggered'] == 'true'` when it triggered; `$l.operationName` starts with `guardrails.prompt`/`guardrails.response`. Per-policy results may also appear as `gen_ai.{prompt|response}.guardrails.{policy}.triggered` (`triggered` can be `'true'` for triggered or `'false'` for passed). Prebuilt guardrails: **Prompt Injection, PII, Toxicity** — plus **custom** guardrails.

**Configuration is not telemetry.** Which policies exist, which are enabled per app, the app inventory, guarded status (`guardrailsIntegrated`), and the team's **custom model pricing** (`ai_center_get_model_pricing`) come from the backend — use the **`ai_center_*` / `manage_ai_*` tools** below, not span queries.

## DataPrime query library (full, runnable)

These are the actual queries behind the AI Center widgets. To use one: keep the GenAI filter, **set the query time range**, and scope to one app by keeping `| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'` (drop that line for org-wide / global Overview; see Scoping for the app=pair caveat). The Widget reference and Examples below cite these by id (**Q1–Q15**).

**Q1 — Key insights** (Overview & Drilldown "Key insights" widgets: Models Used, Time to Response, Token Usage, Estimated Cost, Errors, Guardrail Actions, AI Spans, Unique Users — and the Application Catalog header KPIs when run without the app scope):
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'
| filter ((tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))) || tags['otel.library.name']:string == 'cx_guardrails.client'
| create cost from firstNonNull(tags['gen_ai.prompt_price']:number,0) + firstNonNull(tags['gen_ai.response_price']:number,0) + firstNonNull(tags['gen_ai.read_cache_price']:number,0) + firstNonNull(tags['gen_ai.write_cache_price']:number,0)
| create tokens from firstNonNull(tags['gen_ai.usage.input_tokens']:number,0) + firstNonNull(tags['gen_ai.usage.output_tokens']:number,0)
| create user from firstNonNull(tags['gen_ai.request.user'], tags['enduser.id'], tags['user.id'], tags['traceloop.association.properties.user_id'], tags['langsmith.metadata.user_id'])
| aggregate count() as ai_spans, avg(duration) as ttr_avg, sum(tokens) as token_usage,   // span-level, as the UI counts (distinct_count(traceID) for a deduplicated interaction count)
            sum(cost) as estimated_cost, count_if(tags['otel.status_code']:string == 'ERROR') as errors,
            count_if(tags['guardrails.triggered']:string.toLowerCase() == 'true') as guardrail_actions,
            distinct_count(user) as unique_users,
            collect(firstNonNull(tags['gen_ai.response.model']:string, tags['gen_ai.request.model']:string, ''), distinct=true) as models_used
```
> **Q1 is the UI's *batched* query** — it computes all the widgets at once because the dashboard shows them together. When the user asks for **one** metric (e.g. TTR), do **not** run the whole thing: build a minimal query with **only that aggregation** (and only the `create` lines it needs) and report just that value. e.g. TTR only → `… | aggregate avg(duration) as ttr_avg` (or `percentile(0.95, duration)`; selector supports 0.5/0.75/0.9/0.95/0.99). Issue Rate widget = Q9. Reproduce any single Overview KPI (TTR included) with Q1's filter.

**Q2 — Response Time / latency over time** (Latency → Response Time Trends; Time to Response selector):
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))
| groupby roundTime($m.timestamp, <interval>ms) as Time
  aggregate avg(duration) as avg, percentile(0.75, duration) as p75, percentile(0.90, duration) as p90, percentile(0.95, duration) as p95, percentile(0.99, duration) as p99
| orderby Time
```

**Q3 — Latency by model** (Latency → Latency by Model): as Q2 but `groupby firstNonNull(tags['gen_ai.response.model']:string, tags['gen_ai.request.model']:string,'unknown') as model` (no time bucket), `orderby avg desc`.

**Q4 — Top slowest applications / spans** (Latency → Top Slowest): replace the groupby with `$l.applicationName, $l.subsystemName` (apps) or `$l.operationName` (spans), `aggregate avg(duration) as avg | orderby avg desc | limit 5`.

**Q5 — Cost & tokens over time** (Cost → Cost Over Time, Tokens Over Time, Total Cost, Total Tokens, Cache Hit Rate):
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))
| create input_tokens from firstNonNull(tags['gen_ai.usage.input_tokens']:number,0)
| create output_tokens from firstNonNull(tags['gen_ai.usage.output_tokens']:number,0)
| create cache_read from firstNonNull(tags['gen_ai.usage.cache_read.input_tokens']:number, tags['gen_ai.usage.cache_read_input_tokens']:number, tags['gen_ai.usage.cached_tokens']:number, 0)
| create cache_creation from firstNonNull(tags['gen_ai.usage.cache_creation.input_tokens']:number, tags['gen_ai.usage.cache_creation_input_tokens']:number, 0)
| create cost from firstNonNull(tags['gen_ai.prompt_price']:number,0) + firstNonNull(tags['gen_ai.response_price']:number,0) + firstNonNull(tags['gen_ai.read_cache_price']:number,0) + firstNonNull(tags['gen_ai.write_cache_price']:number,0)
| groupby roundTime($m.timestamp, <interval>ms) as Time
  aggregate sum(cost) as cost, sum(input_tokens) as inputTokens, sum(output_tokens) as outputTokens, sum(cache_read) as cacheReadTokens, sum(cache_creation) as cacheCreationTokens
| orderby Time
```
Cache Hit Rate (calc) = `sum(cacheReadTokens)/sum(inputTokens)`. Drop `roundTime` for the Total Cost/Tokens KPIs.

**Q6 — Cost by model** (Cost → Cost by Model): as Q5 without time bucket, `groupby firstNonNull(tags['gen_ai.response.model']:string, tags['gen_ai.request.model']:string,'unknown') as model | orderby cost desc`.

**Q7 — Most expensive applications / High-spending users** (Cost → Most Expensive Applications / High-Spending Users): as Q5 without time bucket, `groupby $l.applicationName,$l.subsystemName` (apps) or the `user` expr (users), `aggregate sum(cost) as cost, sum(input_tokens+output_tokens) as tokens | orderby cost desc | limit 5`.

**Q8 — Errors over time / Errored vs Total / Top errored apps** (Errors section):
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))
| groupby roundTime($m.timestamp, <interval>ms) as Time
  aggregate count() as total, count_if(tags['otel.status_code']:string == 'ERROR') as errors
| orderby Time
```
Top errored apps/spans: replace the groupby with `$l.applicationName,$l.subsystemName` (or `$l.operationName`), `aggregate count_if(tags['otel.status_code']:string=='ERROR') as errors | orderby errors desc | limit 5`.

**Q9 — Issue rate (prompt / response)** (Overview/Drilldown Issue Rate + Issues → Prompt/Response Issues; also AI‑SPM security issues). Trace-level. An **issue** on a target (prompt/response) = any **built-in eval** flagged `label == 'p1'` **OR** any **custom eval** (`evaluations.custom.{0..9}`) with `triggered == 'true'` **OR** a **guardrail** that triggered on that target. Repeat the `…{eval}.label=='p1'` term once per enabled built-in eval type, and the `custom.{n}` term for each configured index 0–9 (`{eval}` = an enabled eval type; for AI‑SPM use only security types: `prompt_injection`, `pii`, `sql_*`):
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'
| filter ((tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))) || tags['otel.library.name']:string == 'cx_guardrails.client'
| create prompt_issue from (tags['gen_ai.prompt.evaluations.{eval}.label']:string == 'p1' || tags['gen_ai.prompt.evaluations.custom.0.triggered']:string.toLowerCase() == 'true' || ($l.operationName.startsWith('guardrails.prompt') && tags['guardrails.triggered']:string.toLowerCase() == 'true'))
| create response_issue from (tags['gen_ai.response.evaluations.{eval}.label']:string == 'p1' || tags['gen_ai.response.evaluations.custom.0.triggered']:string.toLowerCase() == 'true' || ($l.operationName.startsWith('guardrails.response') && tags['guardrails.triggered']:string.toLowerCase() == 'true'))
| groupby traceID aggregate max(if(prompt_issue,1,0)) as p, max(if(response_issue,1,0)) as r
| aggregate count() as traces, sum(p) as prompt_issue_traces, sum(r) as response_issue_traces
| create prompt_issue_rate from prompt_issue_traces*100.0/traces
| create response_issue_rate from response_issue_traces*100.0/traces
```
**Total issue** (either target — the Issues/AI‑SPM counters): a trace has an issue if a **guardrail triggered** OR a GenAI span has **any built-in eval `p1`** or **any custom eval `custom.{0..9}` triggered**. Issue Distribution / Top Apps With Issues = the same detection grouped by eval **category** (Security = `prompt_injection`/`pii`/`sql_*`; everything else = Quality) or by `$l.applicationName`.

**Q10 — Tool calls** (Drilldown Tool Calls → Distribution / per-interaction / usage):
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))
| create is_tool from (tags['gen_ai.operation.name']:string == 'execute_tool' || tags['gen_ai.response.finish_reasons']:string ~ 'tool_')
| filter is_tool
| extract tags['gen_ai.output.messages']:string into msg_tool using regexp(e=/"type"\s*:\s*"tool_call".*?"name"\s*:\s*"(?<name>[^"]+)"/)
| create tool from firstNonNull(tags['gen_ai.tool.name']:string, msg_tool.name, 'unknown')
| groupby tool aggregate count() as uses | orderby uses desc
```
The `is_tool` condition flags a turn that **used** a tool (either an `execute_tool` span or a response that finished with a tool call). The **name** comes from `gen_ai.tool.name` (present on `execute_tool` spans); for response spans that merely end with a `tool_call` and lack that tag, pull it from the `tool_call` part of `gen_ai.output.messages` (as the UI does) — only truly nameless ones fall back to `'unknown'`. If the distribution is still dominated by `unknown`, scope to `tags['gen_ai.operation.name']:string == 'execute_tool'`, whose spans always carry the tool name.
Calls-per-interaction: `groupby traceID aggregate count_if(is_tool) as n | groupby n aggregate count() as cnt`. Tool usage %: `aggregate distinct_count(traceID) as total, distinct_count_if(is_tool, traceID) as with_tools`.

**Q11 — Read interactions / AI Explorer** (AI Explorer grid; Phase 1 content analysis): the canonical "read interactions" query at the top of this skill (select `gen_ai.input.messages` / `gen_ai.output.messages`, tokens, cost, user, duration).

**Q12 — Session walkthrough**: the `filter traceID == '<traceID>'` query in Phase 1.

**Q13 — Who's using / sessions & AI‑SPM user insights** (High-Activity / High-Spend / Risky users):
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))
| create user from firstNonNull(tags['gen_ai.request.user'], tags['enduser.id'], tags['user.id'], tags['traceloop.association.properties.user_id'], tags['langsmith.metadata.user_id'])
| filter user != null
| groupby user aggregate count() as interactions, distinct_count(tags['gen_ai.conversation.id']) as sessions,
            sum(firstNonNull(tags['gen_ai.prompt_price']:number,0)+firstNonNull(tags['gen_ai.response_price']:number,0)+firstNonNull(tags['gen_ai.read_cache_price']:number,0)+firstNonNull(tags['gen_ai.write_cache_price']:number,0)) as cost
| orderby interactions desc | limit 5
```
High-Activity = orderby interactions; High-Spend = orderby cost; Risky = add `count_if(<security eval label=='p1'>) as security_issues` and orderby that.

**Q14 — Agentic workflow walkthrough** (multi-step agent traces / tool-calls / reasoning chains — Phase 2 "Agent workflows"): reconstruct an agent run for a `traceID`, ordered, showing the agent/workflow/tool chain and messages:
```dataprime
source spans
| filter traceID:string == '<traceID>'
| filter (tags['gen_ai.system']:string != null || tags['gen_ai.provider.name']:string != null || tags['gen_ai.operation.name']:string != null) && !(['cursor-agent','codex_cli_rs','codex-app-server','github-copilot','gemini-cli'].arrayContains($l.serviceName))
| choose $m.timestamp as ts, tags['gen_ai.operation.name']:string as step,
         tags['gen_ai.agent.name']:string as agent, tags['gen_ai.workflow.name']:string as workflow,
         tags['gen_ai.tool.name']:string as tool, tags['gen_ai.tool.call.arguments']:string as tool_args,
         tags['gen_ai.tool.call.result']:string as tool_result, tags['gen_ai.request.model']:string as model,
         tags['gen_ai.input.messages']:string as input_messages, tags['gen_ai.output.messages']:string as output_messages
| orderby ts asc | limit 200
```
Narrate the chain: each `invoke_agent`/`invoke_workflow` is a step; `execute_tool` rows show the tool, its arguments and result; read the messages for the model's reasoning. For "how often / which tools" across many traces use Q10.

**Q15 — Evaluation score distribution / trend** (Issues "score distribution"; the eval `score` is a 0–1 float, separate from the `p1` label): bucket the scores for an eval type:
```dataprime
source spans
| filter $l.applicationName == '<APP>' && $l.subsystemName == '<SUB>'
| filter tags['gen_ai.response.evaluations.{eval}.score']:number != null
| create bucket from round(tags['gen_ai.response.evaluations.{eval}.score']:number, 1)
| groupby bucket aggregate count() as n | orderby bucket
```
For a trend, add `groupby roundTime($m.timestamp, <interval>ms) as Time aggregate avg(tags['gen_ai.response.evaluations.{eval}.score']:number) as avg_score`. Swap `response`→`prompt` for the other target.

## Phase 1 — interaction intelligence (read the content)

Scope by app+time, sample real messages, reason about them, cite traceIDs.

**Method — the default for sentiment / satisfaction / frustration questions** (don't ask first — pick a sensible scope, state it, and proceed):
1. **To judge feelings, read the conversations — don't keyword-search for emotion.** Grepping for words like `~ 'angry'` / `~ 'stupid'` to gauge sentiment misses most of it (people phrase frustration unpredictably). Instead, take a capped sample for the app (see *Cap the volume first*), group it into sessions (`gen_ai.conversation.id`, fall back to `traceID`), and read each session's turns in order — `gen_ai.input.messages` / `gen_ai.output.messages`. Report matched-vs-read. (Keyword-filtering **is** right for a different job — *finding/counting* a **specific named term**; see below.)
2. **Judge each session from the USER's side.** Read the **user** turns to gauge the user's own sentiment/behavior: satisfied (got their answer, "thanks"/"perfect", no re-asks, positive tone) vs not (re-asks/rephrasing the same thing, rising turns, negative/abusive wording, excessive `?`/`!`/ALL-CAPS, "that's not what I asked", abandoning mid-thread). The agent's response quality, `finish_reason`, evals and guardrails are **secondary supporting context — never the headline**. Do **not** pivot a satisfaction question into "the app is broken / returning bad responses": the question is whether the **users** seem satisfied, judged from **their** messages.

**Answer shape (satisfaction / frustration):** lead with a plain-language **summary** of whether users seem satisfied or not (and roughly the split — "most seem satisfied", "a notable share seem frustrated"). Then **show the evidence from the transcripts**: a few **satisfied** sessions — quote the telling user turn(s), each with its **`traceID`** — and a few **dissatisfied** sessions — quote the user turn(s) that show it, each with its **`traceID`**. Examples with real quotes + traceIDs are **required**; never give a satisfaction verdict without showing the conversations behind it. An "N of M" count is optional, not the point.

**An "example" = a verbatim quote of the USER's own message(s)** that shows their sentiment, plus the traceID — e.g. *"this is the third time I'm asking the same thing" (trace abc123)*. It is **not** a description of the agent's reply: *"trace X → refusal"*, *"trace Y → gave advice"* is **response analysis, not user satisfaction — not acceptable**. Read the **user** turns and quote *them*. If the user messages genuinely show no clear sentiment either way, **say that explicitly** instead of substituting the agent's behavior (refusals/inconsistency) as a satisfaction proxy. **Never paste raw lists of trace/span IDs** into the answer — cite only the handful you actually quote.

- **Who's using / sessions:** `groupby <user> aggregate distinct_count(tags['gen_ai.conversation.id']) as sessions, count() as interactions`; read turns within a `conversation.id` for repeat/abandonment.
- **Satisfaction / frustration:** follow the Method above — read whole conversations and judge the **users'** behavior; **no keyword search**, and **don't lead with response-quality / finish_reason / evals**. Frustration: re-asks/rephrasing, rising turns, negative/abusive wording, excessive punctuation, abandonment. Satisfaction: thanks, clean resolution, no re-asks, positive tone. Always back the verdict with quoted user turns + traceIDs (satisfied and dissatisfied examples).
- **Topic analysis** (*"what do users ask about?"*) is an **LLM-judgment** task, not a keyword/regex one — read the **user turns** of your sample — the `text` parts of `role:'user'` messages; skip `system`/`assistant`/`tool` turns (see Message formats) — and **cluster the asks yourself**; report the themes and how many interactions you read. Don't try to bucket topics with keyword filters.
- **Counting/finding a specific term** (*"how often do users mention RUM?"*) is a **different, narrower** job — from the request, decide what they actually want (a count, a list, or examples); don't assume it's always a count. When you do match: match the **user turns** at the **word level** — a bare `~ 'rum'` also hits *forum/premium/spectrum/instrument*, and **never grep the whole `gen_ai.input.messages` blob** (it's the full chat history — the system prompt + tool/skill definitions name features like "RUM"/"real user monitoring", so the blob matches **nearly every** interaction). Report any count as a **floor** (paraphrases under-count).
- **Session walkthrough:** given a `traceID`, fetch ordered turns (messages) and narrate.
- **Agentic workflow walkthrough:** for multi-step agents, reconstruct the `invoke_agent`→`execute_tool` chain + reasoning from the trace (**Q14**).
- **Quality / hallucination:** optionally pre-filter `…evaluations.{name}.label=='p1'`, but **confirm by reading the messages**.
- **Root cause:** `otel.status_code=='ERROR'` (+ `error.type`) then read messages + errored child spans; watch truncation, tool failures, retrieval misses. **Pull the whole trace (`filter traceID == '<id>'`), not just the GenAI spans** — the cause often lives in a sibling **non-GenAI** span (a DB call, HTTP request, retrieval step).
- **Agent behaving off-task / deviating from its instructions:** read the **system prompt** (`gen_ai.system_instructions` and/or the `role:'system'` turn) alongside the user/assistant turns, and judge whether the responses stayed within the task the system prompt defines; cite the `traceID`s where it drifted.

## Widget reference (per page · purpose from the UI tooltip · query/source)

Pages: **Overview** (global) · **Application Catalog** · **Application Drilldown** (per app) · **AI Explorer** · **Policy Catalog** · **Policy Configuration** · **AI‑SPM**. The **Query** column cites the full query from the library above (Q1–Q15). Widgets that read from an AI Center **tool** name the tool inline (config, not a span query — full list in the Configuration tools section); **calc** = values derived from a query's results.

### Overview (global, all apps) & Application Drilldown (one app — same widgets, scoped by application+subsystem; drilldown adds Tool Calls)
Sections: **Overview · Cost · Issues · Errors · Latency** (drilldown also **Tool Calls**).
| Widget | Purpose (tooltip) | Query |
|---|---|---|
| Models Used | "All models used across applications" (drilldown: "in the processed spans") | **Q1** (`models_used`) |
| Time to Response | "The total time from when a user sends a request to when they receive a response" (selector avg/P75/P90/P95/P99) | **Q1** widget (`ttr_avg`); **Q2** for the trend |
| Errors / Error Rate | "The … GenAI spans that returned an error" (span-level count; rate = errored spans / total spans) | **Q1** (`errors`) / **Q8** |
| Issue Rate / Issues count | Rate = flagged-trace % (trace-level); count = flagged spans (span-level). | **Q9** rate; `count_if(prompt_issue || response_issue)` for the count |
| Guardrail Actions | "The percentage of LLM calls where a guardrail action was applied" (Q1 `guardrail_actions` is the span-level **count** of guardrail-triggered spans, matching the UI's span count; for the percentage divide by `ai_spans` × 100) | **Q1** (`guardrail_actions`) |
| Estimated Cost | "Total estimated cost based on token usage and model pricing" | **Q1** (`estimated_cost`) / **Q5** |
| Token Usage | "The total number of tokens consumed" | **Q1** (`token_usage`) / **Q5** |
| AI Spans | "The total number of AI spans" (span-level count, incl. guardrail spans — **not** deduplicated traces) | **Q1** (`ai_spans`) |
| Unique Users | "The number of distinct users who sent requests" | **Q1** (`unique_users`) / **Q13** |
| Activity → Issues Over Time | "Prompt and response issues … over time" | **Q9** + `roundTime` (filterable by eval type) |
| Cost → Cost Over Time / Total Tokens / Tokens Over Time | cost & token trends | **Q5** |
| Cost → Cost by Model | cost per model | **Q6** |
| Cost → Most Expensive Applications | "The applications with the highest costs" | **Q7** (groupby app) |
| Cost → High-Spending Users | "users whose AI usage generated the highest costs" | **Q7** (groupby user) |
| Cost → Cache Hit Rate (calc) | cache-read / input | **Q5** (`cacheReadTokens/inputTokens`) |
| Errors → Errors Over Time / Errored vs Total traces | "Error trends over the selected time period" | **Q8** |
| Errors → Top Errored Applications / Spans | "applications/spans with the highest number of errors" | **Q8** (top variant) |
| Latency → Response Time Trends | "Time to response trends … avg, P75, P90, P95, P99" | **Q2** |
| Latency → Top Slowest Applications / Spans | "applications/spans with the highest time to response" | **Q4** |
| Latency → Latency by Model (drilldown) | "avg, P75…P99 span duration per used model" | **Q3** |
| Issues → Prompt Issues / Response Issues | flagged prompts / responses | **Q9** (`prompt_issue_rate` / `response_issue_rate`) |
| Issues → Issue Distribution | "Distribution … Security (prompt injection, PII) vs Quality (hallucinations, competitor)" | **Q9** grouped by eval category |
| Issues → Top Applications With Issues | "highest issue-to-total messages ratio" | **Q9** grouped by `$l.applicationName` |
| Tool Calls (drilldown) → Number of Tool Calls per Interaction / Tool Distribution / Tool Usage | "distribution of tool calls per interaction" / "usage frequency of each tool" / "user-to-LLM interactions that triggered tool usage" | **Q10** |

### Application Catalog
Header KPIs (**Time to response**, **Estimated cost**, **Token usage**, **Issue rate**) = **Q1**/**Q9** run **without** the app scope (org-wide). **Guarded applications** % = **calc** from `ai_center_list_applications`.
Grid (one row per app) = the `ai_center_list_applications` result's `items` array (gives `guardrailsIntegrated`) **merged with** per-app metrics from **Q1** grouped by `$l.applicationName,$l.subsystemName`. Columns + tooltips: **LLM calls** (`count()`), **Security issues** ("issues triggered by security evaluations" — **Q9** security), **Quality issues** ("issues triggered by quality evaluations (compliance, user experience, hallucinations, topics, toxicity)" — **Q9** quality), **Cost**, **Tokens**, **Time to response**, **Models** (all from Q1), **Guardrail status** (from `guardrailsIntegrated`).

### AI Explorer (interactions/spans grid — per app & global) — the UI for "read the messages"
Query: **Q11**. Columns: **Timestamp**, **Input**, **Output**, **Tokens** (`input+output`), **Cost** (`prompt_price+response_price+read_cache_price+write_cache_price`), **User ID**, **Security issues** ("issues detected by evaluations under the security category, such as prompt injection and PII exposure"), **Quality issues** ("… compliance, user experience, hallucination, topics, and toxicity categories"), **Duration**. Two views: **AI Spans** (span-level) and **Interactions** (trace-grouped). Mirror it by reading `gen_ai.input.messages`/`gen_ai.output.messages`.

### Policy Catalog (config)
Prebuilt + custom **policies**, filterable by **category** (Hallucinations/Toxicity/Security/Topics/User experience/Custom) and **usage** (used/unused). Each card shows name, description, category, "In use in N apps". Source: `ai_center_list_evaluations` (returns both prebuilt and custom policies — read the `custom_evaluations` part for custom). Not a span query.

### Policy Configuration (per app)
Grid of policies configured for the app: **Name · Category · Description · State** (enabled/disabled toggle). Source: `ai_center_list_evaluations(application, subsystem)`. To change state (enable/disable, add/remove a policy) use the write tools (`manage_ai_evaluation(action="update")`, `manage_ai_custom_evaluation(action="add_policy")` / `manage_ai_custom_evaluation(action="remove_policy")`) — each prompts the MCP host for approval.

### AI‑SPM
**KPIs:**
- **Total AI Applications** — the monitored inventory; use `ai_center_list_applications`. (The page also counts apps found via AI App Discovery, which aren't in span/tool data.)
- **Total Security Violations** — the security `p1` count (issues under the security eval category).
- **AI Security Posture Score** — a **backend-computed score** (monitoring coverage + presence of security evaluations). No tool or span query returns it, so it **can't be computed here** — describe what it represents and point the user to the AI-SPM page.

**Security Issues** (Issues Over Time / AI Spans / Prompt Issues / Response Issues) = the issue-rate pattern (**Q9**) restricted to security eval types.

**User Insights** — **High-Activity Users** (top 5 by messages), **High-Spend Users** (top 5 by cost), **Risky Users** (top 5 by security issues) = **Q13** ordered by interactions / cost / security_issues.

**AI App Discovery** (GitHub repo scan) — **not available via this skill**: no DataPrime/PromQL data and no backend tool (the scan service only accepts the user's session auth). You can **explain** what it surfaces — Discovered/Monitored/Unmonitored apps, total AI calls, and a repositories grid (Repository, AI Libraries, Main Contributor, AI Calls, `is_coralogix_monitored`; unmonitored = `is_coralogix_monitored == false`) — but you can't fetch it; tell the user to read it from the AI-SPM page.

## Examples (question → widget → query → params)
> When a question names an app/agent, **call `ai_center_list_applications` first** to resolve the exact `applicationName`/`subsystemName` pair before scoping a query.

- *"Which of my agents / LLM apps do I have?"* → `ai_center_list_applications`.
- *"Which region / agent is the most active?"* → GenAI filter, no app scope, `groupby $l.applicationName, $l.subsystemName aggregate count() as spans | orderby spans desc`.
- *"Which agent deviates from its intended task?"* → read each agent's **system prompt** + user/assistant turns and judge drift (see the agent-deviation playbook); cite traceIDs.
- *"Compare agent X now vs a week ago"* / *"compare agent X to agent Y"* → run the relevant Q twice with different time ranges, or grouped by `$l.applicationName,$l.subsystemName`, and diff the results (cost, error rate, latency, or the system prompt via a trace from each).
- *"What's the average time to response for Financial Advisor last 24h?"* → **Time to Response** → run **Q1** (read `ttr_avg`) with `$l.subsystemName == 'Financial Advisor'` and the 24h range (or **Q2** for the trend). For a percentile, swap `avg(duration)` → `percentile(0.95, duration)`.
- *"Token spend by model this week?"* → **Cost by Model** → **Q6**, set the range to this week.
- *"Which apps have the highest error rate?"* → **Top Errored Applications** → **Q8** top variant: `groupby $l.applicationName,$l.subsystemName aggregate count_if(...=='ERROR') as errors | orderby errors desc | limit 5` (no app scope).
- *"Are users frustrated in app X?"* → Phase 1 frustration playbook → **Q11** to read the conversations (not a single widget).
- *"Which apps lack guardrails?"* → `ai_center_list_applications` → filter `guardrailsIntegrated == false` (config, not spans).
- *"What policies are configured for app X?"* → `ai_center_list_evaluations(application, subsystem)`.

## Configuration tools (`ai_center_*` / `manage_ai_*`)

Use these for inventory / evaluations / policies / pricing (DataPrime can't answer them). **Show the user names, not UUIDs** — refer to apps and evaluations by their human names (application/subsystem, evaluation name). A UUID is only used internally to call a by-id or write tool: resolve it yourself from the matching list tool (never guess it or make the user paste one).

**Reads** (use freely) — 3 read tools:
- `ai_center_list_applications` — AI app inventory + `guardrailsIntegrated` (guarded) status; pass `application_ids=["…"]` to fetch specific apps by UUID.
- `ai_center_list_evaluations` — returns **both** prebuilt and custom evaluations, as `{"prebuilt_evaluations": [...], "custom_evaluations": [...]}` (not a flat list). No filter → all prebuilt + the whole custom library; with `application`+`subsystem` → that app's prebuilt + custom (configured evaluations/policies + enabled state). Pass `evaluation_id="…"` for a single **prebuilt** evaluation by UUID — prebuilt-only; a **custom** policy has no by-id fetch, so list (no scope or app-scoped) and match it by `id` in the returned `custom_evaluations`.
- `ai_center_get_model_pricing` — the team's custom model pricing.

**Writes** (mutating — the MCP host prompts before each; all are `destructiveHint=true`):
- `manage_ai_evaluation(action="create")` — needs `application`, `subsystem`, `config`, and `target` (**`PROMPT` or `RESPONSE`**, uppercase, required); optional `is_enabled`, `threshold`. Then `manage_ai_evaluation(action="update")` (needs `evaluation_id`, `updates`) / `manage_ai_evaluation(action="delete")` (needs `evaluation_id`).
- `manage_ai_custom_evaluation(action="create")` / `manage_ai_custom_evaluation(action="update")`.
- `manage_ai_custom_evaluation(action="add_policy")` / `manage_ai_custom_evaluation(action="remove_policy")` (attach/detach a custom policy; detaching is how you "remove" a policy from an app).
- `manage_ai_model_pricing(action="set")` — model pricing is **team-wide** (not per-app); this replaces the whole set, so pass a new map, or an empty map `{}` to clear all custom pricing.

**No delete here (by design):** there is no tool to delete a custom-evaluation policy, delete an AI application, or delete model pricing — the AI v3 API has those endpoints but they're intentionally not exposed.

## Troubleshooting (zero results & gotchas)
- **No rows for an app** — the name may be in `subsystemName` rather than `applicationName`; try the other field or `search_for_fields`; widen the time range.
- **Empty `gen_ai.*.messages`** — app isn't capturing content (opt-in); say so.
- **No eval/guardrail tags** — those policies aren't enabled; still answer content questions by reading messages.
- **Guarded status / configured policies / inventory / discovery** — configuration; use the `ai_center_*` tools, not spans.

## Answering guidelines
- Prefer reading real messages for content/quality/sentiment; cite traceIDs.
- Map the question to the matching widget's query (above); inject the user's params.
- **Answer only what's asked — query only what's asked.** The library's combined queries (Q1, Q5, Q13) are UI batches that compute many metrics at once for the dashboard. For a single-metric question, run a **minimal query with just that aggregation/field** and report only that result — don't compute or dump the other metrics. Likewise, don't pass extra params to tools or surface fields the user didn't ask for.
- Ground every number in a query/tool result; respect provider cache semantics; point the user to the matching AI Center page when useful.

## Related skills
- **`coralogix-spans`** — `skill://coralogix-spans/SKILL.md` (span querying + `search_for_fields`)
- **`dataprime`** — `skill://dataprime/SKILL.md` (DataPrime syntax + command catalog)
