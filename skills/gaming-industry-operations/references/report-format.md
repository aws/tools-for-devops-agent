# Report contracts

Two output shapes: the **review report** for Chat, and the **games context block**
for incident triage and RCA. Render either directly in the final response, as a
single Markdown message. Do not create files.

## A. Games workload review (Chat)

Order and headings are fixed. Omit nothing; an empty section says why it is empty.

### §1 Executive summary (≤ 8 lines)
- Title, platforms, scenario(s) recognized, accounts/Regions reviewed, review date.
- Overall posture in one sentence, then the count of FAIL by severity
  (Critical / High / Medium / Low) and the number of N/A with the top reason.
- The three actions that most reduce player-impact risk before the next launch or
  event, each with its lens BP ID.

### §2 Workload snapshot
A table of what was found: game-server hosting (GameLift fleets / ASGs / EKS, count,
Regions, Spot share), matchmaking, backend entry points, player identity, data
stores, edge/network protection, telemetry pipeline, observability stack, account
structure. Mark "declared by user, not verified" where applicable.

### §3 Prioritized action plan
Severity-ordered table: `# | Severity | Lens BP | Finding (one line) | Action | Owner (proposed) | Before next event? (Y/N)`.

Severity mapping: a FAIL inherits the lens risk level (High → **High**; Medium →
**Medium**; Low → **Low**). Promote to **Critical** when the gap is on the player
critical path (identity, matchmaking, session placement, session continuity, DDoS
protection of game-server endpoints) **and** a launch or event is within 4 weeks, or
when the gap already caused an incident in the last 90 days. Never promote on
assumption; say which condition applied.

### §4 Detailed findings
One block per FAIL and per noteworthy PASS, grouped by pillar in lens order
(Operational excellence, Security, Reliability, Performance efficiency, Cost
optimization, Sustainability):

- **ID and title** — verdict and severity.
- **Evidence** — the read made and what it returned (resource names/ARNs truncated,
  counts, metric values with period). Quote configuration values, not impressions.
- **Why it matters for players** — one or two sentences in player-experience terms.
- **Remediation** — proposal for human approval, with the AWS feature or setting to
  change and a link to the lens page. Never an executed change.

### §5 Scorecards
One table per pillar listing **every** lens BP in that pillar with
`Verdict (PASS / FAIL / N/A) | Lens risk | Evidence pointer or N/A reason`. The
full canonical ID set from `games-lens-best-practices.md` must appear: 12 + 25 + 6 +
24 + 7 + 4 = 78 rows in total. When the user scoped the review to one pillar or
scenario, still print the other pillars' rows as `N/A — out of requested scope`.

### §6 Launch / event readiness (only when an event date is known)
Checklist against the date: pre-scale minimums set (GAMEOPS03-BP05), quotas raised
(companion `service-quota-check`), load test at projected peak run (GAMEOPS03-BP03),
change freeze and rollback plan (GAMEOPS03-BP04), matchmaking rules validated
(GAMEPERF07-BP03), Shield Advanced and WAF active (GAMESEC06-BP01), on-call and
status page ready (GAMEPERF08-BP01), AWS Countdown engaged for the launch
(GAMEOPS03-BP02). Items that cannot be completed in time are **residual risk** with a
day-of mitigation.

### §7 What was not assessed
- Reads denied and the checks they blocked.
- Checks that need a conversation (Interview needed) and the question to ask.
- Companion skills used, and companions that were not installed (with the reduced
  depth that caused).
- Third-party tools declared but not verifiable from AWS.

## B. Games context block (incident triage and RCA)

Insert this block into the investigation output after the impact statement and
before the root-cause narrative. Keep it under 25 lines.

```
Games context
- Workload shape: <scenario(s) recognized; GameLift / EC2 / EKS game servers; backend type; identity provider>
- Player impact: <CCU delta, logins/min, matchmaking wait, session interruptions, affected game Regions, duration>
- Demand context: <planned launch/event/promo at the time? yes/no + what>
- AWS Health: <events in the Regions/services involved, or none>
- Change timeline: <deployments, fleet/queue/rule-set/scaling changes in the prior hour, or none>
- Capacity signals: <fleet/ASG headroom, scaling failures, quota hits, Spot interruptions>
- Network signals: <ENA allowance exceeded, NAT errors, Shield attacks, Internet Monitor events>
- Dependency signals: <Cognito, DynamoDB, Aurora, ElastiCache, external IdP/payment>
- Candidate causes checked (symptom-map section): <list with confirmed / ruled out / unknown>
- Lens best practices implicated: <IDs with one-line reason>
```

Root-cause rules for games incidents:

- State the root cause only when the evidence chain is complete; otherwise give the
  leading hypothesis with what evidence would confirm it.
- Always separate: AWS impairment vs the studio's own change vs demand/external.
- Prevention recommendations cite the lens BP ID and are proposals, never executed.
- Impact is stated in player terms first; infrastructure metrics are supporting
  evidence.
