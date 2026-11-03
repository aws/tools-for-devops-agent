# Honeycomb Create Board Skill

This skill enables the AWS DevOps Agent to design a Honeycomb board and create it after the operator approves the plan.

## Purpose

A useful board starts from the right SLOs and queries. The skill gathers SLOs and context, builds and runs candidate queries, plans the layout, and shows the full proposed board before it creates anything. It handles boards for a service, a feature or an incident.

## Key Capabilities

- Gather SLOs and context for a service, feature or incident
- Build candidate queries and run them to check they return data
- Plan the panels, text and layout
- Show the full proposed board, and create it only after the operator approves

## Prerequisites

- The Honeycomb connector in your Agent Space, with its read tools enabled.
- Creating the board needs write access: choose **Read-write** when you sign in, or use a Management key with **Write** under **Model Context Protocol**. The Honeycomb connector's README says how.

## Limitations

- It creates a board only when the operator asks, and always shows the plan first, even when asked to skip it.
- If `create_board` is missing or returns a permission error, the skill stops and says that it needs write access.

## Agent Types

This skill is used by the following agent types:

- **Incident RCA** — root cause analysis during an investigation
- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Honeycomb connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/honeycomb-create-board` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

## How to Use This Skill

### Chat

- "Make a Honeycomb board for the checkout service in production."
- "Create a golden signals board for the payments service."

### Investigation

- "Make a Honeycomb board for this incident with the queries you used."

## Non-production disclaimer

> ⚠️ Maintained by Honeycomb. Review anything the agent proposes to create in Honeycomb before you approve it, and validate the skill in a non-production environment first.
