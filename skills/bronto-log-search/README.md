# Bronto Log Search

This skill teaches AWS DevOps Agent how to search logs in Bronto: which MCP tool answers which question, how to write a filter in Bronto's search syntax, and how to read the results.

## Purpose

Bronto's search syntax is SQL-like, with a few rules an agent easily gets wrong: string values take single quotes, field names with dots or hyphens take double quotes, and a misspelled field matches nothing instead of failing. A wrong filter returns zero events, which an agent can then report as "no errors". This skill has the agent check field names before filtering, start from error summaries and counts before reading raw events, keep event fetches small, and treat an empty result as something to verify rather than a finding.

## Key Capabilities

- Choose between the error summary, aggregate counts and percentiles, raw events and saved searches for each question
- Write `search_filter` predicates with correct quoting, `IN`, `IS NULL`, `LIKE`/`ILIKE`, numeric ranges and free text
- Group and bucket counts over time to see when a problem started, and group by message pattern to see which log statements dominate
- Fetch only the events and columns needed, sorted and paged
- Check a zero result before reporting it, compare with a baseline, and link each finding to the same search in Bronto

## Prerequisites

- The Bronto connector associated with your Agent Space in AWS DevOps Agent, using sign-in or an API key with the **API Agent ReadOnly Role**, as described in the connector's README
- The datasets to search. The `bronto-dataset-discovery` skill finds them when they aren't known

## Limitations

- Regular expression operators are an early access feature in Bronto and may not be enabled for your organization
- Free-text search does not match resource attributes such as `$service`; the skill filters on them by name
- The agent can only search datasets the connected Bronto user or API key can access

## Agent Types

This skill is used by the following agent types:

- **Chat tasks** - questions answered from Bronto logs, such as counts, top errors and slow requests
- **Incident triage** - a first look at error volume and when it started
- **Incident RCA** - searches that find and confirm the cause of an incident

## How to Use This Skill

### Chat

- "How many 5xx responses did checkout-api log in the last hour, by path?"
- "What are the slowest requests to the payments service today?"
- "Show me the most common warning messages from the orders worker since 09:00 UTC."

### Investigation

- "Error rates on checkout-api jumped at 14:05 UTC. Find out which errors and when they started."
- "Find every log line for request ID 7f3c2a91 across the payments service."

## Support and testing

Bronto maintains this skill. It only reads data: it runs searches and aggregate queries, and never creates or changes anything in Bronto. Try it in a non-production Agent Space and Bronto organization before you rely on it for live incidents.

## Learn More

- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
- [Bronto and AWS DevOps Agent](https://docs.bronto.io/ai-features/aws-devops-agent)
- [Bronto search syntax](https://docs.bronto.io/query-syntax/search-syntax)
- [Bronto Patterns](https://docs.bronto.io/core-features/patterns)
- [Bronto Hosted MCP Server](https://docs.bronto.io/ai-features/hosted-mcp)
