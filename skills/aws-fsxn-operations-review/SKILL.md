---
name: aws-fsxn-operations-review
description: >
  Amazon FSx for NetApp ONTAP Operational Review. Use when a user asks to review, audit, assess, or
  health-check FSx for NetApp ONTAP (FSxN / FSx ONTAP) — a file system, SVM, volume, or the whole
  footprint — for best-practices posture across Backup, Observability, Operations, Performance, and
  Security, in production or pre-production. Activate even on a brief request with no file-system IDs:
  the skill self-discovers all ONTAP file systems in the account/region and runs all pillars by
  default, so a bare account+region (or no scope) is enough — do not wait for named resources.
  Strictly read-only and fully automated via public AWS APIs (fsx, cloudwatch, backup, ec2); no manual
  steps, no ONTAP CLI. Triggers: "FSxN operational review", "FSx ONTAP review", "review my FSxN",
  "audit my FSx ONTAP", "check my FSxN posture", "FSx ONTAP best-practices audit", "FSxN health check",
  "assess my ONTAP file system".
metadata:
  author: "Aneesh Varghese (aneeshamz)"
  version: "1.5.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation"
  aws-devops-agent-skills.aws-services: "Amazon FSx for NetApp ONTAP, Amazon CloudWatch, AWS Backup, Amazon EC2"
  aws-devops-agent-skills.technical-domains: "Storage"
---

# Amazon FSx for NetApp ONTAP Operational Review

Run the FSx for NetApp ONTAP operational review checks against a customer's FSxN file systems and
produce an **Amazon FSx for NetApp ONTAP Operational Review** report. It evaluates **5 pillars,
46 checks** using native **public AWS APIs** (via `use_aws`): `fsx`, `cloudwatch`, `backup`, and
`ec2`.

This is a strict **READ-ONLY**, **fully automated** review. Every check is driven by a public AWS
`Describe*` / `List*` / `Get*` call or a CloudWatch metric read. There are **no manual steps, no
customer questionnaire, and no ONTAP CLI commands** in this review. Anything that can only be
answered from the ONTAP CLI is **out of scope** for this review.

## When to Use

Activate this skill when the user asks to review, audit, or assess an FSx for NetApp ONTAP workload,
or to check FSxN best-practices posture — for one pillar, a subset of checks, or the full set.

This is an **operational posture review** that can be run against any FSxN file system — whether in
**production or pre-production**. Typical uses:

- **Recurring posture review** (weekly or monthly) of a live file system — successive runs are
  directly comparable so you can track drift over time.
- **Ad-hoc audit** of an existing or newly inherited file system — understand its backup,
  observability, performance, and security posture and get a prioritized remediation list.
- **Health check** when something feels off and you want a full best-practices sweep before deciding
  where to dig in.

Because every finding is severity-ranked and carries a concrete remediation, the report serves as a
prioritized action list for the running workload — clear the Critical, High, and Medium findings to
improve posture.

Deep, ONTAP-CLI-level diagnosis of an active problem (performance degradation, connectivity failure,
failover) is **out of scope** for this automated review.

## Pillars and Checks

Run checks grouped by pillar in the order below. The check definitions are split across small
reference files for reliable loading:

- **Load `references/overview.md` first** — the Severity Model, Status Values, Evidence Guardrails, and
  the public AWS API / `AWS/FSx` metric reference that govern every check. Keep it in context for the
  whole run.
- **Then load the per-pillar checks file for each pillar you run** — load it when you start that
  pillar's checks:
    - `references/backup-checks.md` — Backup (7 checks)
    - `references/observability-checks.md` — Observability (3 checks)
    - `references/operations-checks.md` — Operations (11 checks)
    - `references/performance-checks.md` — Performance (17 checks)
    - `references/security-checks.md` — Security (8 checks)

| Pillar | Checks |
|--------|--------|
| **Backup** | Backup configured · Recovery points exist · SnapMirror (DP) relationships exist · FS automatic backups enabled · Backup size growth trend · Backup staleness · Automatic backup daily cadence |
| **Observability** | CloudWatch alarms configured · Alarms on all file systems · No FSx alarms in ALARM state |
| **Operations** | Cost-allocation tags · Unused volumes identified · Maintenance window aligned · Consistent maintenance windows · Storage efficiency enabled · Snapshot policies on production volumes · Deployment type matches HA requirements · Active Directory configured on SVM · Volume & SVM tag audit · Per-volume capacity utilization · Aged snapshots |
| **Performance** | CPU < 85% · Throughput config matches workload · IOPS not over-provisioned · IOPS util < 80% · SSD capacity < 80% · Volume tiering policies appropriate · Aggregate workload balanced · FlexGroup constituent balance · Network path optimized · Client throughput nominal · Filesystem generation appropriate · Capacity-pool tiering only for archive · HA pair count sufficient · FlexClone not on tiered parent · No unexpected capacity-pool reads · Cache hit ratio · Latency monitoring |
| **Security** | SG allows required ports · SG not overly permissive · Volume security style correct · No unintentional MIXED style · AD integration configured · Route-table associations for Multi-AZ · Encryption at rest / KMS key · Security-group egress |

## Steps

Work through this ordered, dependent procedure and check each item off as you complete it:

- [ ] **Step 1 — Identify scope.** Default path (no clarification round-trip): if the user gives no
  specifics, default to the current account/region via `sts:GetCallerIdentity`, discover **all** ONTAP
  file systems with `fsx describe-file-systems` (filter `FileSystemType = ONTAP`), and run **all 5
  pillars / 46 checks** with the default metric windows. Confirm scope only if the user volunteers it
  or the estate is large.
    - [ ] Note the parameters (all default): file-system IDs / accounts / regions (default current);
      pillars or checks (default all); date range (performance reads = trailing 7 days, backup growth =
      30 days, unused-volume I/O per OPS-02).
    - [ ] **Large-estate guard:** if discovery returns more than ~25 file systems, or they span more
      than 3 regions, ask the user to scope first (by region, by tag, or to a subset of pillars).

- [ ] **Step 2 — Run the checks.** **Load `references/overview.md` first, then each in-scope pillar's
  `references/<pillar>-checks.md`** (authoritative APIs, logic, thresholds, severities, output fields;
  guardrails live in `overview.md`) and keep them in context. For each in-scope check, call the public
  AWS APIs via `use_aws` and build result rows, following:
    - [ ] **Read-only.** `Describe*` / `List*` / `Get*` only; paginate every token. No
      `Create*`/`Update*`/`Delete*`, no data-plane access, no mounting, no ONTAP CLI.
    - [ ] **Automated only.** Every check is answerable from a public AWS API. Emit no questionnaire
      items, "manual verification" steps, or ONTAP CLI. If a finding would need ONTAP-CLI follow-up,
      state it is out of scope — do not inline CLI.
    - [ ] **Evidence-only.** Base every result solely on values returned this run (Evidence Guardrails
      in `references/overview.md`). No assumptions or inference of unobserved state. Classify
      resources only from returned fields (e.g. the SVM root volume by returned `JunctionPath = "/"`).
      Carry observed value(s) into each row; show inputs for any derived figure.
    - [ ] **Per-check isolation.** Record errors per check as a `{ error }` row — one failed check never
      aborts the review.
    - [ ] **Graceful degradation.** On `AccessDenied`, an API error, empty results, an absent field, or
      a metric with no datapoints, set the check **Not evaluated** with the reason — never a false
      "none found", false "Pass", or guessed value.
    - [ ] **Empty results** (permission present, nothing there) → a single "No `<resource>` found" row.
    - [ ] **Units on every number.** Utilization metrics are percent; `*Bytes` → a labelled rate (GB/hr);
      latency from `*OperationTime ÷ *Operations` is seconds → ×1000 ms, labelled.
    - [ ] **Severity per the pillar's `references/<pillar>-checks.md`** (Critical/High/Medium/Low/Informational); use
      only the thresholds each check defines.
    - [ ] **One finding = one non-compliant resource in one check**, keyed by
      `(check, fileSystemId, resource)` — never aggregate.
    - [ ] **One recommendation per Critical/High/Medium finding** — concrete and FSxN-specific.

- [ ] **Step 3 — Validate your own output, then generate the report.** First self-check and fix any
  problem **before** presenting:
    - [ ] **Every row cites observed data** — no Pass/Warning/Fail without the API value(s); derived
      figures show inputs; a check lacking data reads `Not evaluated — <reason>`, not a guess.
    - [ ] **Severity counts reconcile** — the Executive Summary counts equal the per-check totals
      (recount per pillar).
    - [ ] **Every Critical/High/Medium finding is in the Executive Summary**, each with one recommendation.
    - [ ] **Resource identifiers are exact** (IDs copied from the API, not paraphrased).
    - [ ] **Root-volume handling is correct** — SVM root (`JunctionPath = "/"`) is `Excluded` only in
      OPS-10, tagged (never deleted/removed) elsewhere.
    - [ ] **No invented numbers**, no ONTAP CLI, no manual steps anywhere in the report.
    - [ ] **Produce the findings report.** The response MUST contain, at minimum:
        1. a title line identifying it as an **FSx for NetApp ONTAP operational review** and the file
           system(s) / region reviewed;
        2. an **Executive Summary** with **counts by severity** (Critical / High / Medium / Low) and the
           Critical/High/Medium findings **ranked most-severe first**;
        3. for **each** finding: the **check ID** (e.g. `SEC-08`, `BKP-01`) and **pillar** it belongs to,
           the **specific resource** (file-system / volume / SVM id), the **observed value** it is based
           on, and **one concrete FSxN-specific remediation**;
        4. a short "healthy / not evaluated" note for areas that passed or had no data.
      Keep it a prioritized findings report — do not pad with prose, and do not drop the evidence or the
      check IDs. **Output budget:** cover every in-scope check, but render compactly (one line or one
      table row per finding); summarize passing checks in aggregate rather than a full section each.

### Report format: chat vs full

- **Chat task (default):** the prioritized findings report above — concise, evidence-first, keyed to
  check IDs. This is the normal output and is what most requests want.
- **Full tabular report (Evaluation agent, or when the user explicitly asks for the "full report"):**
  load `assets/report-template.md` and render the complete layout — H1 title, the account/region/date
  header, the **AI Disclaimer** blockquote verbatim, the Executive Summary, and one `##` section per
  pillar with a `###` + **Data table** per check. Use this when a complete, archivable document is
  wanted rather than a chat answer.

## Gotchas (FSxN-specific — correct these before they bite)

- **Gen2 file systems do not emit `StorageCapacityUtilization`.** When `DeploymentType` ends in `_2`
  (`SINGLE_AZ_2` / `MULTI_AZ_2`), that metric returns **no datapoints** — it is not 0%. Compute SSD
  utilization from the detailed per-tier `StorageUsed{SSD}` ÷ `StorageCapacity{SSD}` instead (PERF-05).
- **`StorageCapacityUtilization` takes only `FileSystemId`** (no `StorageTier` dimension) and already
  reflects the **primary/SSD tier** (it backs the FSx "low primary storage" alarm).
- **The SVM root volume** is the volume at `JunctionPath = "/"` (`Name = <svm>_root`). Its `StorageUsed`
  does not map to its configured size — excluded only in OPS-10 (shown as `Excluded — SVM root`), tagged
  elsewhere, and **never** a deletion candidate.
- **Latency metrics are in seconds.** `DataReadOperationTime ÷ DataReadOperations` (and write/metadata)
  gives seconds — multiply by 1000 and label **ms**. An unlabelled six-figure number reads as a false
  escalation.
- **Idle file system ≠ a problem.** When there is no traffic, activity metrics (latency, cache hit,
  client throughput, per-volume I/O) return no datapoints → **Not evaluated**, never a guessed 0% or Pass.
- **Volumes are thin-provisioned.** A volume's configured size can exceed the file system; per-volume
  used% is against the **configured volume size**, not the file-system SSD tier.
- **Ages are computed from each resource's timestamp** (`now − CreationTime`); never synthesize a
  standalone past cutoff like `now − 90d` — agent datetime tools guard against far-past timestamps.
- **`ALL` tiering on an active volume forces every read from the capacity pool** (15–25 ms); capacity-pool
  reads on active data are a latency red flag (PERF-17/PERF-21).

## Constraints

- READ-ONLY — no resource mutation, no mounting, no data-plane access, no ONTAP CLI.
- **Fully automated** — no manual steps, no customer questionnaire. Every result comes from a public
  AWS API.
- **Evidence-only — the whole report is built from data the API calls returned this run.** Follow the
  **Evidence Guardrails** in `references/overview.md`: observed data only; no assumptions or
  inference of unobserved state; missing/failed/empty data ⇒ **Not evaluated** with the reason (never a
  guessed Pass/Fail); every result row shows the value(s) it is based on, and derived figures show their
  inputs. A finding that cannot be backed by a returned value must not appear.
- Report only what the APIs return. Do NOT fabricate data or assume unobserved configuration.
- **No invented numbers.** State a throughput tier, IOPS limit, utilization percentage, capacity, age,
  or count only if an API call returned it. Never substitute a tier default for an applied value, and
  never attach "~" or "up to" to a figure you did not read.
- Paginate ALL calls that return a pagination token.
- Empty-scope precedence: if **every** in-scope check across **all** in-scope accounts/file
  systems/regions returns no resources, skip the per-pillar report and instead report the single line
  "No FSx for NetApp ONTAP activity detected." Otherwise render the full report — each check that found
  nothing gets its own empty-state row.
- Keep all guidance and recommendations specific to Amazon FSx for NetApp ONTAP.

## Scope Limitations — state these in the report, do not overclaim past them

- **Control-plane and CloudWatch metrics only.** The review reports configuration and CloudWatch
  signals exposed by public AWS APIs. It cannot read ONTAP-internal state — SnapMirror lag and health,
  WAFL/aggregate internals, per-volume ONTAP latency counters, FlexCache hit ratios, audit-log
  configuration, snapshot auto-delete policy, and similar are **not** assessed. Where a check touches
  such an area (e.g. BKP-03 sees DP volumes but not SnapMirror lag), say so in that check's Guidance
  rather than implying wider coverage.
- **No ONTAP CLI.** This skill never executes or recommends ONTAP CLI. CLI-level diagnosis is **out of
  scope** for this review.
- **Point-in-time.** Findings reflect state at run time. Metric windows are fixed per check, so a spike
  outside the window is not visible.
- **Large estates may need scoping.** Many file systems and volumes across many regions can exhaust the
  run budget; scope to fewer file systems or pillars if a run is at risk of truncating.

## Data Source Boundaries

Public AWS APIs only, via `use_aws`: `fsx` (`describe-file-systems`, `describe-volumes`,
`describe-storage-virtual-machines`, `describe-snapshots`, `describe-backups`, `list-tags-for-resource`),
`cloudwatch` (`describe-alarms`, `get-metric-data`, `list-metrics`), `backup`
(`list-protected-resources`, `list-recovery-points-by-resource`), and `ec2`
(`describe-security-groups`, `describe-subnets`, `describe-route-tables`). No ONTAP CLI, no data-plane
calls, no non-AWS tooling — the skill is self-contained on the DevOps Agent's cloud-source IAM role.
