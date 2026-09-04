# Coverage Logic

All 23 checks, their thresholds, verdict rules, and finding templates.

**MANDATORY COVERAGE RULE.** The report must evaluate and account for every check
in this document. No check may be silently omitted. If a check cannot be
evaluated, render it with status `AccessDenied`, `ToolingFailure`, or
`NotEnumerated` and the "Unable to verify" template — never drop the row.

**ID FIDELITY.** Use these exact IDs with these exact meanings. Never renumber,
split, merge, or invent checks. Before finishing, count the rows in the Check
Coverage Matrix: if the count is not exactly 23, the report is incomplete.

**Use the finding templates verbatim.** Substitute only the `<placeholder>`
values.

## Severity definitions

| Severity | Definition | SLA |
|---|---|---|
| CRITICAL | Data is unrecoverable or believed protected when it is not | Fix within 24–48 hours |
| HIGH | Recovery is possible but materially degraded or at risk | Fix within 1 week |
| MEDIUM | Notable hardening or durability gap | Plan within 30 days |
| LOW | Minor optimization | Address when convenient |
| INFO | Observation, no action required | N/A |

## Emoji map

`CRITICAL → ❌` · `HIGH → ⚠️` · `MEDIUM → ⚠️` · `LOW → ℹ️` · `INFO → ℹ️` ·
`pass → ✅` · `unverifiable → 🚫`

## D1 · Service enablement

### 1.1 Resource type opt-in per Region

- **Source:** `DescribeRegionSettings.ResourceTypeOptInPreference`, cross-referenced
  with the eligible inventory and selection matches.
- **Verdict:** Fail when a resource type is opted out (`false`) in a Region where
  eligible resources of that type exist **and** at least one selection would match
  them. Pass when every type with matched resources is opted in. `INFO` when a
  type is opted out but no resources of that type exist in the Region.
- **Severity:** CRITICAL when matched resources exist; INFO otherwise.
- **Sourcing rule — quote the boolean, never infer it.** Opt-in state comes only from
  `DescribeRegionSettings.ResourceTypeOptInPreference` for that specific Region, read
  as the literal boolean. **Never infer opt-in from the absence of a backup selection,
  from a plan's `AdvancedBackupSettings`, or from the fact that resources are
  unprotected.** Those are independent facts: a type can be opted in and still have no
  selection, and opted out while a selection exists.
  For every Region and type you report on, state the observed value in the form
  `<type> in <region>: ResourceTypeOptInPreference.<type> = <true|false>`. A type
  absent from the map defaults to opted in; only an explicit `false` is opted out.
  Getting the direction wrong sends the operator to change the wrong Region, so if you
  cannot quote the boolean for a Region, mark the check `Unconfirmed` for that Region
  rather than asserting a direction.
- **On a re-run, never "correct" a prior value without the boolean in hand.** If this
  review contradicts an earlier one, cite the `DescribeRegionSettings` response that
  justifies the change. An unevidenced correction is worse than the original, because
  it carries false confidence.
- **Finding:** `<N> <type> resource(s) in <region> are matched by backup selection "<selection>" but the <type> resource type is not opted in for that Region. AWS Backup will never create recovery points for them. The plan and selection appear correctly configured in the console, which makes this gap easy to miss.`

### 1.2 Cross-account and global settings

- **Source:** `DescribeGlobalSettings.isCrossAccountBackupEnabled`.
- **Verdict:** INFO in all cases — this is context, not a defect, for a
  single-account review. Report the value.
- **Severity:** INFO.
- **Finding:** `Cross-account backup monitoring is <enabled|disabled> for this account. This review covers account <account-id> only; enable cross-account monitoring and re-run from the delegated administrator account for an organization-wide view.`

## D2 · Coverage

### 2.1 Unprotected eligible resources

- **Source:** the resolved `coverage_state` for every eligible resource.
- **Verdict:** Fail when any resource is in state `Unprotected`.
- **Severity:** CRITICAL.
- **Finding:** `<N> of <total> backup-eligible resource(s) have no AWS Backup recovery point and are matched by no backup selection. Unrecoverable through AWS Backup today. Affected: <type>: <count> in <region> (see the Coverage Matrix for ARNs).`

### 2.2 Coverage percentage by type and Region

- **Source:** counts of `Protected` + `Stale` over all eligible resources,
  excluding `NotEnumerated` types and types with status `AccessDenied`.
- **Verdict:** Pass at ≥ 95%. HIGH between 80% and 95%. CRITICAL below 80%.
- **Severity:** per the bands above.
- **Finding:** `Account-wide AWS Backup coverage is <pct>% (<covered>/<eligible> resources). Lowest coverage: <type> in <region> at <pct>%. Denominator established by <inventory-strategy>.`
- **Note:** the denominator must exclude `NotEnumerated` and `AccessDenied` types.
  State the exclusions beneath the number. Never round up to 100%.

### 2.3 Selected but never protected

- **Source:** `coverage_state == SelectedNotProtected`.
- **Verdict:** Fail when any resource is in this state.
- **Severity:** CRITICAL.
- **Finding:** `<N> resource(s) are matched by a backup selection but have zero recovery points. Membership in a backup plan is not protection. Likely causes: the plan's first scheduled window has not yet elapsed, the AWS Backup service role lacks permission for the resource type, or every backup job has failed. Cross-reference check 5.2.`

### 2.4 Stale protection

- **Source:** `LastBackupTime` versus the schedule of the plan whose selection
  matched the resource.
- **Verdict:** Compute the expected interval from the rule's `cron`/`rate`
  expression. Fail when `now − LastBackupTime > 2 × expected_interval`. When the
  schedule cannot be parsed, fall back to a 48-hour tolerance and say so.
- **Severity:** HIGH.
- **Finding:** `<N> resource(s) have recovery points older than their plan allows. <resource-arn> was last backed up <age> ago against a <interval> schedule. The resource appears protected in the console but the most recent recovery point may predate the current data.`

## D3 · Plan quality

Evaluate 3.1 through 3.7 **per backup plan rule**, then roll up to the plan.
Thresholds match the AWS Backup Audit Manager control defaults so results are
comparable with Audit Manager output.

### 3.1 Backup frequency at least daily

- **Source:** `rules[].schedule`.
- **Verdict:** Fail when the interval between runs exceeds 24 hours. Pass when
  `EnableContinuousBackup` is `true` regardless of schedule.
- **Severity:** HIGH.
- **Finding:** `Plan "<plan>" rule "<rule>" runs every <interval>, which exceeds the recommended maximum of 24 hours. Recovery point objective for resources in this plan is at least <interval>.`

### 3.2 Retention at least 35 days

- **Source:** `rules[].Lifecycle.DeleteAfterDays`.
- **Verdict:** Fail below 35 days. Fail with severity CRITICAL when
  `DeleteAfterDays` is unset **and** no `MoveToColdStorageAfterDays` is set,
  because recovery points then never expire and cost grows without bound while
  retention is undefined in policy.
- **Severity:** HIGH below 35 days; MEDIUM when unset.
- **Finding:** `Plan "<plan>" rule "<rule>" retains recovery points for <days> days, below the recommended minimum of 35. Recovery from an incident discovered more than <days> days after the fact is not possible.`

### 3.3 Cross-Region copy configured

- **Source:** `rules[].CopyActions[]` with a destination vault ARN in a different
  Region.
- **Verdict:** Fail when no rule in the plan has a cross-Region copy action.
- **Severity:** MEDIUM.
- **Finding:** `Plan "<plan>" has no cross-Region copy action. Recovery points exist only in <region>, so a Region-wide impairment would take the backups with the primary data.`

### 3.4 Cross-account copy configured

- **Source:** `rules[].CopyActions[]` with a destination vault ARN in a different
  account.
- **Verdict:** Fail when no rule in the plan has a cross-account copy action.
- **Severity:** MEDIUM.
- **Finding:** `Plan "<plan>" has no cross-account copy action. Recovery points share the blast radius of account <account-id>; a credential compromise or account-level deletion event could remove both the data and its backups.`

### 3.5 Plan targets a locked vault

- **Source:** `rules[].TargetBackupVaultName` joined to `vaults[].locked`.
- **Verdict:** Fail when the target vault has `Locked == false`.
- **Severity:** MEDIUM.
- **Finding:** `Plan "<plan>" rule "<rule>" writes to vault "<vault>", which has no Vault Lock. Recovery points in that vault can be deleted manually before their retention period expires.`

### 3.6 Selection breadth

- **Source:** `selections[].Resources`, `ListOfTags`, `Conditions`.
- **Verdict:** Fail when a selection enumerates only literal resource ARNs — no
  wildcards, no `ListOfTags`, no `Conditions`. Such a selection cannot match
  resources created after it was written.
- **Severity:** HIGH.
- **Finding:** `Selection "<selection>" in plan "<plan>" lists <N> literal resource ARN(s) with no tag or condition rule. Resources created after this selection was written will not be protected until someone edits it by hand. <M> eligible <type> resource(s) in <region> are already outside it. A tag-based selection protects new resources automatically.`
- **Dangling ARN sub-check.** For each literal ARN in the selection, check whether
  it appears in the eligible inventory. If it does not, the selection points at a
  deleted or terminated resource. Raise the severity to CRITICAL and append:
  `Selection "<selection>" references <arn>, which no longer exists in this account. The plan cannot protect anything through this entry, and the resources that replaced it are not covered.`
  A dangling ARN produces no coverage row of its own, because the resource is not
  in the inventory — so this sub-check is the only place it is visible. Cross-check
  5.2, which will usually show failing jobs for the same ARN.
- **Rationale:** this is the highest-value check in the skill and has no AWS Backup
  Audit Manager equivalent. ARN-only selections are the most common cause of
  coverage silently decaying over time.

### 3.7 Continuous backup / point-in-time recovery

- **Source:** `rules[].EnableContinuousBackup`, plus
  `dynamodb:DescribeContinuousBackups.PointInTimeRecoveryStatus` for DynamoDB
  tables.
- **Verdict:** Evaluate only for resource types that support continuous backup
  (S3, RDS, Aurora, DynamoDB, SAP HANA). Fail when a plan protecting those types
  has `EnableContinuousBackup: false` and no PITR is enabled at the service level.
  Render as `INFO` for types that do not support it.
- **Severity:** MEDIUM.
- **Finding:** `Plan "<plan>" protects <N> <type> resource(s) that support continuous backup, but continuous backup is disabled. Recovery is limited to discrete snapshot points; point-in-time recovery within the retention window is not available.`

## D4 · Vault posture

### 4.1 Vault encryption key ownership

- **Source:** `DescribeBackupVault.EncryptionKeyArn` → `kms:DescribeKey.KeyManager`.
- **Verdict:** Fail when `KeyManager == AWS` (AWS-managed key). Pass on `CUSTOMER`.
- **Severity:** LOW.
- **Finding:** `Vault "<vault>" in <region> uses the AWS-managed key <key-arn>. A customer-managed key allows key policy control, independent rotation, and the ability to revoke access to recovery points.`

### 4.2 Vault Lock

- **Source:** `DescribeBackupVault.Locked`, `LockDate`, `MinRetentionDays`,
  `MaxRetentionDays`.
- **Verdict:** Fail when `Locked == false`. When locked, report the mode —
  compliance mode when `LockDate` has passed and the lock is immutable,
  governance mode otherwise — and pass.
- **Severity:** MEDIUM.
- **Finding:** `Vault "<vault>" in <region> has no Vault Lock. Recovery points can be deleted by any principal with backup:DeleteRecoveryPoint, including before their retention period expires. Governance mode blocks deletion except by named roles; compliance mode blocks it absolutely, including by the account root.`

### 4.3 Vault access policy prevents manual deletion

- **Source:** `GetBackupVaultAccessPolicy`.
- **Verdict:** Pass when the policy contains an explicit `Deny` on
  `backup:DeleteRecoveryPoint` (and ideally `backup:UpdateRecoveryPointLifecycle`).
  Fail on `NotConfigured` or on a policy with no such `Deny`.
- **Severity:** MEDIUM. Downgrade to LOW when 4.2 passes in compliance mode,
  because the lock already provides the guarantee.
- **Finding:** `Vault "<vault>" in <region> has <no access policy | an access policy with no explicit Deny on backup:DeleteRecoveryPoint>. Manual deletion of recovery points is not blocked at the resource-policy layer.`

### 4.4 Logically air-gapped vault

- **Source:** `DescribeBackupVault.VaultType` across all vaults in the account.
- **Verdict:** INFO when at least one vault has
  `VaultType == LOGICALLY_AIR_GAPPED_BACKUP_VAULT`. MEDIUM when none does and the
  account has any resource in state `Protected`.
- **Severity:** MEDIUM when absent; INFO when present.
- **Finding:** `No logically air-gapped vault exists in this account. Air-gapped vaults are immutable by construction and shareable across accounts without the source account being able to delete their contents, which limits the blast radius of a compromise of account <account-id>.`

### 4.5 Vault notifications

- **Source:** `GetBackupVaultNotifications`.
- **Verdict:** Fail on `NotConfigured`, or when configured but the events do not
  include `BACKUP_JOB_FAILED`.
- **Severity:** MEDIUM.
- **Finding:** `Vault "<vault>" in <region> has <no SNS notifications | notifications that do not include BACKUP_JOB_FAILED>. Backup failures for resources in this vault are silent, so a resource can stop being protected without anyone being told.`

## D5 · Coverage integrity

These checks exist because a resource can satisfy D2 and D3 and still not be
recoverable. Nominal coverage without verified recoverability overstates the
account's true position.

Checks 5.1 to 5.3 ask whether protection is *real*: has a restore ever been proven,
are jobs succeeding, are recovery points encrypted. Checks 5.4 and 5.5 ask whether
anyone would *notice it changing* — coverage is a point-in-time state, and without
scheduled reporting or evaluated controls a decline surfaces only the next time
someone runs a review by hand.

### 5.1 Restore testing plan exists and covers protected types

- **Source:** `ListRestoreTestingPlans`, `ListRestoreTestingSelections`.
- **Verdict:** Fail on zero restore testing plans. Fail with severity MEDIUM when
  plans exist but the union of their selections omits a resource type that has
  `Protected` resources. This check verifies **existence and coverage only** — it
  does not read restore test results.
- **Severity:** HIGH when none exists; MEDIUM when coverage is partial.
- **Finding:** `<No restore testing plan is configured | Restore testing plans cover <covered-types> but not <uncovered-types>>. Recovery points are being created but never proven restorable, so the first real restore is the first test.`

### 5.2 Recent backup job failures

- **Source:** `ListBackupJobs` for the last 7 days, grouped by resource ARN.
- **Verdict:** Fail when any resource has a `FAILED` or `ABORTED` job and no
  `COMPLETED` job in the window. MEDIUM when a resource has both, indicating
  intermittent failure. This is a coverage-integrity signal only — **do not
  diagnose the failure cause**; that is out of scope for this skill.
- **Severity:** CRITICAL when no successful job in the window; MEDIUM when
  intermittent.
- **Finding:** `<N> resource(s) had backup jobs fail in the last 7 days with no successful job in that window: <resource-arn> (<failed-count> failed). These resources appear in a backup plan and may appear protected from an older recovery point, but current data is not being captured. Backup or restore job failure triage is outside the scope of this review.`

### 5.3 Recovery point encryption

- **Source:** `ListRecoveryPointsByBackupVault.IsEncrypted` per vault.
- **Verdict:** Fail when any recovery point has `IsEncrypted == false`.
- **Severity:** HIGH.
- **Finding:** `<N> recovery point(s) in vault "<vault>" (<region>) are not encrypted. Encryption for some resource types is inherited from the source resource, so an unencrypted source produces an unencrypted recovery point regardless of the vault's own key.`

### 5.4 Audit Manager report plan scheduled per Region

- **Source:** `ListReportPlans`, per Region, cross-referenced with the Regions that
  contain backup plans or protected resources.
- **Verdict:** Fail when a Region contains protected resources or backup plans but
  has no report plan. Report plans are **per Region**, so a plan in one Region gives
  no visibility into another — evaluate each Region independently rather than
  treating one report plan as account-wide coverage. Pass when every Region with
  backup activity has at least one report plan.
- **Severity:** MEDIUM.
- **Finding:** `<N> Region(s) with backup activity have no AWS Backup Audit Manager report plan: <regions>. Backup, copy, and restore job activity in those Regions is not being reported on a schedule, so a decline in coverage or a rising job failure rate would not surface in any recurring artefact. Report plans are per Region — the <M> existing plan(s) in <regions-with-plans> do not cover the others.`

### 5.5 Audit Manager framework configured

- **Source:** `ListFrameworks`, per Region.
- **Verdict:** Fail on zero frameworks in a Region that has protected resources.
  When frameworks exist, report how many controls each carries. A report plan
  without a framework reports **job activity only** — it does not evaluate control
  compliance, so the two are complementary rather than alternatives.
- **Severity:** MEDIUM.
- **Finding:** `<N> Region(s) with protected resources have no AWS Backup Audit Manager framework: <regions>. Job reports alone show what ran; a framework evaluates whether coverage, retention, and vault configuration meet defined controls, and records the result continuously rather than only when this review is run.`
- **Note:** Audit Manager controls depend on AWS Config resource recording. If the
  inventory strategy for a Region was `direct-enumeration` because no recorder was
  active, say so in the finding — enabling a framework there requires enabling AWS
  Config first, and that dependency belongs in the recommendation.

## Unable-to-verify template

Use verbatim for any check with status `AccessDenied` or `ToolingFailure`:

`Unable to verify — <access denied | tooling failure>. Required action: <iam:Action>. This check did not affect the Coverage Rating, but the rating is capped at Medium while it is unresolved.`

For `NotEnumerated`:

`Unable to enumerate — <type> resources cannot be discovered by this skill. Excluded from the coverage denominator. Verify manually in the AWS Backup console.`

## Coverage Rating roll-up

Deterministic. Never judgment-based.

1. If the eligible inventory could not be established in any Region →
   `Indeterminate`. Stop.
2. If any check returned CRITICAL, or account-wide coverage < 80% → `Low`.
3. Else if account-wide coverage < 95%, or any check returned HIGH → `Medium`.
4. Else → `High`.
5. **Cap:** if any check has status `AccessDenied` or `ToolingFailure`, and the
   result of steps 2–4 is `High`, downgrade to `Medium` and state why.

Per-dimension status in the executive summary is the **worst** finding in that
dimension: any ❌ → Critical; else any ⚠️ → Warning; else Healthy.
