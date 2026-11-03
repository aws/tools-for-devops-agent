# Grafana Cloud Investigation Skill

This skill enables the AWS DevOps Agent to investigate incidents with the telemetry in a customer's Grafana Cloud stack.

## Purpose

When an incident needs metrics, logs, traces or profiles from Grafana Cloud, the skill gives the agent a working order:
1. Find the relevant data sources and dashboards.
2. Check firing alerts, open incidents and recent annotations.
3. Narrow from service-level metrics to the components that moved, then to their logs and traces.

It keeps queries scoped to the incident window, backs each finding with a deep link an operator can check, and, when the operator approves, hands open-ended questions to Grafana Assistant.

## Key Capabilities

- Query Prometheus metrics, Loki logs, Tempo traces and Pyroscope profiles in the incident window
- Check alert rules, firing alerts, incidents, on-call schedules and annotations such as deploys
- Ask Grafana Assistant open-ended questions, or start an Assistant investigation, when the operator asks or approves, and read existing investigations and their reports
- Use the server's own instructions and tool descriptions to pick tools, so the skill keeps working as Grafana adds tools
- Propose changes, such as a silence or an incident update, for the operator to approve, and confirm every write with an exact preview before making it

## Prerequisites

- The Grafana Cloud connector in your Agent Space, with its read tools enabled.
- The person who connects needs the **Assistant Cloud MCP User** role, or the `grafana-assistant-app.cloud-mcp:access` permission, in their Grafana Cloud stack.
- Read access is enough for investigations. Asking Grafana Assistant, or changing anything in Grafana, needs **Write** access, and the SQL query tools need **Query** access. The Grafana Cloud connector's README explains the three access levels and who can grant them.
- If you grant Query or Write, require approval for those tools in DevOps Agent.

## Limitations

- The skill can only find what the stack collects. Services without metrics, logs or traces in Grafana Cloud show up as gaps.
- It makes no writes unless the operator asks. Before each one it shows exactly what it will do and waits for confirmation, and it doesn't retry a write the operator declined.
- It runs only `SELECT` statements with the SQL query tools, and uses the raw Grafana API fallback only for GET requests.
- On a connection without Write access, Grafana Assistant isn't available, and the agent uses the read tools directly.

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

## Non-production disclaimer

> ⚠️ Maintained by Grafana Labs. Review anything the agent proposes to change in Grafana before you approve it, and validate the skill in a non-production environment first.
