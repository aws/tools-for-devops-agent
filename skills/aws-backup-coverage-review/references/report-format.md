# Report Format

The report renders in this exact section order. Sections marked *conditional*
appear only when their trigger applies. Never reorder, rename, merge, or omit a
required section.

## Section order

1. `# AWS Backup Coverage Review — Account <account-id>` (required)
2. `## Scope` (required)
3. `## Coverage Rating` (required)
4. `## Executive Summary` (required)
5. `## Coverage Matrix` (required)
6. `## ⚠️ Permissions Notice` (*conditional* — any `AccessDenied`)
7. `## ⚠️ Tooling Availability Notice` (*conditional* — any `ToolingFailure`)
8. `## ℹ️ Inventory Completeness Notice` (*conditional* — any `NotEnumerated`)
9. `## Findings & Recommendations` (required)
10. `## Check Coverage Matrix` (required — exactly 21 rows)
11. `## Next Steps` (required)
12. `## References` (required)

## 1–2. Header and Scope

```markdown
# AWS Backup Coverage Review — Account <account-id>

## Scope

| Field | Value |
|---|---|
| Account | `<account-id>` (partition `<partition>`) |
| Regions reviewed | `<region>`, `<region>`, … (<N> of <M> enabled) |
| Review date | `<YYYY-MM-DD>` |
| Inventory strategy | `<config-fast-path \| direct-enumeration \| mixed>` |
| Eligible resources found | `<N>` across `<T>` resource types |
| Backup plans | `<N>` · Vaults `<N>` · Restore testing plans `<N>` |
```

When the user narrowed the scope, add a line stating what was narrowed and that
the coverage percentage applies to the narrowed scope only.

**Inventory strategy must always be disclosed.** It determines how trustworthy the
denominator is, and therefore how trustworthy the coverage percentage is.

## 3. Coverage Rating

```markdown
## Coverage Rating

**<High | Medium | Low | Indeterminate>** — <one sentence stating the driver>

Coverage: **~<pct>%** (`<covered>`/`<eligible>` resources protected with a current
recovery point — indicative, see the by-type table)

<if capped> Rating capped at Medium: <N> check(s) could not be verified. See the
Permissions Notice below. </if>
```

Rating emoji: `High → ✅` · `Medium → ⚠️` · `Low → ❌` · `Indeterminate → 🚫`.

## 4. Executive Summary

One row per dimension. Status is the worst finding in that dimension.

```markdown
## Executive Summary

| Dimension | Status | Findings |
|---|---|---|
| D1 Service enablement | ✅ Healthy | 0 critical, 0 warnings |
| D2 Coverage | ❌ Critical | 2 critical, 1 warning |
| D3 Plan quality | ⚠️ Warning | 0 critical, 3 warnings |
| D4 Vault posture | ⚠️ Warning | 0 critical, 2 warnings |
| D5 Coverage integrity | ❌ Critical | 1 critical, 1 warning |

**Headline:** <the single most consequential fact, one sentence.>
```

The headline is the most important line in the report. It states the concrete
recoverability gap, not a score. Good: *"14 EBS volumes in eu-west-1 have no
recovery point, and 3 DynamoDB tables sit in a plan that cannot protect them
because the resource type is not opted in."* Bad: *"Coverage is 72%."*

## 5. Coverage Matrix

One row per eligible resource, grouped by Region then resource type. Sort worst
state first: `OptInBlocked`, `SelectedNotProtected`, `Unprotected`, `Stale`,
`Protected`.

```markdown
## Coverage Matrix

### <region>

| Resource | Type | State | Last backup | Matched selection |
|---|---|---|---|---|
| `vol-0abc…` (`app-data`) | EBS | ❌ Unprotected | — | none |
| `tbl-orders` | DynamoDB | ❌ OptInBlocked | — | `daily-tagged` |
| `db-prod-01` | RDS | ⚠️ Stale | 9 days ago | `daily-tagged` |
| `fs-01f2…` | EFS | ✅ Protected | 6 hours ago | `daily-tagged` |
| `<type>` | <type> | 🚫 Unknown | — | — |

```

**Do not state a per-Region eligible count or percentage.** The Region sections list
resources; the account-wide by-type table is the only place counts are totalled.
Duplicating a total per Region has repeatedly produced figures that disagree with the
by-type table, and adds nothing an operator acts on.

### Precision discipline for counts

Resource-level findings are authoritative: a named ARN reported as `Unprotected` is a
verified fact. **Aggregate counts are inherently less reliable**, because they require
tallying many resources across many Regions, and a bulk type such as S3 or
CloudFormation can be miscounted without any individual finding being wrong.

Therefore:

- Present the coverage percentage as an **indicative** figure and say so once, in the
  Coverage Rating line: `Coverage: ~<pct>% (<protected>/<eligible> — indicative; see
  the by-type table)`.
- Never use a coverage total to justify a severity. Severities come from the checks,
  and check 2.2's bands are wide enough that a small counting error cannot change the
  band.
- For bulk types (S3, CloudFormation), state the count **and** its provenance — the
  API and Region it came from — so a reader can re-derive it.
- If a bulk type's count cannot be established confidently for a Region, mark that
  Region's entry for the type `Unconfirmed` rather than guessing a number. An
  acknowledged gap is more useful than a fabricated total.

State emoji: `Protected → ✅` · `Stale → ⚠️` · `SelectedNotProtected → ❌` ·
`Unprotected → ❌` · `OptInBlocked → ❌` · unreadable → `🚫 Unknown`.

When a Region has more than 50 eligible resources, render every non-`Protected`
row individually and collapse the `Protected` rows into a single summary line:
`✅ Protected: <N> resources (<type>: <count>, …)`. Never truncate a
non-`Protected` row — those are the point of the report.

Close the Coverage Matrix with the account-wide roll-up table of coverage by resource
type. That table is the only place counts are totalled.

## 6–8. Conditional notices

```markdown
## ⚠️ Permissions Notice

The following checks could not be verified. An unreadable resource type is not the
same as an unprotected one, so these did not lower the Coverage Rating — but the
rating is capped at Medium until they are resolved.

| Check | Missing action | Status |
|---|---|---|
| 4.1 Vault encryption key ownership | `kms:DescribeKey` | AccessDenied |
```

```markdown
## ⚠️ Tooling Availability Notice

The following checks could not reach the AWS API after 3 retries with exponential
backoff.

| Check | Status |
|---|---|
| 5.2 Recent backup job failures | ToolingFailure |
```

```markdown
## ℹ️ Inventory Completeness Notice

These resource types cannot be enumerated by this skill and are excluded from the
coverage denominator. Verify them manually in the AWS Backup console.

| Resource type | Reason |
|---|---|
| SAP HANA on Amazon EC2 | Requires SSM and backint agent discovery |
| VirtualMachine | Requires AWS Backup gateway and a registered hypervisor |
```

## 9. Findings & Recommendations

Ordered by severity, then by dimension. Use the finding text from
`references/coverage-logic.md` verbatim.

```markdown
## Findings & Recommendations

| # | Check | Finding | Severity | Recommendation |
|---|---|---|---|---|
| 1 | 1.1 | <verbatim finding text> | ❌ CRITICAL | <remediation from backup-best-practices.md> |
```

For each CRITICAL and HIGH finding, follow the table with a detail block naming
the specific affected resource ARNs (up to 20, then `… and <N> more`).

## 10. Check Coverage Matrix

**Exactly 21 rows, in ID order, always.** This is the anti-omission control.

```markdown
## Check Coverage Matrix

| ID | Check | Verdict | Observed | Threshold applied |
|---|---|---|---|---|
| 1.1 | Resource type opt-in per Region | ❌ | DynamoDB opted out in eu-west-1, 3 matched resources | Opted in where matched resources exist |
| 1.2 | Cross-account and global settings | ℹ️ | Cross-account backup disabled | Informational |
| 2.1 | Unprotected eligible resources | ❌ | 14 of 51 unprotected | 0 unprotected |
| 2.2 | Coverage percentage | ❌ | 72% | ≥ 95% |
| 2.3 | Selected but never protected | ✅ | 0 | 0 |
| 2.4 | Stale protection | ⚠️ | 1 resource, 9 days old | ≤ 2× schedule interval |
| 3.1 | Backup frequency at least daily | ✅ | all rules ≤ 24h | ≤ 24 hours |
| 3.2 | Retention at least 35 days | ⚠️ | plan "weekly" retains 14 days | ≥ 35 days |
| 3.3 | Cross-Region copy configured | ⚠️ | 0 of 2 plans | ≥ 1 rule per plan |
| 3.4 | Cross-account copy configured | ⚠️ | 0 of 2 plans | ≥ 1 rule per plan |
| 3.5 | Plan targets a locked vault | ⚠️ | vault "Default" unlocked | Vault Lock enabled |
| 3.6 | Selection breadth | ⚠️ | "static-list" is ARN-only | Tag or condition based |
| 3.7 | Continuous backup / PITR | ⚠️ | disabled on 3 DynamoDB tables | Enabled where supported |
| 4.1 | Vault encryption key ownership | ℹ️ | AWS-managed key | Customer-managed key |
| 4.2 | Vault Lock | ⚠️ | not locked | Locked |
| 4.3 | Vault access policy blocks deletion | ⚠️ | no access policy | Explicit Deny on DeleteRecoveryPoint |
| 4.4 | Logically air-gapped vault | ⚠️ | none in account | ≥ 1 |
| 4.5 | Vault notifications | ⚠️ | not configured | BACKUP_JOB_FAILED subscribed |
| 5.1 | Restore testing coverage | ⚠️ | none configured | ≥ 1 plan covering protected types |
| 5.2 | Recent backup job failures | ❌ | 2 resources failing, 0 successes | 0 |
| 5.3 | Recovery point encryption | ✅ | 0 unencrypted | 0 |
```

## 11. Next Steps

Bucketed by SLA, derived from severity. Never invent items not backed by a finding.

```markdown
## Next Steps

**Immediate (CRITICAL — 24–48 hours)**
1. <action> — closes finding #<n>

**This week (HIGH — 7 days)**
1. <action> — closes finding #<n>

**This month (MEDIUM — 30 days)**
1. <action> — closes finding #<n>

**When convenient (LOW)**
1. <action> — closes finding #<n>
```

## 12. References

Emit only URLs present in the canonical list in
`references/backup-best-practices.md`. **Never construct, recall, or infer an AWS
documentation URL from any other source.**

## Pre-render validation

Run all 18 checks before delivering. **Do NOT output validation results to the
user.** If any check fails, fix the report and re-validate.

**Structure**
1. All 12 required sections present, in the specified order.
2. The Check Coverage Matrix has exactly 21 rows, IDs `1.1`–`5.3`, in order, with
   no duplicates.
3. Every conditional notice that should appear does, and none that should not.
4. The Coverage Matrix has a row (or a collapsed-summary equivalent) for every
   eligible resource, and an individual row for every non-`Protected` resource.

**Severity coherence**
5. The Coverage Rating matches the deterministic roll-up in
   `references/coverage-logic.md`, including the `AccessDenied` cap.
6. Every Executive Summary dimension status equals the worst finding in that
   dimension.
7. Every CRITICAL and HIGH finding has a corresponding Next Steps entry, and every
   Next Steps entry cites a finding number.

**Substitution**
8. No `<placeholder>` text remains anywhere in the output.
9. Every count, percentage, and ARN traces to collected data — no invented values.

**Internal consistency**
10. `AccessDenied` and `ToolingFailure` checks are rendered with the
    "Unable to verify" template, are excluded from the coverage denominator, and
    are not counted as gaps.

**Single source of truth for every count**

Aggregate counts are computed **once**, in the account-wide by-resource-type table,
by counting Coverage Matrix rows. Every other number in the report is read from that
table, never recomputed. Concretely:

- Per-Region sections list resources and state **no totals at all** — no eligible
  count, no protected count, no percentage. Every duplicated total is another chance
  to disagree with the by-type table, and operators act on the resource rows, not on
  a per-Region subtotal.
- The Coverage Rating percentage, the Executive Summary headline, and check 2.2 all
  quote the by-type table's total verbatim. If you find yourself computing a
  percentage twice, you have already introduced the defect.
- Build the by-type table by counting rows per type across all Region tables,
  including collapsed summary rows by their stated count. Then verify the type
  column sums to the stated total before writing anything else.
- **Orphaned recovery points are in neither column.** A resource in state
  `OrphanedRecoveryPoint` is excluded from `eligible`, from `protected`, and from
  `Stale` — the underlying resource does not exist, so it cannot be covered or
  uncovered. It appears in the Coverage Matrix with its own state and in the findings,
  and nowhere in the arithmetic. Never fold an orphan into the protected count.
- When a resource type is global in its listing API but regional in protection (S3),
  the sum of its per-Region rows must equal the total number of that resource in the
  account. If it does not, a bucket has been assigned to the wrong Region.

**Arithmetic reconciliation — do this explicitly, with the numbers written down**

11. Compute the protected count **once**, then reuse that single value everywhere.
    Before rendering, verify all three of these agree on it: the Coverage Rating
    line, the Executive Summary headline, and the account-wide by-type table total.
    If any two disagree, the report is wrong — recompute from the Coverage Matrix
    rows, which are the source of truth, and correct every occurrence.
12. The by-type table's `Eligible` column sums to its stated total, and the
    `Protected` column sums to the protected count used elsewhere. Check the addition
    explicitly rather than assuming it.
13. Every resource type in the by-type table has `eligible == ` the number of rows
    of that type across all Region tables, counting collapsed summary rows by their
    stated count. A type whose count differs between the Region tables and the
    by-type table is a defect, not a rounding difference.
14. State the coverage percentage to the same precision everywhere, computed as
    `round(100 * protected / eligible)`. Never show two different percentages for
    the same ratio.

**Findings discipline**

15. No duplicate findings. Two rows describing the same underlying condition must
    be merged into one, even when they map to different check IDs — cite both IDs
    in the single row rather than emitting it twice.
16. Every severity is exactly one of CRITICAL, HIGH, MEDIUM, LOW, INFO, taken from
    the check's definition in `references/coverage-logic.md`. **Never invent a
    severity, never blend two, and never escalate a check's severity because it
    relates to another finding.** A check's severity is a property of the check.
    Contextual importance belongs in the finding text, not the severity column.
17. The verdict emoji in the Check Coverage Matrix matches the severity in the
    Findings table for the same check ID, per the emoji map.

**Delivery**
18. The report is complete and is returned verbatim in the final response per the
    Final Delivery Contract, not summarized.
