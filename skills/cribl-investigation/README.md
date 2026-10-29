# Cribl Investigation

This skill teaches AWS DevOps Agent how to use the Cribl MCP server during an investigation: check the health of a Cribl deployment, find where telemetry delivery is blocked or misrouted, and search the customer's ingested data with Cribl Search.

## ⚠️ Important Notice

This skill is provided as sample code. The Cribl MCP server exposes one configuration-changing tool (`cribl_setPipelineConfig`) and Search Notebook editing tools. The skill tells the agent to propose, never apply, a Pipeline change. Validate its behavior in a non-production environment and give the connecting Cribl user only the permissions the investigation needs.

## Purpose

When telemetry is missing, delayed or wrong, the cause is often in the pipeline that carries it rather than in the application. This skill has the agent check Cribl's own health and alerts, inspect Sources, Destinations, Pipelines and Worker Groups for backpressure or misrouting, and query the ingested logs and metrics, so it can tell a pipeline problem apart from an application problem.

## Key Capabilities

- Read Cribl deployment health with `cribl_getSystemMetrics` and `cribl_getAlerts`
- Inspect Sources, Destinations and Pipelines, scoped per Worker Group and Pack
- Run Cribl Search (KQL) over ingested data, starting from `cribl_getSearchContext`
- Query ingested metrics with PromQL and list metric monitors
- Describe an exact Pipeline change for an operator to approve

## Prerequisites

- A Cribl.Cloud workspace with the MCP server enabled (Settings > Global > MCP Server)
- The Cribl connector added to your Agent Space, with your `<workspace>-<organization>` tenant and a Cribl Bearer token
- A Cribl user with read access to the Stream Worker Groups and Search Datasets the investigation needs

## Setup

1. Connect Cribl to your Agent Space by following [connectors/cribl/README.md](https://github.com/aws/tools-for-devops-agent/blob/main/connectors/cribl/README.md).
2. Install this skill in the same Agent Space.

## Sample prompts

- "Our CloudWatch dashboards stopped showing web access logs 30 minutes ago. Check whether Cribl is still delivering them."
- "Find authentication failures in the last 24 hours in Cribl Search."
- "Is any Cribl Destination under backpressure right now?"

## Limitations

- Cribl.Cloud only. On-prem and standalone Docker MCP servers are not covered by the connector.
- Bearer tokens expire after about 24 hours on Cribl.Cloud. Repeated HTTP 401 errors mean the token needs refreshing.
- Tools follow the connecting user's RBAC, so some Worker Groups or Datasets may return a permission error.
