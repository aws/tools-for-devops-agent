# Changelog

## 1.0.0 (2026-09-10)

- Initial release.
- Ten-step review procedure covering scope negotiation and budget, inventory discovery,
  configuration collection, 7-day CloudWatch metrics, log pattern and REPORT-line analysis, alarm
  coverage, security and IAM analysis, cost analysis, best-practice evaluation, and report
  generation.
- Five resource families in scope: Lambda and its event sources (SQS, SNS, EventBridge, EventBridge
  Scheduler, DynamoDB Streams, Kinesis), API Gateway (REST, HTTP, WebSocket), Step Functions, and
  DynamoDB.
- Check catalogs in `references/` with a check id, pillar, severity, detection rule, remediation, and
  AWS documentation citation per row: `checks-lambda.md`, `checks-event-sources.md`,
  `checks-apigateway.md`, `checks-stepfunctions.md`, `checks-dynamodb.md`.
- `references/cloudwatch-alarm-reference.md` maps the Serverless Applications Lens per-service alarm
  list to the published CloudWatch recommended alarm settings, and marks the metrics for which AWS
  publishes no threshold.
- `references/metrics-and-logs.md` carries the per-resource-type CloudWatch metric set and the log
  pattern table, keeping `SKILL.md` to the procedure.
- `references/lambda-runtime-deprecations.md` with supported and deprecated runtime dates verified
  against AWS documentation on 2026-09-10, including the Amazon Linux 2 end-of-life effect.
- `references/report-template.md` fixes the report section order to match the other
  operation-review skills in this repository.

### Notes for maintainers

- Runtime deprecation dates are forecasts and change. Re-verify
  `references/lambda-runtime-deprecations.md` against
  https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html on each release.
