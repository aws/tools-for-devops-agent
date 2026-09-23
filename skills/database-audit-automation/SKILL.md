---
name: database-audit-automation
description: Interpret the compliance reports and reason about the anomaly alerts produced by the Database Auditing Automation Solution for Amazon RDS SQL Server and Aurora PostgreSQL, and troubleshoot its audit log pipeline. Use when a user asks to review or explain a database audit compliance report, understand a high-severity anomaly SNS alert, assess privileged database access, or diagnose why audit logs or reports stopped appearing. Assumes the solution is already deployed (see README).
metadata:
  author: bbhavini0502
  version: "3.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks"
  aws-devops-agent-skills.aws-services: "Amazon RDS, Amazon Aurora, Amazon Bedrock, AWS Lambda, Amazon S3, Amazon EventBridge, Amazon SNS"
  aws-devops-agent-skills.technical-domains: "Databases, Security"
---

# Database Audit Automation

Interpret and troubleshoot the **Database Auditing Automation Solution** — a deployed system that collects database audit logs, runs hourly AI anomaly detection, and generates monthly compliance reports for Amazon RDS SQL Server and Amazon Aurora PostgreSQL.

This skill assumes the solution is **already deployed**. It does not deploy or configure anything. Deployment and setup are the user's responsibility and are covered in `README.md`; if the user asks how to deploy or turn on auditing, point them there and stop.

## Scope

- **You do:** read the compliance report and audit logs, interpret them, reason about anomaly alerts, and diagnose the pipeline.
- **You do not:** deploy the stack, run scripts, modify databases, invoke Lambdas, or change any resource. Work read-only. If a fix needs a change, describe it and let the user apply it.
- **Do not invent** bucket names, ARNs, account IDs, or paths. Read them from the environment or ask the user. If a read is denied, tell the user which permission is missing (permissions are listed in `README.md`).

## Solution facts (ground truth)

The resource names, S3 paths, and anomaly-category thresholds this skill relies on are in
[`references/solution-facts.md`](references/solution-facts.md). Read that file when you start any
task below. Key rule to remember without loading it: the anomaly detector does **not** persist a
findings file — never tell the user to fetch one.

## Task 1: Review a compliance report

Produce an actionable **Database Audit Review** — not a copy of the report, not a bland restatement. Follow the template at `assets/templates/audit-report-review.md`. Work through these steps in order:

- [ ] **Step 1: Locate the report.** If the user pasted the report into chat, use that and skip to Step 3. Otherwise ask for the account ID (and prefix, if customized) and the month; if the month is unknown, list `s3://db-audit-ai-reports-{ACCOUNT-ID}/monthly-reports/` to show available reports.
  - Expected: you have the report path or its content.
  - On failure (access denied listing/reading S3): tell the user the missing permission (see `README.md`) and ask them to paste the report instead.
- [ ] **Step 2: Read the report object** (`s3:GetObject`) at `monthly-reports/<YYYY-MM>/audit-report.txt`.
  - Expected: the full report text is loaded.
- [ ] **Step 3: Extract findings by section.** The report has: Executive Summary, Login Activity Analysis, Privileged Access Monitoring, Change Pattern Analysis, Compliance Findings, Risk Assessment, Recommendations. Pull the concrete facts (principals, objects, times, counts) from each.
  - Expected: a list of raw findings with their supporting detail.
- [ ] **Step 4: Classify and prioritize.** Map each finding to an anomaly category and severity from the table in `references/solution-facts.md`. Order CRITICAL → LOW.
  - Expected: each finding tagged with a category and severity.
- [ ] **Step 5: Corroborate the notable findings** (optional but preferred). For a HIGH/CRITICAL item, read the relevant window under `s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/<db_type>/audit-logs/<date>/` to confirm it against the raw logs, and cite what you saw as evidence.
  - Expected: HIGH/CRITICAL findings backed by a log reference, or a note in Gaps if logs weren't accessible.
- [ ] **Step 6: Write the review** using `assets/templates/audit-report-review.md`: fill every placeholder from data you actually read; put anything you could not determine in "Gaps and Caveats"; cite the report path and any log objects in "Source".
  - Expected output: a completed review following the template, with a prioritized findings table, a privileged-access section, concrete recommended actions, and explicit gaps.
  - Do not fabricate values to fill the template. An empty section with a stated reason is correct; invented data is not.

## Task 2: Reason about an anomaly alert

The user received an SNS alert (or asks why one did/didn't fire). There is no findings file to fetch — reason from the logs and the thresholds. Work through these steps in order:

- [ ] **Step 1: Establish the window and database** the alert concerns (from the alert text or by asking).
  - Expected: a concrete time window and `<db_type>`.
- [ ] **Step 2: Read the audit logs** for that window at `s3://db-audit-ai-audit-logs-{ACCOUNT-ID}/<db_type>/audit-logs/<date>/`.
  - Expected: the relevant log entries are loaded. On access denied, name the missing permission (see `README.md`).
- [ ] **Step 3: Apply the detection rules** from the anomaly-categories table in `references/solution-facts.md` to the log entries. Determine whether the pattern meets a threshold and at what severity.
  - Expected: a category + severity verdict, or "no threshold met."
- [ ] **Step 4: Explain the verdict** — state which category fired (or why none did), cite the specific log entries as evidence, and give the user the concrete next step.
  - Expected output: a short assessment naming the category, severity, the evidence from the logs, and a recommended action — or a clear "no threshold met, here's why."

If the user wants to tune sensitivity: the rules live in the Bedrock prompt inside `db-audit-ai-anomaly-detector`, and the watch list is the `PRIVILEGED_USERS` env var on that Lambda. Describe the change and point them to `README.md`. Do not modify it.

## Task 3: Troubleshoot the pipeline

Diagnose read-only; recommend fixes for the user to apply.

### No logs appearing in S3
Work through the pipeline in order until you find the broken stage:
- [ ] **Step 1:** Check CloudWatch Logs export on the database: `rds:DescribeDBInstances` / `DescribeDBClusters`, look at `EnabledCloudwatchLogsExports`.
- [ ] **Step 2:** Check `db-audit-ai-log-processor` Lambda logs for errors (filter its log group for `ERROR`).
- [ ] **Step 3:** Confirm auditing is configured **inside** the database (pgAudit loaded for Aurora PostgreSQL, or SQL Server Audit enabled). If not, this is a user setup step in `README.md`.
- Expected: you identify which stage of the pipeline is broken and name the fix.

### Reports not generated
- [ ] **Step 1:** Check the report generator's schedule (EventBridge) and that `db-audit-ai-report-generator` timeout is 900s.
- [ ] **Step 2:** Check that the expected month exists under `monthly-reports/<YYYY-MM>/`.
- [ ] **Step 3:** Check the report-generator Lambda logs for errors.

### Bedrock access denied
Claude 3.5 Sonnet model access must be enabled in the account/region (Console → Bedrock → Model access). User action.

### High Lambda cost
Suggest (as user changes): reduce anomaly-detection frequency (hourly → every 4 hours) via the EventBridge schedule, reduce `max_tokens` in the Bedrock calls, or filter low-value log events before sending to Bedrock.

## Edge cases

- **User pastes a report instead of granting S3 access:** interpret the pasted content; note in "Source" that it was user-provided and in "Gaps" that logs could not be corroborated.
- **Report for the requested month doesn't exist:** say so, list what months do exist, and offer Task 3 (reports-not-generated) troubleshooting.
- **Customized `ProjectName`:** confirm the prefix before constructing any path; never assume `db-audit-ai` if the user indicated otherwise.
- **Read denied:** name the missing permission (per `README.md`) rather than guessing at the data.
