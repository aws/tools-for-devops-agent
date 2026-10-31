---
name: cribl-investigation
description: Investigate incidents that involve a Cribl observability pipeline. Decide whether Cribl caused the problem, witnessed it, or is not involved; trace missing or delayed telemetry from Source to Destination; and search the customer's ingested data with Cribl Search (KQL) and PromQL. Load this when an investigation involves Cribl, data-pipeline delivery, missing or delayed telemetry, or a Cribl-sourced alert.
metadata:
  author: criblio
  version: "1.0.0"
  tier: partner-managed
  summary: "Investigate whether Cribl caused, witnessed, or is unrelated to an incident, and gather evidence from pipeline health, config, and Cribl Search data."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Investigating with Cribl

Cribl is an observability data pipeline. It receives telemetry from Sources, processes it in Pipelines, and delivers it to Destinations. It also stores data that customers can query with Cribl Search. In an incident, Cribl can be the thing that broke, a record of what broke elsewhere, or unrelated.

Every tool call runs with the connecting user's Cribl identity and RBAC. A missing tool or a permission error for a specific Worker Group or Dataset is expected, not a bug.

## Ground rules

- **Investigate read-only.** `cribl_setPipelineConfig` and the notebook editing tools (`cribl_addToSearchNotebook`, `cribl_editSearchNotebookSection`, `cribl_removeSearchNotebookSection`) change customer state. Never call them during an investigation. Propose the exact change and let an operator approve it.
- **Every claim needs evidence:** the tool, the time window, and the numbers. "Destination X stopped" is a guess; "`events_out` for Destination X fell from ~12k/min to 0 at 14:05, while `events_in` stayed flat" is a finding.
- **Prefer "inconclusive" to overclaiming.** Say what evidence would settle the question.

## Step 1 — Anchor the investigation

Before calling any tool, write down:
- **The incident window:** start time, and end time or now. Pass it as `earliest`/`latest` on every metrics and search call.
- **A baseline window:** the same length, just before the incident or at the same time the previous day. Most findings are a comparison against it.
- **The affected signal:** what is missing, late, or wrong, which system should receive it, and which service or host produces it.

If the incident gives no time, find it first: chart throughput or event counts over a wide window and locate the change.

## Step 2 — Decide Cribl's role

Open a hypothesis for each role that could apply. Track each as **confirmed**, **unlikely**, or **inconclusive**.

- **Cause:** Cribl dropped, delayed, or misrouted the telemetry. Typical signals: missing or late data in a downstream tool, a Cribl alert, or a recent Cribl config change. Go to Step 3.
- **Witness:** Cribl delivered normally, and the data it carries is evidence about the real fault (application errors, authentication failures, latency). Go to Step 4.
- **Not involved:** the affected signal never passes through Cribl. Confirm it quickly (no matching Source, Destination, or Dataset), say so, and stop.

An incident can need both: check that delivery is healthy (Step 3), then use the data (Step 4).

## Step 3 — Cribl as the cause: walk the data path

Work through these in order and stop at the first step that breaks. Compare the incident window against the baseline throughout.

1. **Cribl health.**
   - `cribl_getAlerts` for firing alerts and system messages in the window.
   - `cribl_listWorkerGroups` to find the Worker Group that carries the signal.
   - An alert naming the affected Source, Destination, or group is your strongest lead. Note it and continue.
2. **Is data arriving?** `cribl_getSystemMetrics` with `splitBys: ["input"]` and `includeDimensionedSeries: true`. Compare `events_in` for the relevant Source.
   - Dropped to near zero: the problem is upstream of Cribl (the sender, the network, or the Source config). Check `cribl_getSources` for that Source. Cribl is probably a witness to an upstream outage, not the cause.
   - Normal: continue.
3. **Is data leaving?** `cribl_getSystemMetrics` with `splitBys: ["output"]`. Compare `events_out` for the expected Destination.
   - Normal: Cribl delivered. The problem is in the receiving system. Mark "Cause" unlikely.
   - Lower than baseline while input is normal: the problem is inside Cribl. Continue.
   - Pipelines often reduce data on purpose (filtering, sampling, aggregation), so `events_out` below `events_in` is normal. Compare the in/out ratio against the baseline ratio, not in against out.
4. **Inside Cribl, check each in turn:**
   - **Destination:** `cribl_getDestinations` (scope with `groupName`) for the endpoint, auth, and persistent-queue settings. Check `cribl_getAlerts` for unhealthy-Destination, backpressure, or persistent-queue messages. The system metrics tool reports throughput only, not backpressure or queue depth, so alerts are your best signal for those.
   - **Pipeline:** `cribl_getPipelines`, then `cribl_getPipelineConfig` for the Pipeline that handles this data. Look for a filter, drop, sampling, or aggregation step that would discard or reshape it. For a Pipeline inside a Pack, pass both `groupName` and `packId`.
   - **Routes:** no tool exposes Routes. If data enters and never reaches the expected Destination, and neither the Destination nor the Pipeline explains it, the likely cause is a Route sending it elsewhere or nowhere. Say so and ask the operator to confirm.
   - **Recent change:** no tool exposes config history. If the break lines up with a specific time, ask the operator what was deployed then.

Report the step that broke and the numbers that show it.

## Step 4 — Cribl as the witness: search the data

1. `cribl_getSearchContext`: lists the available Datasets, saved searches, and KQL guidance. Pick the candidate Datasets.
2. `cribl_getDatasetIntelligence` for each candidate. It returns an analysis that was saved earlier, so it runs no search. Use it to:
   - Decide relevance from the **Overview** and **Limitations**.
   - Scope first: if **Record Families** says the Dataset mixes many sources, filter by the family field it names (usually `datatype` or `source`) before using any family-specific field.
   - Pick field names from **Semantic Field Mappings** (for example, which field holds the user or request ID).
   - Start from **Starter Queries** and follow the **Investigation Playbook**.
   - Handle `status`: `complete` → use it. `partial` → use it, but verify with a small query. `processing`, `failed`, or `not_generated` → run the returned `suggestedQuery` (a small sample) instead. This tool never generates a card.
3. `cribl_runSearchQuery`: one query per hypothesis, with one primary filter and `earliest`/`latest` set to the incident window. Run the same query over the baseline window. A count only means something when compared with that baseline.
4. `cribl_getSearchJobResults`: for long-running queries that return a job ID. Use `mode: "preview"` to read partial results while the job runs.
5. **Ingested metrics:**
   - `cribl_queryMetrics` runs PromQL over metrics the customer sends into Cribl. Use `.labels` or `.metrics` first to discover names.
   - `cribl_getMonitors` lists the customer's alert rules on those metrics.
   - Neither describes Cribl's own health; for that, use Step 3.
6. **Pivot:** the card's playbook names the best field for grouping related events (for example `trace_id` or `requestId`). Use it to tie Cribl evidence to evidence from other systems in the investigation.

## Step 5 — Distrust empty results

These usually mean you asked the wrong question, not that the data is absent:
- A search that returns nothing, times out, or errors.
- A `summarize ... by <field>` that returns one group where `<field>` is null for every row. The field name is probably wrong; re-check field names from search context or the intelligence card.
- A sample dominated by one record family, which hides fields that exist in other families.

Before you conclude data is missing, run a field-coverage check or a small sample over the window. Retry a timed-out search once with a shorter window and a smaller `limit`. The intelligence card is a snapshot: if a query built from it returns nothing, sample the Dataset to check whether the schema has changed.

## Step 6 — Know when to stop

Stop when:
- one hypothesis is confirmed and the others are unlikely, or
- about three queries on a hypothesis have made no progress. Mark it inconclusive and name the evidence that would settle it (for example "Route config for group X" or "deploy log for 14:00–14:10").

Do not keep widening the search to find something.

## Step 7 — Report

Use this structure:
- **Cribl's role:** cause, witness, or not involved, with a confidence level.
- **Hypotheses:** each with its verdict (confirmed, unlikely, inconclusive) and one line of evidence. For each piece of evidence, give the tool or query, the time window, and incident vs baseline numbers.
- **Where it broke:** the step from Step 3, if Cribl is the cause.
- **Gaps:** what you could not check (Routes, config history, permissions) and who can check it.
- **Proposed change (if warranted):** the exact `cribl_setPipelineConfig` change, or the Destination or Route fix, for an operator to approve. Never apply it.

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
- `cribl_getDatasetIntelligence` — the saved intelligence card for one Dataset: overview, record families, KQL field rules, semantic field mappings, starter queries, an investigation playbook, and limitations. Call it after `cribl_getSearchContext`, before writing KQL. Instant; runs no search.
- `cribl_runSearchQuery` — run an exact KQL query. Fast queries return inline; longer ones return a job ID.
- `cribl_getSearchJobResults` — status and paginated results for a job ID, including previews while it runs.
- `cribl_getSearchNotebooks` / `cribl_addToSearchNotebook` / `cribl_editSearchNotebookSection` / `cribl_removeSearchNotebookSection` — read and edit Search Notebooks (the editing tools are write operations).

Ingested metrics (Prometheus remote-write data, not Cribl's own health):
- `cribl_queryMetrics` — a PromQL query, or a metadata command like `.labels` or `.metrics`, over ingested metrics.
- `cribl_getMonitors` — alert-on-metric rules for ingested metrics.

> `cribl_queryMetrics` and `cribl_getMonitors` are about the metrics the customer ingests into Cribl, **not** Cribl's own health. For deployment health use `cribl_getSystemMetrics` and `cribl_getAlerts`.

## Pitfalls

- **Missing tool:** the token lacks that product access (Search or Stream). Report it as a permissions gap; do not retry.
- **`Forbidden: insufficient API permissions for this tool (RBAC).`:** the Worker Group or Dataset is outside the user's access. It is enforced at call time and is not transient.
- **HTTP 401:**
  - Cribl.Cloud: the token has expired (tokens last about 24 hours), so it needs refreshing on the customer side.
  - On-prem Leader: token lifetime follows the Leader's auth settings.
- **HTTP 403:**
  - "Leader MCP is disabled": an admin must enable the MCP server under Settings > Global > MCP Server.
  - Any other 403: the user may lack the Leader MCP Access permission, which an admin grants.
- **Reduced throughput is not a fault:** Pipelines often filter, sample, or aggregate data on purpose. Compare against the baseline, not against zero loss.
- **Two kinds of metrics:** `cribl_queryMetrics` and `cribl_getMonitors` cover the customer's ingested metrics. Cribl's own health comes from `cribl_getSystemMetrics` and `cribl_getAlerts`.
- **Intelligence cards are snapshots:** a card can be out of date. Verify any surprising claim with a small query.

