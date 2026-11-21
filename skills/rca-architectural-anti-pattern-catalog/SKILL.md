---
name: rca-architectural-anti-pattern-catalog
description: >-
  Use this skill when the same service or dependency keeps failing across
  incidents, when failures cascade from a downstream service to its callers,
  or when asked "is there a single point of failure", "why does this keep
  happening", to fix or remediate a single point of failure or cascade path,
  or for an architectural-debt or resilience review. Activate on
  recurring, related incidents that share a dependency path. The skill
  classifies them against named architectural anti-patterns (single point of
  failure, synchronous coupling, missing bulkheads, cascade-failure paths,
  retry storms, shared-fate deployment) and returns a severity-ranked
  architectural-debt report. Do not use it for a single one-off incident.
  Read-only: remediation is proposed for human approval, never executed.
metadata:
  author: saadnu-aws
  version: "1.0.0"
  summary: "Read-only architectural review: classifies recurring incidents against a named anti-pattern catalog and returns a severity-ranked debt report with proposed fixes."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "AWS Health, AWS Config, AWS CloudTrail, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Operations"
---

# RCA Architectural Anti-Pattern Catalog

Classify an account's recurring incidents and resource topology against a named
catalog of architectural anti-patterns, and return a severity-ranked
architectural-debt report in that vocabulary.

> **This skill builds ON TOP OF the base DevOps Agent — it does not duplicate
> it.** DevOps Agent already (a) builds the dependency/topology map
> automatically (Topology graph) and (b) analyzes patterns across incidents on
> a weekly + on-demand schedule, returning a severity-ranked backlog with an
> "architectural resilience" category and agent-ready specs (Proactive Incident
> Prevention). This skill does **not** re-implement topology discovery or
> cross-incident correlation. Its distinct contribution is the layer DevOps
> Agent does not provide: **classifying those findings against a named
> architectural anti-pattern taxonomy and reporting the account's structural
> debt in that language**, rather than a list of discrete incident-derived
> remediation items.

## When to Use This Skill

- Recurring incidents share a dependency path and look like one structural
  flaw, not independent failures.
- You are reviewing a Proactive Incident Prevention backlog and want its
  "architectural resilience" items re-expressed as named anti-patterns.
- A workload/operational review needs an architectural-debt verdict for an
  account.

## Prerequisites

Read-only, control-plane only (all in `AIDevOpsAgentAccessPolicy`); no
data-plane reads:

- `health:DescribeEvents*`, Config read APIs, CloudTrail `LookupEvents`
- resource `Describe*`/`List*` for topology enrichment
- CloudWatch read for alarm/metric correlation

## Workflow

Copy this checklist and work through it in order. Each step is detailed in the
section of the same number below.

- [ ] Step 1: Consume existing DevOps Agent context (Topology graph, Proactive Incident Prevention output). Do not rebuild it.
- [ ] Step 2: Classify each cluster of related findings against the named anti-pattern catalog.
- [ ] Step 3: Produce the severity-ranked architectural-debt report.
- [ ] Step 4: Propose remediation for human approval. Never execute it.
- [ ] Step 5: Validate before presenting: every classified anti-pattern cites the specific resources/dependency path and the incidents that evidence it; drop or mark as unconfirmed any finding without that evidence, and state which inputs (topology, proactive output) were unavailable.

**Finish in one turn.** Do the evidence gathering yourself, in this turn, with
direct read-only calls. Do not hand it to a background task and do not end with
"evidence gathering is running" or "I'll classify once it comes back". Your
final message must contain the classification, the report and the proposed
remediation.

## Step 1: Consume existing DevOps Agent context (do not rebuild it)

- Read the **Topology graph** for the account's dependency/relationship map and
  blast-radius / dependency-chain data. Do not re-discover resources.
- Read the **Proactive Incident Prevention** output for cross-incident
  recommendations, especially the "architectural resilience" (Infrastructure)
  category. Do not re-run cross-incident correlation.

If either is unavailable, say so and proceed with what is available rather than
re-implementing it.

## Step 2: Classify against the named anti-pattern catalog

For each cluster of related findings, test it against the catalog. This is the
enrichment the base agent does not perform.

| Anti-pattern | Signal in topology + incidents |
|---|---|
| **Single point of failure (SPOF)** | A node with no redundancy on a critical path whose failure recurs across incidents |
| **Synchronous cross-service coupling** | A synchronous (request/response) call to a dependency with no fallback/circuit-breaker, where the dependency's failures propagate |
| **Missing bulkheads** | Shared resource (pool, queue, function, DB) whose saturation takes down unrelated consumers |
| **Cascade-failure path** | An ordered chain A→B→C where a failure at the tail is observed as failures all the way up |
| **Retry storm / no backoff** | Correlated error+retry spikes amplifying a downstream failure |
| **Shared-fate deployment** | Independent services sharing one deploy/rollout unit, failing together on a bad change |

Each classified finding carries: the anti-pattern name, the specific resources
/ dependency path involved, the incidents that evidence it, and a severity.

## Step 3: Produce the architectural-debt report

Output a severity-ranked report keyed to the catalog — e.g.:

> **SPOF — `nebula-demo-rca-backend`** (High). The front-end
> `nebula-demo-rca-frontend` calls this single back-end synchronously with no
> fallback; the back-end's failures appear as front-end failures. Evidenced by
> the correlated `*-backend-errors` and `*-frontend-errors` alarms.
> **Also: synchronous-coupling + cascade-failure path** on the same edge.
> Remediation (proposed, not executed): add a fallback / circuit breaker, or
> make the call asynchronous with a durable queue; add a second back-end for
> redundancy.

Use this template for every finding so reports are consistent across runs:

```markdown
### <Anti-pattern name> — `<primary resource>` (<High | Medium | Low>)
- **Path:** <resource A> -> <resource B> [-> ...]
- **Evidence:** <incident IDs / correlated alarms that show the pattern>
- **Why it matters:** <one sentence on blast radius>
- **Remediation (proposed, not executed):** <change for human approval>
```

Order findings by severity, then by number of evidencing incidents.

This is the vocabulary difference from the base agent: a structural verdict
("this account carries a SPOF + cascade path on edge X→Y"), not a list of
discrete remediation items.

## Step 4: Propose remediation — never execute

Every remediation is **proposed → human-approve → execute**. The skill does not
make state changes. Where DevOps Agent can emit an agent-ready spec for a fix,
reference it rather than regenerating it.

## Gotchas

- **One edge, several patterns.** A synchronous call to a single back-end is
  often SPOF *and* synchronous coupling *and* a cascade path at once. Report
  each pattern that has its own evidence, grouped under the same edge, rather
  than picking one.
- **SPOF vs. cascade.** SPOF is about the node having no redundancy; cascade
  is about failure propagating up a chain. A redundant node can still sit on
  a cascade path, so check both independently.
- **Shared services are not shared root cause.** Incidents that touch the same
  service but fail for unrelated reasons do not evidence an anti-pattern.
  Require the failure to originate at, or propagate through, the shared node.
- **Partial inputs.** If the Topology graph or Proactive Incident Prevention
  output is missing, classify only what the available evidence supports and
  mark the rest as unconfirmed.

## Relationship to the base agent (precise)

- Topology discovery and the dependency map: **base agent** (consumed here).
- Cross-incident correlation, weekly/on-demand, severity-ranked backlog,
  agent-ready specs: **base agent** (Proactive Incident Prevention, consumed
  here).
- Named anti-pattern classification + architectural-debt report in that
  language: **this skill** (the enrichment).

## Scope — what this skill does NOT do

- Does not re-implement topology discovery or cross-incident correlation.
- Does not execute any remediation or state change.
- Does not read data-plane contents.
