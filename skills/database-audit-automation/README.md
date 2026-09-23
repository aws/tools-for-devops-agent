# Database Audit Automation — AWS DevOps Agent Skill

An AI-powered database auditing automation skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). In Chat, the agent helps you **operate, interpret, and troubleshoot** an automated database audit pipeline for Amazon RDS SQL Server and Amazon Aurora PostgreSQL — covering audit log collection, AI-based anomaly detection, and compliance report generation.

**Source repository:** https://github.com/aws-samples/sample-database-auditing-automation

> **What the agent does vs. what you do.** This is a Chat-task skill: the agent provides guidance, interprets audit findings and reports, and diagnoses pipeline problems. It does **not** deploy infrastructure, run shell scripts, modify databases, or execute audit-setup SQL. The deployment and audit-configuration steps in this README are actions **you** perform in your own environment. The deployment assets referenced below are vendored in this skill's `assets/` directory, so you don't need to clone the source repository separately.

## What It Does

When activated via Chat, this skill helps the DevOps Agent:

1. Explain how to deploy and configure the solution, pointing you to the templates and scripts in `assets/`.
2. Guide you through enabling database-native auditing — `pgAudit` for Aurora PostgreSQL, SQL Server native audit for RDS SQL Server — and CloudWatch Logs export.
3. Explain the audit-log pipeline (CloudWatch Logs → Lambda → S3 → Bedrock analysis).
4. Interpret AI anomaly-detection findings and privileged-user access patterns.
5. Interpret compliance reports (SOX, PCI-DSS, HIPAA) and explain findings by section.
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

### Deployed resource names

Default names created by the CloudFormation stack (project prefix `db-audit-ai`; substitute your own if you change `ProjectName`):

- **Lambda:** `db-audit-ai-log-processor`, `db-audit-ai-anomaly-detector`, `db-audit-ai-report-generator`
- **S3:** `db-audit-ai-audit-logs-{ACCOUNT-ID}`, `db-audit-ai-reports-{ACCOUNT-ID}`
- **EventBridge rule (reports):** `db-audit-ai-monthly-report`

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

The solution uses Amazon Bedrock (Claude 3.5 Sonnet) for anomaly detection and report generation. Enable model access in the target account/region before deploying (AWS Console → Bedrock → Model access → enable Claude 3.5 Sonnet).

### 3. IAM permissions

Deploying and operating the solution requires permissions beyond read-only — CloudFormation stack operations, RDS/Aurora audit configuration changes, and access to Lambda, S3, EventBridge, SNS, and Bedrock. Review and scope these to your environment before running. The agent's investigative/reporting help operates against audit data already in S3 and CloudWatch Logs.

### 4. AWS CLI configured

The setup and operations commands below are run by you with the AWS CLI configured for the target account/region.

### 5. Target databases

Amazon RDS SQL Server and/or Amazon Aurora PostgreSQL instances you want to audit.

## Setup (User Steps)

These steps deploy and configure the solution. **You run them** — the agent can walk you through them but does not execute them. All referenced files are in this skill's `assets/` directory.

### 1. Deploy the solution via CloudFormation

Template: [`assets/templates/infrastructure.yaml`](assets/templates/infrastructure.yaml). Helper script (source in [`assets/deploy/deploy.md`](assets/deploy/deploy.md) — save it as `deploy.sh` next to the template, edit the alert email and region at the top, then `chmod +x deploy.sh`).

```bash
# Option A: helper script (saved from assets/deploy/deploy.md)
./deploy.sh

# Option B: direct
aws s3 cp assets/templates/infrastructure.yaml s3://YOUR-BUCKET/db-audit-ai/infrastructure.yaml
aws cloudformation deploy \
    --template-file assets/templates/infrastructure.yaml \
    --stack-name db-audit-ai \
    --capabilities CAPABILITY_IAM \
    --region us-east-1
```

### 2. Configure Aurora PostgreSQL auditing (pgAudit)

1. Create a custom parameter group with `shared_preload_libraries = pgaudit`.
2. Apply the parameter group to the cluster.
3. Run the audit setup SQL: [`assets/sql/aurora-postgresql-audit-setup.md`](assets/sql/aurora-postgresql-audit-setup.md).
4. Enable CloudWatch Logs export:

```bash
aws rds modify-db-cluster \
    --db-cluster-identifier YOUR-CLUSTER \
    --cloudwatch-logs-export-configuration '{"LogTypesToEnable":["postgresql"]}' \
    --region us-east-1
```

### 3. Configure RDS SQL Server auditing (native audit)

1. Create an Option Group with the `SQLSERVER_AUDIT` option.
2. Apply it to the RDS instance.
3. Run the audit setup SQL: [`assets/sql/rds-sqlserver-audit-setup.md`](assets/sql/rds-sqlserver-audit-setup.md).
4. Enable CloudWatch Logs export:

```bash
aws rds modify-db-instance \
    --db-instance-identifier YOUR-INSTANCE \
    --cloudwatch-logs-export-configuration '{"LogTypesToEnable":["error","agent"]}' \
    --region us-east-1
```

### 4. (Optional) Deploy the dashboard

Template: [`assets/templates/ui-infrastructure.yaml`](assets/templates/ui-infrastructure.yaml). Script source: [`assets/deploy/deploy-ui.md`](assets/deploy/deploy-ui.md) (save as `deploy-ui.sh`, `chmod +x`, run).

```bash
./deploy-ui.sh
```

### 5. (Optional) Process existing `.sqlaudit` binary files

Deploy the parser stack ([`assets/templates/sqlaudit-parser-stack.yaml`](assets/templates/sqlaudit-parser-stack.yaml)) and upload files with the script in [`assets/deploy/upload-sqlaudit.md`](assets/deploy/upload-sqlaudit.md) (save as `upload-sqlaudit.sh`, `chmod +x`):

```bash
aws cloudformation deploy \
    --template-file assets/templates/sqlaudit-parser-stack.yaml \
    --stack-name db-audit-sqlaudit-parser \
    --capabilities CAPABILITY_IAM \
    --region us-east-1

./upload-sqlaudit.sh /path/to/audit/files/
```

An optional Athena setup for querying audit data is provided in [`assets/sql/athena-setup.md`](assets/sql/athena-setup.md).

## Operations (User Commands)

Run these yourself; the agent presents them when you ask. Replace `{ACCOUNT-ID}`, region, and the `db-audit-ai` prefix with your values.

```bash
# Generate an on-demand compliance report
aws lambda invoke --function-name db-audit-ai-report-generator --region us-east-1 output.json

# Run manual anomaly detection
aws lambda invoke --function-name db-audit-ai-anomaly-detector --region us-east-1 output.json

# List / download reports
aws s3 ls s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/ --recursive
aws s3 cp s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/2026/08/audit-report.txt .

# View audit logs
aws s3 ls s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/postgresql/audit-logs/ --recursive
aws s3 ls s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/sqlserver/audit-logs/ --recursive

# Configure the privileged-user watch list
aws lambda update-function-configuration \
    --function-name db-audit-ai-anomaly-detector \
    --environment Variables={PRIVILEGED_USERS='dba1,dba2,admin_user'} \
    --region us-east-1
```

## Anomaly detection categories

| # | Pattern | Threshold | Severity |
|---|---------|-----------|----------|
| 1 | Failed Login Attempts | >3 in 10 minutes | HIGH |
| 2 | Unusual Login Times | Outside 9 AM – 6 PM | MEDIUM |
| 3 | Privileged User Activities | Any DBA action | MEDIUM–HIGH |
| 4 | Suspicious Query Patterns | Bulk SELECT on sensitive tables, exports | CRITICAL |
| 5 | Unauthorized Schema Changes | DDL without CR reference | HIGH |

EventBridge triggers the anomaly detector hourly; it pulls the last hour of logs from S3, Bedrock analyzes them against the privileged-user list and the rules above, and HIGH/CRITICAL findings fire an SNS alert. Findings are stored in S3 for the audit trail.

## Compliance reports

The AI-generated monthly report includes: Executive Summary, Login Activity Analysis, Privileged Access Monitoring, Change Pattern Analysis, Compliance Findings, Risk Assessment, and Recommendations. Compliance posture is enforced by S3 Object Lock (COMPLIANCE mode, 7-year retention) on the reports bucket, versioned + encrypted buckets, CloudTrail access logging, blocked public access, and lifecycle tiering (S3-IA at 90 days, Glacier at 180 days for logs).

## Customization

| What | How |
|------|-----|
| Add privileged users | Update the `PRIVILEGED_USERS` environment variable |
| Change report schedule | Modify the EventBridge cron in `assets/templates/infrastructure.yaml` |
| Adjust AI sensitivity | Edit the Bedrock prompt in the anomaly detector Lambda code |
| Add databases | Enable CloudWatch export + configure audit on new instances |
| Change retention | Modify S3 lifecycle rules and Object Lock period |

## Approximate cost

| Component | Monthly Cost |
|-----------|-------------|
| Lambda (3 functions) | $5–15 |
| S3 (logs + reports) | $2–10 |
| Bedrock (hourly anomaly + monthly report) | $5–20 |
| CloudWatch Logs | $2–5 |
| SNS | <$1 |
| **Total** | **$15–50** |

## Skill Contents

```
database-audit-automation/
├── SKILL.md        # agent-facing instructions (with frontmatter)
├── README.md       # this file — user setup, operations, reference
├── CHANGELOG.md    # version history
├── assets/
│   ├── templates/  # CloudFormation: infrastructure.yaml, sqlaudit-parser-stack.yaml, ui-infrastructure.yaml
│   ├── sql/        # audit-setup SQL as .md (Aurora PostgreSQL, RDS SQL Server) + Athena setup
│   └── deploy/     # deploy scripts as .md (deploy, deploy-ui, upload-sqlaudit)
└── evals/          # evaluation data (not included in upload zip)
```

The vendored `assets/` are copied from the [source solution](https://github.com/aws-samples/sample-database-auditing-automation) (MIT-0 licensed) so this skill is self-contained. The SQL and shell scripts are stored as `.md` files (with the code in fenced blocks) because AWS DevOps Agent skill uploads only accept a fixed set of file extensions — `.sql` and `.sh` are not among them. Copy the code out of the relevant `.md` file to run it.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review
> and testing. Validate in a non-production environment first. Enabling database auditing,
> modifying parameter/option groups, and deploying the audit pipeline change live database
> configuration — review the CloudFormation template and audit settings, and tune anomaly
> thresholds and compliance mappings to your own workload and regulatory requirements.
