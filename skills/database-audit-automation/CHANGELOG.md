# Changelog

## [2.1.0] - 2026-09-22

### Changed
- Refocused SKILL.md on the two tasks that need agent judgment — interpreting the AI-generated
  compliance report and troubleshooting the audit pipeline. Removed the deterministic
  deploy/configure and operations command recitation from SKILL.md; those steps live in
  README.md, and the skill now points the user there instead of reproducing them (avoids
  spending agent tokens/credits re-emitting a fixed runbook).
- Constrained agent behavior to read-only (read S3 objects and CloudWatch Logs, describe/list);
  the agent no longer presents itself as relaying invoke/modify commands.

### Fixed
- Corrected a false claim that anomaly findings are stored in S3. The anomaly detector does not
  persist a findings file — it returns counts and sends HIGH-severity findings via SNS. The
  durable records are the SNS alert and the monthly report. SKILL.md now reflects this.
- Corrected the monthly report S3 path to `monthly-reports/<YYYY-MM>/audit-report.txt` (single
  `YYYY-MM` segment) in both SKILL.md and README.md, matching the CloudFormation template.

### Added
- Concrete S3 locations for reports and audit logs, and accurate resource names (SNS topic
  `db-audit-ai-anomaly-alerts`, EventBridge rule `db-audit-ai-hourly-anomaly-check`) in SKILL.md.
- A "Required Agent Permissions" section in SKILL.md and a split of user vs. agent IAM
  permissions in README.md, calling out the read access (`s3:GetObject`/`s3:ListBucket` on the
  reports and audit-logs buckets, CloudWatch Logs reads) the agent needs to interpret data.

## [2.0.0] - 2026-09-22

### Changed
- Restructured the skill so SKILL.md contains only agent-facing instructions. The agent now
  provides guidance, interpretation, and troubleshooting, and explicitly does not deploy
  infrastructure, run shell scripts, modify databases, or execute audit-setup SQL.
- Moved all user-facing setup and operations (CloudFormation deployment, pgAudit / SQL Server
  audit configuration, CloudWatch Logs export, shell scripts, and CLI operations commands)
  from SKILL.md into README.md.

### Added
- Vendored the deployment assets from the source solution (MIT-0) into `assets/` so the skill
  is self-contained and users don't need to clone a second repository:
  - `assets/templates/` — `infrastructure.yaml`, `sqlaudit-parser-stack.yaml`, `ui-infrastructure.yaml`
  - `assets/sql/` — `aurora-postgresql-audit-setup.md`, `rds-sqlserver-audit-setup.md`, `athena-setup.md`
  - `assets/deploy/` — `deploy.md`, `deploy-ui.md`, `upload-sqlaudit.md`
  SQL and shell assets are stored as `.md` (code in fenced blocks) because DevOps Agent skill
  uploads accept only a fixed set of file extensions (`.sql` and `.sh` are not among them).
- Agent scope/behavior section and deployed resource-name reference in SKILL.md.

## [1.0.0] - 2026-09-22

### Added
- Initial release of the database-audit-automation skill.
- Guided CloudFormation deployment of the Database Auditing Automation Solution.
- Aurora PostgreSQL audit configuration via pgAudit (parameter group + setup SQL).
- RDS SQL Server audit configuration via native SQL Server audit (option group + setup SQL).
- CloudWatch Logs export enablement for audit log streaming.
- Audit log collection and normalization pipeline (CloudWatch Logs → Lambda → S3).
- AI-based anomaly detection over recent audit activity using Amazon Bedrock (Claude 3.5 Sonnet).
- Compliance report generation (SOX, PCI-DSS, HIPAA) with SNS alerting for high-severity findings.
- Audit log pipeline troubleshooting guidance.
