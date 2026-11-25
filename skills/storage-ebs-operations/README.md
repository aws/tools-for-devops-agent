# Amazon EBS Operations

This skill enables the AWS DevOps Agent to troubleshoot Amazon EBS problems and to review an account's Amazon EBS setup, with one consistent procedure every run.

## What It Does

The skill gives AWS DevOps Agent a fixed, read-only procedure for Amazon EBS. It has two modes.

- **Troubleshoot mode** answers "something is wrong, why?" through five paths: performance, volume modification, snapshots, encryption and AWS KMS, and billing. Each answer names the binding layer (volume, instance, burst credits, quota, not EBS, AWS-side impairment or Indeterminate) and gives the evidence, an exact recommendation, separate findings and gaps.
- **Review mode** answers "is my EBS setup healthy before something goes wrong?" with a Summary table that rates six areas: capacity and quota headroom, observability, cost hygiene, resilience, encryption posture and deletion protection.

On the performance path the agent reads the CloudWatch exceeded checks (`VolumeIOPSExceededCheck`, `VolumeThroughputExceededCheck`, `InstanceEBSIOPSExceededCheck` and `InstanceEBSThroughputExceededCheck`), which show directly whether the volume or the instance limit binds, and the `VolumeStalledIOCheck` stalled I/O check. When the 1-minute CloudWatch data cannot settle the question, the agent gives the customer the documented commands to read the Amazon EBS detailed performance statistics on the instance. The customer runs that step; the agent does not.

Safety rules the skill applies:

- Snapshots are sorted by lineage. A snapshot whose source volume is gone needs owner review, and no snapshot is recommended for deletion.
- Deletes are manual steps the customer runs with their own credentials after the owner confirms.
- AWS-side impairment is named only with a direct signal: a failed `VolumeStalledIOCheck`, an impaired volume status or an open AWS Health event. Without one, the result is Indeterminate and the agent does not recommend more provisioning.
- Every proposed quota request includes the intake questions for the customer and a caution that an increase is not guaranteed and the amount is decided by AWS.

The skill is read-only by design. Every change is a proposal with the exact command, expected effect, rollback and cost direction. It runs only as a directed action that an operator approves on the approval card. A typed approval in chat is not approval.

## Key Capabilities

- **Troubleshoot: performance.** Rules Amazon EBS in or out, then decides whether the volume, the instance's EBS limits, burst credits, a quota or an AWS-side impairment is the binding layer. Reads the four CloudWatch exceeded checks and `VolumeStalledIOCheck`, tells saturation apart from impairment and checks for a running AWS FIS experiment. Gives the detailed performance statistics as a step the customer runs on the instance. Sizes IOPS and throughput within the instance's EBS baseline.
- **Troubleshoot: volume modification.** Explains Elastic Volumes states (`optimizing` already applies the change), the limit of 4 modifications per rolling 24 hours, `ModifyVolume` errors such as the io2 IOPS-to-size ratio, gp2 to gp3 sizing, and file system extension commands.
- **Troubleshoot: snapshots.** Snapshot tiers by lineage (AMI-backing, shared, AWS Backup, Amazon Data Lifecycle Manager by `aws:dlm:*` tags, and snapshots whose source volume is gone, listed for owner review instead of recommended for deletion), reversibility through Recycle Bin, copy and AMI problems, recovery.
- **Troubleshoot: encryption.** AWS KMS key state and permissions blocking attach or start, sharing encrypted snapshots, encryption by default, re-encryption steps.
- **Troubleshoot: billing.** Breaks a cost change into storage, provisioned IOPS, provisioned throughput and snapshots using the account's own AWS Cost Explorer data, finds the change with `DescribeVolumesModifications` (latest modification) and the optional AWS CloudTrail `ModifyVolume` events (earlier modifications), and checks right-sizing.
- **Review mode.** A rated report over six areas: capacity and quota headroom, observability, cost hygiene, resilience, encryption posture and deletion protection.
- **Shared capabilities.** Metric interpretation, quota headroom with a pre-filled Service Quotas request, escalation, and stuck attach or detach diagnosis.
- **Read-only.** Every change is a proposal with exact parameters, cost direction and rollback, run only through an operator-approved directed action. Deletes are manual steps for the customer after the owner confirms.

## Prerequisites

### IAM permissions

The DevOps Agent role needs **read-only** permissions for the APIs in `references/data-collection.md`. The skill makes no write calls. Most actions are covered by the AWS managed policy [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html). The actions marked **Add** are not in that policy and must be added to the agent role.

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
      "Sid": "StorageEbsOperationsReadOnly",
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

To add the same actions with CloudFormation, deploy [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml) with `EnableStorageEbsOperations` set to `true`.

If a call is denied, the skill names the API under Gaps and says which conclusion stays unconfirmed, instead of guessing. AWS CloudTrail access is optional; the skill works without it. `DescribeVolumesModifications` returns only the most recent modification per volume, so without AWS CloudTrail the skill reports modification history and the 24-hour modification count as Gaps.

### AWS resources

- An Agent Space with access to the account and Regions that hold the Amazon EBS volumes and Amazon EC2 instances to investigate.
- For alarm-driven investigations: Amazon CloudWatch alarms on AWS/EBS metrics or on instance `EBSIOBalance%` / `EBSByteBalance%`, routed to the Agent Space.
- For mutating proposals (for example `ec2:ModifyVolume`, `servicequotas:RequestServiceQuotaIncrease`): directed actions enabled in the Agent Space with their own role. Each action needs operator approval on the approval card. The skill itself never runs them.
- Deletes (for example `ec2:DeleteSnapshot`, `ec2:DeleteVolume`) are never directed actions, because AWS DevOps Agent refuses delete-class operations. The skill lists the resource for owner review and gives manual steps for the customer to run with their own credentials.

## Limitations

- Amazon EBS metrics are 1-minute data. Sub-minute micro-bursts can hide below the average; the skill says so instead of claiming headroom.
- `VolumeAvg*` metrics exist only on Nitro instances. `EBSIOBalance%` and `EBSByteBalance%` exist only on some instance sizes. The skill falls back to Sum-based math and the instance baseline.
- Service Quotas and most Amazon EBS settings are per Region. The skill checks the Regions you name.
- Latency, queue length and idle-time thresholds are not encoded, because no public AWS source states them. The skill compares a volume with its own history and its type's documented expectation.
- The encryption path and Review mode are built from public documentation and are not yet live-tested.
- Amazon EBS Multi-Attach volumes are not covered. The instance-layer checks assume each volume is attached to one instance.
- Some Agent Spaces hold read calls such as `dlm:GetLifecyclePolicies` and `rbin:ListRules` behind an approval gate. The skill then reports the conclusion as unconfirmed.

## Agent Types

This skill is used by the following agent types:

- **Chat tasks (`CHAT`)**: conversational troubleshooting and Review mode
- **Incident RCA (`INCIDENT_RCA`)**: root cause analysis for Amazon EBS alarms and incidents

## Uploading to AWS DevOps Agent

The agent needs only `SKILL.md` and `references/`. When you upload or import the skill yourself, include only those.

**Option A: Upload as a zip file**

1. From the folder that contains `storage-ebs-operations/`, zip the directory (only including allowed extensions):
   ```bash
   zip -r -X storage-ebs-operations.zip storage-ebs-operations/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*' '*/.DS_Store'
   ```
2. In the AWS DevOps Agent Operator Web App, choose **Knowledge**, then the **Skills** tab.
3. Choose **Add skill**, then **Upload skill**.
4. Drag and drop `storage-ebs-operations.zip` (max 6 MB).
5. Select the agent types: **Chat tasks** and **Incident RCA**.
6. Choose **Upload** and confirm the status is **Active**.

**Option B: Import from a repository**

If your Agent Space has a repository connection, choose **Add skill**, then **Import from repository**. Import or zip only `SKILL.md` and `references/`. Pointing the import at the whole `storage-ebs-operations` directory pulls in every file in it, including `evals/`.

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
| Snapshot management: cross-Region and cross-account copy, AMI creation stuck or slow, Amazon Data Lifecycle Manager and Recycle Bin, which snapshots need owner review before deletion, cost, recovery, escalation | Amazon EC2 issues unrelated to Amazon EBS |
| Encryption and AWS KMS: key access blocking attach or start, sharing encrypted snapshots and AMIs, default encryption, re-encryption | OS-level changes executed by the agent (commands are given, not run) |
| Volume modification: gp2 to gp3, sizing, file system extension commands, stuck or slow optimizing, `ModifyVolume` errors, the 4 per 24 hours limit, shrink and cancel | Any mutating action without an approved directed action |
| Cost and billing: forecast and optimization, Recycle Bin retention, unexplained charges, pricing model, idle or over-provisioned volumes, snapshot growth | Effort, hours or FTE estimates |
| Shared: metric interpretation, quota headroom, escalation, stuck attach and detach | |
| Review mode: the six areas listed under Key Capabilities | |

## File Layout

```
storage-ebs-operations/
├── SKILL.md                     # published, read by the agent
├── references/                  # published, read by the agent
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
├── README.md                    # published
├── CHANGELOG.md                 # not published
├── .skilleval.yaml              # not published
└── evals/                       # not published
    ├── evals.json               # eval definitions
    ├── structure/               # structure test results
    ├── best-practices/          # best-practices test results
    └── functional/              # functional test results and the evals.json the run executed
```

## Version and Change Log

Version 1.0.0. See the CHANGELOG.md file in this skill directory.

## Disclaimer

This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.
