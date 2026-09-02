# Finding Logic

Severity rules and verbatim body templates for the seven SLA dimensions plus the
cost-optimization notes. Apply each rule against the structured configuration object
from `references/data-collection.md`. **Use the body text verbatim; substitute only
the `<placeholder>` values.** Never invent thresholds — every threshold below is
grounded in AWS documentation (see `references/fsx-windows-sla-best-practices.md`).

## Severity levels

| Severity | Meaning | Effect on rating |
|---|---|---|
| 🔴 Critical | Active or imminent availability loss | Rating → Low |
| ⚠️ Warning | Weakens the SLA; not yet failing | Rating capped at Medium |
| ✅ Pass | Meets the availability best practice | No cap |
| ❓ Unable to verify | Data missing (AccessDenied / ToolingFailure) | Rating capped at Medium |
| ℹ️ Info | Transient/contextual note (e.g. storage optimization in progress) | **No effect on rating** |
| 💰 Cost note | Advisory only — over-provisioning | **No effect on rating** |

Apply the "Unable to verify" template for any dimension whose `status` is
`AccessDenied` or `ToolingFailure`:

> **❓ Unable to verify.** The `<dimension>` check could not complete
> (`<AccessDenied|ToolingFailure>`). This configuration was not assessed; the SLA
> Readiness rating is capped at Medium. Add the missing read permission or retry.

---

## Dimension 1 — Deployment type (Single-AZ vs Multi-AZ)

The single biggest availability lever. Read `deployment.type`.

- `MULTI_AZ_1` → **✅ Pass**
- `SINGLE_AZ_1` or `SINGLE_AZ_2` → **⚠️ Warning**

**✅ Pass body:**
> **✅ Multi-AZ deployment.** The file system uses `MULTI_AZ_1`, a high-availability
> cluster across two Availability Zones with synchronous replication and automatic
> failover to the standby (Windows Server Failover Clustering). This is the
> configuration required for the highest availability during AZ disruption and
> planned maintenance.
>
> **Client-side caveat:** automatic failover only helps clients that re-resolve the
> file system's DNS name on failover. Windows SMB clients do this automatically;
> Linux/macOS clients and some runtimes (e.g. .NET on Linux, Lambda) cache DNS and
> will **not** fail over unless configured to honor DNS TTL. If you front FSx with
> third-party DNS (e.g. Infoblox), publish **two A records** — one per file-system IP
> (preferred + standby) — so name resolution survives a failover. You can validate
> failover safely by issuing a throughput-capacity update, which triggers a
> controlled failover.

**⚠️ Warning body (Single-AZ):**
> **⚠️ Single-AZ deployment (`<deployment_type>`).** This file system runs in a
> single Availability Zone with no standby, so it has **no automatic cross-AZ
> failover**. Single-AZ file systems typically incur ~30 minutes of downtime during
> failure-recovery events and during the weekly maintenance window, and in rare
> multi-component or non-graceful failures the file system may be unrecoverable
> except by restoring from a backup. AWS Security Hub control **FSx.5** and AWS
> Config rule `fsx-windows-deployment-type-check` both flag non-Multi-AZ file
> systems for production use.
>
> **Remediation:** deployment type **cannot be changed in place**. To gain
> automatic failover, create a new `MULTI_AZ_1` file system and migrate the data
> (e.g. AWS DataSync or a robocopy cutover), then repoint clients via DNS alias.

---

## Dimension 2 — Active Directory health

FSx for Windows depends on Active Directory; when it cannot reach AD, the file
system enters `MISCONFIGURED` and is unavailable or at risk. Evaluate `lifecycle`
first, then `active_directory`.

Order of evaluation:

1. `lifecycle.value == "MISCONFIGURED_UNAVAILABLE"` → **🔴 Critical** (data already
   inaccessible — quarantined after prolonged AD failure)
2. `lifecycle.value == "MISCONFIGURED"` → **🔴 Critical** (AD reachability problem)
3. `lifecycle.value == "FAILED"` → **🔴 Critical** (file system failed)
4. AWS Managed AD with `active_directory.stage` in {`Impaired`, `Inoperable`,
   `RequestedFailed`} → **🔴 Critical**
5. `lifecycle.value` in {`CREATING`, `UPDATING`, `DELETING`} → **⚠️ Warning**
   (transient; note and move on)
6. Otherwise (`AVAILABLE`, AD `Active` or self-managed with healthy lifecycle) →
   **✅ Pass**

**🔴 Critical body (Misconfigured):**
> **🔴 File system is Misconfigured — Active Directory unreachable.** `<file_system_id>`
> is in the `MISCONFIGURED` lifecycle state, which FSx enters when it cannot
> communicate with the Active Directory domain controllers. In this state the file
> system is unavailable or at imminent risk of losing availability, and backups may
> not succeed. Reported detail: "`<failure_message>`".
>
> `<ad_root_cause_note>`
>
> The common root causes are: (1) security groups / network ACLs blocking the
> required ports to the DNS servers or domain controllers; (2) invalid or rotated
> service-account credentials; (3) the service account lacking permission to join the
> file system to the target OU; (4) the file system's OU computer object was moved or
> deleted. Do not move or delete the OU objects FSx created.
>
> **Remediation:** run the `AWSSupport-ValidateFSxWindowsADConfig` Systems Manager
> automation runbook to pinpoint the reachability or credential failure, then update
> the file system's Active Directory configuration.

Set `<ad_root_cause_note>` by matching the reported `failure_message` (case-insensitive
substring) against these known lifecycle detail codes — quote the matched cause so the
operator gets a targeted fix rather than the generic list:

| `failure_message` contains | `<ad_root_cause_note>` text |
|---|---|
| `ACTIVE_DIRECTORY_INVALID_CREDENTIALS` | "The reported detail points to **invalid service-account credentials** — the password was almost certainly rotated or expired in AD. Update the file system's self-managed AD configuration with the current username/password. If the account uses the `user@domain` UPN and is a member of the **Protected Users** group, NTLM is blocked for it — either remove it from Protected Users or supply an account that is not in that group." |
| `ACTIVE_DIRECTORY_INSUFFICIENT_PERMISSIONS` | "The reported detail points to the **service account lacking permission** to create/manage the computer object in the target OU. Delegate 'Create/Delete Computer objects' and password-reset rights on the OU to the service account (or use an account that already has them)." |
| `ACTIVE_DIRECTORY_COMP_ACC_REUSE_BLOCKED_BY_POLICY` | "The reported detail points to **computer-account re-use being blocked by domain policy** (the Windows netjoin hardening from KB5020276). Enable the GPO **Domain member: Allow computer account re-use during domain join** for the FSx OU, or pre-stage/remove the stale computer object, then retry the AD update." |

If none match, omit `<ad_root_cause_note>` (leave the generic root-cause list only).

**🔴 Critical body (Misconfigured-Unavailable — quarantined):**
> **🔴 File system is Misconfigured-Unavailable — data currently inaccessible.**
> `<file_system_id>` is in the `MISCONFIGURED_UNAVAILABLE` state. FSx moves a file
> system here after it has been unable to reach Active Directory for a prolonged
> period (backups and patching have been failing), and **the file system's data is
> not accessible** until the AD configuration is repaired. This is the most severe AD
> state. Reported detail: "`<failure_message>`".
>
> `<ad_root_cause_note>`
>
> **Remediation:** repair the underlying AD problem (credentials / OU permissions /
> DC reachability) and update the file system's AD configuration to recover it; run
> `AWSSupport-ValidateFSxWindowsADConfig` to confirm the fix. If it does not recover,
> engage AWS Support — a quarantined file system may require a backend recovery.

**🔴 Critical body (AD directory unhealthy — AWS Managed AD):**
> **🔴 Associated AWS Managed Microsoft AD is `<stage>`.** Directory `<directory_id>`
> is not in the `Active` stage (`<stage_reason>`). While the directory is impaired,
> the file system's authentication and availability are at risk. Restore directory
> health (check domain controller status, VPC connectivity, and DNS) before relying
> on the SLA.

**✅ Pass body:**
> **✅ Active Directory healthy.** The file system is `AVAILABLE` and its
> `<AWS Managed|self-managed>` Active Directory shows no reachability problems.

---

## Dimension 3 — Throughput capacity (SLA + cost lens)

Evaluate against the AWS sizing guidance **read + 2 × write**, computed at both the
average and the **peak** of the daily series (see `references/trend-analysis.md`).
Peak matters because a file system fine on average can throttle every weekday
morning. Use `throughput.required_peak_mbps` and `throughput.required_avg_mbps` vs
`throughput.provisioned_mbps`, and read `trend.usage_profile` /
`trend.throughput_pattern` for evidence.

Evaluate in this order:

- `provisioned_mbps < required_peak_mbps` → **⚠️ Warning** (peaks exceed capacity →
  SLA risk, even if the average looks fine)
- `required_peak_mbps <= provisioned_mbps <= 4 × required_peak_mbps` (and provisioned
  ≥ 32) → **✅ Pass**
- `provisioned_mbps > 4 × required_peak_mbps` → **✅ Pass** for SLA **plus a 💰 cost
  note** (see below)

**⚠️ Warning body (undersized at peak):**
> **⚠️ Throughput capacity may be undersized at peak.** Provisioned throughput is
> `<provisioned_mbps>` MBps, but the measured **peak** demand over the last
> `<lookback>` is ~`<required_peak_mbps>` MBps (approximate peak read
> `<peak_read_mbps>` MBps + 2 × write `<peak_write_mbps>` MBps; average demand was
> ~`<required_avg_mbps>` MBps). When demand meets or exceeds provisioned throughput —
> which here happens at peak (`<throughput_pattern>` pattern) — requests are
> throttled and clients see latency, timeouts, or disconnects that count against
> availability. `<peak_timing_note>`
>
> **Remediation:** increase throughput capacity (an online, in-place update; a brief
> failover occurs on Multi-AZ). Size to at least read + 2 × write **at peak**, with
> headroom.

Where `<peak_timing_note>` is, when `usage_profile` is `weekday-dominant` or
`idle-off-hours`: "The usage profile is weekday-concentrated, so the shortfall likely
bites during business-hours peaks (e.g. a morning mount storm)." Otherwise omit.

**✅ Pass body:**
> **✅ Throughput capacity adequate.** Provisioned `<provisioned_mbps>` MBps covers
> the measured peak demand of ~`<required_peak_mbps>` MBps (read + 2 × write at peak;
> average ~`<required_avg_mbps>` MBps) over the last `<lookback>`. Usage pattern:
> `<throughput_pattern>`, profile `<usage_profile>`.

**💰 Cost note (over-provisioned throughput) — append to the Pass, do NOT change the rating:**
> **💰 Cost optimization — throughput over-provisioned.** Provisioned
> `<provisioned_mbps>` MBps is well above even the measured **peak** demand of
> ~`<required_peak_mbps>` MBps (read + 2 × write) over the last `<lookback>`.
> `<profile_evidence>` Throughput capacity is billed continuously, so this is likely
> wasted spend. Review whether a lower throughput tier still meets peak demand with
> headroom; throughput can be adjusted online. `<sub32_caveat>` This is an efficiency
> observation only — it does not lower the SLA Readiness rating.

Where `<sub32_caveat>` is included only when the recommended/target tier would be at
or below 32 MBps (i.e. `required_peak_mbps` is well under 32): "Note that FSx
publishes throughput-utilization metrics only at **≥ 32 MBps** — the 8 and 16 MBps
tiers emit no CloudWatch performance metrics, so a drop to those tiers can only be
validated by observing the workload after the change, not from these metrics.
Recommend stepping down toward 32 MBps first." Otherwise omit.

Where `<profile_evidence>` is, when `usage_profile` is `idle-off-hours` or
`weekday-dominant`: "Usage is concentrated on weekday business hours
(weekend:weekday ratio `<weekend_weekday_ratio>`), so this capacity sits largely idle
nights and weekends — the file system pays for peak throughput 24/7 while using it a
fraction of the week." Otherwise omit.

---

## Dimension 4 — Storage capacity headroom (SLA + cost lens)

AWS recommends maintaining **at least 20% free** storage capacity at all times;
running near-full degrades performance and can introduce data inconsistencies. Use
`storage.free_min_pct` (worst-case in the window).

- `free_min_pct < 10` → **🔴 Critical**
- `10 <= free_min_pct < 20` → **⚠️ Warning**
- `free_min_pct >= 20` → **✅ Pass**
- `free_min_pct` very high (e.g. `> 70` sustained) → **✅ Pass plus 💰 cost note**

**🔴 Critical body (<10% free):**
> **🔴 Storage critically low.** Worst-case free storage over the last `<lookback>`
> was `<free_min_pct>%` (`<free_min_gib>` GiB of `<provisioned_gib>` GiB). Below 10%
> free, performance degrades and writes can fail — a direct availability risk.
>
> **Remediation:** increase storage capacity now (online, in-place). Consider the
> AWS dynamic-scaling CloudFormation template to auto-increase when
> `FreeStorageCapacity` drops below a threshold. **Sequencing caution:** a storage
> increase kicks off a background storage-optimization phase that consumes disk
> throughput and can pin `FileServerDiskThroughputUtilization` near 100% until it
> finishes, degrading performance during the copy. If throughput is already tight
> (dimension 3), **raise throughput capacity first, then increase storage** so the
> optimization has headroom. FSx now allows up to **4 storage/throughput
> modifications per rolling 24 hours**.

**⚠️ Warning body (10–20% free):**
> **⚠️ Storage headroom below the 20% guidance.** Worst-case free storage over the
> last `<lookback>` was `<free_min_pct>%` (`<free_min_gib>` GiB of
> `<provisioned_gib>` GiB). AWS recommends keeping at least 20% free at all times.
> `<growth_projection_note>`
>
> **Remediation:** increase storage capacity, or set a `FreeStorageCapacity`
> CloudWatch alarm and enable dynamic storage scaling.

**✅ Pass body:**
> **✅ Storage headroom healthy.** Worst-case free storage over the last
> `<lookback>` was `<free_min_pct>%` (`<free_min_gib>` GiB of `<provisioned_gib>`
> GiB), at or above the 20% guidance. `<growth_projection_note>`

**Growth projection (`<growth_projection_note>`)** — from `trend.storage_trend` and
`trend.weeks_to_floor` (see `references/trend-analysis.md`). Append to the Warning
and Pass bodies:

- `storage_trend == "growing"` and `weeks_to_floor` is a finite number:
  "At the current growth rate (~`<used_growth_gib_per_week>` GiB/week), free space is
  projected to reach the 20% floor in **~`<weeks_to_floor>` weeks** — plan a capacity
  increase before then." **If `weeks_to_floor <= 4`, raise this dimension to ⚠️
  Warning** even when current free % is healthy (an imminent-fill forecast is itself
  a risk).
- `storage_trend == "stable"` (flat or shrinking): "Used capacity is stable over the
  window; no near-term fill projected."
- `trend.usage_profile == "insufficient-data"`: "Too few datapoints to project a
  growth trend." (omit the projection)

**💰 Cost note (over-provisioned storage) — append to the Pass, do NOT change the rating:**
> **💰 Cost optimization — storage may be over-provisioned.** Worst-case free
> storage was `<free_min_pct>%` (`<free_min_gib>` GiB idle of `<provisioned_gib>`
> GiB) over the last `<lookback>`, indicating large unused headroom.
> `<storage_type_note>` Storage capacity can only be increased, not decreased, so
> right-sizing means migrating to a smaller file system — weigh the migration effort
> against the ongoing savings. This is an efficiency observation only — it does not
> lower the SLA Readiness rating.

Where `<storage_type_note>` is, when `storage.storage_type == "SSD"` and utilization
is low: "The file system uses SSD storage; if this is a throughput-light,
latency-tolerant workload, HDD storage would be materially cheaper." Otherwise omit.

### Idle-file-system cost signal (cross-cutting 💰 — do NOT change the rating)

When `trend.idle == true` (near-zero data I/O **and** near-zero
read/write/metadata operations across the whole window — not merely quiet
off-hours; see `references/trend-analysis.md`), emit a single top-priority cost note.
This is the strongest cost signal because the entire file system is billed while
serving no workload.

> **💰 Cost optimization — file system appears idle.** Over the last `<lookback>`,
> `<file_system_id>` shows effectively no data I/O and no read/write/metadata
> activity — it does not appear to be in active use. The full cost of the file system
> (throughput, `<provisioned_gib>` GiB of storage, and backups) is being billed for
> no measured workload. Confirm with the owner whether it is still needed; if not, a
> final backup (snapshot) followed by deletion, or decommissioning, would eliminate
> the spend. This is an efficiency observation only — it does not lower the SLA
> Readiness rating.

When a file system is idle, still run the SLA dimensions normally (an idle file
system can still be Misconfigured, Single-AZ, etc.), but list this idle note first in
the Cost Optimization Opportunities section. Do **not** also emit the
over-provisioned-throughput note for an idle system — the idle note supersedes it.

---

## Dimension 5 — Backups

Read `backups`. Automatic backups are the recovery path for a Single-AZ
unrecoverable failure.

- `automatic_retention_days == 0` (status `NotConfigured`) → **⚠️ Warning**
- `1 <= automatic_retention_days < 7` → **⚠️ Warning** (short retention)
- `automatic_retention_days >= 7` → **✅ Pass**

**⚠️ Warning body (disabled):**
> **⚠️ Automatic backups are disabled.** `AutomaticBackupRetentionDays` is 0, so
> there is no daily point-in-time recovery point. For a Single-AZ file system this
> is the only recovery path from an unrecoverable failure.
>
> **Remediation:** enable automatic daily backups with a retention window that meets
> your RPO (commonly 7–35 days) and set a daily backup start time outside peak hours.

**⚠️ Warning body (short retention):**
> **⚠️ Short backup retention.** Automatic backups retain only
> `<automatic_retention_days>` day(s). Consider a longer window to meet your
> recovery objectives.

**✅ Pass body:**
> **✅ Automatic backups enabled.** Daily automatic backups retain
> `<automatic_retention_days>` days (start time `<daily_start_time>`).
> `<copy_tags_note>`

Where `<copy_tags_note>` is "Tags are copied to backups." when
`copy_tags_to_backups` is true, else omitted.

---

## Dimension 6 — Maintenance window

Read `maintenance.weekly_start_time` (format `d:HH:MM` UTC, where `d` is 1=Monday).
On Single-AZ, maintenance implies downtime, so the window placement matters more.

- `weekly_start_time` present → **✅ Pass** (note the window; if Single-AZ, add the
  peak-hours caution)
- `weekly_start_time` missing/unset → **⚠️ Warning**

**✅ Pass body:**
> **✅ Maintenance window configured.** Weekly maintenance is scheduled at
> `<weekly_start_time>` (UTC). `<single_az_caution>`

Where `<single_az_caution>` (only when Single-AZ): "Because this is a Single-AZ file
system, maintenance causes an outage while patching completes. AWS documents this as
*typically* under ~20 minutes, but it is a best-effort figure, not a guarantee —
real events have run longer (~25–30 minutes observed), so treat the whole window as
potentially unavailable and confirm it falls outside your business-critical hours."

**⚠️ Warning body:**
> **⚠️ No explicit maintenance window.** No weekly maintenance start time is set, so
> AWS may run maintenance at a default time that could coincide with peak usage
> (and, on Single-AZ, cause an outage then). Set an explicit low-traffic window.

---

## Dimension 7 — Alarms / observability

Read `alarms`. Without alarms, the operator will not detect the above risks before
they become outages.

- `free_storage_alarm == true` (or `fsx_alarm_count > 0` covering key metrics) →
  **✅ Pass**
- `fsx_alarm_count == 0` (status `NotConfigured`) → **⚠️ Warning**

**⚠️ Warning body:**
> **⚠️ No CloudWatch alarms on this file system.** There are no `AWS/FSx` alarms
> scoped to `<file_system_id>`, so low free storage, throughput saturation, or a
> Misconfigured state would go unnoticed until users are affected.
>
> **Remediation:** at minimum, alarm on `FreeStorageCapacity` (below your 20%
> threshold). Consider EventBridge + Lambda notifications on file-system health
> state changes.

**✅ Pass body:**
> **✅ Alarm coverage present.** `<fsx_alarm_count>` `AWS/FSx` alarm(s) are scoped to
> this file system`<free_storage_note>`.

Where `<free_storage_note>` is ", including a `FreeStorageCapacity` alarm" when
`free_storage_alarm` is true, else "".

---

## Administrative-action failures (cross-cutting)

If `administrative_actions[]` contains any entry with `status == FAILED`, add a
warning to whichever dimension it belongs to (storage/throughput update), using the
observed `type`:

> **⚠️ A recent `<action_type>` administrative action FAILED.** The last attempt to
> change `<storage/throughput>` did not complete. Review the file system's
> administrative-action history and the failure reason before relying on the new
> capacity; the file system may still be at the prior value.

If `administrative_actions[]` contains a `STORAGE_OPTIMIZATION` entry with
`status == IN_PROGRESS` (or `UPDATED_OPTIMIZING`), add an informational note — this is
the expected post-storage-increase phase and explains transient throughput pressure:

> **ℹ️ Storage optimization in progress.** A storage-capacity increase is still
> running its background optimization on `<file_system_id>`. During this phase disk
> throughput is consumed by the optimization and `FileServerDiskThroughputUtilization`
> can read near 100% — treat current throughput metrics as elevated by the migration,
> not steady-state demand, and re-check after it completes.

## Consistency rules

- A dimension is evaluated **only** when its parent data is present. Never emit both
  a Pass and a Warning for the same dimension.
- Cost notes (💰) attach only to Pass results on dimensions 3 and 4, and never
  change the rating.
- Findings must not contradict each other (e.g. do not call storage both critical
  and over-provisioned).
- Every finding cites the specific measured value it is based on.
