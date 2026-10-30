# Sumo Logic Investigator Skill

This skill enables the AWS DevOps Agent to investigate incidents and answer operational questions with Sumo Logic logs, alerts, dashboards and SIEM insights.

## Purpose

During an investigation the agent has to pick the right Sumo Logic tool, scope its queries, and read the results. The skill tells the agent to sample first, discover the data topology, then run targeted, scoped log searches, and to check alerts, dashboards and insights before concluding that data doesn't exist.

## Key Capabilities

- Sample and discover partitions, fields and extraction rules before querying
- Run scoped log searches and aggregate the results
- Check monitors, alerts and SIEM insights related to an incident
- Inspect dashboards for context

## Prerequisites

- The Sumo Logic connector in your Agent Space, with its read tools enabled. Read-only access is enough.

## Limitations

- The agent acts as the user who signed in, so it sees only what that user's roles allow.
- Tools that create dashboards or detection rules, or update insights, change Sumo Logic content. Leave them disabled or require approval.

## Agent Types

This skill is used by the following agent types:

- **Incident triage** — initial assessment of an incoming incident
- **Incident RCA** — root cause analysis during an investigation
- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Sumo Logic connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/sumo-logic-investigator` directory.

## How to Use This Skill

### Chat

- "Search Sumo Logic for errors from the checkout service in the last hour and group them by message."
- "Which Sumo Logic monitors fired in the last 24 hours?"

### Investigation

- "Check Sumo Logic logs and insights around the time this alarm fired."

## Non-production disclaimer

> ⚠️ Maintained by Sumo Logic. The skill only reads from Sumo Logic unless write tools are enabled. Validate it in a non-production environment first.
