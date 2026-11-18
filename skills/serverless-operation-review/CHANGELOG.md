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
- Citation and self-check discipline covers the conversational answer, not only the report artifact:
  check ids, observed values, severities, recommendations and threshold sources all survive into a
  chat reply, which shortens by dropping whole findings rather than a finding's attributes.
- `metadata.summary` and `metadata.aws-devops-agent-skills.agent-types` set, so the skill installs
  for `CHAT` rather than as `GENERIC` and carries card text in the catalogs.

- `references/delegation-and-output-shape.md` fixes the turn shape and the finding format: one reply
  carries the full review (no status-only turn while work is pending), each finding is a table row
  with check id, severity, observed value, source API and doc or threshold source, and an observation
  without a check id is context. Delegation prompts carry the catalog rows and severity table, and the
  caller re-attaches omitted ids. Measured zero, no datapoints and never queried stay distinct, and a
  tool outage is reported as "nothing checked".
- Account IDs are never printed (alias or last four digits).
- Description adds the trigger phrases "how healthy is my serverless workload" and "audit the Lambda
  functions against best practices", and tells the agent to load the skill before choosing subagent
  skills and to preload it in collection subagents. The Error Handling and Known API Quirks sections
  merged and the Appendix links moved to the report template to keep `SKILL.md` under 500 lines.
- Live run 1 showed the agent announcing scope, delegating and ending its turn on that text, then
  posting "one of three slices is back" turns. The skill now forbids any user-visible text before the
  review is complete (including the scope and budget line, which moves into the final reply), makes
  inline collection the default, and says to write nothing while subagents are pending.
- Live run 4 showed the one remaining interim reply was a sentence the agent wrote while waiting on a
  subagent. Delegation now needs an inventory-count line (inline up to 40 functions or 25 of any other
  family), a wake-up rule (no text while subagents are pending), and a required reply shape that begins
  with `# Serverless health review: <region>`. Guardrail 6 shrank to a pointer.
### Notes for maintainers

- Runtime deprecation dates are forecasts and change. Re-verify
  `references/lambda-runtime-deprecations.md` against
  https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html on each release.
- Moved the review cap table, per-service alarm metric table and cost opportunity table out of
  SKILL.md into `references/budget-and-cost-tables.md`.
