# Aurora/RDS Incident Business Context (Skill)

Enriches an Amazon Aurora or Amazon RDS incident investigation with business
context — dependent services, estimated cost of downtime, compliance
reporting exposure, and recent-change correlation — so AWS DevOps Agent's
technical root-cause findings come with an answer to "who does this affect
and what does it cost us."

> ⚠️ This skill is sample code, not intended for production use without
> additional review and testing. Users should validate in a non-production
> environment first.

## What it does

DevOps Agent's built-in investigation tools (CloudWatch, Performance
Insights, RDS/Aurora logs) answer *what* is technically wrong. This skill
adds the *business* half of the incident report: which teams/services are
affected, a defensible dollar estimate of downtime cost, which compliance
reporting obligations could apply (for the compliance owner to assess), and
whether a recent change correlates with the incident.

It is evidence-driven, not generative — it tells the agent **where to look**
(resource tags, AWS Config history, CloudTrail, customer-supplied
dependency maps) and **how to reason** about what it finds. It does not
invent dependency graphs, dollar figures, or compliance frameworks. If the
evidence isn't tagged or configured in the account, the skill says so and
asks the operator, rather than guessing.

## Prerequisites

For the skill to find real evidence (rather than reporting gaps), the
target account should have some of the following in place:

- **IAM permissions** on the DevOps Agent role. All four are read-only.
  `AIDevOpsAgentAccessPolicy` already covers `rds:ListTagsForResource`,
  `tag:GetResources` and `cloudtrail:LookupEvents`. It doesn't cover
  `config:GetResourceConfigHistory`, which the recent-change check uses. Add
  it with the `EnableAuroraIncidentBusinessContext` parameter of
  [`devops-agent-skill-policies.yaml`](../../cloudformation/devops-agent-skill-policies/).
  Without it, the skill falls back to CloudTrail and says that Config
  history wasn't readable.
- **Resource tags** on the Aurora/RDS resource, e.g. `DependentServices`,
  `OnCallTeam`, `RevenuePerMinute`, `SLAThresholdMinutes`,
  `DataClassification`, `Compliance`. None are required for the skill to
  activate — it degrades gracefully to "no evidence found" per category.

## How to use it with DevOps Agent

Install the skill in your Agent Space (Investigations and/or Chat
subagents, depending on where you want business-context enrichment
available). It activates automatically once DevOps Agent is investigating
an Aurora/RDS alarm and the reasoning trace calls for business impact.

You can also invoke it on demand in chat, e.g.:

> Investigate the Aurora cluster `example-cluster` — the
> `example-cluster-connections-high` alarm is firing. Once you've found the
> technical root cause, tell me who's affected, what this costs us, and
> whether we have a compliance reporting deadline.

## Origin

Adapted from the business-context enrichment logic prototyped in the
Aurora MySQL Incident Investigation with AWS DevOps Agent demo (GenAI Ops
Demo Library), currently proposed in
[aws-samples/sample-aws-genai-ops-demos#95](https://github.com/aws-samples/sample-aws-genai-ops-demos/pull/95). That demo originally shipped this as a
Lambda-backed mock MCP server returning synthetic example data
(fictional dependency graph, a fixed revenue figure, canned compliance
thresholds) for demonstration purposes. This skill generalizes that same
reasoning into an evidence-based framework suitable for real accounts,
with no infrastructure to deploy.

The demo above shows this skill's reasoning in action against a live
incident (connection storm, CPU spike, deadlock, or failover on a real
Aurora MySQL cluster) — see its README for a runnable, end-to-end
walkthrough.
