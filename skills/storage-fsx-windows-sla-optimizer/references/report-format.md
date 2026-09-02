# Report Format

The structure of the SLA Readiness report, the rating criteria, the dimensions
matrix, and the mandatory pre-render validation. Render the report verbatim,
substituting only placeholder values. This is the authoritative output (see the
Final Delivery Contract in `SKILL.md`).

## SLA Readiness rating

The rating summarizes the seven availability dimensions. **Cost notes (💰) never
affect the rating.**

| Rating | Criteria |
|---|---|
| **High** | No 🔴 Critical and no ⚠️ Warning findings across all seven dimensions, and no dimension is "Unable to verify". |
| **Medium** | No 🔴 Critical findings, but one or more ⚠️ Warning findings, **or** one or more dimensions "Unable to verify". |
| **Low** | One or more 🔴 Critical findings. |
| **Indeterminate** | Core configuration could not be retrieved (the `fsx describe-file-systems` call itself failed with AccessDenied/ToolingFailure), so the file system was not assessed. |

Rating precedence: any Critical → Low; else any Warning or Unable-to-verify →
Medium; else High. A file system may be **High** on SLA and still carry 💰 cost
notes — that is the intended "safe but wasteful" signal.

## Single-file-system report

````markdown
# FSx for Windows SLA Review — `<file_system_id>`

> ⚠️ This report is AI-generated. Independently verify findings before acting on
> them, especially before any capacity or deployment change.

**File system:** `<file_system_id>` (`<name_tag>`)
**Region / Account:** `<region>` / `<account_id>`
**Deployment:** `<deployment_type>` · **Storage:** `<provisioned_gib>` GiB `<storage_type>` · **Throughput:** `<provisioned_mbps>` MBps
**Active Directory:** `<AWS Managed|Self-managed>` · **Lifecycle:** `<lifecycle>`
**Usage profile:** `<usage_profile>` · **Throughput pattern:** `<throughput_pattern>` · **Storage trend:** `<storage_trend>`
**Review date:** `<YYYY-MM-DD>` · **Metric lookback:** `<lookback>`

## SLA Readiness: <High|Medium|Low|Indeterminate>

<one-sentence rationale naming the deciding finding(s), e.g. "Single-AZ deployment
and storage below the 20% free guidance cap this at Medium.">

## Dimensions

| # | Dimension | Result |
|---|---|---|
| 1 | Deployment type (Multi-AZ) | <emoji> <short state> |
| 2 | Active Directory health | <emoji> <short state> |
| 3 | Throughput capacity | <emoji> <short state> <💰 if cost note> |
| 4 | Storage headroom | <emoji> <short state> <💰 if cost note> |
| 5 | Backups | <emoji> <short state> |
| 6 | Maintenance window | <emoji> <short state> |
| 7 | Alarms / observability | <emoji> <short state> |

## Findings

<Each dimension's finding body from finding-logic.md, in dimension order. Include
the 💰 cost note appended to dimensions 3 and 4 where applicable. Omit no dimension;
use the "Unable to verify" template where data was missing.>

## Cost Optimization Opportunities

<If any 💰 cost notes fired, restate them here as a consolidated list, ordered by
magnitude. If the idle-file-system note fired (`trend.idle == true`), list it FIRST
(it supersedes the over-provisioned-throughput note — do not list both). Include the
supporting usage-pattern evidence where available (e.g. "idle nights/weekends,
weekend:weekday ratio <n>", "throughput provisioned at 4×+ measured peak demand").
If none, write: "No over-provisioning detected in the reviewed dimensions.">

## Recommended Actions

<Ordered list, highest-severity first: Critical, then Warning, then cost notes.
Each item is a concrete next step drawn from the finding remediation text.>

## References

- Availability and durability: Single-AZ and Multi-AZ file systems —
  https://docs.aws.amazon.com/fsx/latest/WindowsGuide/high-availability-multiAZ.html
- Why is my FSx for Windows File Server in a Misconfigured state? —
  https://repost.aws/knowledge-center/fsx-windows-misconfigured-state
- Validate your Active Directory configuration for Amazon FSx —
  https://repost.aws/knowledge-center/fsx-validate-ad-configuration
- Managing storage capacity (20% free guidance, dynamic scaling) —
  https://docs.aws.amazon.com/fsx/latest/WindowsGuide/managing-storage-configuration.html
- Monitoring with Amazon CloudWatch (AWS/FSx metrics) —
  https://docs.aws.amazon.com/fsx/latest/WindowsGuide/monitoring-cloudwatch.html
- Security Hub control FSx.5 (Multi-AZ) —
  https://docs.aws.amazon.com/securityhub/latest/userguide/fsx-controls.html
````

## Fleet report

See `references/fleet-orchestration.md` for the full fleet layout. Summary:

````markdown
# FSx for Windows SLA Fleet Review — <N> File Systems

> ⚠️ This report is AI-generated. Independently verify findings before acting.

## Summary
- File systems reviewed, accounts, region(s), date, metric lookback
- SLA Readiness distribution (High / Medium / Low / Indeterminate counts)
- Common gaps table (finding → count, worst first)
- Cost-optimization summary (count of file systems with 💰 notes)

## Dimensions Matrix
| File system | Deploy | AD | Thrpt | Storage | Backup | Maint | Alarms | Rating |
| `<id>` (`<name>`) | <e> | <e> | <e> | <e> | <e> | <e> | <e> | <R> |
<one row per file system; 💰 shown inline on Thrpt/Storage cells>

## File System Details
<full single-file-system report for Low-rated file systems (or all, for ≤10)>

## References
<same list as single report>
````

## Short-state vocabulary (matrix cells)

Keep matrix cells terse and consistent:

- Deployment: `✅ Multi-AZ`, `⚠️ Single-AZ`
- AD: `✅ Healthy`, `🔴 Misconfigured`, `🔴 Misconfig-Unavail`, `🔴 AD <stage>`,
  `⚠️ <lifecycle>`
- Throughput: `✅ Adequate`, `⚠️ Undersized@peak`, `✅ Adequate 💰`
- Storage: `✅ <pct>% free`, `⚠️ <pct>% free`, `🔴 <pct>% free`, `✅ <pct>% free 💰`,
  `⚠️ full ~<n>w` (healthy free % but projected to hit the floor in ≤4 weeks)
- Backups: `✅ <n>d`, `⚠️ Disabled`, `⚠️ <n>d`
- Maintenance: `✅ Set`, `⚠️ Unset`
- Alarms: `✅ <n>`, `⚠️ None`
- Idle (fleet only): append `💤` to the rating cell when `trend.idle == true`
- Unverified (any): `❓ <check>`

## Pre-render validation (mandatory)

Run all checks before delivering. If any fails, fix the report — do not deliver a
malformed report.

1. All seven dimensions appear in the Dimensions matrix and the Findings section.
2. The SLA Readiness rating matches the precedence rule (any Critical → Low; any
   Warning/Unverified → Medium; else High; core-config failure → Indeterminate).
3. No dimension shows both a Pass and a Warning/Critical.
4. Every finding cites the specific measured value it is based on (a percentage,
   MBps, retention days, count) — no unquantified claims.
5. 💰 cost notes on dimensions 3 and 4 appear **only** alongside a ✅ Pass; the
   cross-cutting idle-file-system 💰 note may appear regardless of other dimensions.
   No 💰 note (throughput, storage, or idle) ever lowers the SLA Readiness rating.
6. The deployment-type remediation never implies an in-place switch (it must say
   "create new + migrate").
7. Every 🔴/⚠️ finding has a corresponding entry in Recommended Actions.
8. Placeholders are all substituted — no literal `<...>` remains.
9. Byte values are converted to GiB and rates to MBps; no raw byte counts shown.
10. The AI-generated caveat line is present at the top.
11. For "Unable to verify" dimensions, the rating is capped at Medium (or
    Indeterminate) and the report says which permission/retry is needed.
12. Region and account are shown; the file-system ID is shown exactly as returned.
13. The References section is present with the canonical AWS URLs above.
14. The header shows the usage profile, throughput pattern, and storage trend; the
    metric lookback is stated.
15. The throughput finding is evaluated against **peak** demand (`required_peak_mbps`),
    and any peak figure is labeled approximate.
16. If `storage_trend == "growing"`, the storage finding includes the
    `weeks_to_floor` projection; a projection of ≤ 4 weeks is reflected as at least a
    ⚠️ Warning even when the current free % is healthy.
17. If `trend.idle == true`, the idle-file-system 💰 note is listed **first** in Cost
    Optimization Opportunities and the over-provisioned-throughput note is **not**
    also listed.
18. No week-over-week volume table is rendered (growth rate is an internal input to
    the projections only).
19. If `usage_profile == "insufficient-data"` (new file system), trend projections
    are omitted and the data gap is noted rather than extrapolated.
20. When lifecycle is `MISCONFIGURED` or `MISCONFIGURED_UNAVAILABLE` and the
    `failure_message` matches a known AD detail code, the targeted `<ad_root_cause_note>`
    is present (invalid-credentials / insufficient-permissions / computer-account-reuse);
    `MISCONFIGURED_UNAVAILABLE` is rendered as 🔴 Critical and states the data is
    currently inaccessible.
21. If the throughput 💰 cost note recommends a tier at or below 32 MBps, the
    `<sub32_caveat>` (no metrics below 32 MBps; validate customer-side) is present.
    A `STORAGE_OPTIMIZATION` action in progress is surfaced as the ℹ️ info note and
    the throughput finding acknowledges metrics may be elevated by the optimization.
