# AWS Backup Best Practices and Remediation

Reasoning behind the thresholds in `references/coverage-logic.md`, the remediation
text to use in the Findings table, and the canonical documentation URLs.

## Why these thresholds

### Daily frequency and 35-day retention (checks 3.1, 3.2)

Both numbers are the AWS Backup Audit Manager control defaults, chosen so this
skill's output is directly comparable with an Audit Manager framework. A daily
schedule bounds the recovery point objective at 24 hours. Thirty-five days exceeds
a calendar month, so an incident discovered during month-end review is still
recoverable — the common failure is a 7- or 14-day retention that expires before
anyone notices data was corrupted.

Raise either threshold when the workload warrants it; the skill reports against
the default and the report states the threshold applied, so a stricter local
standard is easy to argue from.

### Why selection breadth matters more than it looks (check 3.6)

A backup selection that lists literal resource ARNs is a snapshot of the
infrastructure at the moment someone wrote it. Every resource created afterwards
is unprotected until a human edits the selection. Coverage therefore decays
silently and continuously, and the decay is invisible in the console because the
plan and selection both look healthy.

Tag-based selections invert the default: a new resource is protected as soon as it
carries the tag, and the gap becomes a tagging problem, which is far easier to
detect and enforce (through tag policies, IaC, or AWS Config) than a hand-edited
ARN list. This check has no AWS Backup Audit Manager equivalent and is usually the
most actionable finding the review produces.

### Why opt-in is checked first (check 1.1)

Service opt-in is per account **and** per Region, and a resource type that is
opted out cannot be protected no matter how correct the plan and selection are.
The console renders the plan and selection normally, so this misconfiguration
survives review by eye. It is the single most common cause of a plan that has
"worked" for months while protecting nothing of a given type.

### Why membership is not protection (checks 2.3, 5.2)

`ListBackupSelections` describes intent. `ListProtectedResources` describes
outcome. They diverge whenever the AWS Backup service role lacks permission for a
resource type, the first scheduled window has not elapsed, or jobs are failing.
Reporting intent as outcome is the most damaging error this skill could make,
which is why check 2.3 exists as a distinct CRITICAL finding rather than being
folded into check 2.1.

### Why restore testing is in scope (check 5.1)

A recovery point that has never been restored is an untested assumption. Restore
testing converts backup from a hope into a measured capability. This skill checks
only that restore testing plans **exist and cover the protected resource types** —
reading and interpreting restore test results is deliberately out of scope.

### Why permission gaps never lower the score

An unreadable resource type is not an unprotected one. Scoring a blind spot as a
gap produces false alarms that train operators to distrust the report; scoring it
as a pass produces false confidence, which is worse. The skill does neither: it
reports the blind spot explicitly, excludes it from the denominator, and caps the
rating at Medium so the number can never look better than the evidence supports.

## Remediation text

Use these in the Recommendation column, matched by check ID.

| Check | Recommendation |
|---|---|
| 1.1 | Enable the resource type in AWS Backup → Settings → Service opt-in for `<region>`, then confirm with `backup:DescribeRegionSettings`. Opt-in is per account and per Region and applies only to backups created after it is enabled. |
| 1.2 | For an organization-wide view, enable cross-account backup in the management account and re-run this review from the delegated administrator account. |
| 2.1 | Add the unprotected resources to a backup plan, preferably by tagging them and using a tag-based selection rather than adding ARNs. |
| 2.2 | Close the gaps from findings above, then re-run. Where the denominator was established by direct enumeration, consider enabling AWS Config recording so coverage can be tracked continuously. |
| 2.3 | Verify the AWS Backup service role has the managed policy for the resource type, confirm the plan's first window has elapsed, then check backup job history for the affected resources. |
| 2.4 | Investigate why the schedule is not producing recovery points; check the plan's `ScheduleExpression`, its start window, and whether jobs are being throttled by concurrent job limits. |
| 3.1 | Change the rule's schedule to run at least daily, or enable continuous backup for resource types that support it. |
| 3.2 | Raise `Lifecycle.DeleteAfterDays` to 35 or more. Where retention is unset, set it explicitly so retention is a policy decision rather than an accident. |
| 3.3 | Add a `CopyAction` targeting a vault in a second Region so recovery points survive a Region-wide impairment. |
| 3.4 | Add a `CopyAction` targeting a vault in a separate backup account so recovery points survive compromise or deletion of this account. |
| 3.5 | Apply Vault Lock to the target vault. Use governance mode first to validate the retention window, then compliance mode once the window is proven. |
| 3.6 | Replace the ARN list with a tag-based selection (`ListOfTags`) or a condition on `aws:ResourceTag`, so newly created resources are protected without a manual edit. |
| 3.7 | Enable continuous backup on the plan rule for supported resource types, and enable point-in-time recovery on DynamoDB tables at the service level. |
| 4.1 | Recreate the vault with a customer-managed KMS key. A vault's encryption key cannot be changed after creation, so this requires a new vault and a plan update. |
| 4.2 | Apply Vault Lock with a retention window that matches policy. Compliance mode is irreversible after the cooling-off period — validate in governance mode first. |
| 4.3 | Attach a vault access policy with an explicit `Deny` on `backup:DeleteRecoveryPoint` and `backup:UpdateRecoveryPointLifecycle`, scoped to all principals except a named break-glass role. |
| 4.4 | Create a logically air-gapped vault and add a `CopyAction` to it. Its contents are immutable and cannot be deleted by this account. |
| 4.5 | Configure vault notifications to an SNS topic subscribed to `BACKUP_JOB_FAILED`, and route it somewhere a human reads. |
| 5.1 | Create a restore testing plan covering every protected resource type, with a validation window long enough for the restore to complete. |
| 5.2 | Review the failed jobs' status messages for the affected resources. Backup job failure triage is outside this skill's scope — investigate separately. |
| 5.3 | Encrypt the source resources. For several resource types the recovery point inherits encryption from the source, so an unencrypted source cannot produce an encrypted recovery point. |

## Common misconceptions

| Belief | Reality |
|---|---|
| "The resource is in a backup plan, so it is protected." | Only a recovery point proves protection. Opt-in, service role permissions, and job failures all break the chain. |
| "Coverage is 100% because AWS Backup lists no unprotected resources." | `ListProtectedResources` returns what *is* protected. It cannot tell you what is missing — that requires an independent inventory. |
| "Cross-Region copy is a backup." | It is a second copy of the same recovery point. It protects against Region loss, not against a logical error propagated into the backup. |
| "Vault Lock in governance mode prevents deletion." | Governance mode blocks deletion except by principals with `backup:DeleteRecoveryPoint` and the lock-management permissions. Only compliance mode is absolute. |
| "Snapshots I take myself count as AWS Backup coverage." | Manual and service-native automated snapshots are not AWS Backup recovery points, are not governed by the plan's lifecycle, and do not appear in `ListProtectedResources`. |
| "AWS Backup Audit Manager already tells me this." | Its coverage control depends on AWS Config resource recording, a framework, and a report plan that has run. Without all three there is no coverage answer. |

## IAM

The review is read-only. The baseline `AIDevOpsAgentAccessPolicy` covers most
control-plane reads; the AWS-managed `AWSBackupAuditAccess` policy is the closest
managed equivalent for the AWS Backup portion. See the skill README for the exact
action list and `cloudformation/devops-agent-skill-policies.yaml` for the
deployable policy.

## Canonical AWS documentation URLs

Emit only URLs from this list. **Never construct, recall, or infer an AWS
documentation URL from any other source.**

**Core**
- What is AWS Backup — https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html
- Feature availability by Region and resource — https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html

**Plans, selections, and opt-in**
- Assigning resources to a backup plan, and service opt-in — https://docs.aws.amazon.com/aws-backup/latest/devguide/assigning-resources.html
- Creating a backup plan — https://docs.aws.amazon.com/aws-backup/latest/devguide/creating-a-backup-plan.html
- Point-in-time recovery and continuous backup — https://docs.aws.amazon.com/aws-backup/latest/devguide/point-in-time-recovery.html

**Copies and resilience**
- Cross-Region backup — https://docs.aws.amazon.com/aws-backup/latest/devguide/cross-region-backup.html
- Creating cross-account backup copies — https://docs.aws.amazon.com/aws-backup/latest/devguide/create-cross-account-backup.html
- Managing cross-account backup — https://docs.aws.amazon.com/aws-backup/latest/devguide/manage-cross-account.html

**Vault protection**
- AWS Backup Vault Lock — https://docs.aws.amazon.com/aws-backup/latest/devguide/vault-lock.html
- Logically air-gapped vaults — https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html
- Encryption of backups — https://docs.aws.amazon.com/aws-backup/latest/devguide/encryption.html
- Deleting backups — https://docs.aws.amazon.com/aws-backup/latest/devguide/deleting-backups.html
- Backup notifications — https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-notifications.html

**Verification and governance**
- Restore testing — https://docs.aws.amazon.com/aws-backup/latest/devguide/restore-testing.html
- AWS Backup Audit Manager — https://docs.aws.amazon.com/aws-backup/latest/devguide/aws-backup-audit-manager.html
- Choosing your controls — https://docs.aws.amazon.com/aws-backup/latest/devguide/choosing-controls.html
- Controls and remediation — https://docs.aws.amazon.com/aws-backup/latest/devguide/controls-and-remediation.html
- Working with audit reports — https://docs.aws.amazon.com/aws-backup/latest/devguide/working-with-audit-reports.html

**IAM and API reference**
- AWS managed policies for AWS Backup — https://docs.aws.amazon.com/aws-backup/latest/devguide/security-iam-awsmanpol.html
- AWSBackupAuditAccess managed policy — https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AWSBackupAuditAccess.html
- DescribeRegionSettings — https://docs.aws.amazon.com/aws-backup/latest/APIReference/API_DescribeRegionSettings.html
- ListProtectedResources — https://docs.aws.amazon.com/aws-backup/latest/APIReference/API_ListProtectedResources.html
- GetSupportedResourceTypes — https://docs.aws.amazon.com/aws-backup/latest/APIReference/API_GetSupportedResourceTypes.html
