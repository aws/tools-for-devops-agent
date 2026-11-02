# Honeycomb Metrics Queries Skill

This skill enables the AWS DevOps Agent to query Honeycomb OpenTelemetry metrics datasets correctly.

## Purpose

Metrics datasets follow different rules from trace datasets. Some operations are rejected, temporal aggregation is automatic, and each metric has its own attributes. The skill tells the agent how to find the metrics dataset, which operations are allowed, and how to aggregate gauges, counters, histograms and sums.

## Key Capabilities

- Find the metrics dataset and the metrics and attributes in it
- Avoid operations that metrics datasets reject, such as bare COUNT and the RATE_* operations
- Apply the right temporal aggregation for each metric type, and override it when needed
- Query histograms and use query math for utilization, tail and error ratios
- Query infrastructure metrics such as CPU, memory, disk I/O and network

## Prerequisites

- The Honeycomb connector in your Agent Space, with its read tools enabled. Read-only access is enough.

## Limitations

- Only for datasets with `dataset_type=metrics`. Event datasets that only have metrics in their name use the Honeycomb Query Patterns skill.

## Agent Types

This skill is used by the following agent types:

- **Incident RCA** — root cause analysis during an investigation
- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Honeycomb connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/honeycomb-metrics-queries` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

## How to Use This Skill

### Chat

- "Using our Honeycomb OpenTelemetry metrics dataset, show average CPU utilization per host over the last 3 hours."
- "How do I graph requests per second from the http.server.request.count counter in a Honeycomb metrics dataset?"

### Investigation

- "Memory on the checkout hosts looks high. Check the Honeycomb metrics dataset for when it started."

## Non-production disclaimer

> ⚠️ Maintained by Honeycomb. The skill only reads from Honeycomb. Validate it in a non-production environment first.
