---
name: database-audit-automation
description: Deploy and manage AI-powered database auditing automation for Amazon RDS SQL Server and Aurora PostgreSQL. Covers deployment, audit configuration, anomaly detection, compliance reporting, and troubleshooting using Amazon Bedrock, Lambda, EventBridge, and S3.
metadata:
  author: bbhavini0502
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks"
  aws-devops-agent-skills.aws-services: "Amazon RDS, Amazon Aurora, Amazon Bedrock, AWS Lambda, Amazon S3, Amazon EventBridge, Amazon SNS"
  aws-devops-agent-skills.technical-domains: "Databases, Security"
---

# Database Audit Automation

## Overview

This skill guides the agent through deploying, configuring, operating, and troubleshooting the Database Auditing Automation Solution — an AI-powered system that automates database audit log collection, anomaly detection, and compliance report generation for Amazon RDS SQL Server and Aurora PostgreSQL.

**Source Repository:** https://github.com/aws-samples/sample-database-auditing-automation

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

## Deployment

### Prerequisites

1. AWS Account with appropriate permissions
2. AWS CLI configured
3. Amazon Bedrock access enabled (Claude 3.5 Sonnet model)
4. RDS SQL Server and/or Aurora PostgreSQL instances

### Deploy via CloudFormation

```bash
# Upload template to S3
aws s3 cp infrastructure.yaml s3://YOUR-BUCKET/db-audit-ai/infrastructure.yaml

# Deploy stack
aws cloudformation deploy \
    --template-file infrastructure.yaml \
    --stack-name db-audit-ai \
    --capabilities CAPABILITY_IAM \
    --region us-east-1
```

### Deploy Dashboard (Optional)

```bash
chmod +x deploy-ui.sh
./deploy-ui.sh
```

## Database Audit Configuration

### Aurora PostgreSQL (pgAudit)

1. Create a custom parameter group with `shared_preload_libraries = pgaudit`
2. Apply the parameter group to the cluster
3. Run the audit setup SQL:

```sql
-- aurora-postgresql-audit-setup.sql
CREATE EXTENSION IF NOT EXISTS pgaudit;

-- Audit all DDL and DML
ALTER SYSTEM SET pgaudit.log = 'ddl, write, role';
ALTER SYSTEM SET pgaudit.log_catalog = on;
ALTER SYSTEM SET pgaudit.log_relation = on;
ALTER SYSTEM SET pgaudit.log_statement_once = off;

SELECT pg_reload_conf();
```

4. Enable CloudWatch Logs export:

```bash
aws rds modify-db-cluster \
    --db-cluster-identifier YOUR-CLUSTER \
    --cloudwatch-logs-export-configuration '{"LogTypesToEnable":["postgresql"]}' \
    --region us-east-1
```

### RDS SQL Server (Native Audit)

1. Create an Option Group with `SQLSERVER_AUDIT` option
2. Apply to the RDS instance
3. Run the audit setup SQL:

```sql
-- rds-sqlserver-audit-setup.sql
USE [master]
GO

CREATE SERVER AUDIT [ServerAudit]
TO FILE (FILEPATH = 'D:\rdsdbdata\SQLAudit\')
WITH (QUEUE_DELAY = 1000, ON_FAILURE = CONTINUE);
GO

ALTER SERVER AUDIT [ServerAudit] WITH (STATE = ON);
GO

CREATE SERVER AUDIT SPECIFICATION [ServerAuditSpec]
FOR SERVER AUDIT [ServerAudit]
ADD (FAILED_LOGIN_GROUP),
ADD (SUCCESSFUL_LOGIN_GROUP),
ADD (DATABASE_PERMISSION_CHANGE_GROUP),
ADD (SCHEMA_OBJECT_CHANGE_GROUP),
ADD (SERVER_ROLE_MEMBER_CHANGE_GROUP)
WITH (STATE = ON);
GO
```

4. Enable CloudWatch Logs export:

```bash
aws rds modify-db-instance \
    --db-instance-identifier YOUR-INSTANCE \
    --cloudwatch-logs-export-configuration '{"LogTypesToEnable":["error","agent"]}' \
    --region us-east-1
```

## Operations

### Generate On-Demand Report

```bash
aws lambda invoke \
    --function-name db-audit-ai-report-generator \
    --region us-east-1 \
    output.json

cat output.json
```

### Run Manual Anomaly Detection

```bash
aws lambda invoke \
    --function-name db-audit-ai-anomaly-detector \
    --region us-east-1 \
    output.json
```

### View Reports

```bash
# List all reports
aws s3 ls s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/ --recursive

# Download latest
aws s3 cp s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/2026/08/audit-report.txt .
```

### View Audit Logs

```bash
aws s3 ls s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/sqlserver/audit-logs/ --recursive
aws s3 ls s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/postgresql/audit-logs/ --recursive
```

### Configure Privileged Users

```bash
aws lambda update-function-configuration \
    --function-name db-audit-ai-anomaly-detector \
    --environment Variables={PRIVILEGED_USERS='dba1,dba2,admin_user'} \
    --region us-east-1
```

## Anomaly Detection

The system detects five categories of anomalies:

| # | Pattern | Threshold | Severity |
|---|---------|-----------|----------|
| 1 | Failed Login Attempts | >3 in 10 minutes | HIGH |
| 2 | Unusual Login Times | Outside 9 AM – 6 PM | MEDIUM |
| 3 | Privileged User Activities | Any DBA action | MEDIUM–HIGH |
| 4 | Suspicious Query Patterns | Bulk SELECT on sensitive tables, exports | CRITICAL |
| 5 | Unauthorized Schema Changes | DDL without CR reference | HIGH |

### How It Works

1. **EventBridge** triggers the anomaly detector Lambda every hour
2. **Lambda** pulls the last hour's logs from S3
3. **Bedrock (Claude)** analyzes logs with a structured prompt including:
   - Privileged user list (from environment variable)
   - Detection rules (5 patterns above)
   - Output format (JSON with type, severity, description)
4. If severity is HIGH or CRITICAL → **SNS alert** fires immediately
5. All findings stored in S3 for audit trail

### Prompt Structure

```
Analyze these database audit logs for anomalies:

Privileged users to monitor: {PRIVILEGED_USERS}

Logs:
{RECENT_LOGS_JSON}

Detect:
1. Failed login attempts (>3 in 10 minutes)
2. Unusual login times (outside 9 AM - 6 PM)
3. Privileged user activities
4. Suspicious query patterns
5. Unauthorized schema changes

Return JSON: {"anomalies": [{"type": "...", "severity": "high/medium/low", "description": "..."}]}
```

## Compliance Features

| Feature | Implementation |
|---------|---------------|
| 7-Year Retention | S3 Object Lock (COMPLIANCE mode) on reports bucket |
| Immutable Trail | Versioned S3 + Object Lock — no one can delete, not even account admin |
| Encryption | AES-256 server-side encryption on all buckets |
| Access Logging | CloudTrail tracks all API calls to audit data |
| No Public Access | All S3 buckets block public access |
| Cost Optimization | S3-IA after 90 days, Glacier after 180 days for logs |

## Monthly Report Sections

The AI-generated compliance report includes:

1. **Executive Summary** — Overall compliance status
2. **Login Activity Analysis** — Authentication patterns, failures
3. **Privileged Access Monitoring** — DBA user activities
4. **Change Pattern Analysis** — Schema changes, CR correlation
5. **Compliance Findings** — Violations and gaps
6. **Risk Assessment** — Severity scoring
7. **Recommendations** — Actionable remediation steps

## SQL Server Audit File Processing

For existing `.sqlaudit` binary files:

```bash
# Upload existing audit files
chmod +x upload-sqlaudit.sh
./upload-sqlaudit.sh /path/to/audit/files/

# The sqlaudit_parser Lambda automatically processes uploaded files
# Converts binary .sqlaudit → structured JSON → same AI pipeline
```

Deploy the parser stack separately:

```bash
aws cloudformation deploy \
    --template-file sqlaudit-parser-stack.yaml \
    --stack-name db-audit-sqlaudit-parser \
    --capabilities CAPABILITY_IAM \
    --region us-east-1
```

## Troubleshooting

### No Logs Appearing

1. Verify CloudWatch Logs export is enabled:
   ```bash
   aws rds describe-db-instances --db-instance-identifier YOUR-INSTANCE \
     --query 'DBInstances[0].EnabledCloudwatchLogsExports'
   ```
2. Check Lambda log processor for errors:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/db-audit-ai-log-processor \
     --filter-pattern "ERROR"
   ```
3. Verify audit is configured inside the database (pgAudit extension loaded, SQL Server Audit enabled)

### Bedrock Access Denied

```
Enable model access: AWS Console → Bedrock → Model access → Enable "Claude 3.5 Sonnet"
```

### Reports Not Generated

1. Check EventBridge rule: `aws events describe-rule --name db-audit-ai-monthly-report`
2. Verify Lambda timeout is 900s (15 min)
3. Check S3 permissions on reports bucket

### High Lambda Costs

- Reduce anomaly detection frequency (change cron from hourly to every 4 hours)
- Reduce max_tokens in Bedrock calls
- Filter low-value log events before sending to Bedrock

## Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| Lambda (3 functions) | $5–15 |
| S3 (logs + reports) | $2–10 |
| Bedrock (hourly anomaly + monthly report) | $5–20 |
| CloudWatch Logs | $2–5 |
| SNS | <$1 |
| **Total** | **$15–50** |

## Customization

| What | How |
|------|-----|
| Add privileged users | Update `PRIVILEGED_USERS` environment variable |
| Change report schedule | Modify EventBridge cron in `infrastructure.yaml` |
| Adjust AI sensitivity | Edit the Bedrock prompt in Lambda code |
| Add databases | Enable CloudWatch export + configure audit on new instances |
| Change retention | Modify S3 lifecycle rules and Object Lock period |

## References

- GitHub Repository: https://github.com/aws-samples/sample-database-auditing-automation
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/
- pgAudit: https://github.com/pgaudit/pgaudit
- RDS SQL Server Audit: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.SQLServer.Options.Audit.html
- S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
