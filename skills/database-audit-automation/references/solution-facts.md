# Solution Facts (Ground Truth)

Reference data for the Database Auditing Automation Solution. Load this when interpreting a report,
reasoning about an anomaly, or troubleshooting the pipeline.

Default resource prefix is `db-audit-ai`; if the user changed `ProjectName` at deploy time, use
theirs. `{ACCOUNT-ID}` is their 12-digit account ID.

## Resources and locations

- **Monthly report:** `s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/<YYYY>/<MM>/audit-report.txt` (plain text or Markdown).
- **Audit logs:** `s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/<db_type>/audit-logs/<date>/...` where `<db_type>` is `postgresql` or `sqlserver`.
- **Anomaly detector Lambda:** `db-audit-ai-anomaly-detector` — runs hourly (EventBridge `db-audit-ai-hourly-anomaly-check`), reads recent logs, classifies with Bedrock, sends HIGH-severity findings to SNS topic `db-audit-ai-anomaly-alerts`. **It does not persist a findings file** — the durable records are the SNS alert and the monthly report. Never tell the user to fetch an anomaly-findings file.
- **Log processor Lambda:** `db-audit-ai-log-processor`.
- **Report generator Lambda:** `db-audit-ai-report-generator`.

## Anomaly categories the detector uses

| Category | Threshold | Severity |
|----------|-----------|----------|
| Failed login attempts | >3 in 10 minutes | HIGH |
| Unusual login times | Outside 9 AM – 6 PM | MEDIUM |
| Privileged user activity | Any DBA action | MEDIUM–HIGH |
| Suspicious query patterns | Bulk SELECT on sensitive tables, exports | CRITICAL |
| Unauthorized schema changes | DDL without CR reference | HIGH |
