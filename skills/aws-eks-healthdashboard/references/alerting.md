# Alerting — templates and routing

How findings turn into alerts, and where they go.

> **Scope within `reviewing-eks-operations`.** In a normal Discover→Review pass, Control Plane Health findings are written into the **main review report** — `report-format.md` §4 (Detailed findings) and the Recommended Alarms deliverable — not into a separate file. The `cp-health-report-*.md` artifact and the live `oneshot`/`scan` routing below describe the **optional continuous-monitoring mode** (recurring schedule, delta-against-prior-run). Use the label mapping and customer-facing language rules in this file regardless of mode; use the separate report/routing only when running that continuous mode.

The component emits **findings** (structured JSON). It does not deliver alerts — every delivery hop (Slack, PagerDuty, ServiceNow, email, CloudWatch alarm) goes through DevOps Agent's existing connectors. That keeps the security boundary clean and reuses the routing customers already have set up.

## Contents

- Alert lifecycle
- Customer-facing language rules
- Severity → label mapping
- Routing rules (`oneshot` · `scan` · ad-hoc investigation)
- Alert routing config
- Slack / PagerDuty / ServiceNow templates
- Markdown report (oneshot mode)
- What goes in the JSON companion
- Mute / acknowledge
- What the skill never does

## Alert lifecycle

```
oneshot/scan/tool ──► findings (JSON) ──► DevOps Agent ──► customer's connectors
                                              │
                                              ├─ Slack
                                              ├─ PagerDuty
                                              ├─ ServiceNow
                                              ├─ email
                                              └─ CloudWatch composite alarm (optional)
```

Findings carry enough context that the connector can format a usable message without re-querying anything:

- `tier` (internal: critical / high / medium / informational)
- `customer_facing_label` (descriptive — never a Sev number)
- `observation` (one sentence, with numbers)
- `evidence` (query ID + log group + window timestamps)
- `remediation` (playbook ID + 2–4 next steps + reference links)
- `confidence` (high / medium / low — driven by source agreement)

## Customer-facing language rules

- **No internal severity numbers** (Sev 1–5) in any customer-visible content. Use the descriptive label.
- **No internal tool names or aliases** in alerts the customer sees.
- **Every claim cites a query.** "etcd at 78% of quota (CP10, last 60 min)" — never "etcd looks high."
- **Plain English at 2 a.m.** The first sentence of every alert is what the customer reads first; it must say what's wrong and why it matters without jargon.

## Severity → label mapping

| Internal tier | Customer-facing label |
|---------------|----------------------|
| critical | "Action required — control plane impaired" |
| high | "Action required — control plane saturation risk" |
| medium | "Attention — operational hygiene" |
| informational | "Healthy — informational" |

## Routing rules

### `oneshot` mode

A single Markdown report goes to `output_directory`. No live alert routing — this mode is for explicit, on-demand checks. The user inspects the report.

### `scan` mode (proactive nightly scan)

The skill runs nightly with a 24-hour window, diffs against the previous run, and emits findings only when:

- A new finding appears that wasn't in the previous run.
- An existing finding's tier escalated (e.g., high → critical).
- A finding from the previous run resolved.

Each emitted finding goes through one or more channels based on tier:

| Tier | Default channels | Override key |
|------|------------------|--------------|
| critical | PagerDuty (page) + Slack (post) + ServiceNow (ticket) | `routing.critical` |
| high | Slack (post) + ServiceNow (ticket) | `routing.high` |
| medium | Slack (post) | `routing.medium` |
| informational | aggregated weekly digest | `routing.informational` |

### Ad-hoc agent investigation

When a user asks the agent a single question ("is etcd OK on prod-cluster?"), the agent runs the relevant procedure(s) from `procedures.md` and answers in chat. No scheduled alert delivery — the agent is in the loop and the user decides what to do with the response.

## Alert routing config

Pass an `alert_routing` JSON object on the `scan` invocation:

```json
{
  "routing": {
    "critical": {
      "pagerduty_service": "P12345",
      "slack_channel": "#prod-incidents",
      "servicenow_assignment_group": "EKS Platform"
    },
    "high": {
      "slack_channel": "#prod-incidents",
      "servicenow_assignment_group": "EKS Platform"
    },
    "medium": {
      "slack_channel": "#eks-ops"
    },
    "informational": {
      "slack_channel": "#eks-ops",
      "delivery": "weekly_digest"
    }
  },
  "include_resolved": true,
  "deduplication_window_hours": 24
}
```

`deduplication_window_hours` prevents the same finding from re-paging if it persists across nightly scans — repeated occurrences accumulate in the existing PagerDuty incident or ticket instead of opening new ones.

## Slack template

Slack uses the `customer_facing_label` as the post heading. Block kit-style structure:

```
🟧  Action required — control plane saturation risk
Cluster: prod-cluster-us-east-1   |   Detected: <YYYY-MM-DD HH:MM UTC>

Observation
etcd at 78% of 8 GB quota; trending +9.1% week-over-week.
Top growth resource: jobs in payments-prod (49% of writes in the last 60 minutes).

Likely cause
CronJob without spec.ttlSecondsAfterFinished.

Recommended action (R-ETCD-1)
1. Set ttlSecondsAfterFinished: 3600 and successfulJobsHistoryLimit: 3 on the CronJob.
2. Bulk-delete completed Jobs older than 7 days, in batches of 200.

Confidence: high  |  Evidence: query CP10, last 60 min
References: [Kubernetes - cleanup for finished Jobs] [EKS scale-workloads guide]

[Acknowledge] [Mute 24h] [Open in DevOps Agent]
```

Color icons by tier:

| Tier | Icon |
|------|------|
| critical | 🟥 |
| high | 🟧 |
| medium | 🟨 |
| informational | 🟦 |

Action buttons (`Acknowledge`, `Mute 24h`, `Open in DevOps Agent`) are wired through DevOps Agent's existing Slack interactivity layer — the skill does not implement them.

## PagerDuty template

PagerDuty incidents use:

- **Title.** `[EKS-CP] {customer_facing_label} — {cluster}`
- **Severity.** `critical` for tier `critical`, `error` for tier `high`. Lower tiers do not page.
- **Custom details.** Full finding JSON, so the on-call can paste it into the postmortem.
- **Dedup key.** `{cluster_arn}::{playbook_id}` so repeated detection of the same issue accumulates rather than re-paging.

## ServiceNow template

ServiceNow tickets use:

- **Short description.** `[EKS-CP] {customer_facing_label} — {cluster}`
- **Description.** The Slack template body, formatted as text.
- **Assignment group.** From `routing.{tier}.servicenow_assignment_group`.
- **Priority.** `1 - Critical` for tier `critical`, `2 - High` for tier `high`, `3 - Moderate` for tier `medium`.
- **Configuration item.** The EKS cluster ARN.

## Markdown report (oneshot mode)

The `oneshot` report is a single Markdown file at `{output_directory}/cp-health-report-{cluster}-{YYYYMMDD-HHMM}.md` with this structure:

```markdown
# EKS Control Plane Health Report — {cluster_name}

> Region: {region} | Time window: last {N} minutes | Generated: {ISO timestamp}
> Sources: {comma-separated list}

## Summary
- Overall status: 🟢 healthy | 🟡 attention | 🔴 action required
- {N} findings: {breakdown by tier}
- Confidence: {high/medium/low}

## Findings (action required first)
### 1. {customer_facing_label}: {finding title}
- **Signal:** {etcd | apf | api_server | kcm | scheduler | eviction}
- **Observation:** {one sentence with numbers}
- **Why it matters:** {plain English}
- **Recommended action ({playbook_id}):** {2-4 numbered next steps}
- **Evidence:** {query ID + log group + window}
- **References:** {linked AWS / upstream docs}

## Signals (all)
| Signal | Status | Detail | Confidence |
|--------|--------|--------|-----------|
| etcd | 🟧 attention | 78% of 8 GB, +9% in 7 days | high |
| apf | 🟢 ok | 0 rejections in system/leader-election | high |
| api_server | 🟢 ok | P99 LIST 0.3s | high |
| kcm | 🟢 ok | max controller QPS 4.2 | high |
| scheduler | 🟢 ok | 0 unschedulable pods | high |
| eviction | 🟢 ok | no eviction stalls | high |

## Data sources
- **Used:** cloudwatch_logs_insights, container_insights, datadog
- **Missing:** amp, in_cluster_prom
- **Queries run:** CP2, CP4, CP7, CP10, CP13, CP14, CP17, CP18
- **Metrics queried:** apiserver_storage_db_total_size_in_bytes, apiserver_request_total

## Methodology
- Time window: 60 minutes (incident triage default).
- Cross-validation: 2+ sources for etcd, apf, api_server signals.
- Thresholds: defaults from thresholds.md (no overrides).
```

## What goes in the JSON companion

Every Markdown report has a `.json` companion with the full finding objects, used by `scan` mode for delta detection. Schema:

```json
{
  "cluster": {"name": "...", "arn": "...", "region": "..."},
  "generated_at": "<ISO8601-UTC>",
  "time_window_minutes": 60,
  "sources_detected": ["..."],
  "sources_missing": ["..."],
  "overall_status": "attention",
  "findings": [{
    "id": "etcd-quota-warn",
    "tier": "high",
    "customer_facing_label": "Action required — control plane saturation risk",
    "signal": "etcd",
    "observation": "...",
    "evidence": {"query": "CP10", "log_group": "...", "window_start_epoch": ..., "window_end_epoch": ...},
    "remediation": {"playbook_id": "R-ETCD-1", "headline": "...", "next_steps": ["..."], "references": ["..."]},
    "confidence": "high"
  }],
  "signals": {
    "etcd": "attention",
    "apf": "ok",
    "api_server": "ok",
    "kcm": "ok",
    "scheduler": "ok",
    "eviction": "ok"
  }
}
```

## Mute / acknowledge

Customers can mute findings to prevent re-paging:

- **Slack `Mute 24h` button** sets a deduplication entry. The next `scan` run skips this finding for the next 24 hours but logs that it's muted.
- **Persistent mute** (e.g., for known-and-accepted findings during a migration) is configured in `alert_routing.muted_findings`:

```json
{
  "muted_findings": [
    {
      "playbook_id": "R-WORKLOAD-1",
      "cluster_arn": "arn:aws:eks:us-east-1:111122223333:cluster/legacy-cluster",
      "until": "<ISO8601-UTC>",
      "reason": "Migrating to two namespaces by Q3."
    }
  ]
}
```

Muted findings still appear in the Markdown report (with a `[muted]` annotation) — they just don't generate connector deliveries.

## What the skill never does

Per the conventions file and AWS DevOps Agent security guidance:

- **Never auto-pages without delivery rules in place.** No default PagerDuty service.
- **Never includes secret values, credentials, or PII in alerts.** Reference Secrets by name only.
- **Never paginates by emitting findings to a single Slack thread without dedup.** Use the deduplication key.
- **Never escalates tier without human-in-loop.** A finding can be promoted from `high` to `critical` only via an explicit threshold change in `thresholds_override` — not by the agent's own judgment.
