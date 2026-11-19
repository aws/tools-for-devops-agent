# ClickHouse Observability Investigation Skill

This skill enables AWS DevOps Agent to investigate incidents and answer operational questions with logs, traces and metrics in ClickHouse Observability, the managed ClickStack service in ClickHouse Cloud. It uses the tools of the hosted ClickStack MCP server, which ClickHouse Observability runs for you on top of the open-source ClickStack MCP server.

## Purpose

During an investigation the agent has to find the right ClickStack source, scope its queries and pick the right tool. The skill gives it an order to follow: discover sources, check service health against yesterday, then branch into error, latency or change analysis, and confirm findings with example rows and traces.

## Key Capabilities

- Discover log, trace and metric sources and their columns before querying
- Rank unhealthy services by error rate and latency against a baseline window
- Explain error spikes with log patterns and attribute deltas between failing and healthy rows
- Break down latency regressions to the slowest child operations, and show an example trace
- Find log patterns that are new or gone since a baseline, such as after a deployment
- Query OpenTelemetry metrics, including runtime metrics for a flagged service
- Check firing alerts and existing dashboards

## Prerequisites

- The ClickHouse Observability connector in your Agent Space. Reading needs no extra permissions beyond your role in ClickHouse Observability.

## Limitations

- The agent acts as the user who connected ClickHouse Observability, so it sees only the sources that user's role allows.
- The agent queries one service per connection: by default the first observability service provisioned and used by your account, which you can change in **User Preferences** in ClickStack.
- Tools that save or delete dashboards, alerts, saved searches, sources and webhooks change ClickHouse Observability content. The skill uses them only when you ask and confirm. Leave them disabled or require approval to rule writes out.

## Agent Types

This skill is used by the following agent types:

- **Incident triage**: initial assessment of an incoming incident
- **Incident RCA**: root cause analysis during an investigation
- **Chat tasks**: questions the operator asks in chat

## Installing

When you add the ClickHouse Observability connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings, then Add Skill, then Import from repository, and point to the `skills/clickstack-investigation` directory.

## How to Use This Skill

### Chat

- "Which services in ClickHouse Observability have a higher error rate than yesterday?"
- "What new log messages has the checkout service started logging in the last hour?"
- "Why is the p99 latency of the payment API up since 14:00 UTC?"

### Investigation

- "Check ClickHouse Observability logs and traces for the affected service around the time this alarm fired."

## Non-production disclaimer

> Maintained by ClickHouse. The skill only reads from ClickHouse Observability unless you ask for a change and confirm it. Validate it in a non-production environment first.
