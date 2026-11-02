---
name: honeycomb-slos-and-triggers
description: 'Load before calling Honeycomb get_slos or get_triggers, or when an investigation must judge SLO compliance, error budget burn or trigger status. Explains what the numbers mean, how to spot a misconfigured SLI, when a burn rate justifies paging or freezing deploys, and how to design burn alert thresholds.'
metadata:
  author: "honeycombio/agentic-intelligence"
  version: "1.0.0"
  summary: "Interpret Honeycomb SLO compliance, budget burn and trigger status, and decide what to do."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "INCIDENT_TRIAGE, INCIDENT_RCA, CHAT"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Honeycomb SLOs and Triggers

Requires the Honeycomb connector in the Agent Space, with its read tools enabled. Creating a board, SLO or trigger needs write access: **Read-write** at sign-in, or a key with **Write** under **Model Context Protocol**. If a create tool is missing or returns a permission error, stop and tell the operator that it needs write access. Do not retry.

Guidance for configuring and reasoning about reliability in Honeycomb. The `get_slos`
and `get_triggers` tools document their own parameters — this skill focuses on
_designing_ effective SLOs, _choosing_ between SLOs and triggers, and _interpreting_
what the numbers mean.

**Availability**: SLOs require Pro or Enterprise plan. Triggers available on all plans.

## SLO vs Trigger — When to Use Which

| Question                                      | SLO                    | Trigger |
| --------------------------------------------- | ---------------------- | ------- |
| "Are we meeting our reliability commitments?" | Yes                    | No      |
| "Is something broken right now?"              | No                     | Yes     |
| "How fast are we burning our error budget?"   | Yes (burn alerts)      | No      |
| "Did error count exceed a threshold?"         | No                     | Yes     |
| "Should we slow down deploys?"                | Yes (budget remaining) | No      |

**Rule of thumb**: SLOs measure reliability against commitments over time. Triggers catch immediate operational issues.

## Designing Effective SLOs

### Define the SLI

An SLI is a per-event boolean: was this event successful? Implemented as a calculated field returning undefined (not a relevant event), 1 (success), or 0 (failure).

- **Format**: `IF(<qualifying-condition>, <success-condition>)` The qualifying condition filters to relevant events; the success condition defines what counts as success. If the qualifying condition is not met, the formula returns undefined, and the SLI is unpopulated.
- **Specific Qualifying Condition**: Choose the relevant subset of events (e.g. `AND(EQUALS($http.route, "/checkout"), NOT(EXISTS($trace.parent_id)))` for root spans of checkout endpoint)
- **Latency Success Condition**: `LTE(duration_ms, 500)` — requests faster than 500ms
- **Availability Success Condition**: `LTE(http.status_code, 499)` — non-5xx responses
- **Business Logic Success Condition**: `EQUALS(checkout.status, "completed")` — successful checkouts

### Set the Target

- Start conservative (99% before 99.99%)
- Measure current baseline first with P50/P99 queries
- Set target slightly above current performance
- Ask: what reliability do users actually need?

### Configure Exhaustion Time Alerts

At minimum, two alerts:

- **Near exhaustion** (exhaustion time ~4h): pages on-call via PagerDuty
- **Trending to exhaustion** (budget rate over 24h): notifies team via Slack

### Configure Burn Rate Alerts

Detect fast burns even if the budget isn't close to exhaustion yet. For example:

- 1h burn rate > 10x — page on-call

Recommend these alerts to the user after an SLO is created. Agents do not have the ability to set up these alerts or their recipients.

### Best Practices

- Measure close to the user (at the edge, not deep in the stack)
- Design around user workflows, not team boundaries
- Favor broad SLOs over many narrow ones
- Start with one SLO, reduce noise, then expand

## Interpreting SLO Status

When reviewing SLOs with `get_slos`:

- **Budget remaining > 50%**: Healthy — room for risk
- **Budget remaining 10-50%**: Caution — slow down changes
- **Budget remaining < 10%**: At risk — freeze non-critical deploys
- **Budget negative**: Breached — investigate immediately with the honeycomb-production-investigation skill
- **Compliance at 0%**: Likely misconfigured SLI (wrong column, inverted logic, no matching events) — check the SLI definition

## Configuring Triggers

### Prefer Count-Based Over Percentile-Based

"50 requests slower than 2s" is more actionable than "P99 is 2100ms."
Use `COUNT WHERE duration_ms > threshold` instead of P99 triggers.

### Common Patterns

- **Error spike**: COUNT WHERE error = true, threshold > N in 5 min
- **Slow requests**: COUNT WHERE duration_ms > 2000, threshold > N in 5 min
- **Traffic drop**: COUNT WHERE is_root, threshold < N in 10 min (below normal)

### Best Practices

- **Name**: What the alert is. **Description**: What to do (link to runbook).
- Set duration 5-10 min minimum to avoid flapping
- Start less sensitive, tighten based on false positive rate

## Multi-Service SLOs

Share a single error budget across up to 10 services.

- SLI must be an environment-level calculated field
- Events from included services weighted equally
- Use cases: multiple edge services, monolith-to-microservices migration

## Check in with the user

Create an SLO or trigger only when the operator asks for one. Workspaces in Honeycomb have a limited number of SLOs and triggers. Before executing the create tool, display all parameters and your reasoning, and ask for confirmation.

## Constructing links to SLOs

The tools you have will not let you link directly to the SLO page in Honeycomb.
Instead, you can link to the list of SLOs.

`/<team_slug>/environments/<environment_slug>/slos`

## Additional Resources

### Reference Files

- **`references/slo-design-guide.md`** — Detailed SLO design methodology, multi-service SLOs, error budget math
- **`references/trigger-examples.md`** — Complete trigger example library organized by use case
- **`references/alerting-strategy.md`** — How to combine SLO burn alerts and triggers into a cohesive alerting strategy

### Cross-References

- For constructing SLI queries and calculated fields, see the **honeycomb-query-patterns** skill
- For investigating SLO budget burn, see the **honeycomb-production-investigation** skill
