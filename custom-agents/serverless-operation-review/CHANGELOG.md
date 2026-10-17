# Changelog

## 1.0.0 (2026-09-10)

- Initial release.
- Weekly scheduled agent (`0 7 * * 1`) that runs the `serverless-operation-review` skill across
  Lambda, API Gateway, Step Functions, DynamoDB, and Lambda event sources.
- Adds a **Change Since Last Review** section after the Executive Summary: new CRITICAL/HIGH findings,
  findings resolved, findings unchanged for three or more runs, and resources added or removed.
- Reports metric direction between runs for error rate, `Duration` p99 as a share of timeout, peak
  memory utilization, concurrency runway against the account quota, DLQ depth and `IteratorAge`, and
  Lambda plus CloudWatch Logs spend.
- Read-only tool assignment; the agent recommends remediation and never applies it.
- Includes `sample-app/` — a SAM template that seeds one fault per check family for validating
  detection.
