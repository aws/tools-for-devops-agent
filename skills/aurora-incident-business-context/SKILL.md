---
name: aurora-incident-business-context
description: >
  Use this skill when the user wants the business impact of an Amazon Aurora
  or Amazon RDS incident: who is affected, what the downtime costs, whether an
  SLA or compliance deadline is at risk, or whether a recent change caused it.
  Use it for questions about blast radius, customer impact, or a leadership
  incident summary, even if the user doesn't name the database.
metadata:
  author: maayushii
  version: "1.0.0"
  summary: "Adds business impact (dependent services, downtime cost, compliance exposure, recent changes) to Aurora/RDS incident investigations."
  aws-devops-agent-skills.agent-types: "INCIDENT_RCA, CHAT"
  aws-devops-agent-skills.aws-services: "Amazon RDS, AWS Config, AWS CloudTrail"
  aws-devops-agent-skills.technical-domains: "Databases, Observability"
---

## Instructions

You are enriching a database incident investigation with **business context**
— the information that turns "CPU is at 95% on example-cluster-writer" into
"checkout is degraded for about 18,000 users, and the SLA threshold is 4
minutes away."
DevOps Agent's built-in tools (CloudWatch, Performance Insights, RDS/Aurora
logs) tell you *what* is happening technically. This skill tells you *why it
matters* and *who needs to know*.

### Required behavior

These apply to every response that uses this skill.

1. **Return the Business Impact section with all four lines**: Dependent
   services, Estimated cost, Compliance exposure, Recent changes. This applies
   even when the resource isn't found, no evidence is found, or the
   investigation is still in progress. A line without evidence uses its
   "none found" wording from the Output template instead of being left out.
2. **If the incident can't be confirmed, include the section and mark it
   provisional.** Treat the incident as confirmed when there is an alarm, a
   metric anomaly, log evidence, or the operator states that it is
   happening. Otherwise, for example when the operator describes only a
   suspected problem, title the section `Business Impact (provisional:
   incident not confirmed)` and add a `Status` line that says what evidence
   would confirm it. The four lines follow the same evidence rules as usual.
3. **Report only what the evidence supports.** Don't estimate a number, an
   owner, or a compliance deadline that isn't backed by a tag, an API result,
   or the operator's input. Where evidence is missing, say so.
4. **Answer first, then ask.** The Business Impact section is your final
   answer for this turn. Write any questions for the operator as plain text
   at the end of that response, not as a separate ask-the-user step. If you
   can't identify the exact resource, list it as an open question there.

Work through these four evidence categories. For each one, look for real
evidence in the account before answering.

If the operator already gave you the inputs (for example downtime, revenue
per minute, and an SLA threshold), use them directly. You don't need to find
the resource in the account before calculating the cost.

Load [references/evidence-sources.md](references/evidence-sources.md) when you
need the exact API call, tag name, or reporting window for a category, or
when deciding how much weight to give a weak signal such as network evidence.

### 1. Dependent services and criticality

**Goal:** which services are affected if this resource is unavailable or degraded.

Evidence sources, in order of preference:
- Resource tags on the cluster/instance, e.g. `DependentServices`,
  `Owner`, `Criticality`, `OnCallTeam` — read via
  `rds:ListTagsForResource` / `resourcegroupstaggingapi:GetResources`.
- A customer-supplied dependency map (CMDB export, architecture doc, or a
  small JSON/YAML config the operator points you at).
- Application-layer evidence: Aurora `SHOW PROCESSLIST` / Performance
  Insights top SQL by calling application, or VPC Flow Logs / security
  group references showing which compute resources connect to this
  database.

If none of the above exists, state plainly: *"No dependency mapping is
tagged or configured for this resource. I can't identify affected downstream
services without one — consider tagging critical resources with
`DependentServices` and `OnCallTeam`, or pointing me at a dependency map."*

### 2. Cost of downtime

**Goal:** a defensible dollar estimate of business impact, tied to real
inputs, not an assumed industry-average number.

Evidence sources:
- Tags such as `RevenuePerMinute`, `SLAThresholdMinutes`, `SLAPenaltyUsd` on
  the resource or its associated application/service tag group.
- A cost-of-downtime figure the operator states directly in the
  conversation (treat this as authoritative for that investigation only —
  do not persist or reuse it elsewhere).
- Absent both: report technical impact only (e.g. connections/queries
  blocked, replica lag introduced) and flag that a dollar estimate requires
  a revenue-per-minute input you don't have.

Formula once you have real inputs:
```
estimated_loss_usd = revenue_per_minute_usd * downtime_minutes
sla_breach = downtime_minutes >= sla_threshold_minutes
sla_minutes_remaining = sla_threshold_minutes - downtime_minutes   # when not yet breached
sla_penalty_usd = SLAPenaltyUsd tag value, applied only if sla_breach is true
```

Report the SLA result on the Estimated cost line: breached, not breached
with the minutes remaining, or "no SLA threshold found" when there is no
`SLAThresholdMinutes` tag or operator-stated threshold. Include the penalty
only when an `SLAPenaltyUsd` tag or operator input provides it.

### 3. Compliance and reporting exposure

**Goal:** does this incident trigger a mandatory reporting clock.

Evidence sources:
- Data-classification tags (`DataClassification`, `Compliance`) on the
  resource.
- Known reporting-window reference (use as background knowledge, not as a
  substitute for checking whether the tag/framework actually applies to
  this resource):

  | Framework | Typical mandatory reporting window |
  |---|---|
  | PCI-DSS | Immediate notification to acquirer/processor on suspected breach |
  | SOC 2 Type II | Per the org's documented incident response policy (commonly ≤60 min internal escalation) |
  | GDPR | 72 hours to the supervisory authority for a personal-data breach |
  | HIPAA | 60 days to HHS (and affected individuals) for a breach of PHI |

- If the resource carries no compliance/classification tag, say so — do not
  assume a framework applies by default.

### 4. Recent-change correlation

**Goal:** did something change recently that could explain this incident.

Evidence sources:
- AWS Config resource timeline / configuration history for the cluster or
  its parameter group, over a lookback window (default 14 days, adjust if
  the operator specifies otherwise).
- CloudTrail events for `ModifyDBClusterParameterGroup`,
  `ModifyDBCluster`, `ModifyDBInstance`, `FailoverDBCluster`, engine
  version upgrades.
- Deployment/change-tracking system the customer already uses (if named in
  the conversation), e.g. a pipeline history or change-ticket system.

Rank findings by proximity to the incident start time and by blast radius
(a parameter group change on the exact cluster outranks an unrelated app
deploy).

### Output

Fold the four categories into the incident report as a **Business Impact**
section, alongside (not replacing) the technical root-cause findings from
CloudWatch/Performance Insights/logs. In an investigation, include this
section in the investigation summary itself, not only in intermediate notes:

```
Business Impact
----------------
Dependent services  : <found, with criticality — or "none found, needs tagging">
Estimated cost      : <$X, using inputs Y; SLA: breached (penalty $Z if known) or not breached, N min remaining — or "not calculable, no cost inputs found; no SLA threshold found">
Compliance exposure : <framework + reporting deadline — or "no classification tag found">
Recent changes      : <ranked list of correlated changes — or "none found in lookback window">
```

If the incident can't be confirmed (rule 2 under Required behavior), use this
form instead:

```
Business Impact (provisional: incident not confirmed)
-----------------------------------------------------
Status              : <why it's unconfirmed, and what evidence would confirm it>
Dependent services  : ...
Estimated cost      : ...
Compliance exposure : ...
Recent changes      : ...
```

Before you return the report, run these checks:
1. Is the Business Impact section present with all four lines? If not, add
   it, using the "none found" wording for any line without evidence.
2. If you couldn't confirm the incident, is the section marked provisional
   with a `Status` line?
3. Does every value trace to a tag, an API result, or something the operator
   said in this conversation? If not, replace it with the "none found" wording.
4. Does every "none found" line say what tag or input would fill the gap?
5. Did you apply a compliance framework only because the resource is tagged
   with it or the operator said it applies?

If any check fails, fix the section and run the checks again.

Be explicit about which parts are grounded in evidence versus which are
gaps in the customer's tagging/configuration. A partially-answered business
impact section that's honest about its gaps is more useful than one that
fills every field with a plausible-sounding guess.

### Gotchas

- **Tags can be stale or wrong.** A `DependentServices` tag naming a service
  that has no reachable compute resource is a claim, not evidence. Cross-check
  it against network or connection evidence, and label it unverified if you
  can't confirm it.
- **The example data in the reference file is synthetic.** The demo values in
  `references/evidence-sources.md` (checkout-service, $5,100/min, PCI-DSS) are
  illustrative only. Never use them as defaults or fallbacks.
- **Operator-stated figures are session-scoped.** Use a revenue figure the
  operator gives you for this investigation only. Don't carry it into other
  investigations.
- **Correlation isn't causation.** A change close to the incident start is a
  lead to check against the technical findings, not a confirmed root cause.
