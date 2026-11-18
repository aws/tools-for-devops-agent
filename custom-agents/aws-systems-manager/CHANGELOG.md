# Changelog

## 1.0.0

- Initial version: read-only Systems Manager review with one section per capability. Automation review: failed, timed-out and cancelled executions, rate-control and alarm settings on multi-target runs, account-owned runbook findings, and AWS-owned alternatives for recurring failures.
- Review round 2: a preflight step verifies `use_aws` with one read call before the reviews start (a missing tool now produces the blocked report and Recommendation in seconds), and the reviews run in-session rather than in subagents, which don't inherit tools.
