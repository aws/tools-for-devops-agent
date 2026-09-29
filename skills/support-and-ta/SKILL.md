---
name: support-and-ta
description: Use this skill when a user asks for an AWS support case summary broken down by service, a review of critical (error/red status) Trusted Advisor recommendations, or a combined daily or periodic reliability report covering both. It produces a report of support cases grouped by AWS service and account alongside the Trusted Advisor findings that need immediate attention, each tagged with its account ID.
metadata:
  author: anilmalakar
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "All agents"
  aws-devops-agent-skills.aws-services: "AWS Support, AWS Trusted Advisor"
  aws-devops-agent-skills.technical-domains: "Operations"
---

# Support Cases & Critical Trusted Advisor Report

## When to Use
- User asks for a support case summary grouped or broken down by AWS service
- User asks which Trusted Advisor recommendations need immediate/urgent attention
- A recurring report combining both is requested (e.g., a daily morning report)

## Workflow

Work through these steps in order; each depends on the previous one:

- [ ] Step 1: Gather support cases grouped by service and account
- [ ] Step 2: Gather critical (status `error`) Trusted Advisor findings
- [ ] Step 3: Cross-reference top services against TA findings in the same account
- [ ] Step 4: Assemble the three-section report
- [ ] Step 5: Validate the report against the tool output, then present

### Step 1: Gather support cases
Call `get_support_insights` with a query asking for all support cases grouped by AWS service and account for the relevant time window (default: trailing 12 months if not specified). Rank services by case count and keep only the **top 5 services with the most cases created**. For each of the top 5, extract: **account ID**, total case count, a **severity breakdown** including the count of high/urgent (**critical-severity**) cases and how many of those are still open, resolution status, and any recurring patterns. Critical-severity support cases are the support-side equivalent of TA `error` findings — surface them explicitly, do not reduce them to a total.

### Step 2: Gather critical Trusted Advisor recommendations
Call `get_trusted_advisor_recommendations` with a query asking for all recommendations across the organization/account. Filter to `status: error` (red) findings only — these are the ones needing immediate attention. For each finding, note **account ID**, check description, and flagged resource counts/regions.

### Step 3: Cross-reference
Check if any of the top 5 services also have related critical Trusted Advisor findings **in the same account** (e.g., DMS support cases + DMS-related TA findings on the same account ID). Call out this overlap explicitly, including matching account IDs — it indicates a recurring operational risk rather than an isolated incident.

### Step 4: Assemble the report
Produce three sections: (1) top 5 services by support case count, with the individual critical-severity cases listed below the table; (2) critical Trusted Advisor findings; (3) cross-cutting overlap between the two data sets, called out per account ID. Use the [report template](assets/report-template.md) when assembling this report so section order and table columns stay consistent across runs.

### Step 5: Validate before presenting
Before showing the report to the user, check your own output and fix any mismatch before presenting:
- Confirm the 5 services in Section 1 are actually the 5 with the highest case counts — re-rank from the tool output and compare.
- Confirm each row's critical-severity (open/total) count equals the number of individual critical cases you listed for that service; if they disagree, recount from the tool output.
- Confirm every finding in Section 2 has `status: error` — no `warning` or `ok` items leaked in.
- Confirm every row in both tables has a non-empty account ID.
- Confirm each Section 3 overlap shares the same account ID across both data sets.

If any check fails, correct the report and re-run the checks before presenting.

## Gotchas
- **Trusted Advisor status is three-valued**: `error` (red), `warning` (yellow), `ok` (green). Only `error` is "critical" here. `warning` sounds urgent but is **not** critical — never promote yellow findings into Section 2.
- **TA findings are per-account**: a single check can return one finding per affected account. Keep findings separated by account ID; do not merge or sum counts across accounts.
- **Severity and open-state are independent**: a case's critical-severity (high/urgent) classification does not change when it is resolved. A resolved urgent case still counts toward the critical total — show it as resolved rather than dropping it.
- **State the time window**: support case counts are meaningless without the window they cover. Always report the window you queried; if you fell back to the default, say so.
- **Break ranking ties deterministically**: when services tie on case count at the top-5 boundary, order by critical-severity count first and note the tie, so repeated runs produce a stable list.

## Constraints
- Both Section 1 and Section 2 must surface the account ID — as a per-row column when the data spans multiple accounts, and stated once at the top of each section when all rows belong to a single account. Never omit it on the grounds that there is only one account.
- Section 1 must be limited to the top 5 services by case count — do not list every service.
- Section 1 must surface critical-severity (high/urgent) support cases individually — case ID, subject, status — not just an aggregate count, mirroring the detail level of the Section 2 critical TA findings. If a top-5 service has no critical-severity cases, say so.
- Only surface Trusted Advisor findings with `status: error` as "critical" — do not include `warning` or `ok` status items in the critical section (they can be mentioned separately as lower priority if asked).
- Always report counts and identifiers accurately from the tool output; do not estimate or round without noting it.
- If either data source returns no findings, state that explicitly rather than omitting the section.

## Output
When this skill runs inside a recurring custom agent, write the report as a text summary to the agent's run journal, and refresh a persisted report artifact if one already exists rather than creating a duplicate on every run.
