---
name: grafana-cloud-investigation
title: Grafana Cloud investigations
description: Use the Grafana Cloud connector to investigate incidents with the customer's Grafana Cloud telemetry. Covers choosing tools, handing open-ended questions to Grafana Assistant, read and write access, keeping results small, and querying Prometheus, Loki and Tempo data. Use when an investigation needs metrics, logs, traces or profiles from Grafana Cloud, when checking Grafana dashboards, alert rules, incidents or on-call schedules, or when the customer asks a question about their Grafana Cloud stack.
metadata:
  author: "sd2k"
  version: "1.0.0"
  tier: "partner-managed"
  summary: "Investigate incidents with Grafana Cloud metrics, logs, traces, dashboards, alerts and Grafana Assistant."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Grafana Cloud investigations

The Grafana Cloud connector reaches the customer's Grafana Cloud stack through Grafana's hosted MCP server. It acts as the person who connected it, so it can see and do only what their Grafana roles allow.

## Choosing tools

The server's tools change as Grafana adds capabilities, so this skill doesn't list them. Rely on the server instead:

- Read the server's instructions and each tool's description. They're kept current with the server and say what each tool does and when to use it.
- Pick tools by what you need. There are tools for dashboards, data sources, Prometheus, Loki, Tempo and Pyroscope queries, SQL data sources, alerting, incidents, on-call, annotations, Grafana Assistant investigations, deep links and panel rendering.
- When no dedicated tool covers a task, the server describes fallbacks (a Grafana CLI tool and a raw Grafana API tool). Use those before concluding the data isn't available.
- If a tool you expect isn't available, the connection may be read-only, or the feature may not be enabled on the stack. Say so in your findings rather than guessing.

## A typical investigation

1. Find the relevant data sources and dashboards for the affected service before querying anything.
2. Check firing alerts, open incidents and recent annotations (deploys, config changes) in the incident's time window.
3. Query metrics for the service's error rate, latency and saturation around the incident start, then narrow to the components that moved.
4. Query logs for the same components and window, and pull traces for slow or failing requests.
5. Include deep links to the dashboards, Explore queries or traces that support each finding, so an operator can check them.

## Grafana Assistant

- For open-ended questions about the stack ("Why is checkout latency spiking?", "What changed before this alert fired?"), hand the question to Grafana Assistant. It plans its own investigation across metrics, logs and traces and returns a grounded answer. For longer root-cause work, start an Assistant investigation and read its report.
- Asking Grafana Assistant needs a connection with write access. On a read-only connection, use the query tools directly and note that Assistant wasn't available.
- For targeted lookups (a known query, dashboard, alert or incident), call the specific tool directly. Going through Assistant there only adds latency.

## Keeping results small

- Prefer the tools that return a dashboard's summary or a single property over the one that returns its full JSON.
- Discover metric and label names before writing PromQL or LogQL, rather than guessing.
- Always set a time range, starting from the incident window, and widen it only if needed.
- In Loki, use label matchers to select streams before filtering on line content.
- Aggregate before returning series: a `sum by (...)` or `topk` is usually more useful than hundreds of raw series.

## Safety

- Don't change anything in Grafana (dashboards, alert rules, silences, incidents) unless an operator asked for it.
- Prefer read-only steps during triage and root-cause analysis. Propose changes, such as a silence or an incident update, as recommended actions for the operator to approve.
