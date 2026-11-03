# Honeycomb Verify Recent Trace Skill

This skill enables the AWS DevOps Agent to find the Honeycomb traces a recent test or deployment produced.

## Purpose

After a test or deployment, the quickest check is the trace it produced. The skill finds the traces created since the test started, summarizes the most recent one, and explains what to check when no traces appear.

## Key Capabilities

- Get a trace by ID
- Find all traces since a test started
- Find the most recent trace and summarize its root span, span count and services
- Link to the trace in Honeycomb
- Diagnose a missing trace by checking the time range

## Prerequisites

- The Honeycomb connector in your Agent Space, with its read tools enabled. Read-only access is enough.

## Limitations

- It needs the time the test started, from the operator or the test record.

## Agent Types

This skill is used by the following agent types:

- **Release testing** — checking what a test or deployment produced
- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Honeycomb connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/honeycomb-verify-recent-trace` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

## How to Use This Skill

### Release testing

- "I just ran the checkout integration test against staging. Find the trace it produced in Honeycomb."

### Chat

- "Honeycomb shows no traces from my test that ran about 10 minutes ago. What should I check?"
- "Show me the most recent trace for the payments service in Honeycomb."

## Non-production disclaimer

> ⚠️ Maintained by Honeycomb. The skill only reads from Honeycomb. Validate it in a non-production environment first.
