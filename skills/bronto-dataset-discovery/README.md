# Bronto Dataset Discovery

This skill has AWS DevOps Agent find where an affected service's logs live in Bronto before it searches them. It returns the datasets to use, the key that identifies the service in each one, and whether there are events in the incident window.

## Purpose

A Bronto organization can hold hundreds of datasets, grouped into collections, each with its own schema. Without guidance an agent tends to search every dataset, or to filter on a field name that exists in one dataset but silently matches nothing in another. This skill makes the agent narrow down first: find candidate datasets by tag, name or recent errors, confirm the filter key, and check there is data for the window. The searches that follow return only the service's events, and an empty result means the service really logged nothing.

## Key Capabilities

- Find a service's datasets by `service` and `environment` tag, by dataset or collection name, or by which datasets logged errors in the incident window
- Rank candidates by environment, and set aside metrics and trace collections and datasets that have been dormant for days
- Confirm the exact key and value that identify the service in each dataset
- Show whether the service logged before, during and after the incident, and report a logging gap as evidence
- Report plainly when the service's logs are not in Bronto, instead of searching everything

## Prerequisites

- The Bronto connector associated with your Agent Space in AWS DevOps Agent, using sign-in or an API key with the **API Agent ReadOnly Role**, as described in the connector's README
- Datasets tagged with `service` and `environment` give the best results; name matching works without tags

## Limitations

- The skill can only see datasets the connected Bronto user or API key can access. A dataset that is missing may be one the connection can't see
- Key values come from Bronto's most frequent keys, so a rarely used value may not be listed
- The skill stops after a fixed number of tool calls and reports what it found

## Agent Types

This skill is used by the following agent types:

- **Chat tasks** - questions about where a service's logs are and what to search
- **Incident triage** - the first look at an incoming incident, to find where the affected service's logs are
- **Incident RCA** - root cause analysis that needs a service's logs from Bronto

## How to Use This Skill

### Chat

- "Which Bronto datasets hold the checkout-api logs in production?"
- "Where would I find logs for the payments service in Bronto, and what field identifies it?"
- "Did the orders worker log anything in Bronto between 14:00 and 14:30 UTC today?"

### Investigation

- "checkout-api is returning 5xx errors since 14:05 UTC. Find the cause."
- "Latency on the payments service doubled after the last deployment. Investigate using its logs."
- "The orders worker stopped processing messages an hour ago. Find out why."

## Support and testing

Bronto maintains this skill. It only reads data: it lists datasets, keys and event counts, and never creates or changes anything in Bronto. Try it in a non-production Agent Space and Bronto organization before you rely on it for live incidents.

## Learn More

- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
- [Bronto and AWS DevOps Agent](https://docs.bronto.io/ai-features/aws-devops-agent)
- [Bronto Hosted MCP Server](https://docs.bronto.io/ai-features/hosted-mcp)
