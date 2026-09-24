# Database Audit Automation — AWS DevOps Agent Skill

A skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html) that helps you **interpret** the compliance reports and anomaly alerts produced by the Database Auditing Automation Solution, and **troubleshoot** its audit log pipeline, for Amazon RDS SQL Server and Amazon Aurora PostgreSQL.

The skill (the `SKILL.md` and its `assets/`) is the only artifact in this directory. It does **not** deploy or configure the solution — you deploy the solution first (from the source repository below), then use this skill in Chat to interpret and troubleshoot it.

**Solution source repository (deploy from here):** https://github.com/aws-samples/sample-database-auditing-automation

## What the skill does

Once the solution is deployed and you're in a DevOps Agent Chat, this skill helps the agent:

1. **Review a compliance report** — read the monthly `audit-report.txt` from S3 (or one you paste in) and produce a prioritized, actionable audit review (see [expected output](#expected-output)).
2. **Reason about an anomaly alert** — explain a high-severity SNS alert by reading the underlying audit logs and applying the solution's detection thresholds.
3. **Troubleshoot the pipeline** — diagnose why audit logs stopped reaching S3, or why a report wasn't generated.

The agent works **read-only**. It never deploys, invokes, or modifies resources.

## Prerequisites

### 1. Deploy the solution

Deploy the Database Auditing Automation Solution from its [source repository](https://github.com/aws-samples/sample-database-auditing-automation) and follow that repo's instructions to:

- Deploy the CloudFormation stack (Lambda functions, S3 buckets, EventBridge rules, SNS topic).
- Enable database-native auditing — `pgAudit` for Aurora PostgreSQL, SQL Server native audit for RDS SQL Server — and CloudWatch Logs export.
- (Optional) Deploy the dashboard and the `.sqlaudit` parser stack.

The solution is self-contained in that repository; this skill deliberately does not vendor its templates or scripts, so there's a single source of truth for deployment.

### 2. An AWS DevOps Agent Space with the target account

An existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the account that has the deployed solution configured as a cloud source.

### 3. Grant the agent read permissions (define these before using the skill)

The agent reads the report, the audit logs, and pipeline configuration. It needs these **read-only** permissions on its cloud-source role **before** you use the skill — if they aren't in place, the skill can't read the data at chat time. Scope them to the deployed resources (default prefix `db-audit-ai`; substitute yours if you changed `ProjectName`):

- `s3:GetObject`, `s3:ListBucket` on `db-audit-ai-reports-{ACCOUNT-ID}` (compliance reports) and `db-audit-ai-audit-logs-{ACCOUNT-ID}` (audit logs)
- `logs:FilterLogEvents`, `logs:GetLogEvents`, `logs:DescribeLogGroups`, `logs:DescribeLogStreams` (inspect Lambda logs during troubleshooting)
- `rds:DescribeDBInstances`, `rds:DescribeDBClusters` (check CloudWatch Logs export configuration)
- `lambda:GetFunctionConfiguration`, `events:DescribeRule` (check Lambda timeout and schedules)

The agent needs **no** write permissions.

### 4. Amazon Bedrock access

The solution itself uses Amazon Bedrock (Claude Sonnet 4.5, via the `us.anthropic.claude-sonnet-4-5-20250929-v1:0` inference profile) for its anomaly detection and report generation — enable model access in the target account/region when you deploy it.

## Expected output

For a report review, the agent produces a **Database Audit Review** following the template at [`assets/templates/audit-report-review.md`](assets/templates/audit-report-review.md): a summary, compliance posture, a severity-ordered findings table, a privileged-access review, prioritized recommended actions, and an explicit gaps/caveats section. It is an actionable review grounded in the report and logs — not a copy or a bare restatement of the report.

## Deployed resource names (reference)

Default names created by the solution's CloudFormation stack (prefix `db-audit-ai`; substitute yours if changed):

- **Lambda:** `db-audit-ai-log-processor`, `db-audit-ai-anomaly-detector`, `db-audit-ai-report-generator`
- **S3:** `db-audit-ai-audit-logs-{ACCOUNT-ID}`, `db-audit-ai-reports-{ACCOUNT-ID}`
- **SNS topic:** `db-audit-ai-anomaly-alerts`
- **EventBridge (anomaly schedule):** `db-audit-ai-hourly-anomaly-check`
- **Report path:** `s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/<YYYY>/<MM>/audit-report.txt`
- **Audit log path:** `s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/<db_type>/audit-logs/<date>/` (`db_type` = `postgresql` | `sqlserver`)

## Anomaly detection categories (reference)

| Category | Threshold | Severity |
|----------|-----------|----------|
| Failed login attempts | >3 in 10 minutes | HIGH |
| Unusual login times | Outside 9 AM – 6 PM | MEDIUM |
| Privileged user activity | Any DBA action | MEDIUM–HIGH |
| Suspicious query patterns | Bulk SELECT on sensitive tables, exports | CRITICAL |
| Unauthorized schema changes | DDL without CR reference | HIGH |

## Skill Contents

```
database-audit-automation/
├── SKILL.md                              # agent-facing instructions (with frontmatter)
├── README.md                             # this file — deployment pointer, prerequisites, reference
├── CHANGELOG.md                          # version history
├── assets/
│   └── templates/
│       └── audit-report-review.md        # output template the agent fills for a report review
└── evals/                                # evaluation data (not included in upload zip)
```

## References

- Solution source & deployment: https://github.com/aws-samples/sample-database-auditing-automation
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/
- pgAudit: https://github.com/pgaudit/pgaudit
- RDS SQL Server Audit: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.SQLServer.Options.Audit.html
- S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- AWS DevOps Agent skills: https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review
> and testing. Validate in a non-production environment first. Tune anomaly thresholds and
> compliance mappings to your own workload and regulatory requirements.
