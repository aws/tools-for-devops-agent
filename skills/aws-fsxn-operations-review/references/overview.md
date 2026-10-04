# Amazon FSx for NetApp ONTAP — Operations Review Check Definitions

**5 pillars, 46 checks.** Every check is a read-only, fully automated evaluation driven by
**public AWS APIs** (`fsx`, `cloudwatch`, `backup`, `ec2`) via the `use_aws` tool. There are
**no manual steps, no customer questionnaire, and no ONTAP CLI commands** anywhere in this review —
anything that cannot be answered from a public AWS API is **out of scope** for this review.

This file is the single source of truth for each check's APIs, logic, thresholds, severity, and
output fields. `SKILL.md` defers to it.

## Severity Model

| Severity | Meaning | Examples |
|----------|---------|----------|
| **Critical** | Immediate action — active production risk | CPU ≥ 85%; SG open to `0.0.0.0/0`; SSD utilization > 90% (tiering promotion stops) |
| **High** | Address promptly (within ~2 weeks) | No backups configured; no recovery points; alarm in ALARM state; IOPS ≥ 80%; no snapshot policy on RW volume |
| **Medium** | Best-practice gap (within ~30 days) | Missing cost-allocation tags; storage efficiency disabled; MIXED security style without justification |
| **Low** | Minor hygiene / informational posture | Maintenance window not aligned; inconsistent maintenance windows |
| **Informational** | Inventory / state, no pass/fail signal | Deployment type, HA pair count, filesystem generation, tiering-policy inventory |

A check marked **Report value** emits an Informational row unless its stated fail condition is met,
in which case it carries the severity defined for the finding.

## Status Values

Each evaluated resource gets a status:

- **Pass** — meets the best-practice condition (backed by an observed value).
- **Warning** — partial / borderline (where the check defines a warning band), backed by an observed value.
- **Fail** — violates the condition; produces a severity-ranked finding and one recommendation. Backed
  by an observed value.
- **Info** — inventory value reported for review (no pass/fail).
- **Not evaluated** — the data needed could not be retrieved this run: an API returned `AccessDenied`
  or an error, a required field was absent, a CloudWatch metric returned no datapoints, or the resource
  was idle. State the concrete reason. **Not evaluated is a valid, expected outcome and is always
  preferred over a guess.** Never convert it to a false "Pass", "Fail", or "none found".

## Evidence Guardrails — apply to EVERY check

The report must reflect **only what the API calls actually returned this run**. No assumptions, no
inferences about unobserved state, no filling gaps from defaults, documentation, prior runs, or
"typical" values.

1. **Observed data only.** Every Pass / Warning / Fail / Info result must be derived from a value an
   API returned **in this run** — a `describe-*`/`list-*` field or a CloudWatch datapoint. If you did
   not retrieve the value, you may not assert the finding.
2. **No inference of unobserved state.** Classify resources only from returned fields. Example: identify
   the SVM root volume to exclude by the **returned `JunctionPath = "/"`** (and/or `Name = <svm>_root`),
   never by assumption. Do not infer a setting the public API does not expose — if a determination needs
   data no public API returns, the check is **Not evaluated — not available via public API**.
3. **Missing or failed data ⇒ Not evaluated.** On `AccessDenied`, an API error, empty results, an
   absent field, or a metric with no datapoints, set the check **Not evaluated** with the concrete
   reason. Never fabricate a Pass/Fail and never guess a value.
4. **Show the evidence.** Every result row carries the actual value(s) it is based on — the field, the
   metric value with its unit and window, the timestamp. A **derived** figure must show its inputs
   (e.g. `usedPct` must show the `StorageUsed` bytes and the `SizeInMegabytes` it was computed from).
5. **No invented numbers.** State a throughput tier, IOPS limit, utilization %, capacity, age, or count
   only if an API returned it. Never substitute a tier default for an applied value; never attach "~" or
   "up to" to a figure you did not read. If a figure would help but was not retrieved, point the reader
   at the console page or API that holds it.
6. **Thresholds and severities come only from this file.** Do not invent thresholds a check does not
   define, and use only the severities each check specifies.
7. **One finding = one observed non-compliant resource** in one check. No aggregated or extrapolated
   findings; evaluate only the resources the discovery calls actually returned.

If any check cannot be completed from observed data, report it **Not evaluated** with the reason —
that is the correct result, not a reason to estimate.

## Public AWS API Reference

All calls are read-only `Describe*` / `List*` / `Get*` control-plane and CloudWatch reads via
`use_aws`. No data-plane access, no mutations.

| Namespace | Operations used | Purpose |
|-----------|-----------------|---------|
| `fsx` | `describe-file-systems`, `describe-volumes`, `describe-storage-virtual-machines`, `describe-snapshots`, `describe-backups`, `list-tags-for-resource` | File system, SVM, and volume configuration and inventory |
| `cloudwatch` | `describe-alarms`, `get-metric-data`, `list-metrics` | Alarm posture and `AWS/FSx` performance / capacity metrics |
| `backup` | `list-protected-resources`, `list-recovery-points-by-resource` | AWS Backup coverage and recovery-point history |
| `ec2` | `describe-security-groups`, `describe-subnets`, `describe-route-tables` | Network port access and routing posture |

### `AWS/FSx` metrics used (confirm names exactly — public FSx for ONTAP metrics)

| Metric | Dimensions | Used by |
|--------|-----------|---------|
| `CPUUtilization` (%) | `FileSystemId` | PERF-01 |
| `FileServerDiskThroughputUtilization` (%), `NetworkThroughputUtilization` (%) | `FileSystemId` | PERF-02, PERF-15 |
| `FileServerDiskIopsUtilization` (%) | `FileSystemId` | PERF-04 |
| `StorageCapacityUtilization` (%) | `FileSystemId` | PERF-05 (primary/SSD-tier utilization) |
| `StorageCapacity`, `StorageUsed` (bytes, detailed) | `FileSystemId`, `StorageTier` (`SSD` \| `StandardCapacityPool`), `DataType` | PERF-05 fallback (compute `StorageUsed{SSD}` ÷ `StorageCapacity{SSD}`) |
| `DataReadBytes`, `DataWriteBytes`, `DataReadOperations`, `DataWriteOperations` | `FileSystemId` (+ `VolumeId` for per-volume) | OPS-02, PERF-15 |
| `CapacityPoolReadBytes` | `FileSystemId` (+ `VolumeId`) | PERF-21 |
| `FileServerCacheHitRatio` (%) | `FileSystemId` | PERF-22 |
| `DataReadOperationTime`, `DataWriteOperationTime`, `MetadataOperationTime` (seconds) | `FileSystemId` (+ `VolumeId`) | PERF-23 (latency = op-time ÷ ops × 1000 ms) |
| `StorageUsed` (bytes, detailed) | `FileSystemId`, `VolumeId`, `StorageTier`, `DataType` | OPS-10 (per-volume used ÷ volume `SizeInMegabytes`) |

> **Identifying the SVM root volume (do not hide volumes).** Identify the SVM root volume from returned
> fields: the volume whose `OntapConfiguration.JunctionPath == "/"` (primary signal), confirmed by
> `Name == "<svm-name>_root"`. Handle it per check — **do not blanket-exclude it from the review**:
> - **OPS-10 only** skips the root volume, because its `usedPct = StorageUsed ÷ configured size` is
>   mathematically invalid for a namespace root (not sized to hold data). Show it as an explicit
>   `Excluded — SVM root (JunctionPath=/)` row, never silently dropped.
> - **All other volume checks (OPS-02, OPS-05, OPS-06, and the volume-level PERF/SEC checks) evaluate
>   the root volume like any other volume** and report its observed values. **Tag** the root-volume row
>   as `SVM root (JunctionPath=/)` so the reader has context, and **never emit a destructive
>   recommendation** (e.g. "delete"/"remove") against it — the SVM root cannot be removed.
> - Treat volumes with `OntapVolumeType` of `DP` (SnapMirror destination) or `LS` as non-data where a
>   check's logic says so, but still list them.
> - If neither `JunctionPath` nor `Name` is returned for a volume, do not guess its role — evaluate it
>   and note the ambiguity rather than excluding it.

> **Age / time-window computations.** For every check with an age or lookback threshold (30/90 days),
> compute the **age of each resource from its own timestamp** — `ageDays = now − CreationTime` (a
> positive number of days) — and compare that age to the threshold. Do **not** synthesize a standalone
> past cutoff date such as `now − 90d`; some agent datetime tools guard against far-past/future
> timestamps and will refuse it. Likewise, derive a metric window as a `start = now − Nd` / `end = now`
> pair passed straight to the CloudWatch call, not as a bare far-past timestamp to reason about.

---

## References

- NetApp TR-4958: Best Practices for FSx for ONTAP
- AWS Prescriptive Guidance: FSx ONTAP Enterprise Deployment
- AWS FSx for ONTAP Performance Guide and CloudWatch metrics documentation
- AWS Well-Architected Framework (Reliability, Performance Efficiency, Security, Cost Optimization pillars)
