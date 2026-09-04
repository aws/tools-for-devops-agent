# AWS Backup Coverage Review Skill

A skill for AWS DevOps Agent that performs a structured, **read-only** coverage and
posture review of AWS Backup across all enabled Regions of an account, and reports
which backup-eligible resources are actually recoverable and which are not.

## Purpose

AWS Backup Audit Manager can report backup coverage, but its
`BACKUP_RESOURCES_PROTECTED_BY_BACKUP_PLAN` control requires AWS Config resource
recording to be enabled, plus a framework and a report plan that has already run.
Many accounts have none of that, which leaves operators with no on-demand way to
answer a simple question: *what isn't being backed up?*

This skill answers it live from read-only APIs. It builds an independent inventory
of backup-eligible resources, compares it against what AWS Backup is actually
protecting, and explains why each gap exists. AWS Config is used only as an
optimization when it happens to be available.

The core insight the review encodes is that **coverage is not binary**. A resource
can sit inside a correctly configured backup plan and still be unrecoverable —
because its resource type is not opted in for that Region, because the plan has
never successfully run for it, or because every backup job is failing. Each of
those looks healthy in the console.

## Key Capabilities

- Resolves every backup-eligible resource to one of five coverage states:
  `Protected`, `Stale`, `SelectedNotProtected`, `Unprotected`, or `OptInBlocked`
- Detects per-Region resource type opt-in gaps, where a plan and selection appear
  correct but AWS Backup will never protect the resource
- Distinguishes backup plan *membership* from actual *protection* by verifying
  recovery points exist, rather than trusting selections
- Flags ARN-only backup selections, which cannot match resources created after the
  selection was written and cause coverage to decay silently over time
- Evaluates backup plan frequency, retention, cross-Region copies, cross-account
  copies, continuous backup, and target vault lock status
- Evaluates vault posture: KMS key ownership, Vault Lock and its mode, access
  policies that block manual deletion, logically air-gapped vaults, and failure
  notifications
- Checks that restore testing plans exist and cover the protected resource types
- Runs 23 fixed, numbered checks across 5 dimensions, every one of which appears in
  the report with an explicit verdict — no check is ever silently omitted
- Produces a Coverage Rating (High / Medium / Low / Indeterminate) with a coverage
  matrix, severity-ranked findings, and remediation bucketed by SLA
- Never lets a permissions gap masquerade as a coverage gap: unreadable checks are
  excluded from the denominator and cap the rating instead of lowering it

## Prerequisites

The DevOps Agent role must have **read-only** permissions for the review to produce
complete results.

### Required: five actions to add

`AIDevOpsAgentAccessPolicy` already covers 43 of the 49 actions this skill uses —
verified with `iam:SimulatePrincipalPolicy` against a live agent role. **These five
are not covered and must be added:**

```
backup:GetSupportedResourceTypes
config:SelectResourceConfig
dsql:ListClusters
storagegateway:ListFileShares
storagegateway:ListVolumes
```

`sts:GetCallerIdentity` is also used and requires no IAM permission.

Deploy them with the `EnableAwsBackupCoverageReview` parameter in
[cloudformation/devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies.yaml).
**Each Agent Space has its own IAM role, so apply this to the role of every space
where the skill is installed** — use one stack per role:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies-<role-suffix> \
  --parameter-overrides ExistingRoleName=<DevOpsAgentRole-AgentSpace-XXXX> \
      EnableAwsBackupCoverageReview=true \
  --capabilities CAPABILITY_NAMED_IAM --region <region>
```

The template's other `Enable*` parameters default to `true`. Set the ones you do not
want to `false`, or you will also attach the other skills' policies — some of which
grant write actions such as `servicequotas:RequestServiceQuotaIncrease`.

**The skill still runs without these five.** Denied actions are reported as
"Unable to verify — access denied", excluded from the coverage denominator, and cap
the Coverage Rating at Medium rather than being guessed at. What you lose is
denominator completeness: Storage Gateway volumes and DSQL clusters cannot be
enumerated, and the supported-resource-type list falls back to a static table that
may lag new AWS Backup resource types.

### Full action list (reference)

AWS Backup and supporting reads:

```
backup:DescribeBackupVault
backup:DescribeGlobalSettings
backup:DescribeProtectedResource
backup:DescribeRegionSettings
backup:GetBackupPlan
backup:GetBackupSelection
backup:GetBackupVaultAccessPolicy
backup:GetBackupVaultNotifications
backup:GetRestoreTestingPlan
backup:GetSupportedResourceTypes
backup:ListBackupJobs
backup:ListBackupPlans
backup:ListBackupSelections
backup:ListBackupVaults
backup:ListFrameworks
backup:ListProtectedResources
backup:ListRecoveryPointsByBackupVault
backup:ListRecoveryPointsByResource
backup:ListReportPlans
backup:ListRestoreTestingPlans
backup:ListRestoreTestingSelections
backup:ListTags
kms:DescribeKey
sts:GetCallerIdentity
```

Resource inventory reads (the coverage denominator):

```
cloudformation:ListStacks
config:DescribeConfigurationRecorderStatus
config:DescribeConfigurationRecorders
config:SelectResourceConfig
dynamodb:DescribeContinuousBackups
dynamodb:DescribeTable
dynamodb:ListTables
ec2:DescribeInstances
ec2:DescribeRegions
ec2:DescribeVolumes
eks:DescribeCluster
eks:ListClusters
elasticfilesystem:DescribeFileSystems
fsx:DescribeFileSystems
fsx:DescribeVolumes
rds:DescribeDBClusters
rds:DescribeDBInstances
redshift:DescribeClusters
s3:GetBucketLocation
s3:ListAllMyBuckets
storagegateway:ListFileShares
storagegateway:ListVolumes
timestream:ListDatabases
timestream:ListTables
```

### Why not an AWS managed policy for the delta

Do not substitute a backup-specific AWS managed policy here. Both would grant write
access the skill never uses, and neither is a drop-in:

| Managed policy | Grants the 5 actions above? | Write actions it would add |
|---|---|---|
| [AWSBackupAuditAccess](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AWSBackupAuditAccess.html) | none of them | `backup:CreateFramework`, `CreateReportPlan`, `DeleteFramework`, `DeleteReportPlan`, `StartReportJob`, `UpdateFramework`, `UpdateReportPlan` |
| [AWSBackupOperatorAccess](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AWSBackupOperatorAccess.html) | 3 of 5 | `backup:StartBackupJob`, `StartCopyJob`, `StartRestoreJob`, `StartScanJob`, `CreateBackupSelection`, `DeleteBackupSelection` |

`ReadOnlyAccess` does cover all five and is effectively read-only, but grants
roughly 2,900 actions across every AWS service to obtain five — a large
over-grant for no benefit.

The five-action inline policy keeps the role's write surface empty. With
`AIDevOpsAgentAccessPolicy` plus that policy, every mutating AWS Backup action —
`StartBackupJob`, `StartRestoreJob`, `StartCopyJob`, `DeleteRecoveryPoint`,
`DeleteBackupPlan`, `PutBackupVaultLockConfiguration`, `UpdateRegionSettings` —
remains denied, so the read-only guarantee is enforced by IAM and does not depend
on the skill's instructions being followed.

If a check lacks permission, the skill reports it as "Unable to verify — access
denied", excludes it from the coverage denominator, and caps the Coverage Rating at
Medium rather than guessing the configuration.

If a check lacks permission, the skill reports it as "Unable to verify — access
denied", excludes it from the coverage denominator, and caps the Coverage Rating at
Medium rather than guessing the configuration.

The skill **never** performs any write, create, update, delete, or start operation —
in particular never `StartBackupJob`, `StartRestoreJob`, `StartCopyJob`, or
`StartReportJob` — and never reads backup content or object data.

## Limitations

- **Single account.** Reviews the calling account only. Organization-wide coverage
  via a delegated administrator account is not yet supported.
- **The coverage denominator is approximate without AWS Config.** Direct
  enumeration covers 16 of the resource types AWS Backup supports. `SAP HANA on
  Amazon EC2` and `VirtualMachine` cannot be enumerated — they require SSM/backint
  discovery and an AWS Backup gateway respectively. Both are reported as
  `NotEnumerated` and excluded from the denominator, never as covered. The report
  always discloses which inventory strategy was used.
- **Coverage integrity, not job triage.** The review flags that backup jobs are
  failing but does not diagnose why. Backup and restore job failure triage is out
  of scope.
- **Restore testing existence, not results.** The skill verifies that restore
  testing plans exist and cover the protected resource types. It does not read or
  interpret restore test outcomes.
- **AWS Backup only.** Service-native automated backups and manual snapshots taken
  outside AWS Backup (RDS automated backups, manual EBS snapshots) are not counted
  as coverage, because they are not governed by a backup plan lifecycle and do not
  appear in `ListProtectedResources`. For S3 bucket versioning, replication, and
  Object Lock posture, use `storage-s3-resiliency-expertise` instead.
- **Point-in-time snapshot.** The review reflects state at the moment it runs. It
  does not track coverage over time or detect regressions between runs.
- **The coverage percentage is indicative, not audited.** Per-resource states are
  authoritative — a named ARN reported as unprotected is a verified fact, and the
  findings and remediation are reliable. The account-wide totals require tallying
  resources across every enabled Region, and bulk types such as S3 buckets and
  CloudFormation stacks can be miscounted by a margin without any individual finding
  being wrong. Treat the percentage as a magnitude indicator, and the Coverage Matrix
  as the record of record. If you need an exact audited figure, enable AWS Config
  recording and use AWS Backup Audit Manager's coverage control alongside this review.
- **Schedule parsing.** Staleness tolerance is derived from the plan rule's cron or
  rate expression. Where an expression cannot be parsed, the skill falls back to a
  48-hour tolerance and says so in the finding.

## Agent Types

This skill is used by the following agent types (selected in the Operator Web App
at upload time):

- **Chat tasks** — conversational, on-demand reviews ("what isn't being backed up
  in this account?", "audit my backup plans").
- **Evaluation** — proactive, best-practices coverage and posture reviews against
  the 23 checks.

Agent type names differ between DevOps Agent releases — newer Agent Spaces present
options such as **All agent types**, **Chat tasks**, **Incident
mitigation/triage/RCA/UI**, **Improvement**, and **Release management/testing**,
and do not offer **Evaluation** by that name. If the types above are not listed
exactly, select **All agent types** (or **Generic** on older spaces) to make the
skill available everywhere. Nothing in the skill depends on a particular agent
type.

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/aws-backup-coverage-review` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Instead, connect your personal GitHub account and select any repository from it during the connection setup. Once a GitHub connection is established, you can import skills from any public repository, including this one, even if it wasn't selected during the connection setup.

**Option B: Upload as a zip file**

1. Zip the `aws-backup-coverage-review/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r aws-backup-coverage-review.zip aws-backup-coverage-review/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `aws-backup-coverage-review.zip` file (max 6 MB).
5. Select the agent types: **Chat tasks** and **Evaluation** — or **All agent
   types** if your Agent Space presents a different set (see Agent Types above).
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage skills — useful for CI/CD pipelines or automation workflows. Assign the skill to the `CHAT` and `EVALUATION` agent types. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to Use This Skill

Describe the task in natural language — you do not need to name the skill.

**Chat tasks**

- "What isn't being backed up in this account?"
- "Run an AWS Backup coverage review."
- "Audit my backup plans and vaults."
- "Are my EBS volumes and RDS databases protected by AWS Backup?"
- "Do a backup gap analysis for us-east-1 and eu-west-1."
- "Which resources are in a backup plan but have no recovery points?"

**Evaluation**

- "Assess our AWS Backup posture against best practices."
- "Review backup coverage, retention, and vault protection across all Regions."
- "Check whether our backup plans meet a 35-day retention and daily frequency bar."

The agent gathers configuration via its `use_aws` tool under the assumed role in
the target account, resolves each resource's coverage state, applies the 23 checks,
and returns a Markdown report artifact.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
