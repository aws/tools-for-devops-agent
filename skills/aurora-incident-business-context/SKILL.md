---
name: aurora-incident-business-context
description: >
  Load this skill whenever an Amazon Aurora or Amazon RDS incident is being
  investigated, or a user asks about the business impact of a database
  problem: who is affected, what the downtime costs, whether an SLA or
  compliance deadline is at risk, or whether a recent change caused it. Also
  load it for questions about blast radius, customer impact, or a leadership
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
   In an investigation, also write each unconfirmed line as an
   `**Investigation gap:**` item (see Output).
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
4. **Don't decide whether a compliance reporting clock has started.** A
   reporting deadline starts when someone with that responsibility determines
   that a breach occurred, not because a resource is tagged. Never say that a
   deadline is running, or that one doesn't apply because the incident isn't
   a breach. Name the frameworks that could apply and leave the
   determination to the compliance owner (see category 3).
5. **Never write a 12-digit AWS account ID.** This applies everywhere in your
   response: sentences, ARNs, tables, and code. Write "this account" or
   `****` instead, for example "the account this agent space can see" or
   `arn:aws:rds:us-west-2:****:cluster:example-cluster`.
6. **Answer first, then ask.** The Business Impact section is your final
   answer for this turn. Write any questions for the operator as plain text
   at the end of that response, not as a separate ask-the-user step. If you
   can't identify the exact resource, list it as an open question there.

Work through these four evidence categories. For each one, look for real
evidence in the account before answering.

If the operator already gave you the inputs (for example downtime, revenue
per minute, and an SLA threshold), use them directly. You don't need to find
the resource in the account before calculating the cost.

Load [references/evidence-sources.md](references/evidence-sources.md) when you
need the exact API call or tag name for a category, or when deciding how much
weight to give a weak signal such as network evidence.

### 1. Dependent services and criticality

**Goal:** which services are affected if this resource is unavailable or degraded.

Evidence sources, in order of preference:
- Resource tags on the cluster/instance, e.g. `DependentServices`,
  `Owner`, `Criticality`, `OnCallTeam` — read via
  `rds:ListTagsForResource` / `tag:GetResources`.
- A customer-supplied dependency map (CMDB export, architecture doc, or a
  small JSON/YAML config the operator points you at).
- Connection evidence: Performance Insights `DescribeDimensionKeys` grouped
  by `db.host`, `db.user`, or `db.application` shows which clients are
  connected and generating load. VPC Flow Logs or security group references
  show which compute resources can reach the database.

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

**Goal:** which reporting obligations could apply to this resource, so the
compliance owner can assess them. You identify the candidates. You don't
decide whether the incident is a breach or whether a deadline has started.

Evidence sources:
- Data-classification tags (`DataClassification`, `Compliance`) on the
  resource, or the operator stating that a framework applies.
- Each reporting window starts only on a breach determination, never on a
  tag: for PCI-DSS, a suspected or confirmed compromise of cardholder data;
  for GDPR, the controller becoming aware of a personal data breach (a loss
  of availability of personal data can itself be one); for HIPAA, discovery
  of a breach of unsecured PHI. Load
  [references/evidence-sources.md](references/evidence-sources.md) for each
  framework's window, and use it only for a framework the resource is tagged
  with or the operator named.
- For each applicable framework, write the window as conditional:
  *"GDPR: within 72 hours to the supervisory authority if assessed as a
  personal data breach, for the compliance owner to decide."* Don't add
  whether you think the incident qualifies.
- If the resource carries no compliance/classification tag and the operator
  hasn't named a framework, say so. Don't assume a framework applies.

### 4. Recent-change correlation

**Goal:** did something change recently that could explain this incident.

Evidence sources:
- AWS Config resource timeline (`config:GetResourceConfigHistory`) for the
  cluster or its parameter group, over a lookback window (default 14 days,
  adjust if the operator specifies otherwise).
- CloudTrail events for `ModifyDBClusterParameterGroup`,
  `ModifyDBCluster`, `ModifyDBInstance`, `FailoverDBCluster`, engine
  version upgrades.
- Deployment/change-tracking system the customer already uses (if named in
  the conversation), e.g. a pipeline history or change-ticket system.

If the Config call returns AccessDenied, continue with CloudTrail and say on
the Recent changes line that Config history wasn't readable. The agent role
needs `config:GetResourceConfigHistory`, which `AIDevOpsAgentAccessPolicy`
doesn't include.

Rank findings by proximity to the incident start time and by blast radius
(a parameter group change on the exact cluster outranks an unrelated app
deploy).

### Output

Fold the four categories into the incident report as a **Business Impact**
section, alongside (not replacing) the technical root-cause findings from
CloudWatch/Performance Insights/logs.

In a chat answer, write it as a section with the heading below.

In an investigation, the platform turns your root-cause answer into the
summary leadership reads. It keeps findings and investigation gaps, and drops
business commentary attached to the symptom. So, in your root-cause answer:
- Write the Business Impact section (template below) after the technical
  cause.
- Also write each business-impact line that isn't confirmed as its own item
  labeled `**Investigation gap:**`, with its values and evidence, in this
  form:
  - `**Investigation gap:** Business cost unconfirmed. <$X and the inputs
    used>; SLA <breached, or N minutes left>.`
  - `**Investigation gap:** Reporting obligation undetermined. <tags
    found>; for the compliance owner to decide.`
  - `**Investigation gap:** Impact on dependent services unverified.
    <services and criticality, and where they came from>.`
- Record a correlated change as a finding, with its evidence.
- A line with no evidence at all is also a gap. Name the tag or input that
  would fill it.

```
Business Impact
----------------
Dependent services  : <found, with criticality — or "none found, needs tagging">
Estimated cost      : <$X, using inputs Y; SLA: breached (penalty $Z if known) or not breached, N min remaining — or "not calculable, no cost inputs found; no SLA threshold found">
Compliance exposure : <tagged framework(s) + window "if assessed as a breach, for the compliance owner to decide" — or "no classification tag found">
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
1. Are all four lines covered? In chat, is the Business Impact section
   present with all four lines? In an investigation, does the root-cause
   answer include the section, with each unconfirmed line also labeled
   `**Investigation gap:**`? If not, add them.
2. If you couldn't confirm the incident, is the section marked provisional
   with a `Status` line?
3. Does every value trace to a tag, an API result, or something the operator
   said in this conversation? If not, replace it with the "none found" wording.
4. Does every "none found" line say what tag or input would fill the gap?
5. Did you apply a compliance framework only because the resource is tagged
   with it or the operator said it applies? Does the Compliance exposure
   line avoid saying a deadline has started, or doesn't apply?
6. Does any 12-digit number that is an AWS account ID appear anywhere in your
   response, including in a sentence like "(account …, us-west-2)"? If so,
   replace it with "this account" or `****`.

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
- **Example values are illustrative.** The figures in this skill's text
  (18,000 users, `example-cluster`) show the format only. Never use them as
  defaults or fallbacks.
- **Operator-stated figures are session-scoped.** Use a revenue figure the
  operator gives you for this investigation only. Don't carry it into other
  investigations.
- **Correlation isn't causation.** A change close to the incident start is a
  lead to check against the technical findings, not a confirmed root cause.
