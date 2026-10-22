---
name: coralogix-docs
description: Search and read official Coralogix platform documentation using **`search_docs`** and **`fetch_doc`**. Use when the user asks how Coralogix features work, how to configure or use the UI, set up integrations (OpenTelemetry, agents, collectors, webhooks), manage API keys, explore spans/traces/logs in the product, configure alerts/SLOs/dashboards, or needs authoritative product docs — not live tenant telemetry.
metadata:
  author: "coralogix"
  version: "1.0.0"
  tier: "partner-managed"
  agent_types: "CHAT,INCIDENT_TRIAGE,INCIDENT_RCA,INCIDENT_MITIGATION,INCIDENT_UI"
---

# Coralogix docs (`search_docs`, `fetch_doc`)

These MCP tools read **official Coralogix product documentation** from [coralogix.com/docs](https://coralogix.com/docs). They answer **how the platform works** and **how to configure or use it**. They do **not** query your tenant's logs, spans, metrics, or alerts.

## When to use these tools

Use **`search_docs`** + **`fetch_doc`** when the user wants:

| Topic | Example questions |
|-------|-------------------|
| **UI / workflows** | "How do I view spans in Coralogix?", "Where is Explore spans?" |
| **Ingestion & integrations** | OpenTelemetry setup, agent/collector config, Send Your Data API keys |
| **Platform features** | Alerts, SLOs, dashboards, enrichments, parsing rules, retention |
| **Concepts & architecture** | How tracing works, trace-log correlation, data model |
| **Account & access** | API keys, SSO, roles, regions |

**Prefer these tools over guessing** when the answer depends on current Coralogix product behavior or UI navigation.

## When **not** to use these tools

| User need | Use instead |
|-----------|-------------|
| **Query live logs** | **`query_dataprime`** with `source logs` — [coralogix-logs](skill://coralogix-logs/SKILL.md) |
| **Query live spans/traces** | **`query_dataprime`** with `source spans` — [coralogix-spans](skill://coralogix-spans/SKILL.md) |
| **DataPrime syntax / commands** | [dataprime](skill://coralogix-dataprime/SKILL.md) — **`list_dataprime_commands`**, **`show_dataprime_command_details`**, **`list_dataprime_constructs`**, **`describe_dataprime_construct`** |
| **RUM SDK install & API** | **`read_rum_sdk_docs`** — [coralogix-rum](skill://coralogix-rum/SKILL.md) |
| **Alerts or incidents in the tenant** | **`olly_ask`** — [olly](skill://coralogix-olly/SKILL.md) |
| **Metrics (PromQL)** | [metrics-query](skill://coralogix-metrics-query/SKILL.md) |
| **Discover field paths in tenant data** | **`search_for_fields`** |

## Tool reference

| Tool | Purpose |
|------|---------|
| **`search_docs`** | Find doc pages by keyword. Returns numbered titles + path suffixes. |
| **`fetch_doc`** | Download one page as markdown. Pass the suffix from **`search_docs`**. |

### `search_docs`

- **`query`**: Short, specific keywords (feature name, integration, UI area). Examples: `"explore spans"`, `"OpenTelemetry traces"`, `"API keys"`, `"MCP setup"`.
- **`limit`**: 1–20 results (default 5). Increase when the first page of hits is ambiguous.

Tips:

- Start with **2–4 focused terms**, not full sentences.
- If no matches, try synonyms or broader terms (`"tracing"` instead of `"distributed trace waterfall view"`).
- Re-run with different wording before giving up.

### `fetch_doc`

- **`suffix`**: Path suffix from **`search_docs`** (e.g. `user-guides/data_exploration/spans/`).
- Returns the page URL plus full markdown body.

Tips:

- **`fetch_doc` one page at a time** — pick the best match from search results first.
- If the page is incomplete, **`search_docs`** again for a related page and **`fetch_doc`** that too.
- Cite the doc URL when answering the user.

## Standard workflow

1. **`search_docs`** with a focused **`query`**.
2. Pick the most relevant suffix from the results (prefer user-guides / integrations over release notes unless the user asked about a new feature).
3. **`fetch_doc`** on that suffix.
4. Answer from the fetched content. Fetch additional pages only when needed.

```
User: "How do I show spans in the Coralogix website?"

1. search_docs(query="explore spans", limit=5)
2. fetch_doc(suffix="user-guides/data_exploration/spans/")
3. Summarize: Explore → spans dataset → Spans/Traces/Flows tabs → drilldown
```

```
User: "How do I send OpenTelemetry traces to Coralogix?"

1. search_docs(query="OpenTelemetry traces ingestion", limit=5)
2. fetch_doc(suffix=<best match from search>)
3. If needed: fetch_doc on a second page (collector vs direct export)
```

## Examples

**Good `search_docs` queries**

- `"explore spans"`
- `"OpenTelemetry custom traces"`
- `"Send Your Data API key"`
- `"alert webhook"`
- `"trace log correlation"`

**Avoid**

- `"how do I fix my slow checkout service"` → query **live spans** with **`query_dataprime`**, not docs.
- `"filter syntax for groupby"` → use **`coralogix-dataprime`** skill / command catalog, not general docs search (unless catalog is insufficient).
- `"install @coralogix/browser"` → use **`read_rum_sdk_docs`** with topic `BROWSER_SDK`.

## Troubleshooting

| Problem | Action |
|---------|--------|
| **`search_docs` returns no matches** | Broaden or rephrase the query; try feature name + category (`"spans UI"`, `"OTel ingestion"`). |
| **Fetched page is too narrow** | Search for the parent topic or run a second search with related terms. |
| **User wants their actual data** | Switch to telemetry tools (`query_dataprime`, metrics, `olly_ask`) — docs describe the product, not tenant contents. |

## Related

- **Logs queries:** [coralogix-logs](skill://coralogix-logs/SKILL.md)
- **Traces / spans queries:** [coralogix-spans](skill://coralogix-spans/SKILL.md)
- **DataPrime language:** [dataprime](skill://coralogix-dataprime/SKILL.md)
- **RUM SDK docs:** [coralogix-rum](skill://coralogix-rum/SKILL.md)
- **Investigation (alerts, incidents):** [olly](skill://coralogix-olly/SKILL.md)
