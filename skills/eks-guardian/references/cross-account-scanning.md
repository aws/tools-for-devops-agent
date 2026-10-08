# EKS Guardian — Cross-Account Scanning Guide

Instructions for scanning EKS clusters across multiple AWS accounts using the DevOps Agent.

---

## Overview

In enterprise environments, EKS clusters are typically spread across multiple AWS accounts (dev, staging, production, shared services). EKS Guardian supports fleet-wide scanning by leveraging the DevOps Agent's cross-account IAM access.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  DevOps Agent Space (Hub Account)                           │
│  IAM Role: AgentSpaceRole                                   │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ Account A   │  │ Account B   │  │ Account C   │       │
│  │ (Dev)       │  │ (Staging)   │  │ (Prod)      │       │
│  │ 3 clusters  │  │ 2 clusters  │  │ 5 clusters  │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Setup

### Step 1: Configure Cloud Sources

In the DevOps Agent Operator Web App:

1. Navigate to **Capabilities** → **Cloud**
2. Add each AWS account as a cloud source
3. Ensure the Agent Space IAM role can assume a role in each target account

### Step 2: Create Cross-Account IAM Role (per target account)

In each target account, create an IAM role that the Agent Space role can assume:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<agent-space-account-id>:role/<AgentSpaceRoleName>"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<your-external-id>"
        }
      }
    }
  ]
}
```

### Step 3: Attach Read-Only EKS Permissions (per target account)

Attach this policy to the cross-account role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EKSReadOnly",
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters",
        "eks:ListNodegroups",
        "eks:DescribeNodegroup",
        "eks:ListAddons",
        "eks:DescribeAddon",
        "eks:DescribeAddonVersions",
        "eks:ListInsights",
        "eks:DescribeInsight",
        "eks:ListAccessEntries",
        "eks:DescribeAccessEntry",
        "eks:ListAssociatedAccessPolicies",
        "eks:ListPodIdentityAssociations"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EC2ReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeSubnets",
        "ec2:DescribeVpcs",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeVpcEndpoints",
        "ec2:DescribeNatGateways",
        "ec2:DescribeFlowLogs"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "logs:FilterLogEvents",
        "logs:DescribeLogGroups"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudTrailReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### Step 4: Create EKS Access Entry (per cluster, per account)

For K8s API access in each target account:

```bash
aws eks create-access-entry \
  --cluster-name <cluster-name> \
  --principal-arn arn:aws:iam::<target-account-id>:role/<CrossAccountRoleName> \
  --type STANDARD

aws eks associate-access-policy \
  --cluster-name <cluster-name> \
  --principal-arn arn:aws:iam::<target-account-id>:role/<CrossAccountRoleName> \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonAIOpsAssistantPolicy \
  --access-scope type=cluster
```

## Usage Patterns

### Scan all clusters in all accounts

> "Run an EKS Guardian review across all accounts and regions"

### Scan specific accounts

> "Review EKS clusters in the production account (123456789012) only"

### Compare across accounts

> "Compare EKS security posture between dev and production accounts"

### Fleet-wide summary

> "Generate a fleet summary showing cluster health across all accounts"

## Fleet Report Format

When scanning multiple accounts, EKS Guardian generates:

1. **Individual cluster reports** — one per cluster (same as single-cluster mode)
2. **Fleet summary report** — aggregated view across all clusters:

```markdown
# EKS Fleet Summary — <date>

## Account Overview
| Account | Alias | Region | Clusters | Critical | High | Medium |
|---------|-------|--------|----------|----------|------|--------|
| 111...  | dev   | us-east-1 | 3     | 0        | 2    | 8      |
| 222...  | prod  | us-east-1 | 5     | 1        | 5    | 12     |

## Common Issues (appear in 2+ clusters)
| Finding | Affected Clusters | Severity |
|---------|-------------------|----------|

## Per-Account Grade
| Account | Security | Reliability | Networking | Cost | Overall |
|---------|----------|-------------|------------|------|---------|
```

## Best Practices for Multi-Account Scanning

1. **Use AWS Organizations SCPs** to enforce baseline security (IMDSv2, encryption) — reduces findings volume
2. **Tag clusters consistently** (environment, team, cost-center) for meaningful grouping
3. **Run fleet scans weekly** to track drift across accounts
4. **Prioritize production accounts** for immediate action; use dev account findings for prevention
5. **Use comparison mode** to identify configuration drift between environments (dev vs prod should match except for scale)
