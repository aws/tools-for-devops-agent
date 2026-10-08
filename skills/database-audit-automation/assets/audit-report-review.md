# Database Audit Review — {DATABASE_OR_ACCOUNT} — {REPORT_PERIOD}

> Output template for the `database-audit-automation` skill. The agent fills every `{PLACEHOLDER}`
> from the audit report and audit logs it read this session. Do not copy example values from this
> file into a real review. Omit a section only if the source data genuinely has nothing for it,
> and say so rather than inventing content.

## Summary
{2-4 sentences: overall compliance posture for the period, the single most important thing the
reader should know, and whether any item needs action now.}

## Compliance Posture
- **Frameworks in scope:** {e.g. SOX, PCI-DSS, HIPAA — only those the report addresses}
- **Overall status:** {Compliant | Gaps found | At risk} — {one-line justification}

## Findings
List each finding the report or logs support. One row per finding. Order by severity (CRITICAL first).

| Severity | Category | Finding | Evidence |
|----------|----------|---------|----------|
| {CRITICAL/HIGH/MEDIUM/LOW} | {Failed logins / Unusual login time / Privileged activity / Suspicious query / Schema change / Other} | {what happened, specific principals/objects/times} | {report section or S3 log reference the finding is grounded in} |

## Privileged Access Review
{What privileged/DBA users did in the period, anything outside expected patterns, and whether it
was authorized. Name the users and actions. If none, state that explicitly.}

## Recommended Actions
Concrete, prioritized next steps. Each names the responsible action, not just the problem.

1. {Action} — {why, and which finding it addresses} — {priority}
2. {Action} — {why} — {priority}

## Gaps and Caveats
{What could NOT be determined and why — missing log windows, sections absent from the report,
permissions the agent lacked, data the user should provide for a complete review. Be explicit;
do not present an incomplete review as complete.}

## Source
- Report: `{S3 URI of the audit-report.txt read, or "provided by user in chat"}`
- Audit logs consulted: `{S3 prefixes/objects read, if any}`
- Period covered: `{REPORT_PERIOD}`
