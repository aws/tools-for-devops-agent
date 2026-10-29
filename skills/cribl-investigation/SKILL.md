---
name: cribl-investigation
description: Use the Cribl MCP tools to investigate a Cribl observability-pipeline environment during an incident — check deployment health and alerts, review Sources, Destinations, Pipelines, and Worker Groups, run Cribl Search (KQL) over ingested data, and query ingested metrics. Load this when an investigation involves Cribl, data-pipeline delivery, missing or delayed telemetry, or a Cribl-sourced alert.
metadata:
  author: criblio
  version: "1.0.0"
  tier: partner-managed
  summary: "Investigate Cribl pipeline health, Sources, Destinations, Pipelines and Cribl Search data during an incident."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Investigating with Cribl

Cribl is an observability data-pipeline platform. These tools read and (for one tool) change the configuration of a Cribl environment, run Cribl Search over the customer's ingested data, and query the metrics they ingest. Every call runs with the connecting user's own Cribl identity and RBAC, so a tool may be absent from the list or return a permission error for a specific Worker Group or Dataset — that is expected, not a bug.

## When to use which tool

Health and alerts (the state of the Cribl deployment itself):
- `cribl_getSystemMetrics` — system metrics for the deployment, filterable by expression, metric name, and time range. Start here for "is Cribl healthy?"
- `cribl_getAlerts` — Cribl's own alerts and system messages, with filtering and pagination.
- `cribl_listWorkerGroups` — list Worker Groups, optionally by product type. Use before scoping other calls.

Pipeline configuration (why data is or isn't flowing the way it should):
- `cribl_getSources` / `cribl_getDestinations` — input and output configs. Pass `groupName` to scope to a Worker Group.
- `cribl_getPipelines` — Pipeline definitions; `groupName` scopes it, and it can reach Pipelines inside Packs.
- `cribl_getPipelineConfig` — full config for one Pipeline by ID. For a Pipeline inside a Pack, pass `groupName` and `packId`.
- `cribl_setPipelineConfig` — **write tool**. Applies a new Pipeline config. Requires Stream write access and should be treated as an approval-gated change, not an investigation read. Do not call it to diagnose; propose the change and let the operator approve.

Cribl Search (the customer's ingested log/event data, queried with KQL):
- `cribl_getSearchContext` — **call this first** unless you already know the Dataset and exact KQL. Returns available Datasets, saved searches, and KQL guidance.
- `cribl_runSearchQuery` — run an exact KQL query. Fast queries return inline; longer ones return a job ID.
- `cribl_getSearchJobResults` — status and paginated results for a job ID, including previews while it runs.
- `cribl_getSearchNotebooks` / `cribl_addToSearchNotebook` / `cribl_editSearchNotebookSection` / `cribl_removeSearchNotebookSection` — read and edit Search Notebooks (the editing tools are write operations).

Ingested metrics (Prometheus remote-write data, not Cribl's own health):
- `cribl_queryMetrics` — a PromQL query, or a metadata command like `.labels` or `.metrics`, over ingested metrics.
- `cribl_getMonitors` — alert-on-metric rules for ingested metrics.

> `cribl_queryMetrics` and `cribl_getMonitors` are about the metrics the customer ingests into Cribl, **not** Cribl's own health. For deployment health use `cribl_getSystemMetrics` and `cribl_getAlerts`.
> cribl_getDatasetIntelligence - Pass in a datasetId to retrieve its generated Dataset Intelligence card if enabled. The card will show an Overview of the dataset, record families, semantic field mappings, starter queries, investigation playbook, and limitations

## A typical investigation

1. `cribl_getSystemMetrics` and `cribl_getAlerts` for an overall health read and any firing Cribl alerts.
2. `cribl_listWorkerGroups` to see the groups, then `cribl_getSources` / `cribl_getDestinations` / `cribl_getPipelines` scoped by `groupName` to find where delivery is blocked, backpressured, or misrouted.
3. If the question is about the data itself (for example "find authentication failures in the last 24h"), call `cribl_getSearchContext` first to discover Datasets and KQL syntax, then `cribl_runSearchQuery`, then `cribl_getSearchJobResults` for a long-running job.
4. Summarize findings and, only if a config change is clearly warranted, describe the exact `cribl_setPipelineConfig` change for an operator to approve — never apply it silently.

## Pitfalls

- A Dataset or KQL query you assume may not exist. When search returns nothing useful, call `cribl_getSearchContext` and re-check available Datasets and syntax before concluding.
- A tool missing from the list means the token lacks that product access (Search / Stream) — report it as a permissions gap, do not retry.
- A tool present in the list can still return `Forbidden: insufficient API permissions for this tool (RBAC).` for a Worker Group or Dataset outside the user's access. That is call-time enforcement, not a transient error.
- Tokens expire (about 24h on Cribl.Cloud). Repeated HTTP 401s mean the token needs refreshing on the customer side; HTTP 403 means the MCP server was disabled.
- For a Pipeline inside a Pack, you must name both the Pack (`packId`) and its Worker Group (`groupName`).
