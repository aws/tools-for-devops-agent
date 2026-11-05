# Honeycomb Query Patterns Skill

This skill enables the AWS DevOps Agent to build and read Honeycomb queries on trace, log and event datasets.

## Purpose

A Honeycomb query gives a misleading answer when it uses the wrong operation, the wrong span or the wrong attribute. The skill tells the agent which operation to pick, when to use relational and calculated fields, and how to read the results it gets back.

## Key Capabilities

- Pick percentiles and HEATMAP over AVG for latency
- Use relational fields (`root.`, `parent.`, `any.`, `none.`) to filter spans by their trace
- Use calculated fields and query math for ratios and classifications
- Read P99/P50 ratios, heatmap bands and TOTAL/OTHER rows

## Prerequisites

- The Honeycomb connector in your Agent Space, with its read tools enabled. Read-only access is enough.

## Limitations

- Not for metrics datasets (`dataset_type=metrics`). Use the Honeycomb Metrics Queries skill for those.

## Agent Types

This skill is used by the following agent types:

- **Incident RCA** — root cause analysis during an investigation
- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Honeycomb connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/honeycomb-query-patterns` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

## How to Use This Skill

### Chat

- "Write a Honeycomb query that shows the latency distribution of the /api/orders endpoint over the last 6 hours and explain how to read it."
- "In Honeycomb, how do I count database spans that belong to traces whose root request was POST /checkout?"

### Investigation

- "Show the error rate of the checkout service by route in Honeycomb over the last hour."

## Non-production disclaimer

> ⚠️ Maintained by Honeycomb. The skill only reads from Honeycomb. Validate it in a non-production environment first.
