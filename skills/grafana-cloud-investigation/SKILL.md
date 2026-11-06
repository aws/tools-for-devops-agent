---
name: grafana-cloud-investigation
title: Grafana Cloud investigations
description: Use the Grafana Cloud connector to investigate incidents with the customer's Grafana Cloud telemetry. Covers choosing tools, when to use Grafana Assistant, the Read, Query and Write access levels, confirming every write with the operator, keeping results small, and querying Prometheus, Loki and Tempo data. Use when an investigation needs metrics, logs, traces or profiles from Grafana Cloud, when checking Grafana dashboards, alert rules, incidents or on-call schedules, or when the customer asks a question about their Grafana Cloud stack.
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
- When no dedicated tool covers a task, the server describes fallbacks: a Grafana CLI tool and a raw Grafana API tool. Use them only to read: GET requests with the API tool, and only commands that read with the CLI tool. Never use them to create, change or delete anything.
- The SQL query tools run a query exactly as written. Only run `SELECT` queries; treat any other statement as a write.
- If a tool you expect isn't available, the connection may not have been granted that access level, or the feature may not be enabled on the stack. Say so in your findings rather than guessing.

## A typical investigation

1. Find the relevant data sources and dashboards for the affected service before querying anything.
2. Check firing alerts, open incidents and recent annotations (deploys, config changes) in the incident's time window.
3. Query metrics for the service's error rate, latency and saturation around the incident start, then narrow to the components that moved.
4. Query logs for the same components and window, and pull traces for slow or failing requests.
5. Include deep links to the dashboards, Explore queries or traces that support each finding, so an operator can check them.

## Grafana Assistant

- Investigate with the read tools first. Grafana Assistant can plan its own investigation across metrics, logs and traces, but asking it a question or starting an Assistant investigation is a write: it needs a connection with Write access and counts toward the stack's Grafana Assistant usage.
- Use Grafana Assistant only when an operator asks for it, or when you recommend it and the operator approves. Follow the rules for writes below, showing the exact question you'll send.
- On a connection without Write access, the Assistant tools aren't available. Use the read tools and say in your findings that Assistant wasn't used.
- Reading existing Assistant investigations, their reports and their evidence is a read, and is fine at any time.

## Keeping results small

- Prefer the tools that return a dashboard's summary or a single property over the one that returns its full JSON.
- Discover metric and label names before writing PromQL or LogQL, rather than guessing.
- Always set a time range, starting from the incident window, and widen it only if needed.
- In Loki, use label matchers to select streams before filtering on line content.
- Aggregate before returning series: a `sum by (...)` or `topk` is usually more useful than hundreds of raw series.

## Rules for writes

A write is any call that creates, changes or deletes something in Grafana (dashboards, alert rules, silences, incidents, annotations, data sources), asks Grafana Assistant a question, starts an Assistant investigation, or runs SQL other than `SELECT`.

1. Only make a write when an operator explicitly asked for it. During triage and root-cause analysis, propose changes as recommended actions instead.
2. Before each write, show the operator exactly what you'll do: the tool, the target, and the full change, query or question.
3. Ask for confirmation immediately before the call, and make the call only after the operator confirms.
4. If the operator declines, or DevOps Agent's approval is denied, don't retry the write and don't try another tool or route to the same effect. Report that it wasn't made.
