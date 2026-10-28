# Grafana Cloud Investigation Skill

This skill enables the AWS DevOps Agent to investigate incidents with the telemetry in a customer's Grafana Cloud stack.

## Purpose

When an incident needs metrics, logs, traces or profiles from Grafana Cloud, the skill gives the agent a working order:
1. Find the relevant data sources and dashboards.
2. Check firing alerts, open incidents and recent annotations.
3. Narrow from service-level metrics to the components that moved, then to their logs and traces.

For open-ended questions it hands the investigation to Grafana Assistant. It keeps queries scoped to the incident window, and backs each finding with a deep link an operator can check.

## Key Capabilities

- Query Prometheus metrics, Loki logs, Tempo traces and Pyroscope profiles in the incident window
- Check alert rules, firing alerts, incidents, on-call schedules and annotations such as deploys
- Ask Grafana Assistant open-ended questions, or start an Assistant investigation and read its report
- Use the server's own instructions and tool descriptions to pick tools, so the skill keeps working as Grafana adds tools
- Propose changes, such as a silence or an incident update, for the operator to approve rather than making them

## Prerequisites

- The Grafana Cloud connector in your Agent Space, with its read tools enabled.
- The person who connects needs the **Assistant Cloud MCP User** role, or the `grafana-assistant-app.cloud-mcp:access` permission, in their Grafana Cloud stack.
- Asking Grafana Assistant, or changing anything in Grafana, needs a connection with write access. Choose read and write access on the consent page when you connect; the Grafana Cloud connector's README says who can grant it.

## Limitations

- The skill can only find what the stack collects. Services without metrics, logs or traces in Grafana Cloud show up as gaps.
- It doesn't change dashboards, alert rules, silences or incidents unless the operator asks.
- On a read-only connection, Grafana Assistant isn't available, and the agent uses the query tools directly.

## Agent Types

This skill is used by the following agent types:

- **Incident triage** — the first look at an incoming incident
- **Incident RCA** — root cause analysis during an investigation
- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Grafana Cloud connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/grafana-cloud-investigation` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

## How to Use This Skill

### Investigation

- "Error rates on the checkout service in Grafana Cloud jumped in the last 30 minutes. Find out why."
- "The `HighLatency` alert fired for the payments API at 14:05. Check Grafana Cloud for what changed around then."
- "Did the 13:00 deploy of the orders service cause the spike in 5xx responses? Use the Grafana Cloud metrics and logs."

### Questions

- "Ask Grafana Assistant what's driving the memory growth on the ingest pods."
- "Which Grafana Cloud alerts are firing right now, and who's on call for them?"
