---
name: database-audit-automation
description: Deploy and manage AI-powered database auditing automation for Amazon RDS SQL Server and Aurora PostgreSQL. Covers deployment, audit configuration, anomaly detection, compliance reporting, and troubleshooting using Amazon Bedrock, Lambda, EventBridge, and S3.
metadata:
  author: bbhavini0502
  version: "2.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks"
  aws-devops-agent-skills.aws-services: "Amazon RDS, Amazon Aurora, Amazon Bedrock, AWS Lambda, Amazon S3, Amazon EventBridge, Amazon SNS"
  aws-devops-agent-skills.technical-domains: "Databases, Security"
---

# Database Audit Automation

## Overview

Use this skill to help a user operate, interpret, and troubleshoot the **Database Auditing Automation Solution** — an AI-powered system that automates database audit log collection, anomaly detection, and compliance report generation for Amazon RDS SQL Server and Amazon Aurora PostgreSQL.

The solution is deployed by the user from a CloudFormation template and its supporting scripts (see the skill's `README.md` and `assets/` directory). This skill assumes the solution is already deployed unless the user is asking how to deploy it, in which case direct them to the setup steps in `README.md`.

## Agent Scope and Behavior

This is a **Chat-task** skill. Follow these rules:

- **You provide guidance, interpretation, and diagnosis. You do not execute infrastructure changes.** Deploying the CloudFormation stack, running shell scripts, creating parameter/option groups, modifying database clusters, and running audit-setup SQL inside the database engine are all actions the **user** performs. When such a step is needed, tell the user the exact command or file to run and where to find it (`assets/...`) — do not attempt to run it yourself.
- Prefer read-only investigation (describe/list/get and reading logs and S3 objects) when helping diagnose a problem.
- When you recommend a command that changes state (a `modify-*`, `deploy`, `update-*`, or SQL DDL), present it as a step for the user to review and run, and briefly note its effect.
- Ground every answer in this skill's documented resource names, thresholds, and pipeline. Do not invent resource names, ARNs, or account IDs — ask the user or read them from their environment.

## When to Use This Skill

Activate this skill when the user asks about:
- Setting up database auditing on RDS SQL Server or Aurora PostgreSQL
- Deploying the database audit automation solution
- Generating compliance reports from database audit logs
- Detecting anomalies in database activity
- Monitoring privileged database user access
- Database audit compliance (SOX, PCI-DSS, HIPAA)
- Configuring pgAudit or SQL Server native audit
- Analyzing database security events with AI
- Troubleshooting audit log pipelines

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

### Components

| Component | Service | Purpose |
|-----------|---------|---------|
| Log Collection | CloudWatch Logs + Lambda | Stream and normalize audit logs |
| Log Storage | S3 (Versioned, Encrypted) | Store structured audit data with lifecycle policies |
| Anomaly Detection | Lambda + Bedrock | Hourly AI analysis of recent logs |
| Report Generation | Lambda + Bedrock | Monthly compliance reports |
| Alerting | SNS | Real-time notifications for high-severity findings |
| Report Retention | S3 Object Lock (COMPLIANCE) | 7-year immutable audit trail |
| Dashboard | CloudFront + API Gateway + Lambda | Web UI for team access |

### Deployed Resource Names

Default names created by the CloudFormation stack (project prefix `db-audit-ai`). Use these when helping the user locate or inspect resources:

- **Lambda:** `db-audit-ai-log-processor`, `db-audit-ai-anomaly-detector`, `db-audit-ai-report-generator`
- **S3:** `db-audit-ai-audit-logs-{ACCOUNT-ID}`, `db-audit-ai-reports-{ACCOUNT-ID}`
- **EventBridge rule (reports):** `db-audit-ai-monthly-report`
- **Privileged-user list:** `PRIVILEGED_USERS` environment variable on the anomaly detector Lambda

If the user changed `ProjectName` at deploy time, substitute their prefix.

## Helping the User Deploy or Configure (point to README/assets)

When the user wants to deploy the solution or turn on database auditing, these are **user actions** — provide the steps and the asset locations, and let the user run them:

- **Deploy the solution:** the CloudFormation template `assets/templates/infrastructure.yaml` and the helper script in `assets/deploy/deploy.md`. Full walkthrough is in `README.md`.
- **Aurora PostgreSQL auditing (pgAudit):** the user creates a custom parameter group with `shared_preload_libraries = pgaudit`, applies it, runs the SQL in `assets/sql/aurora-postgresql-audit-setup.md`, and enables CloudWatch Logs export for the `postgresql` log type.
- **RDS SQL Server auditing:** the user creates an Option Group with `SQLSERVER_AUDIT`, applies it, runs the SQL in `assets/sql/rds-sqlserver-audit-setup.md`, and enables CloudWatch Logs export for `error` and `agent` logs.
- **Optional dashboard:** `assets/templates/ui-infrastructure.yaml` and the script in `assets/deploy/deploy-ui.md`.
- **Existing `.sqlaudit` binary files:** the parser stack `assets/templates/sqlaudit-parser-stack.yaml` and the script in `assets/deploy/upload-sqlaudit.md`.

(SQL and shell assets are stored as `.md` files because DevOps Agent skill uploads accept only a fixed set of file extensions; the code is in fenced blocks inside each file.)

Do not run these for the user. Summarize the step, name the exact asset, and note that it must be run in their environment. The detailed commands live in `README.md`.

## Operations Guidance

When the user asks how to operate the deployed solution, give them the command to run (these are user-run CLI calls; you present them, the user executes):

- **Generate an on-demand report:** invoke the `db-audit-ai-report-generator` Lambda. Reports land in `s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/<YYYY>/<MM>/`.
- **Run manual anomaly detection:** invoke the `db-audit-ai-anomaly-detector` Lambda.
- **View reports / logs:** list and copy objects under the reports and audit-logs S3 buckets.
- **Configure privileged users:** update the `PRIVILEGED_USERS` environment variable on the anomaly detector Lambda.

Always fill in the user's real account ID and region rather than placeholders, and confirm the resource prefix if they customized `ProjectName`.

## Interpreting Anomaly Detection

The anomaly detector classifies five categories. Use this table to explain findings and set expectations about severity:

| # | Pattern | Threshold | Severity |
|---|---------|-----------|----------|
| 1 | Failed Login Attempts | >3 in 10 minutes | HIGH |
| 2 | Unusual Login Times | Outside 9 AM – 6 PM | MEDIUM |
| 3 | Privileged User Activities | Any DBA action | MEDIUM–HIGH |
| 4 | Suspicious Query Patterns | Bulk SELECT on sensitive tables, exports | CRITICAL |
| 5 | Unauthorized Schema Changes | DDL without CR reference | HIGH |

### How the pipeline works

1. **EventBridge** triggers the anomaly detector Lambda every hour.
2. The Lambda pulls the last hour's logs from S3.
3. **Bedrock (Claude)** analyzes the logs against the privileged-user list and the five detection rules and returns structured JSON (`type`, `severity`, `description`).
4. HIGH or CRITICAL findings fire an **SNS alert** immediately.
5. All findings are stored in S3 for the audit trail.

When a user asks why an alert did or didn't fire, reason from these thresholds and this flow. If they want to tune sensitivity, the detection rules live in the Bedrock prompt inside the anomaly detector Lambda, and the privileged-user list is the `PRIVILEGED_USERS` environment variable.

## Interpreting Compliance Reports

The AI-generated monthly report contains: Executive Summary, Login Activity Analysis, Privileged Access Monitoring, Change Pattern Analysis, Compliance Findings, Risk Assessment, and Recommendations. When a user shares or asks about a report, map their question to the relevant section and explain the finding in terms of the anomaly categories and thresholds above.

Compliance posture is enforced by: S3 Object Lock (COMPLIANCE mode, 7-year retention) on the reports bucket, versioned + encrypted buckets, CloudTrail logging of access, blocked public access, and lifecycle tiering (S3-IA at 90 days, Glacier at 180 days for logs).

## Troubleshooting

Diagnose these by reading configuration and logs (read-only). Recommend fixes for the user to apply.

### No logs appearing in S3

1. Verify CloudWatch Logs export is enabled on the database (`describe-db-instances` / `describe-db-cluster`, check `EnabledCloudwatchLogsExports`).
2. Check the `db-audit-ai-log-processor` Lambda logs for errors (filter its log group for `ERROR`).
3. Verify auditing is configured **inside** the database — the pgAudit extension is loaded (Aurora PostgreSQL) or SQL Server Audit is enabled. If not, this is a user setup step (see the deploy/config section and `README.md`).

### Bedrock access denied

Model access for Claude 3.5 Sonnet must be enabled in the account/region (AWS Console → Bedrock → Model access). This is a user action.

### Reports not generated

1. Check the EventBridge rule `db-audit-ai-monthly-report` (`describe-rule`).
2. Verify the report-generator Lambda timeout is 900s (15 min).
3. Check S3 permissions on the reports bucket.

### High Lambda costs

Suggest: reduce anomaly-detection frequency (hourly → every 4 hours) via the EventBridge schedule, reduce `max_tokens` in the Bedrock calls, or filter low-value log events before sending to Bedrock.

## References

- Setup, deployment, and command details for users: this skill's `README.md`
- Vendored deployment assets: `assets/templates/`, `assets/sql/`, `assets/deploy/`
- Source solution: https://github.com/aws-samples/sample-database-auditing-automation
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/
- pgAudit: https://github.com/pgaudit/pgaudit
- RDS SQL Server Audit: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.SQLServer.Options.Audit.html
- S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
