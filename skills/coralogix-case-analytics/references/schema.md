# Dataset: `system/labs.cases.state_updates`
Data for this dataset is only available from June 8th, 2026 onward. If a query requests earlier dates, inform the user that data starts from this date and adjust the query window accordingly.
A single events dataset that captures every state-change emitted by the Cases service, plus periodic **heartbeat** events for cases that are still active but otherwise inactive (so an open case still shows up inside a query window even when nothing happened to it). All queries in this skill target this dataset.

### Schema (representative event)

```json
{
  "eventLabels": {},
  "eventMetadata": {
    "timestamp": 1737017985447000000,
    "cxEventId": "0523fa80-fef0-4a7c-8d04-15a449becce5",
    "severity": "Info",
    "priorityClass": "medium",
    "entityType": "cases"
  },
  "userData": {
    "caseId": "76c411be-ff4d-4fb1-a987-5fce042deaaf",
    "caseNumber": 1234,
    "schemaVersion": 1,
    "metadata": {
      "trigger": "caseClosed",
      "change": {
        "$type": "statusChanged",
        "previousStatus": "RESOLVED",
        "currentStatus": "CLOSED"
      }
    },
    "title": "Test Case",
    "description": "This is the description of the Test Case",
    "assignee": {
      "$type": "coralogixUser",
      "coralogixUser": { "id": "test-user-id-123" }
    },
    "status": "CLOSED",
    "priority": "P4",
    "priorityDetails": { "system": "P4", "override": null },
    "category": "AVAILABILITY",
    "createdAt": 1754817300000000000,
    "activatedAt": 1754817330000000000,
    "updatedAt": 1754904300000000000,
    "acknowledgedAt": 1754817390000000000,
    "acknowledgedBy": null,
    "assignedAt": null,
    "firstInteractedAt": null,
    "firstTriggerAt": 1754817240000000000,
    "resolvedAt": 1754903700000000000,
    "closedAt": 1754904300000000000,
    "closedBy": {
      "$type": "coralogixUser",
      "coralogixUser": { "userEmail": "test-user@coralogix.com" }
    },
    "resolutionDetails": {
      "resolutionType": "SYSTEM",
      "resolutionReason": "This was a false alert.",
      "resolvedAt": 1754903700000000000,
      "resolvedBy": { "$type": "system", "system": {} }
    },
    "kpiBreaches": {
      "breachedKpis": [
        {
          "id": "0e0a2a2b-4e6f-4f8e-9e2a-1b2c3d4e5f60",
          "createdAt": 1754817400000000000,
          "kpiType": "TIME_TO_ACKNOWLEDGE",
          "casePriority": "P4",
          "breachedAt": 1754817400000000000,
          "mitigatedAt": 1754817500000000000,
          "breachStatus": "MITIGATED"
        }
      ]
    },
    "indicators": {
      "alerts": [
        {
          "instanceId": "instance-id-1",
          "alertDefinitionId": "987e4567-e89b-12d3-a456-426614174111",
          "alertVersionId": "887e4567-e89b-12d3-a456-426614174112",
          "title": "Test CPU Alert",
          "alertType": "METRIC_THRESHOLD",
          "priority": "P4",
          "groupingType": "COMBINATION_ALERT",
          "permutations": [
            [
              { "key": "coralogix.metadata.applicationName", "value": "monitoring24",       "permutationIndex": 0 },
              { "key": "coralogix.metadata.subsystemName",   "value": "no_subsystem_name", "permutationIndex": 0 }
            ]
          ],
          "labels": { "metric": "cpu", "team": "platform" },
          "state": "TRIGGERED",
          "isNoData": false,
          "triggeredAt": 1754817240000000000,
          "resolvedAt": null,
          "alertQuery": {
            "queryString": "avg(node_cpu_seconds_total{mode=\"system\",service=\"payment-api\"}) > 0.8",
            "type": "ALERT_QUERY_PROMQL"
          }
        }
      ]
    },
    "permutations": [
      [
        { "key": "coralogix.metadata.applicationName", "value": "monitoring24",       "permutationIndex": 0 },
        { "key": "coralogix.metadata.subsystemName",   "value": "no_subsystem_name", "permutationIndex": 0 }
      ]
    ],
    "labels": {
      "metric":          ["cpu"],
      "team":            ["platform"],
      "routing.service": ["cases"]
    },
    "notificationEvidences": [
      { "type": "slack",         "evidence": { "url": "https://coralogix.slack.com/archives/C0123456789/p1754817400000200" } },
      { "type": "service_now",   "evidence": { "url": "https://coralogix.service-now.com/nav_to.do?uri=incident.do?sys_id=abc123" } },
      { "type": "generic_https" },
      { "type": "pagerduty" },
      { "type": "email" }
    ],
    "aiSummary": "CPU saturation on monitoring24 cleared after autoscaler added two pods.",
    "impactedEntities": [
      { "kind": "apmService",  "name": "payment-api", "language": "go" },
      { "kind": "apmDatabase", "name": "orders_db",   "system": "postgresql", "source": "db.name" }
    ]
  }
}
```

### Field reference (partial)

The dataset is one row per *state-update event* for a case. Because heartbeats fire for active cases, the **same `caseId` appears many times** within any window. Every analytical query must collapse to one row per case via the dedup patterns in the [Hard rules](../SKILL.md#hard-rules-always-apply).

#### Identity

| Field | Type | Meaning |
|---|---|---|
| `caseId` | UUID string | **Primary key.** All `groupby` / `dedupeby` operations key on this. |
| `caseNumber` | integer | Readable number behind the `CASE-<n>` ID shown in the UI. Useful for human-facing listings. |

#### Event metadata (this specific state-update)

| Field | Meaning |
|---|---|
| `metadata.trigger` | What triggered this event. Drives which lifecycle timestamp got set on this row. Common values: `caseCreated`, `caseActivated`, `caseAcknowledged`, `caseAssigned`, `caseResolved`, `caseClosed`, `caseArchived`, plus a heartbeat trigger emitted periodically for still-active cases. |
| `metadata.change` | A discriminated union describing the **diff** introduced by this event. The `$type` field is the discriminator. The most common variant is `statusChanged` with `previousStatus` and `currentStatus`. Use this when you want "transitions out of X" rather than "current state == X". |

#### Status & priority

| Field | Domain | Notes |
|---|---|---|
| `status` | `PENDING_ACTIVATION` / `ACTIVE` / `ACKNOWLEDGED` / `RESOLVED` / `CLOSED` | Filter on this after dedup for "currently in X" queries. |
| `priority` | `P1` / `P2` / `P3` / `P4` / `P5` | **String**, not numeric. Use equality (`== 'P1'`). |
| `priorityDetails.system` | same as `priority` | The system-derived priority. |
| `priorityDetails.override` | same as `priority`, or `null` | If set, the user overrode the system priority. When reporting priority, the override wins; |
| `category` | `AVAILABILITY` or `SECURITY` | Filter dimension. |

#### Lifecycle timestamps

**All timestamps in `userData` are numeric nanoseconds since epoch.** Cast with `:timestamp` for arithmetic and time-unit conversion, e.g. `(resolvedAt:timestamp - createdAt:timestamp).toTimeUnit('m')`. Null when the corresponding lifecycle step hasn't happened.

| Field | Meaning |
|---|---|
| `createdAt` | Case opened. |
| `activatedAt` | Moved `PENDING_ACTIVATION → ACTIVE`. `null` if never activated. |
| `updatedAt` | Last state change (any kind). |
| `acknowledgedAt` / `acknowledgedBy` | First acknowledge timestamp + actor. |
| `assignedAt` | First assignment timestamp. |
| `firstInteractedAt` | First human interaction (comment, status change by a person). |
| `firstTriggerAt` | When the underlying alert first fired. May be *earlier* than `createdAt`. |
| `resolvedAt` | Case resolved |
| `closedAt` / `closedBy` | Case closed (post-resolution). |

#### Alert indicators

`indicators.alerts[]` — the alerts that opened or feed this case.

Per-element fields:

| Field | Meaning |
|---|---|
| `alertDefinitionId` / `alertVersionId` | Stable IDs. Useful for joining with alert-side data (e.g. via alert tools for a specific alert definition). |
| `priority` | Alert priority at trigger (independent of case priority). |
| `groupingType` | `STANDARD` / `COMPOSITE_ALERT` / `COMBINATION_ALERT`. The latter two mean the indicator combines multiple sub-conditions. |
| `permutations` | Per-indicator permutations list — same `[[{key, value, permutationIndex}]]` structure as the root field. Contains the actual observed label combinations that fired this indicator. |
| `state` | `TRIGGERED` (still firing) / `RESOLVED` / `NO_DATA` (signal dropped, **not** a recovery) / `MUTED`. |
| `triggeredAt` / `resolvedAt` | Indicator-side timing (different from case-level resolution). |

#### Permutations & labels (routing / attribution)

`permutations` — the actual observed label combinations that produced this case. Each element of `permutations` is a **permutation-group**: a list of `{key, value, permutationIndex}` objects representing one real co-occurring set of key/value pairs.

- Exists at two levels:
  - **Per-indicator** (`indicators.alerts[].permutations`): the combinations that fired a specific alert indicator.
  - **Root/case level** (`permutations`): a merged view across all indicators for the whole case.

`labels` — free-form labels. The `routing.*` prefix is the convention for routing config:
  - `routing.team` — owner team (use this for "MTTR per team" style queries).
  - `routing.environment` — env (`prod`, `staging`, …).
  - `routing.service` — service tag.

#### Notifications

`notificationEvidences[]` — per-channel record of where the case's notifications landed. The `type` field is the discriminator.

| `type` | `evidence` shape | Notes |
|---|---|---|
| `slack` | `{ url: "<workspace>.slack.com/archives/<channel>/p<ts>" }` | Verbatim permalink to thread / channel. |
| `service_now` | `{ url: "<instance>.service-now.com/nav_to.do?uri=incident.do?sys_id=<id>" }` | Incident URL. |
| `pagerduty` | may or may not have `url` | PagerDuty often records only the incident ID, not a deep URL. |
| `email` | usually no `url` | Surface recipient/distribution alias if present. |
| `generic_https` | usually no `url` | Custom HTTPS connector. |

#### Other fields

`aiSummary` is a pre-computed string. Treat it as one input among many — never the source of truth.
`$m.timestamp` is the **event timestamp** (when the state-update was emitted) and is what you order by. `createdAt` (or `$d.createdAt`) is the **case creation time**.

