# aws-fsxn-diagnostics

An AWS DevOps Agent skill that diagnoses Amazon FSx for NetApp ONTAP file
systems and answers questions about them using the file system's real
configuration and metrics.

> **Disclaimer:** This skill is sample code, not intended for production use
> without additional review and testing. Users should validate in a
> non-production environment first.

## What it does

The skill teaches DevOps Agent how to investigate an FSx for NetApp ONTAP file
system through AWS control-plane APIs. It reads the FSx API, CloudWatch
`AWS/FSx` metrics, CloudTrail, and the state of the services the file system
depends on (VPC networking, AWS Directory Service / Active Directory, AWS KMS,
AWS Backup, AWS Health). It then reports findings with a severity and the
evidence behind each one, a likely root cause, and recommended fixes.

It covers all four deployment types: Multi-AZ 2, Single-AZ 2, Multi-AZ 1 and
Single-AZ 1.

Typical problems it handles:

- Slow performance: throughput, IOPS, disk and network burst exhaustion, per-file-server and aggregate utilization
- SSD capacity running out, growth rate and headroom, storage tiering that isn't reclaiming space
- NFS, SMB or iSCSI clients that can't mount or connect: security groups, NACLs, routes, DNS, AD domain join
- SnapMirror lag, file systems or volumes stuck in `MISCONFIGURED` or `FAILED`, stuck administrative actions
- Backup, snapshot and recovery questions: retention, snapshot policies, what can be restored
- Change audits: what changed and who changed it (CloudTrail)
- Concerns with no clear symptom yet ("something seems off"): a baseline sweep for conditions that cause or precede incidents
- Sizing and deployment-type fit
- How-to and configuration questions (tiering, snapshot policies, SVMs, security style), answered against the file system's actual settings
- ONTAP CLI requests such as `vol show`: answered with the equivalent data from the AWS API, plus a filled-in, read-only ONTAP CLI command pack the operator can run themselves

### Scope

This skill diagnoses problems with a specific file system: a symptom, an
incident, a question about its configuration, or a change request. It is not a
best-practices posture audit.

What it covers beyond reading the AWS APIs: NFS/SMB/iSCSI access and Active
Directory join failures (directory existence, DNS reachability), `MISCONFIGURED` /
`FAILED` states and stuck administrative actions, CloudTrail change history linked
to findings, burst-credit and per-HA-pair (`FileServer` / `Aggregate`) analysis,
SnapMirror lag signals, false-signal suppression, refusal of change requests with
the operator steps instead, an escalation-readiness packet for AWS Support, and a
read-only ONTAP CLI command pack, filled in with the real SVM and volume names, for
the operator to run.

### Read-only by design

The skill never changes anything. It never calls a mutating API and never
offers to. If asked to resize, fix or delete something, it explains the
impact and gives the steps for the operator to do it. Before suggesting
deletion of backups or snapshots, it states the recovery impact first. It
makes the read-only checks that inform a decision itself instead of offering
them, and it never logs in to ONTAP or asks for ONTAP (`fsxadmin`) credentials.

Anything it could not check, for example because a permission is missing, is
reported under **Data gaps** rather than being called healthy.

## Prerequisites

### AWS resources

- An Amazon FSx for NetApp ONTAP file system in an AWS account connected to your DevOps Agent Agent Space.
- Optional, depending on the problem:
  - VPC flow logs delivered to CloudWatch Logs (connectivity analysis)
  - CloudTrail event history (change audits; enabled by default in every account)
  - A Business Support+, Enterprise Support or Unified Operations plan for the AWS Health checks. Without one, Health is reported as a data gap.

### IAM permissions

Attach [`automation/iam-policy.json`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aws-fsxn-diagnostics/automation/iam-policy.json) to the role
DevOps Agent uses for the connected account. It contains **38 read-only
actions** and no action that can change infrastructure. See
[`automation/README.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aws-fsxn-diagnostics/automation/README.md) for how to apply it.

| Service | Actions |
|---|---|
| Amazon FSx | `DescribeFileSystems`, `DescribeStorageVirtualMachines`, `DescribeVolumes`, `DescribeBackups`, `DescribeSnapshots`, `ListTagsForResource` |
| Amazon CloudWatch | `GetMetricData`, `GetMetricStatistics`, `ListMetrics`, `DescribeAlarms` |
| Amazon EC2 / VPC | `DescribeSecurityGroups`, `DescribeNetworkAcls`, `DescribeRouteTables`, `DescribeVpcs`, `DescribeSubnets`, `DescribeNetworkInterfaces`, `DescribeDhcpOptions`, `DescribeInstances`, `DescribeFlowLogs`, `DescribeVpcPeeringConnections`, `DescribeTransitGatewayAttachments`, `DescribeTransitGatewayVpcAttachments`, `DescribeTransitGatewayRouteTables`, `SearchTransitGatewayRoutes` |
| AWS Directory Service | `DescribeDirectories`, `DescribeDomainControllers` |
| AWS CloudTrail | `LookupEvents` |
| Amazon CloudWatch Logs | `DescribeLogGroups`, `StartQuery`, `GetQueryResults` |
| Amazon Route 53 Resolver | `ListResolverRules`, `ListResolverRuleAssociations` |
| AWS KMS | `DescribeKey` |
| AWS Backup | `ListBackupJobs`, `DescribeBackupVault` |
| AWS Health | `DescribeEvents`, `DescribeEventDetails`, `DescribeAffectedEntities` |

Notes:

- For customer managed KMS keys, the key policy must also allow the role to call `kms:DescribeKey`.
- No ONTAP management endpoint access and no AWS Secrets Manager access are required.
- Missing permissions don't break a run. The affected checks are listed under **Data gaps**.

## Using it with AWS DevOps Agent

### Install

1. Open your Agent Space in the DevOps Agent web app and go to **Skills**.
2. Choose **Add skill**, then **Upload skill**, and upload a zip of this folder. The archive's root folder must be `aws-fsxn-diagnostics/`.
3. Agent type: **Chat**.

### Agent types

| Agent type | Status |
|---|---|
| Chat | Supported and tested. `metadata.aws-devops-agent-skills.agent-types` is `CHAT` |
| Incident RCA and other agent types | Not targeted. They may be added in a later version once tested |

### Example prompts

You don't need to name the skill. DevOps Agent loads it when the question is
about FSx for NetApp ONTAP. Include the file system ID (`fs-…`) and Region
when you know them.

- "We have a heavy batch run on `fs-0123456789abcdef0` (us-east-1) next week. Check it for anything that could cause trouble and tell me what to fix first."
- "Users say our ONTAP file system has been slow for the last few days. What's going on?"
- "How much SSD headroom do we have on `fs-0123456789abcdef0`, and when will we run out at the current rate?"
- "Our Linux clients can't mount the NFS export from the ONTAP SVM. What's blocking them?"
- "What changed on `fs-0123456789abcdef0` in the last 14 days, and who made the changes?"
- "If someone deleted a folder on volume `vol1` yesterday, how would we get it back?"
- "How should we set up storage tiering for the volumes on `fs-0123456789abcdef0`?"
- "Show me the `vol show` output for `fs-0123456789abcdef0`."

### What you get back

- A summary naming the file system, Region and deployment type, e.g. "Multi-AZ 2 (`MULTI_AZ_2`)"
- Findings, each with a severity and the API call or metric it is based on
- A likely root cause, with what was observed kept separate from what was inferred
- Recommended fixes, written as steps for the operator to perform
- **Data gaps**: anything that could not be checked
- Where a data-plane check is needed, a read-only ONTAP CLI command pack filled in with the real SVM and volume names

## Limitations

- The skill has been validated against accounts with a single FSx for ONTAP file system in one Region. In accounts with several file systems or Regions, name the file system ID and Region in your prompt.
- CloudTrail and CloudWatch are regional. The skill must query the file system's own Region; a lookup in another Region returns no data.
- Deletions made by an NFS or SMB client are data-plane operations and don't appear in CloudTrail.
- The skill uses control-plane data only. ONTAP-internal state such as EMS events, export policies or aggregate details is covered by the ONTAP CLI pack, which the operator runs.
- FSx for Windows File Server, FSx for Lustre, FSx for OpenZFS and Amazon EFS are out of scope.

## Files

```
aws-fsxn-diagnostics/
├── SKILL.md                         skill definition and activation description
├── README.md                        this file
├── CHANGELOG.md                     version history
├── assets/
│   └── sample-fsx-context.json      sample file system context (placeholder IDs)
├── automation/
│   ├── iam-policy.json              least-privilege, read-only IAM policy
│   └── README.md                    how to apply the policy
├── evals/                           evaluation test cases and results
└── references/
    ├── REFERENCE.md                 failure-mode playbook
    ├── review-checks.md             required-check procedures, severity definitions, analysis rules
    ├── deployment-types.md          Multi-AZ 2 / Single-AZ 2 / Multi-AZ 1 / Single-AZ 1
    ├── cloudwatch-metrics.md        metric catalog and per-type query rules
    ├── cloudtrail-audit.md          change audit: who changed what
    ├── dependencies-and-errors.md   service dependency map and API error handling
    ├── ontap-cli-pack.md            operator-run, read-only ONTAP CLI commands
    └── unlisted-symptoms.md         approach for symptoms not covered elsewhere
```

## Author

shankarh1310
