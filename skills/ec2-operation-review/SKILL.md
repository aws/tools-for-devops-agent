---
name: ec2-operation-review
description: >
  Comprehensive Amazon EC2 operational review aligned with the AWS
  Well-Architected Framework and EC2 best practices. Assesses one or many EC2
  instances (and their Auto Scaling groups, EBS volumes, security groups, and
  networking) across five pillars — security, reliability, performance
  efficiency, cost optimization, and operational excellence — using read-only
  control-plane and CloudWatch API calls, then produces a rated report with
  prioritized findings and remediation guidance.

  Use when a user asks to review, audit, or assess EC2 instances, Auto Scaling
  groups, or EBS volumes for best-practices compliance, security posture,
  reliability, performance, cost optimization, right-sizing, or operational
  readiness. Triggers on phrasings like "EC2 review", "EC2 best practices
  audit", "EC2 operational assessment", "review my EC2 instances", "EC2 health
  check", "EC2 right-sizing", "are my EC2 instances secure", "ORR for EC2", or
  "audit my Auto Scaling group".

  Do NOT use for EKS/ECS container workloads (use the EKS skills), Lambda (use
  the Lambda skill), RDS/Aurora database hosts (use the RDS skill), or for
  authoring CloudFormation, CDK, or Terraform templates.
metadata:
  author: awslokesh
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation"
  aws-devops-agent-skills.aws-services: "Amazon EC2, Amazon EBS, Amazon EC2 Auto Scaling, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Compute"
---

# EC2 Operational Review

Conduct a comprehensive, read-only operational review of Amazon EC2 instances
and their directly associated resources (Auto Scaling groups, EBS volumes,
security groups, key pairs, and networking) aligned with the
[AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
and [EC2 best practices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-best-practices.html).

## When to Use

Activate this skill when the user asks to:
- Review, audit, or assess EC2 instances, Auto Scaling groups, or EBS volumes
- Check EC2 best-practices compliance
- Evaluate EC2 security posture, reliability, performance, or cost optimization
- Right-size EC2 instances or find idle / underutilized instances
- Perform an EC2 operational readiness review (ORR)
- Investigate EC2 configuration drift or hardening gaps

Do **not** activate for:
- Container workloads on EKS or ECS (use the EKS skills)
- AWS Lambda functions (use the `lambda-operational-review` skill)
- RDS / Aurora database instances (use the `rds-operation-review` skill)
- Authoring CloudFormation, CDK, or Terraform templates

## Critical Warnings

- **This skill is read-only.** Every command is a `Describe*`, `List*`, `Get*`,
  or a read-only CloudWatch call. The agent does NOT execute `RunInstances`,
  `TerminateInstances`, `StopInstances`, `ModifyInstanceAttribute`,
  `CreateSnapshot`, `DeleteVolume`, or any mutating API. All remediations are
  presented as recommendations for the operator to run after review.
- **Never recommend an action that reduces availability without stating the
  impact.** Stopping, resizing, or deleting requires an instance reboot or
  downtime — always state this and the preconditions.
- **UNKNOWN ≠ PASS.** Any check that cannot be assessed (missing metric,
  missing permission, no data) MUST be reported as `NOT_ASSESSED` with the
  reason, never silently marked as passing.

## Step 1: Identify Target Resources

Ask the user which instances to review. Accept:
- Specific instance IDs (`i-0abc...`) and regions
- Instance name tags
- Auto Scaling group names
- "all instances" in specific regions
- "all instances in all regions"

If no scope is given, default to all configured account regions. Do not silently
substitute a target — if a named instance is not found, list the closest
candidates and ask the user to confirm before assessing.

## Step 2: Discover EC2 Resources

Per region (skip empty regions):

```
ec2.DescribeInstances                 # instances + state, type, AMI, tags, IAM profile, metadata options
ec2.DescribeInstanceStatus            # system/instance status checks, scheduled events
ec2.DescribeVolumes                   # attached EBS volumes: type, size, IOPS, encryption
ec2.DescribeSnapshots (self)          # snapshot recency per volume (owner-id = self)
ec2.DescribeSecurityGroups            # ingress/egress rules for attached SGs
ec2.DescribeSubnets                   # subnet AZ, public/private
ec2.DescribeVpcs                      # VPC context
ec2.DescribeAddresses                 # Elastic IPs (associated / idle)
ec2.DescribeKeyPairs                  # key pair inventory
autoscaling.DescribeAutoScalingGroups # ASG membership, min/max/desired, health checks
autoscaling.DescribeLaunchConfigurations / ec2.DescribeLaunchTemplates
ec2.DescribeInstanceCreditSpecifications  # T-family unlimited vs standard
ssm.DescribeInstanceInformation       # SSM managed status (patch/agent) — optional
```

Capture per instance: instance ID, name tag, type/family, AMI ID and age,
platform (Linux/Windows), lifecycle (on-demand/spot), placement AZ, VPC/subnet,
public IP presence, IAM instance profile, IMDS configuration (`HttpTokens`,
`HttpEndpoint`, `HttpPutResponseHopLimit`), monitoring (basic/detailed),
`EbsOptimized`, termination protection, tenancy, and all tags.

## Step 3: Collect CloudWatch Metrics

Retrieve a 14-day window (`Period=3600`) via `cloudwatch.GetMetricData` for each
instance and volume. See `references/metrics-thresholds.md` for the metric list,
statistics, and severity thresholds. Also collect:

```
cloudwatch.DescribeAlarms / DescribeAlarmsForMetric   # alarm coverage per instance
```

If detailed monitoring is disabled, note that metric granularity is 5 minutes
and state this as a limitation for any right-sizing conclusion.

## Step 4: Analyze Against the Five Pillars

Apply the checklist in `references/best-practices-checklist.md`. Summary of
dimensions:

1. **Security** — IMDSv2 enforced (`HttpTokens=required`), no overly permissive
   security group ingress (0.0.0.0/0 on 22/3389/database ports), EBS encryption,
   IAM instance profile scoped (not `*`), no long-lived embedded credentials,
   AMI patch currency, SSM-managed for patching, public IP necessity.
2. **Reliability** — Multi-AZ spread for ASG, ASG health checks (ELB vs EC2),
   EBS snapshot recency and backup policy (AWS Backup / DLM), instance status
   check health, Auto Recovery / termination protection where appropriate,
   Spot interruption handling.
3. **Performance Efficiency** — CPU / memory (if CloudWatch agent present) /
   network / EBS throughput utilization vs instance limits, T-family CPU credit
   balance and unlimited-mode surprises, current-generation and Graviton
   candidacy, `EbsOptimized` on EBS-heavy workloads, gp2 → gp3 migration.
4. **Cost Optimization** — idle / stopped-but-billing (EBS, EIP), underutilized
   right-sizing candidates, previous-generation instances, unattached EBS
   volumes, idle Elastic IPs, Savings Plans / Reserved Instance / Spot
   candidacy, gp2 → gp3 savings.
5. **Operational Excellence** — required tags present, CloudWatch alarm
   coverage, detailed monitoring, SSM agent managed, scheduled maintenance /
   events pending, launch-template vs launch-configuration (deprecated).

## Step 5: Assign Severity

Use the shared severity model. Every finding gets exactly one severity:

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | 24–48 hours |
| HIGH | Significant gap that could lead to incidents | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |

## Step 6: Generate the Report

Produce one report artifact per instance (or one fleet report for multi-instance
reviews), named `ec2-review-<instance-or-scope>-<YYYY-MM-DD>.md`.

Report structure:
1. **Summary** — resource identity, overall rating, count of findings by severity.
2. **Assessment table** — one row per pillar with status (GOOD / NEEDS ATTENTION
   / NOT_ASSESSED) and headline.
3. **Findings** — grouped by severity (CRITICAL first). Each finding includes:
   the observation (with the concrete value/metric that triggered it), the
   affected resource, the risk, and a specific remediation with expected outcome
   and any downtime/impact precondition.
4. **Right-sizing appendix** (if performance/cost data available) — per-instance
   observed utilization vs a recommended type.
5. **Coverage note** — what was assessed, what was NOT_ASSESSED and why (missing
   metrics, permissions, or memory data without the CloudWatch agent).

## Prerequisites

Requires the DevOps Agent's primary cloud-source role to have read access to
EC2, EBS, Auto Scaling, CloudWatch, and (optionally) SSM and Cost Explorer.
See the README for the exact IAM action list. The skill never calls a mutating
API.
