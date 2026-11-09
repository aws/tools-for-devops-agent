# Alerting Strategy

How to combine SLO burn alerts and triggers into a cohesive alerting system.

## The Two-Layer Approach

### Layer 1: SLO Burn Alerts (Reliability)
Track whether the service is meeting its reliability commitments.
- **What they measure**: Error budget consumption rate
- **Time horizon**: Hours to days
- **Signal**: "We're burning budget too fast" -> investigate and fix
- **Audience**: Service owners, SRE team

### Layer 2: Triggers (Operational)
Catch immediate issues that need attention right now.
- **What they measure**: Threshold crossings in real-time
- **Time horizon**: Minutes
- **Signal**: "Something just broke" -> respond immediately
- **Audience**: On-call engineer

## Recommended Alert Configuration

### Critical Path Services (e.g., checkout, auth)
- SLO: 99.9% latency (< 500ms) with burn alerts at 4h and 0h exhaustion
- SLO: 99.95% availability with burn alerts at 4h and 0h exhaustion
- Trigger: Error rate spike > 3x baseline (5 min window)
- Trigger: P99 > 2x normal (10 min window)

### Internal Services (e.g., batch processors)
- SLO: 99% availability with burn alert at 0h exhaustion only
- Trigger: Complete failure (error rate > 90%) for 5 min

### Background Jobs (e.g., crons, workers)
- Trigger: Job didn't run in expected window
- Trigger: Job duration > 2x normal

## Alert Hygiene

1. **Every alert must be actionable** — If nobody needs to do anything, delete it
2. **Every PagerDuty alert must require immediate action** — Slack for awareness, PD for action
3. **Review alerts monthly** — Delete stale alerts, tune thresholds
4. **Track false positive rate** — >50% false positives = alert needs tuning or removal
5. **Correlate related alerts** — If the same incident triggers 5 alerts, consolidate

## Notification Routing

| Severity | Channel | SLO Alert Type | Trigger Type |
|----------|---------|---------------|--------------|
| Critical (page) | PagerDuty | Exhaustion time = 0h | Error rate > 10x baseline |
| Urgent (page) | PagerDuty | Exhaustion time = 4h | Critical path P99 > 3x |
| Warning (notify) | Slack | Exhaustion time = 72h | Non-critical threshold cross |
| Info (log) | Email/Webhook | Budget rate trending up | Informational thresholds |

## Using MCP for Alert Monitoring

Combine `get_slos` and `get_triggers` for a comprehensive view:

1. **Daily check**: `get_slos(environment_slug: "production")` — Any budgets running low?
2. **Active alerts**: `get_triggers(environment_slug: "production")` — Any triggers firing?
3. **Deep dive**: `get_slos(slo_id: "...")` — Detailed burn rate and compliance graphs
4. **Investigation**: Switch to the honeycomb-production-investigation skill if any SLO or trigger needs attention

If the operator asks for a board, show the proposed title and panels, and call `create_board` only after the operator approves. The board organizes:
- Critical SLOs (pass SLO PKs)
- Key trigger queries
- Text panel with on-call runbook links
