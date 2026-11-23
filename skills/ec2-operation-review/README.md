# EC2 Operation Review — AWS DevOps Agent Skill

A comprehensive Amazon EC2 operational review skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Conducts best-practices assessments aligned with [EC2 best practices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-best-practices.html) and the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html). Generates a shareable report artifact per resource.

> **Disclaimer:** This skill is provided as **sample code**, not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions and findings against your organization's policies before relying on it.

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to:

1. Discover EC2 instances, Auto Scaling groups, EBS volumes, security groups, and networking in the configured account/regions.
2. Collect instance configuration (type, AMI, IMDS options, IAM profile, monitoring, tags), volume config, security-group rules, and Auto Scaling group settings.
3. Collect a 14-day CloudWatch metrics window (CPU, network, status checks, EBS I/O, and CloudWatch-agent memory/disk when present) and alarm coverage.
4. Analyze against five Well-Architected pillars (Security, Reliability, Performance Efficiency, Cost Optimization, Operational Excellence).
5. Generate a shareable report artifact per resource, named `ec2-review-<instance-or-scope>-<YYYY-MM-DD>.md`.

All data is gathered through native AWS APIs (`ec2`, `autoscaling`, `cloudwatch`, `ssm`). The skill operates entirely in **read-only** mode.

## Agent Types

- **On-demand** — conversational invocation in Chat ("review my EC2 instances", "EC2 health check").
- **Evaluation** — proactive operational improvement recommendations.

Select **Generic** to make it available to all agent types.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. IAM permissions for the DevOps Agent's primary cloud-source role

The Agent Space's IAM role must have read access to EC2, Auto Scaling, CloudWatch, and (optionally) SSM and Cost Explorer. The AWS managed read-only policy typically covers these — verify in your account before running the review:

- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`, `ec2:DescribeInstanceCreditSpecifications`
- `ec2:DescribeVolumes`, `ec2:DescribeSnapshots`, `ec2:DescribeAddresses`, `ec2:DescribeKeyPairs`
- `ec2:DescribeSecurityGroups`, `ec2:DescribeSubnets`, `ec2:DescribeVpcs`
- `ec2:DescribeLaunchTemplates`, `ec2:DescribeLaunchTemplateVersions`
- `autoscaling:DescribeAutoScalingGroups`, `autoscaling:DescribeLaunchConfigurations`, `autoscaling:DescribePolicies`
- `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:DescribeAlarms`, `cloudwatch:DescribeAlarmsForMetric`
- `ssm:DescribeInstanceInformation`, `ssm:ListComplianceItems` (optional — patch/SSM status)
- `iam:GetInstanceProfile`, `iam:GetRolePolicy`, `iam:ListAttachedRolePolicies` (optional — instance-profile scope check)
- `ce:GetCostAndUsage`, `ce:GetReservationCoverage` (optional — cost/commitment analysis)
- `tag:GetResources` (optional — cross-service tag reporting)

The skill operates entirely in **read-only** mode: it never calls `RunInstances`, `TerminateInstances`, `StopInstances`, `ModifyInstanceAttribute`, `CreateSnapshot`, `DeleteVolume`, or any mutating API.

### 3. CloudWatch agent (recommended)

`CPUUtilization`, network, and EBS metrics are emitted automatically. **Memory** and **in-guest disk** utilization require the [CloudWatch agent](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Install-CloudWatch-Agent.html) (`CWAgent` namespace). Without it, memory/disk-based right-sizing checks are reported as `NOT_ASSESSED` rather than passing.

### 4. Detailed monitoring (recommended)

With basic monitoring, EC2 metrics are 5-minute granularity. Enabling [detailed monitoring](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-cloudwatch-new.html) gives 1-minute data and higher-confidence right-sizing conclusions.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

### 1. Package the skill

From the `skills/` directory in this repo:

```bash
cd skills
zip -r ec2-operation-review.zip ec2-operation-review/ -x 'ec2-operation-review/evals/*'
```

Constraints (enforced at upload time):

- Total zip size ≤ **6 MB**.
- `SKILL.md` is required and must include `name` and `description` frontmatter.
- A `scripts/` directory is **not** allowed — uploads containing scripts are rejected.

`evals/` is excluded from the upload (it's only used for offline evaluation).

### 2. Upload via the Operator Web App

1. Navigate to the **Skills** page in your Agent Space Operator Web App.
2. Click **Add skill** → **Upload skill**.
3. Drag and drop `ec2-operation-review.zip`.
4. Select agent types: **On-demand** and **Evaluation** (or leave **Generic**).
5. Review the validation results and click **Upload**.

## Usage

In the DevOps Agent Chat, use natural language:

- *"Run an EC2 operational review for all instances in us-east-1."*
- *"Review my EC2 instance `i-0abc123` for best practices."*
- *"Audit EC2 security and cost optimization across all regions."*
- *"Find idle or right-sizing candidates among my EC2 instances."*
- *"ORR for our production EC2 fleet."*

The agent collects data automatically and generates a report artifact per resource, named `ec2-review-<instance-or-scope>-<YYYY-MM-DD>.md`.

## Skill Contents

```
ec2-operation-review/
├── SKILL.md                           # main skill instructions (with frontmatter)
├── README.md                          # this file
├── CHANGELOG.md
├── references/
│   ├── best-practices-checklist.md    # checklist mapped to EC2 best practices
│   └── metrics-thresholds.md          # CloudWatch metric thresholds & severity rules
└── evals/                             # evaluation data (not included in upload zip)
```

## Best-Practices Sections Covered

| # | Pillar | Reference |
|---|--------|-----------|
| 1 | Security (IMDSv2, security groups, EBS encryption, IAM profile, AMI currency) | [EC2 security](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security.html), [IMDSv2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html) |
| 2 | Reliability (Multi-AZ ASG, health checks, snapshots/backup, Auto Recovery) | [Auto Scaling](https://docs.aws.amazon.com/autoscaling/ec2/userguide/), [EBS snapshots](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSSnapshots.html) |
| 3 | Performance Efficiency (CPU/network/EBS, T-credits, current-gen, Graviton) | [Instance types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html) |
| 4 | Cost Optimization (idle/right-sizing, gp2→gp3, orphaned EBS/EIP, SP/RI/Spot) | [Cost optimization](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-cost-optimization.html) |
| 5 | Operational Excellence (tags, alarms, detailed monitoring, SSM, events) | [Well-Architected Operational Excellence](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html) |

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | 24–48 hours |
| HIGH | Significant gap that could lead to incidents | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |
