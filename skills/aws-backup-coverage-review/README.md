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

### Required: six actions to add

`AIDevOpsAgentAccessPolicy` already covers 45 of the 52 actions this skill uses —
verified with `iam:SimulatePrincipalPolicy` against a live agent role. **These six
are not covered and must be added:**

```
backup:GetSupportedResourceTypes
config:SelectResourceConfig
dsql:ListClusters
storagegateway:ListFileShares
storagegateway:ListGateways
storagegateway:ListVolumes
```

`sts:GetCallerIdentity` is also used and requires no IAM permission.

Deploy them with the `EnableAwsBackupCoverageReview` parameter in
[cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml).
**Each Agent Space has its own IAM role, so apply this to the role of every space
where the skill is installed** — use one stack per role:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies-<role-suffix> \
  --parameter-overrides ExistingRoleName=<DevOpsAgentRole-AgentSpace-XXXX> \
      EnableAwsBackupCoverageReview=true \
  --capabilities CAPABILITY_NAMED_IAM --region <region>
```

The template's other `Enable*` parameters default to `true`. Set the ones you do not
want to `false`, or you will also attach the other skills' policies — some of which
grant write actions such as `servicequotas:RequestServiceQuotaIncrease`.

**The skill still runs without these six.** Denied actions are reported as
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
backup-gateway:ListHypervisors
backup-gateway:ListVirtualMachines
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
storagegateway:ListGateways
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
- **Some read-only calls are blocked by the DevOps Agent guardrail, not by IAM.**
  The DevOps Agent's [permission guardrail](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-limiting-agent-access-in-an-aws-account.html)
  classifies a few read-only operations as mutative and cancels them with
  `Cancelled mutative operation: … requires an operator approval`. `backup:ListRestoreTestingPlans`
  (check 5.1, restore testing coverage) and `storagegateway:ListGateways` (Storage
  Gateway enumeration) are the two observed. This is a platform classification, **not
  an IAM gap** — the action can be granted in IAM and remain uncallable, and no policy
  change or CloudFormation edit fixes it. When it occurs, the skill records the check
  as `ToolingFailure`, which caps the Coverage Rating at Medium and is never scored as
  a coverage gap; it does **not** report "no restore testing plan is configured," since
  a cancelled call carries no information about whether resources exist. The
  `ToolingFailure` line in the report is expected behavior, not a defect. Granting an
  operator approval for the operation, or running the same review outside the guarded
  runtime, is the only way to obtain the underlying data.
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

- **On-demand** (`CHAT`) — conversational, on-demand reviews ("what isn't being backed up
  in this account?", "audit my backup plans").

Select **Generic** instead if you want the skill available to all agent types.
Nothing in the skill depends on a particular agent type.

## Uploading to AWS DevOps Agent

Add the [six IAM actions](#required-six-actions-to-add) that `AIDevOpsAgentAccessPolicy` doesn't cover first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs an on-demand backup coverage review that you ask for in chat and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add backup posture context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `aws-backup-coverage-review`, or filter by AWS service **AWS Backup**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust the daily-frequency and 35-day retention bar in `references/backup-best-practices.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/aws-backup-coverage-review/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f aws-backup-coverage-review.zip
   zip -r aws-backup-coverage-review.zip aws-backup-coverage-review/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l aws-backup-coverage-review.zip | tail -1   # expect 5 files
   ```

2. Check that the zip has this structure:

   ```text
   aws-backup-coverage-review.zip
   └── aws-backup-coverage-review/
       ├── SKILL.md                          # required: frontmatter with name and description
       ├── assets/
       │   └── report-format.md
       └── references/
           ├── backup-best-practices.md
           ├── coverage-logic.md
           └── data-collection.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `aws-backup-coverage-review.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

Describe the task in natural language — you do not need to name the skill.

**On-demand**

- "What isn't being backed up in this account?"
- "Run an AWS Backup coverage review."
- "Audit my backup plans and vaults."
- "Are my EBS volumes and RDS databases protected by AWS Backup?"
- "Do a backup gap analysis for us-east-1 and eu-west-1."
- "Which resources are in a backup plan but have no recovery points?"
- "Assess our AWS Backup posture against best practices."
- "Review backup coverage, retention, and vault protection across all Regions."
- "Check whether our backup plans meet a 35-day retention and daily frequency bar."

The agent gathers configuration via its `use_aws` tool under the assumed role in
the target account, resolves each resource's coverage state, applies the 23 checks,
and returns a Markdown report artifact.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
