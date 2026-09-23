# Database Audit Automation — AWS DevOps Agent Skill

An AI-powered database auditing automation skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Guides the agent through deploying, configuring, operating, and troubleshooting an automated database audit pipeline for Amazon RDS SQL Server and Amazon Aurora PostgreSQL — covering audit log collection, AI-based anomaly detection, and compliance report generation.

**Source repository:** https://github.com/aws-samples/sample-database-auditing-automation

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to:

1. Deploy the Database Auditing Automation Solution via CloudFormation.
2. Configure database-native auditing — `pgAudit` for Aurora PostgreSQL, SQL Server native audit for RDS SQL Server — and enable CloudWatch Logs export.
3. Stream and normalize audit logs through CloudWatch Logs and Lambda into versioned, encrypted S3 storage.
4. Run scheduled AI analysis (Lambda + Amazon Bedrock) over recent audit activity to detect anomalies and privileged-user access patterns.
5. Generate compliance reports (SOX, PCI-DSS, HIPAA) and route high-severity findings to SNS for alerting.
6. Troubleshoot the audit log pipeline when logs stop flowing or reports fail to generate.

## Architecture

```
RDS/Aurora → CloudWatch Logs → Lambda (Log Processor) → S3 (Audit Logs)
                                                          ↓
                                                Lambda (AI Analyzer)
                                                          ↓
                                                Bedrock (Claude 3.5 Sonnet)
                                                          ↓
                                                S3 (Reports) + SNS (Alerts)
```

| Component | Service | Purpose |
|-----------|---------|---------|
| Log Collection | CloudWatch Logs + Lambda | Stream and normalize audit logs |
| Log Storage | S3 (Versioned, Encrypted) | Store structured audit data with lifecycle policies |
| Anomaly Detection | Lambda + Bedrock | Scheduled AI analysis of recent logs |
| Report Generation | Lambda + Bedrock | Compliance reports |
| Alerting | SNS | Real-time notifications for high-severity findings |
| Report Retention | S3 Object Lock (COMPLIANCE) | Immutable audit trail |

## When It Activates

This skill is intended for **Chat tasks**. It triggers when a user asks about:

- Setting up database auditing on RDS SQL Server or Aurora PostgreSQL
- Deploying the database audit automation solution
- Generating compliance reports from database audit logs
- Detecting anomalies in database activity
- Monitoring privileged database user access
- Database audit compliance (SOX, PCI-DSS, HIPAA)
- Configuring pgAudit or SQL Server native audit
- Analyzing database security events with AI
- Troubleshooting audit log pipelines

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. Amazon Bedrock access

The solution uses Amazon Bedrock (Claude 3.5 Sonnet) for anomaly detection and report generation. Enable model access in the target account/region before deploying.

### 3. IAM permissions

Deploying and operating the solution requires permissions beyond read-only — CloudFormation stack operations, RDS/Aurora audit configuration changes, and access to Lambda, S3, EventBridge, SNS, and Bedrock. Review and scope these to your environment before running. The skill's investigative/reporting steps operate against audit data already in S3 and CloudWatch Logs.

### 4. Target databases

Amazon RDS SQL Server and/or Amazon Aurora PostgreSQL instances you want to audit.

## Skill Contents

```
database-audit-automation/
├── SKILL.md        # main skill instructions (with frontmatter)
├── README.md       # this file
├── CHANGELOG.md    # version history
└── evals/          # evaluation data (not included in upload zip)
```

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review
> and testing. Validate in a non-production environment first. Enabling database auditing,
> modifying parameter/option groups, and deploying the audit pipeline change live database
> configuration — review the CloudFormation template and audit settings, and tune anomaly
> thresholds and compliance mappings to your own workload and regulatory requirements.
