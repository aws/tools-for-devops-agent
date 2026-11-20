# Amazon EBS Expertise

This skill enables the AWS DevOps Agent to troubleshoot Amazon EBS problems and to review an account's Amazon EBS setup, with one consistent procedure every run.

## What It Does

Without a skill, AWS DevOps Agent gathers the right Amazon EBS data but can interpret it inconsistently. It can frame an answer in a way that pushes toward the wrong fix, such as "buy a bigger volume" when the instance is the ceiling, or "your modification failed" when it succeeded. This skill encodes Amazon EBS interpretation as a fixed procedure, so the correct and correctly framed answer is the default.

It is one skill with two modes. Troubleshoot mode answers "something is wrong, why?". Review mode answers "is my EBS setup healthy before something goes wrong?".

## Key Capabilities

- **Troubleshoot: performance.** Rules Amazon EBS in or out, then decides whether the volume, the instance's EBS limits, burst credits, a quota or an AWS-side impairment is the binding layer. Tells saturation apart from impairment and checks for a running AWS FIS experiment. Sizes IOPS and throughput within the instance's EBS baseline.
- **Troubleshoot: volume modification.** Explains Elastic Volumes states (`optimizing` already applies the change), the limit of 4 modifications per rolling 24 hours, `ModifyVolume` errors such as the io2 IOPS-to-size ratio, gp2 to gp3 sizing, and file system extension commands.
- **Troubleshoot: snapshots.** Safe-to-delete tiers by lineage (AMI-backing, shared, AWS Backup, Amazon Data Lifecycle Manager by `aws:dlm:*` tags, orphaned), reversibility through Recycle Bin, copy and AMI problems, recovery.
- **Troubleshoot: encryption.** AWS KMS key state and permissions blocking attach or start, sharing encrypted snapshots, encryption by default, re-encryption steps.
- **Troubleshoot: billing.** Breaks a cost change into storage, provisioned IOPS, provisioned throughput and snapshots using the account's own AWS Cost Explorer data, finds the change with `DescribeVolumesModifications`, and checks right-sizing.
- **Review mode.** A rated report over six areas: capacity and quota headroom, observability, cost hygiene, resilience, encryption posture and deletion protection.
- **Shared capabilities.** Metric interpretation, quota headroom with a pre-filled Service Quotas request, escalation, and stuck attach or detach diagnosis.
- **Read-only.** Every change is a proposal with exact parameters, cost direction and rollback, run only through an operator-approved directed action.

## Prerequisites

### IAM permissions

The DevOps Agent role needs **read-only** permissions for the APIs in `references/data-collection.md`. The skill makes no write calls. Most actions are covered by the AWS managed policy [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html) (checked against policy version v14). The actions marked **Add** are not in that policy and must be added to the agent role.

| Service | IAM actions | In `AIDevOpsAgentAccessPolicy` |
|---|---|---|
| Amazon EC2 | `ec2:DescribeVolumes`, `ec2:DescribeVolumeStatus`, `ec2:DescribeVolumesModifications`, `ec2:DescribeVolumeAttribute`, `ec2:DescribeInstances`, `ec2:DescribeInstanceTypes`, `ec2:DescribeInstanceAttribute`, `ec2:DescribeSnapshots`, `ec2:DescribeSnapshotAttribute`, `ec2:DescribeImages`, `ec2:DescribeFastSnapshotRestores`, `ec2:DescribeLockedSnapshots` | Yes (`ec2:Describe*`) |
| Amazon EC2 | `ec2:GetSnapshotBlockPublicAccessState` | Yes |
| Amazon EC2 | `ec2:GetEbsEncryptionByDefault`, `ec2:GetEbsDefaultKmsKeyId` | **Add** |
| Amazon CloudWatch | `cloudwatch:DescribeAlarms`, `cloudwatch:DescribeAlarmHistory`, `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics` | Yes |
| Service Quotas | `servicequotas:ListServiceQuotas`, `servicequotas:GetServiceQuota`, `servicequotas:GetAWSDefaultServiceQuota`, `servicequotas:ListRequestedServiceQuotaChangeHistoryByQuota` | Yes |
| Amazon Data Lifecycle Manager | `dlm:GetLifecyclePolicies`, `dlm:GetLifecyclePolicy` | **Add** |
| Recycle Bin | `rbin:ListRules`, `rbin:GetRule` | **Add** |
| AWS Backup | `backup:ListBackupPlans`, `backup:ListBackupSelections`, `backup:GetBackupSelection`, `backup:ListRecoveryPointsByResource`, `backup:ListProtectedResources` | Yes |
| AWS KMS | `kms:DescribeKey`, `kms:GetKeyPolicy`, `kms:ListGrants` | Yes |
| AWS Cost Explorer | `ce:GetCostAndUsage`, `ce:GetDimensionValues` | Yes |
| AWS FIS | `fis:ListExperiments` | Yes |
| AWS FIS | `fis:GetExperiment` | **Add** |
| AWS Health | `health:DescribeEvents` | Yes |
| AWS Compute Optimizer (optional) | `compute-optimizer:GetEBSVolumeRecommendations` | **Add** |
| AWS CloudTrail (optional) | `cloudtrail:LookupEvents` | Yes |

Least-privilege policy for the actions to add:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StorageEbsExpertiseReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:GetEbsEncryptionByDefault",
        "ec2:GetEbsDefaultKmsKeyId",
        "dlm:GetLifecyclePolicies",
        "dlm:GetLifecyclePolicy",
        "rbin:ListRules",
        "rbin:GetRule",
        "fis:GetExperiment",
        "compute-optimizer:GetEBSVolumeRecommendations"
      ],
      "Resource": "*"
    }
  ]
}
```

If a call is denied, the skill names the API under Gaps and says which conclusion stays unconfirmed, instead of guessing. AWS CloudTrail access is optional; the skill works without it and uses `DescribeVolumesModifications` as the change record.

### AWS resources

- An Agent Space with access to the account and Regions that hold the Amazon EBS volumes and Amazon EC2 instances to investigate.
- For alarm-driven investigations: Amazon CloudWatch alarms on AWS/EBS metrics or on instance `EBSIOBalance%` / `EBSByteBalance%`, routed to the Agent Space.
- For mutating proposals (for example `ec2:ModifyVolume`, `ec2:DeleteSnapshot`, `servicequotas:RequestServiceQuotaIncrease`): directed actions enabled in the Agent Space with their own role. Each action needs operator approval on the approval card. The skill itself never runs them.

## Limitations

- Amazon EBS metrics are 1-minute data. Sub-minute micro-bursts can hide below the average; the skill says so instead of claiming headroom.
- `VolumeAvg*` metrics exist only on Nitro instances. `EBSIOBalance%` and `EBSByteBalance%` exist only on some instance sizes. The skill falls back to Sum-based math and the instance baseline.
- Service Quotas and most Amazon EBS settings are per Region. The skill checks the Regions you name.
- Latency, queue length and idle-time thresholds are not encoded, because no public AWS source states them. The skill compares a volume with its own history and its type's documented expectation.
- The encryption path and Review mode are built from public documentation and are not yet live-tested.
- Some Agent Spaces hold read calls such as `dlm:GetLifecyclePolicies` and `rbin:ListRules` behind an approval gate. The skill then reports the conclusion as unconfirmed.

## Agent Types

This skill is used by the following agent types:

- **Chat tasks (`CHAT`)**: conversational troubleshooting and Review mode
- **Incident RCA (`INCIDENT_RCA`)**: root cause analysis for Amazon EBS alarms and incidents

## Uploading to AWS DevOps Agent

Only `SKILL.md` and `references/` are uploaded. `README.md`, `CHANGELOG.md`, `.skilleval.yaml` and `evals/` are not.

**Option A: Upload as a zip file**

1. From the folder that contains `storage-ebs-expertise/`, zip the directory (only including allowed extensions):
   ```bash
   zip -r -X storage-ebs-expertise.zip storage-ebs-expertise/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*' '*/.DS_Store'
   ```
2. In the AWS DevOps Agent Operator Web App, choose **Knowledge**, then the **Skills** tab.
3. Choose **Add skill**, then **Upload skill**.
4. Drag and drop `storage-ebs-expertise.zip` (max 6 MB).
5. Select the agent types: **Chat tasks** and **Incident RCA**.
6. Choose **Upload** and confirm the status is **Active**.

**Option B: Import from a repository**

If your Agent Space has a repository connection, choose **Add skill**, then **Import from repository**, and point to the `storage-ebs-expertise` directory.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to manage the skill programmatically, for example from a CI/CD pipeline. Assign the skill to the `CHAT` and `INCIDENT_RCA` agent types. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html).

The single-file **Create skill** form in the Operator Web App holds only `SKILL.md`, so the `references/` files would not be available to the agent. Use one of the options above.

For more details, see [AWS DevOps Agent skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html) in the AWS DevOps Agent User Guide.

## How to Use This Skill

You do not name the skill; the agent matches it from the request or the alarm.

### Chat

- "The application on instance i-0123456789abcdef0 has gotten slow over the last half hour. Can you look into what's going on?"
- "I changed the IOPS on one of my volumes a while ago and it still hasn't taken effect. Is it stuck?"
- "My snapshot costs keep going up. Which of my snapshots can I safely delete?"
- "I got 'You have exceeded your maximum io2 IOPS limit' when creating an io2 volume. What do I do?"
- "My instance won't start after I attached a KMS-encrypted volume. What's wrong?"
- "My EBS bill is higher than expected. Why?"
- "Review my EBS setup in us-east-1. Is my storage production-ready?"

### Investigation

- A CloudWatch alarm on `VolumeQueueLength`, `VolumeReadOps` or `BurstBalance` for an Amazon EBS volume.
- A CloudWatch alarm on `EBSIOBalance%` or `EBSByteBalance%` for an instance.
- "Application timeouts started 20 minutes ago and EBS latency is high. Determine whether Amazon EBS is the cause."

## Scope

| In scope | Out of scope |
|---|---|
| Performance attribution: rule EBS in or out, AWS-side impairment and escalation, volume-limit saturation, how much IOPS or throughput, micro-bursting, instance EBS-limit bottleneck, volume initialization after restore, burst credits | Amazon S3, Amazon EFS, Amazon FSx, instance store |
| Snapshot management: cross-Region and cross-account copy, AMI creation stuck or slow, Amazon Data Lifecycle Manager and Recycle Bin, safe-to-delete and cost, recovery, escalation | Amazon EC2 issues unrelated to Amazon EBS |
| Encryption and AWS KMS: key access blocking attach or start, sharing encrypted snapshots and AMIs, default encryption, re-encryption | OS-level changes executed by the agent (commands are given, not run) |
| Volume modification: gp2 to gp3, sizing, file system extension commands, stuck or slow optimizing, `ModifyVolume` errors, the 4 per 24 hours limit, shrink and cancel | Any mutating action without an approved directed action |
| Cost and billing: forecast and optimization, Recycle Bin retention, unexplained charges, pricing model, idle or over-provisioned volumes, snapshot growth | Effort, hours or FTE estimates |
| Shared: metric interpretation, quota headroom, escalation, stuck attach and detach | |
| Review mode: the six areas listed under Key Capabilities | |

## File Layout

```
storage-ebs-expertise/
├── SKILL.md                     # uploaded
├── references/                  # uploaded
│   ├── troubleshoot-performance.md
│   ├── troubleshoot-snapshots.md
│   ├── troubleshoot-encryption.md
│   ├── troubleshoot-volume-modification.md
│   ├── troubleshoot-billing.md
│   ├── review-operational.md
│   ├── data-collection.md
│   ├── finding-logic.md
│   ├── metrics-thresholds.md
│   ├── review-report-format.md
│   └── ebs-best-practices.md
├── README.md                    # not uploaded
├── CHANGELOG.md                 # not uploaded
├── .skilleval.yaml              # not uploaded
└── evals/                       # not uploaded
    ├── eval_queries.json
    └── evals.json
```

## Version and Change Log

Version 1.0.0. See [CHANGELOG.md](CHANGELOG.md).

## Disclaimer

This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.
