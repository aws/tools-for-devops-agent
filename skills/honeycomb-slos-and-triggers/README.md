# Honeycomb SLOs and Triggers Skill

This skill enables the AWS DevOps Agent to read Honeycomb SLO compliance, error budget burn and trigger status, and to decide what to do about them.

## Purpose

SLO and trigger numbers need context: a burn rate can justify a page or only a ticket, and an SLO at 0% compliance can mean an outage or a misconfigured SLI. The skill explains what the numbers mean and when to act. It also covers how to design SLOs, burn alerts and triggers.

## Key Capabilities

- Interpret SLO compliance, remaining budget and burn rate
- Decide when a burn rate justifies paging someone or freezing deploys
- Spot a misconfigured SLI
- Read trigger status and design count-based triggers
- Create an SLO, trigger or board when the operator asks, after the operator confirms it

## Prerequisites

- The Honeycomb connector in your Agent Space, with its read tools enabled.
- Creating an SLO, trigger or board needs write access: choose **Read-write** when you sign in, or use a Management key with **Write** under **Model Context Protocol**. The Honeycomb connector's README says how.

## Limitations

- Workspaces have a limited number of SLOs and triggers.
- A new SLO can take a few minutes to backfill before it shows data.

## Agent Types

This skill is used by the following agent types:

- **Incident triage** — the first look at an incoming incident
- **Incident RCA** — root cause analysis during an investigation
- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Honeycomb connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/honeycomb-slos-and-triggers` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

## How to Use This Skill

### Chat

- "Our checkout availability SLO shows 4% budget remaining and a burn rate of 6x. Should we page someone or freeze deploys?"
- "A Honeycomb SLO reports 0% compliance even though the service looks healthy. What is going on?"

### Investigation

- "Check which Honeycomb SLOs are burning budget and which triggers are firing in production."

## Non-production disclaimer

> ⚠️ Maintained by Honeycomb. Review anything the agent proposes to create in Honeycomb before you approve it, and validate the skill in a non-production environment first.
