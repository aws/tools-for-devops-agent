---
name: coralogix-dashboards
description: Dashboard analysis and editing workflow and rules for using dashboard JSON, filters, variables, and time ranges. Load when the user provides dashboard context (for example a dashboard link) or asks to create or change a dashboard.
metadata:
  author: coralogix
  version: 1.0.0
---

# Dashboards Skill - Analyzing and building Coralogix dashboards

This skill describes how to understand Coralogix dashboards the user links to the chat, and how to create or edit dashboards.

## Dashboard Tools

Use the following tools for dashboard management:

| Task | Tool |
|---|---|
| List the dashboard catalog | `manage_dashboards(action="list")` |
| Fetch a dashboard's indexed metadata by ID or find one semantically | `search_dashboard` |
| List dashboard folders | `list_dashboard_folders` |
| Get, create, update, validate, or delete a dashboard | `manage_dashboards` |
| Create or delete a dashboard folder | `manage_dashboard_folders` |

### Safe dashboard workflow

1. Use `manage_dashboards(action="list")` to browse the catalog, or `search_dashboard` to find a relevant dashboard or retrieve its indexed metadata.
2. Use `list_dashboard_folders` before creating a dashboard when the target folder is unknown.
3. Before creating or updating a dashboard, call `manage_dashboards(action="validate", openAPIDefinition=...)` to validate the definition without saving it. `validate` takes API-language JSON, not the MCP dashboard JSON: produce it with `manage_dashboards(action="generate_openapi", dashboard=...)`.
4. Use `manage_dashboards(action="create", dashboard=...)` to create a new dashboard.
5. Use `manage_dashboards(action="update", dashboard=...)` to overwrite an existing dashboard. The dashboard definition must include its `id`.
6. Use `manage_dashboards(action="delete", id=...)` only after the user explicitly confirms deletion.

`update` replaces the whole dashboard, so call `manage_dashboards(action="get", id=...)` right before updating and change only what the user asked for on the returned object.

`validate` doesn't run the query: a field mapped to a column the query never returns still passes, then renders empty.

Dashboard-folder creation requires a body with `requestId` and `folder` (`name` and optional `parentId`). Folder and dashboard deletion are destructive.

## Building a dashboard

- **Visualize, don't ship tables.** Set a `dynamic` widget's `visualization` to a chart that fits the query's output; use `table` only for raw rows. Map its fields to aliased query columns.
- **Infrastructure and SLO questions want metrics.** For CPU, memory, latency percentiles, or request/error rate, give a `dynamic` widget a `metrics` query: `promqlQuery`, with `promqlQueryType` `PROM_QL_QUERY_TYPE_RANGE` for a series or `PROM_QL_QUERY_TYPE_INSTANT` for one value. Service Catalog can't back a widget, so write the PromQL with the `coralogix-metrics-query` skill.
- **Always set `dataModeType`** on logs, spans, and DataPrime queries: `DATA_MODE_TYPE_ARCHIVE` (Monitoring) or `DATA_MODE_TYPE_HIGH_UNSPECIFIED` (Frequent Search). Omitted, it defaults to Frequent Search. Ask if unsure which tier holds the data.

## Dashboard Analysis

**Dashboard Capabilities:**
When a user provides a Coralogix dashboard link, extract the dashboard ID from the link and fetch the stored JSON definition with `manage_dashboards(action="get", id=...)` if it is not already provided as part of the conversation. Read URL parameters such as `from`, `to`, and `var-*` from the link itself to understand the user-selected time range and variable values.

**Important optional parameters are:**
 - from, to: user chosen time ranges, use this for the dataprime and promql queries. If not provided, ALWAYS use the `relativeTimeFrame` from the dashboard JSON.
   E.g. from=now-86400s to=now
 - var-*: user chosen variables used in the dashboard, use this to understand the dashboard's JSON and to run queries. If not provided ask the user.
   E.g. var-environment=cx440

**Important fields:**
 - filters: default filters YOU MUST ADD to the dataprime and promql queries from the dashboard.
 - relativeTimeFrame: default time range YOU MUST USE if `from` and `to` are not provided in the optional parameters.

**Focused Analysis**: Since dashboards can be large and complex:
   - If the user's question is specific, focus on the relevant widgets/sections
   - If the user's question is vague, list the sections/widgets and let the user choose what to analyze
   - Prioritize widgets that are most relevant to the user's query

**Analysis Guidelines with dashboards:**
- Use read-only tools and actions for investigation. Use `create`/`update`/`delete` only when the user asks to change dashboards or folders.
- Run select queries from the dashboard to help your investigation. Usually the required information will not be in the dashboard JSON but in the results of the queries.
- Focus on interpretation and analysis, not UI navigation
- If no structured JSON is provided, extract the dashboard ID from the link and fetch it with `manage_dashboards(action="get", id=...)`. If that fails, ask the user to validate the link.
- When resulting data indicates an issue, use other skills to investigate deeper
- Always internally validate the dashboard analysis with the actual JSON structure provided

Dashboard link example for dashboard abcdefghijklmnopqrstuvwxyz with time range 1 day and environment variable prod:
    https://[...].coralogix.com/#/dashboards/abcdefghijklmnopqrstuvwxyz?from=now-86400s&to=now&var-environment=prod
