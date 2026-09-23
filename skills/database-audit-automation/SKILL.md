---
name: database-audit-automation
description: Interpret and troubleshoot the AI-powered database auditing automation solution for Amazon RDS SQL Server and Aurora PostgreSQL. Use to read and explain the compliance reports it generates, reason about anomaly alerts, and diagnose the audit log pipeline (CloudWatch Logs → Lambda → S3 → Bedrock). Deployment and operations are documented in README.md.
metadata:
  author: bbhavini0502
  version: "2.1.0"
  aws-devops-agent-skills.agent-types: "Chat tasks"
  aws-devops-agent-skills.aws-services: "Amazon RDS, Amazon Aurora, Amazon Bedrock, AWS Lambda, Amazon S3, Amazon EventBridge, Amazon SNS"
  aws-devops-agent-skills.technical-domains: "Databases, Security"
---

# Database Audit Automation

## Overview

Use this skill to **interpret** and **troubleshoot** the Database Auditing Automation Solution — an AI-powered system that collects database audit logs, runs hourly anomaly detection, and generates monthly compliance reports for Amazon RDS SQL Server and Amazon Aurora PostgreSQL.

This skill assumes the solution is **already deployed**. It exists for the two jobs that need judgment, not a fixed runbook:

1. **Interpreting the AI-generated compliance report** stored in S3.
2. **Diagnosing the audit pipeline** when logs stop flowing or reports/alerts don't appear.

Deploying the solution, turning on database auditing, and the routine operations commands (invoking a Lambda, listing S3) are **deterministic user steps** and are documented in `README.md` and `assets/`. Do not recite those steps from here — if the user asks how to deploy or operate the solution, point them to `README.md`. That keeps this skill focused on what the agent actually adds.

## Agent Scope and Behavior

This is a **Chat-task** skill. Follow these rules:

- **You interpret and diagnose. You do not change infrastructure.** Deploying the stack, running scripts, modifying databases, and running audit-setup SQL are user actions documented in `README.md`.
- Work **read-only**: read S3 objects (reports, audit logs) and CloudWatch Logs, and use `describe`/`list` calls. Do not call `put`, `modify`, `update`, `delete`, or `invoke`.
- When a fix requires a state change, describe it and point the user to the exact command or asset in `README.md` for them to run — do not run it.
- Ground every answer in the resource names, S3 paths, and thresholds documented below. **Do not invent** bucket names, ARNs, account IDs, or file paths — read them from the user's environment or ask.

## When to Use This Skill

Activate when the user asks about:
- Understanding or explaining a database audit **compliance report**
- Why an **anomaly alert** did or didn't fire, or what a finding means
- Monitoring privileged database user access, or audit compliance (SOX, PCI-DSS, HIPAA), in the context of this solution
- **Troubleshooting** the audit log pipeline (no logs in S3, reports not generated, Bedrock access errors, high Lambda cost)

If the user instead wants to **deploy** the solution or **turn on** pgAudit / SQL Server audit, that's a setup task — direct them to `README.md`.

## Architecture

```
RDS/Aurora → CloudWatch Logs → Lambda (Log Processor) → S3 (Audit Logs)
                                                          ↓
                                                Lambda (Anomaly Detector)
                                                          ↓
                                                Bedrock (Claude 3.5 Sonnet)
                                                          ↓
                                          SNS (Alerts) ; S3 (Monthly Reports)
```

- The **anomaly detector** runs hourly (EventBridge), reads the recent audit logs from S3, asks Bedrock to classify anomalies, and **sends HIGH-severity findings via SNS**. It returns counts in its response. It does **not** write a findings file to S3 — SNS alerts and the monthly report are the durable records.
- The **report generator** writes a monthly compliance report to S3.

### Deployed resource names and locations

Default names use the project prefix `db-audit-ai`. If the user changed `ProjectName` at deploy time, substitute their prefix. `{ACCOUNT-ID}` is their 12-digit AWS account ID.

- **Lambda:** `db-audit-ai-log-processor`, `db-audit-ai-anomaly-detector`, `db-audit-ai-report-generator`
- **Audit logs (input):** `s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/<db_type>/audit-logs/<date>/...` where `<db_type>` is `postgresql` or `sqlserver`
- **Monthly reports:** `s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/<YYYY-MM>/audit-report.txt` (plain text)
- **SNS alerts:** topic `db-audit-ai-anomaly-alerts`
- **EventBridge:** `db-audit-ai-hourly-anomaly-check` (anomaly detection schedule)
- **Privileged-user list:** `PRIVILEGED_USERS` environment variable on `db-audit-ai-anomaly-detector`

## Required Agent Permissions

To interpret reports and diagnose the pipeline, the agent's cloud-source role needs **read** access beyond a bare describe-only posture. Confirm these are present; if a call is denied, tell the user which permission is missing rather than guessing at the data:

- `s3:GetObject` and `s3:ListBucket` on `db-audit-ai-reports-{ACCOUNT-ID}` (read the compliance report) and `db-audit-ai-audit-logs-{ACCOUNT-ID}` (read audit logs when reasoning about anomalies)
- `logs:FilterLogEvents`, `logs:GetLogEvents`, `logs:DescribeLogGroups`, `logs:DescribeLogStreams` (inspect the log-processor / detector Lambda logs)
- `rds:DescribeDBInstances`, `rds:DescribeDBClusters` (check CloudWatch Logs export config)
- `lambda:GetFunctionConfiguration`, `events:DescribeRule` (check timeout and schedule during troubleshooting)

These are read-only. The agent does not need — and should not use — write permissions.

## Interpreting Compliance Reports

The report is at `s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/<YYYY-MM>/audit-report.txt`. To interpret it:

1. Ask the user for their account ID (and prefix, if customized) and the month, or list the `monthly-reports/` prefix to find available reports.
2. Read the report object (`s3:GetObject`). If the user has already pasted the report into chat, use that and skip the S3 read.
3. The report contains these sections — map the user's question to the relevant one and explain it: **Executive Summary, Login Activity Analysis, Privileged Access Monitoring, Change Pattern Analysis, Compliance Findings, Risk Assessment, Recommendations.**
4. Explain findings in terms of the anomaly categories and thresholds below, and translate them into concrete risk and next actions.

Compliance posture the report relies on: S3 Object Lock (COMPLIANCE mode, 7-year retention) on the reports bucket, versioned + encrypted buckets, CloudTrail access logging, blocked public access, lifecycle tiering (S3-IA at 90 days, Glacier at 180 days for logs).

## Reasoning About Anomaly Alerts

There is **no persisted anomaly-findings file** — do not tell the user to fetch one. The durable records are the **SNS alert** the user received and the anomaly-related sections of the **monthly report**. To reason about a specific alert or "why did/didn't this fire", read the underlying **audit logs** in S3 for the relevant window and apply these detection rules:

| # | Pattern | Threshold | Severity |
|---|---------|-----------|----------|
| 1 | Failed Login Attempts | >3 in 10 minutes | HIGH |
| 2 | Unusual Login Times | Outside 9 AM – 6 PM | MEDIUM |
| 3 | Privileged User Activities | Any DBA action | MEDIUM–HIGH |
| 4 | Suspicious Query Patterns | Bulk SELECT on sensitive tables, exports | CRITICAL |
| 5 | Unauthorized Schema Changes | DDL without CR reference | HIGH |

How the detector works: EventBridge triggers it hourly → it reads the last window of logs from `db-audit-ai-audit-logs-{ACCOUNT-ID}/<db_type>/audit-logs/<date>/` → Bedrock classifies against the `PRIVILEGED_USERS` list and the rules above → HIGH-severity findings fire an SNS alert. If the user wants to change sensitivity, the rules live in the Bedrock prompt inside the `db-audit-ai-anomaly-detector` Lambda and the watch list is the `PRIVILEGED_USERS` env var — describe the change and point them to `README.md`; don't modify it yourself.

## Troubleshooting

Diagnose read-only; recommend fixes for the user to apply.

### No logs appearing in S3
1. Verify CloudWatch Logs export is enabled on the database (`rds describe-db-instances` / `describe-db-cluster`, check `EnabledCloudwatchLogsExports`).
2. Check `db-audit-ai-log-processor` Lambda logs for errors (filter its log group for `ERROR`).
3. Verify auditing is configured **inside** the database — pgAudit extension loaded (Aurora PostgreSQL) or SQL Server Audit enabled. If not, this is a user setup step in `README.md`.

### Bedrock access denied
Claude 3.5 Sonnet model access must be enabled in the account/region (Console → Bedrock → Model access). User action.

### Reports not generated
1. Check the report generator's schedule (EventBridge) and the `db-audit-ai-report-generator` timeout is 900s.
2. Confirm the reports bucket exists and the report month you expect is present under `monthly-reports/<YYYY-MM>/`.
3. Check the report-generator Lambda logs for errors.

### High Lambda cost
Suggest (as user changes): reduce anomaly-detection frequency (hourly → every 4 hours) via the EventBridge schedule, reduce `max_tokens` in the Bedrock calls, or filter low-value log events before sending to Bedrock.

## References

- Deployment, audit configuration, and operations commands (user steps): this skill's `README.md`
- Vendored assets: `assets/templates/`, `assets/sql/`, `assets/deploy/`
- Source solution: https://github.com/aws-samples/sample-database-auditing-automation
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/
- pgAudit: https://github.com/pgaudit/pgaudit
- RDS SQL Server Audit: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.SQLServer.Options.Audit.html
- S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
