# Honeycomb Production Investigation Skill

This skill enables the AWS DevOps Agent to find the root cause of a production issue with Honeycomb telemetry.

## Purpose

When latency spikes, errors surge, a deployment regresses or a dependency fails, the skill gives the order of Honeycomb MCP tool calls that leads to a root cause: orient in the workspace, run a broad query, compare the anomaly with its baseline in BubbleUp, drill into traces, and verify the hypothesis with a filtered query. It carries each result into the next step.

## Key Capabilities

- Characterize latency spikes with HEATMAP and percentile queries
- Find what differs in the anomalous requests with BubbleUp
- Drill into a representative trace to find the slow or failing span
- Verify a hypothesis by comparing queries with and without the suspected cause
- Follow patterns for latency spikes, error surges, deployment regressions and dependency failures
- Create a board of the findings when the operator asks, after the operator approves it

## Prerequisites

- The Honeycomb connector in your Agent Space, with its read tools enabled.
- Creating a board, SLO or trigger needs write access: choose **Read-write** when you sign in, or use a Management key with **Write** under **Model Context Protocol**. The Honeycomb connector's README says how.

## Limitations

- The skill can only find what your instrumentation sends to Honeycomb. Missing spans or attributes show up as gaps.
- It creates nothing unless the operator asks, and shows the proposed board first.

## Agent Types

This skill is used by the following agent types:

- **Incident triage** — the first look at an incoming incident
- **Incident RCA** — root cause analysis during an investigation
- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Honeycomb connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/honeycomb-production-investigation` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

## How to Use This Skill

### Investigation

- "p99 latency on the checkout service jumped from 300ms to 2s in the last hour. Use Honeycomb to find out why."
- "Errors on the payments API spiked right after the 14:00 deploy. Investigate in Honeycomb whether the new version caused it."
- "Calls from the orders service to its database started timing out. Use Honeycomb to find which dependency is failing."

### Chat

- "Make a Honeycomb board of what you found in this investigation."

## Non-production disclaimer

> ⚠️ Maintained by Honeycomb. Review anything the agent proposes to create in Honeycomb before you approve it, and validate the skill in a non-production environment first.
