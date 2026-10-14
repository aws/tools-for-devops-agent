# Observability — Check Definitions

> **Read `overview.md` first.** It holds the Severity Model, Status Values, the Evidence
> Guardrails (observed-data-only), and the public AWS API / `AWS/FSx` metric reference that
> govern every check below. Load this pillar file when you run this pillar's checks.

## Observability (3 checks)

### OBS-01 — CloudWatch alarms configured

- **Severity**: High
- **API**: `cloudwatch describe-alarms`
- **Logic**: Confirm alarms exist covering CPU, SSD capacity, IOPS, and latency for the in-scope file
  systems (match on `AWS/FSx` namespace and `FileSystemId` dimension).
- **Status**: Pass — alarms exist for CPU, SSD capacity, IOPS, and latency. Warning — some alarms but
  missing one or more critical metrics. Fail — no FSx alarms.
- **Recommendation (Fail/Warning)**: Create alarms for CPU > 85%, SSD capacity > 80%, IOPS > 80%, and
  read/write latency.
- **Fields**: `fileSystemId`, `metricsCovered`, `status`, `severity`

### OBS-02 — Alarms on all file systems

- **Severity**: High
- **API**: `cloudwatch describe-alarms`
- **Logic**: Every in-scope file system has at least one alarm.
- **Status**: Pass — every file system has ≥ 1 alarm. Fail — one or more file systems have none.
- **Recommendation (Fail)**: Add alarms for every FSx file system, not only the primary.
- **Fields**: `fileSystemId`, `alarmCount`, `status`, `severity`

### OBS-06 — No FSx alarms in ALARM state

- **Severity**: High
- **API**: `cloudwatch describe-alarms` (filter `StateValue = ALARM`)
- **Logic**: Report any FSx-related alarm currently in ALARM state.
- **Status**: Pass — all FSx alarms OK. Warning — 1–2 non-critical metric alarms in ALARM. Fail — any
  critical-metric alarm (CPU, latency, SSD capacity) in ALARM.
- **Recommendation (Fail/Warning)**: Investigate and resolve each active alarm. If an alarm is stale or
  noisy, tune its threshold — do not leave alarms perpetually in ALARM; it causes alert fatigue and masks
  real incidents.
- **Fields**: `alarmName`, `metric`, `stateValue`, `status`, `severity`

---
