# Changelog

## [3.1.0] - 2026-09-23

### Added
- Real **functional** eval results (`evals/functional/v1/`) from running the skill-eval tool
  against a live deployment of the solution. 27/27 runs succeeded. Across all four scored evals,
  with-skill passed the expected-output bar 67–100% while without-skill passed 0%, and with-skill
  output was rated consistent vs. inconsistent without it — a clear, repeated positive delta.
- Removed `evals/exemptions.json` entirely: all three eval types (structure, best-practices,
  functional) now have real results, satisfying the enforce-evals requirement.

### Fixed
- Corrected the monthly report S3 path to `monthly-reports/<YYYY>/<MM>/audit-report.txt` (nested
  year/month) to match the actually deployed solution. The earlier `<YYYY-MM>` single-segment form
  came from the source template and did not match the live layout — caught by testing against the
  real setup.

### Security
- Scrubbed account-specific identifiers (account IDs, an IAM principal ID, RDS endpoints, resource
  names) from the committed functional eval artifacts, replacing them with documentation
  placeholders, since these were produced against a live account and this repo is public.
- Excluded the functional `journal_records.json` files from the commit (and gitignored them): they
  captured extensive live-account data (KMS key ARNs, resource UUIDs) that a public repo should not
  carry. The committed `benchmark.json`, per-scenario `functional-tests-results.json`, and
  `_metadata.json` contain the scores and verdicts and are free of that data.

## [3.0.0] - 2026-09-22

### Changed
- Aligned the skill with the Agent Skills specification.
- **SKILL.md** rewritten as explicit step-by-step instructions for three tasks (review a
  compliance report, reason about an anomaly alert, troubleshoot the pipeline), each with
  expected outcomes, on-failure handling, and an edge-cases section, per the spec's recommended
  body sections.
- Removed the "Required Agent Permissions" section from SKILL.md and moved it to README.md as a
  **user prerequisite** — permissions must be granted before the skill is used, so they belong in
  setup docs, not in the agent's runtime instructions.
- Removed the "References" link section from SKILL.md to README.md (user-facing material).

### Removed
- **Removed all user deployment artifacts from `assets/`** (CloudFormation templates, audit-setup
  SQL, deploy scripts). Per the spec, `assets/` is for resources the agent uses (e.g. output
  templates), not user deployment files. The solution is self-contained in its source repository
  (https://github.com/aws-samples/sample-database-auditing-automation); README.md now directs
  users to deploy from there before using the skill, keeping a single source of truth for
  deployment and leaving the skill as the only artifact here.

### Added
- **`assets/templates/audit-report-review.md`** — the output template the agent fills when
  reviewing a compliance report, defining the expected output (a prioritized, actionable audit
  review rather than a copy or bare summary of the report). Referenced from SKILL.md, per the
  spec's "templates for output format" guidance.
- README.md sections for the expected output and the deployment pointer.

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
