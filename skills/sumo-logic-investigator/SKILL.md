---
name: sumo-logic-investigator
description: Investigate incidents and answer operational and security questions with evidence from the customer's Sumo Logic org (logs, alerts, Cloud SIEM insights, detection rules, dashboards, and metrics and tracing through Mobot). Use during incident triage and root cause analysis when telemetry is in Sumo Logic, or when the user asks about errors, outages, latency, suspicious activity, alerts, monitors or ingestion, asks to search Sumo Logic logs, or mentions Sumo Logic or Mobot.
metadata:
  author: vsinghal13
  version: "1.1.0"
  summary: Query Sumo Logic logs, alerts, dashboards, SIEM insights and Mobot to investigate incidents.
  tier: partner-managed
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Sumo Logic Investigation Agent
This skill helps answer operational and security questions with evidence from the user's Sumo Logic platform: logs, alerts, Cloud SIEM insights, detection rules and dashboards, plus metrics and tracing through Mobot. It works with the Sumo Logic MCP server, so the tools below come from the user's own deployment and org, and what they can see depends on the user's permissions.

There are two ways to answer, and the skill picks between them:
- **Direct tools** (log search, alerts, insights, rules, dashboards). They give exact control and cost no investigation quota, so use them for any specific question. Each has a workflow below.
- **Mobot**, Sumo Logic's AI investigation agent. Use it for open-ended or cross-signal questions and anything the direct tools can't reach, such as metrics, tracing, ingestion volume, monitors and collector health. It spends the user's limited daily quota. See Mobot below.

Two rules apply throughout:
- **Explore before declining.** If a question might be answerable from platform data, run the discovery workflow first, and only say no once you've looked and confirmed the data isn't there.
- **Back every claim with a tool result.** Don't state anything you can't point to in what the tools returned. No Speculation — if the tools don't have the answer, say so. 

## Connect the logs to the code

Sumo Logic holds what the code does in production, and the repository holds why. Linking the two is what makes an investigation useful: it turns a log line, alert or Mobot finding into the code path behind it, and lets each Mobot turn, log search and metrics query build on what the code already showed.

The logs you search often come from code in the user's current working directory. When the question is about a service that lives in that code, use it on both ends of the investigation.

- **Before querying:** look in the relevant code for the log messages, logger names, error and exception classes, service names and source categories it emits. Use them to build a precise query, or to write a precise Mobot question. Mobot searches platform data, not code, so pass it these signals in plain words rather than code snippets.
- **After results come back:** map each finding to where it comes from in the code, such as the line that logs the message or the path that throws the error. Use that to confirm or rule out a cause.

Keep the code search scoped. Start from files the user referenced or the service in the question. If you can't tell where it lives, ask the user which file or folder holds it, or go ahead without code signals, rather than scanning the whole tree. If the code has nothing to do with the question, skip this step.

## Gotchas

- **Raw queries: `| limit N` must be the FIRST pipe operator**, before any `parse`, `json`, or
  `fields`. A leading limit terminates the scan early (scans MB); a trailing limit scans TB
  and *then* truncates.
- **Aggregate queries must be bounded** — end with `| sort _count desc | limit N` (or `topk`).
  An unbounded `count by` on a high-cardinality field overflows the context window.
- **`parse` / `json` on a field that may be absent needs `nodrop`.** Without it, rows missing
  the field are silently dropped — you lose data with no error and no warning.
- **Caps: 2 minutes runtime, 256MB results.** A query spanning more than ~30 minutes with no
  `_sourceCategory`, `_collector`, `_index`, or `_view` filter is rejected outright (400).
- **`listPartitions` is how you find `_sourceCategory` values** — read each partition's
  `routingExpression`. Don't invent category names and don't probe them one at a time.
- **Create detection rules with `enabled: false`** and have the user review before enabling.
- **Dates in this skill and its references are placeholders.** Always compute the real ISO
  8601 range from the current date in context — never copy a literal date out of an example.

## Mobot
Mobot is Sumo Logic's AI investigation agent. It has its own pre-built tools across logs, metrics, dashboards, monitors, alerts and Cloud SIEM, and it keeps multi-turn context. Use it for open-ended or cross-signal questions, or ones this skill has no tool for. Each investigation uses the user's limited daily quota, so use the direct tools for anything narrow.

### One conversation per investigation
Keep using a single `conversation_id` for the whole investigation and send every follow-up as another turn in it. Mobot manages tokens and holds the multi-turn context, so prior findings carry forward without you restating them. Start a new conversation only when you genuinely need to: the user changes topic or platform surface, or the old conversation has expired or can't be recovered. Don't open a new one just to rephrase, narrow or retry.

### Tools
- `mobot_invoke` starts an investigation and returns `conversation_id` and `message_id` right away. It spends the user's quota, so confirm with the user first. If the status is `rate_limited`, show the message as is and don't poll or retry before `reset_time`. If `quota_warning` is present, show it to the user.
- `mobot_poll` reads progress and results. Pass `wait_seconds` of 10 to 20 so the user sees an update at least that often (a long wait looks like a hang), and pass back the returned `char_offset` so each poll returns only new text. Keep polling until the status is `completed`, `failed` or `cancelled`. Mobot runs are long, so after every poll you MUST show the user what Mobot did in it, including the Sumo Logic queries it ran with their time ranges and the tools it used, before you poll again. Describe Mobot's tools in plain words ("ran a metrics query"), the same as for the direct tools, not by their internal names. Never poll silently.
- `mobot_cancel` stops a running investigation. Use it when the user asks to stop.
- `submit_hitl_feedback` answers a tool call that Mobot has paused for approval (`mobot_poll` status `waiting_for_approval`). The decision is the user's, so don't answer it yourself. Show them `tool_name` and `tool_args` and ask, then pass their choice as `kind` (`accept`, `reject`, or `text` with custom instructions) along with that poll's `tool_call_id`. Mobot can pause again with a new `tool_call_id`, and each one needs its own decision. If it fails with `hitl_tool_call_mismatch`, that call is no longer pending, so poll again and ask about the one pending now.

### Routing
Route on how well-scoped the user's prompt is and which tools can answer it. Direct tools cost no quota and give exact control, so prefer them whenever the question is specific.
- **Mobot:** vague, exploratory or open-ended asks ("why are errors spiking?", "investigate", "debug"), and anything this skill has no tool for: metrics, tracing, ingestion or data volume, monitors, collector or OTel health.
- **Direct:** everything specific. That means simple lookups ("HTTP 500s in the last 15 min"), aggregations, field filters and structured queries, follow-ups that need precise control (`timeslice`, `parse`, `transaction`), and alerts, insights, detection rules and dashboards.

Note: If Mobot's quota is exhausted, tell the user and fall back to the direct tools. Mobot is not enabled for every org: if the Mobot tools are not available, use the direct tools, and say that metrics, tracing and similar questions need Mobot.

## Log search workflow

Never skip a step.

### 1. DISCOVER — metadata only

Call `listPartitions`, `listCustomFields`, and `listExtractionRules` **in parallel**. Pick
target `_sourceCategory` values from the partition routing expressions before querying.

### 2. SCOPED SAMPLE

One narrow search to confirm the source: `_sourceCategory=<candidate>` plus a keyword,
**≤5 minute window, limit 5**. Read the output for real field names, log format, and
`_collector` values — step 3 needs them.

### 3. TARGETED SEARCH

Build the final query from what steps 1-2 established: confirmed `_sourceCategory`, plus
`_collector` if found, the full time range, field filters matching the observed format, and
the appropriate aggregation. Obey the limit / `nodrop` / bounding rules in Gotchas.

Query shapes, operators, per-domain strategies, and what to do when a query returns nothing:
`references/queries.md`.

## Security questions

Start from `getInsights`, not from logs — an insight already correlates the signals for you.
Workflow, insight query DSL, and rule-creation constraints: `references/siem.md`.

## Time handling

Operate in the user's timezone, ISO 8601. Compute `from`/`to` for relative asks ("last hour",
"yesterday") from the current date in context.

## Asking the user

Ask only when no source expression can be inferred, the data genuinely isn't in the platform,
or you are stuck. One targeted question, and say why it blocks you. Don't re-ask about values
the user already gave you, and don't ask speculative or optional questions.

## Reporting

State what you searched and what you found. Concise by default; expand when asked. No
speculation, no tangents, and no tool names or implementation details in user-facing text.
