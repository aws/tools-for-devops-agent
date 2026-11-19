# Bronto Error Investigation

This skill teaches AWS DevOps Agent how to explain an error from logs in Bronto: what the failing events have in common, when the error started, and whether the lead holds up against a control query.

## Purpose

Reading error log lines tells an agent what failed, but not where or since when. This skill applies the method behind BrontoScope, Bronto's in-product error investigation. It isolates the error to one log statement by its pattern ID, finds when it started, and splits it by version, host, endpoint, customer, client and region. It then compares each concentration with how traffic is spread, and verifies the strongest lead by counting the error with and without it. The result is a scoped finding, such as "96% of the errors come from version 4.12.0, which handles 30% of the requests", rather than a guess from a few log lines.

## Key Capabilities

- Start from a Bronto monitor alert, a specific error event, or a service and a symptom
- Isolate the error by its Bronto message pattern, so counts include only this error
- Find when the error started by searching back 3 hours, then 3 days, then 7 days, and recognize a long-standing error
- Tell an error that grew on its own from one that grew with traffic
- Break the error down by version, host, endpoint, customer, user, client, region and dependency, and skip keys that cannot explain it
- Compare each value's share of errors with its share of traffic, and verify the lead with a with-and-without query
- Report the primary issue, scope, evidence, hypothesis and next steps, with links to each supporting search in Bronto

## Prerequisites

- The Bronto connector associated with your Agent Space, using sign-in or an API key with the **Agent Read Only** role, as described in the connector's README
- The `bronto-log-search` skill, for Bronto's search syntax, and the `bronto-dataset-discovery` skill, when the datasets holding the service's logs aren't known
- To start investigations from Bronto monitors, the webhook set up as described in the connector's README

## Limitations

- The breakdown can only use the keys your logs carry. If no event records a version or host, the skill cannot attribute the error to one, and says which keys were missing.
- Pattern IDs are assigned at ingestion. Events with no pattern fall back to a filter on the message or exception type.
- The skill finds what the failing events share. Confirming why that causes the error, such as reading the code in a bad release, is left to the next steps it suggests.
- The agent can only search datasets the connected Bronto user or API key can access.

## Agent Types

This skill is used by the following agent types:

- **Incident triage** - the first look at an error alert: which error, since when, and how widespread
- **Incident RCA** - finding and verifying what the error is concentrated on
- **Chat tasks** - questions such as "why is checkout-api throwing 500s?"

## How to Use This Skill

### Investigation

- "Bronto monitor 'checkout-api 5xx rate' alerted at 14:20 UTC. Find out what the errors have in common and when they started."
- "Payment authorization timeouts spiked in the last hour. Use Bronto to find whether one version, host or customer is responsible."
- "Errors on the orders worker doubled after this morning's deploy. Check in Bronto whether the new version caused it."

### Chat

- "Why is checkout-api throwing NullPointerException in Bronto since yesterday?"
- "Is this database connection error new, or has the orders service always logged it?"

## Support and testing

Bronto maintains this skill. It only reads data: it runs searches and aggregate queries, and never creates or changes anything in Bronto. Try it in a non-production Agent Space and Bronto organization before you rely on it for live incidents.

## Learn More

- [BrontoScope](https://docs.bronto.io/ai-features/brontoscope)
- [Bronto Patterns](https://docs.bronto.io/core-features/patterns)
- [Bronto search syntax](https://docs.bronto.io/query-syntax/search-syntax)
- [Bronto Hosted MCP Server](https://docs.bronto.io/ai-features/hosted-mcp)
- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
