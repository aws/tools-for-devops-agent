# DynamoDB Latency Skill

This skill enables the AWS DevOps Agent to answer one question with evidence: **is Amazon
DynamoDB actually slow, and if so, why?** It classifies a table's latency profile from
CloudWatch metrics per API operation, and attributes what is left to the client side when the
service side is clean.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and
> testing. Users should validate in a non-production environment first. It is read-only and
> never reads item data, but its thresholds are operating heuristics rather than AWS
> commitments, and its findings are diagnostic guidance — not a substitute for your own
> judgment about your workload.

## Purpose

`SuccessfulRequestLatency` is the metric everyone reaches for, and on its own it cannot answer
the question. It measures time **internal to the DynamoDB service** — client activity and
network trip times are excluded — and it measures only *successful* requests, so throttled and
failed calls never appear in it.

That produces a trap that runs in both directions. A clean service-side curve gets read as "no
problem found" on a workload that really is slow, and an ordinary p99 excursion gets escalated
as service degradation. Two further confusions are common: a table-wide latency average blends
`GetItem` with `Scan`, whose documented expectations differ by an order of magnitude, and a
flat latency curve beside non-zero throttle events looks healthy when it is in fact the
signature of retry-inflated client latency.

This skill collects the signals that separate those cases, commits to exactly one
classification, and says plainly what the metrics do not cover.

## Key Capabilities

- **One classification, chosen in a fixed order** — service-side (`SystemErrors`),
  throttle-induced (throttle events coinciding with the latency rise), systemic degradation
  (sustained `Average`/p50), an isolated tail spike (p99 elevated, p50 normal), nominal, or
  explicitly indeterminate when the data cannot support a verdict
- **Per-operation analysis** — `SuccessfulRequestLatency` as `Average`, p50, p90, p99,
  `Maximum` and `SampleCount` for every operation, because a singleton operation and a
  multi-item operation cannot share a threshold. Multi-item operations are judged against their
  own trailing baseline, never an absolute number
- **Throttle-induced detection that survives a flat curve** — intersects the timestamps of
  elevated-latency periods with the timestamps of throttle events, rather than comparing totals
- **Client-side attribution** — when the service-side portion is normal, the report says where
  the remaining time must be and names the measurement that would confirm it, instead of
  closing the investigation
- **Nine contributing-factor rules** — connection cost, mean item size, multi-item request
  shape, on-demand ramp, provisioned ceiling, read-after-write consistency, client-to-endpoint
  distance, partial metric coverage, and an explicit "asked but not measurable" rule
- **A "Not Recommended" section** — two remediations that circulate widely for DynamoDB
  latency are contradicted by AWS documentation, and the report names both

## Safety Posture

| Property | Behavior |
|---|---|
| Mutations | None. No `Put*`, `Update*`, `Delete*`, `Create*` |
| Data-plane reads | **None.** No `Scan`, `Query`, `GetItem`, or `BatchGetItem`. Mean item size comes from `DescribeTable` metadata, not from reading items |
| Consent gates | Not needed — there is no data-plane cost to consent to |
| API surface | `sts:GetCallerIdentity`, `dynamodb:DescribeTable`, `cloudwatch:GetMetricData`. That is the entire allowlist |
| Cost | CloudWatch `GetMetricData` charges per metric queried; a single run is a small number of metric queries. No read or write capacity is consumed on the table |
| `NoData` handling | Never coerced to zero. A metric that published nothing blocks the nominal classification rather than confirming it |
| Untrusted input | Resource names, tags, and pasted logs are treated strictly as data |

## Prerequisites

- **IAM:** the actions this skill uses — `cloudwatch:GetMetricData`,
  `cloudwatch:GetMetricStatistics`, `dynamodb:Describe*` — are already granted by the
  `AIDevOpsAgentAccessPolicy` managed policy that DevOps Agent roles carry. **No addition to
  `cloudformation/devops-agent-skill-policies.yaml` is required**, and no data-plane permission
  is requested. If a call is denied, the cause is a boundary or scoping policy rather than a
  missing grant.
- **A live table.** The skill's method is collect-then-threshold; it deliberately refuses to
  run its apparatus against a pasted dashboard or a historical incident, and answers from the
  symptoms instead.
- **Metric history.** A table younger than the analysis window cannot have full coverage; the
  skill computes and reports actual coverage rather than assuming it.

## Limitations

- **It cannot see client-side or network time.** No DynamoDB metric can. Where that is the
  answer, the skill says so and names the measurement — SDK latency metric logging, or
  distributed tracing on the caller.
- **It cannot attribute latency to an index.** `SuccessfulRequestLatency` has `TableName`,
  `Operation`, and `StreamLabel` dimensions; there is no index dimension.
- **It reports mean item size, not the distribution.** A few very large items can drive a tail
  while the mean looks ordinary. Measuring that needs item reads, which this skill does not do.
- **It does not classify which throttle ceiling was hit.** It establishes that throttling
  coincides with the latency; table, partition, account, and on-demand-max classification is
  read from the cause-specific throttle metrics and is out of scope.
- **It does not size capacity, redesign a data model, recommend indexes, diagnose DNS or VPC
  connectivity, or request quota increases.**
- **Thresholds are heuristics.** DynamoDB publishes no latency SLA. The skill states its own
  numbers as its own.

## Agent Types

Chat tasks, Prevention, Incident RCA.

## Uploading to AWS DevOps Agent

```bash
cd skills
zip -r dynamodb-latency.zip dynamodb-latency/ \
  -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' \
  -x '*/.claude/*' '*/README.md' '*/.skilleval.yaml' '*/CHANGELOG.md' '*/evals/*'
```

Then in the DevOps Agent console: open your Agent Space → **Skills** → **Add skill** → upload
`dynamodb-latency.zip` → select the agent types above.

## How to Use This Skill

### Chat tasks

- "Our `orders-prod` table feels slow this afternoon — is it DynamoDB?"
- "p99 on `sessions-prod` is 80 ms but p50 is 4 ms. Is that a problem?"
- "We're getting intermittent DynamoDB timeouts from the checkout service. Where is the time
  going?"
- "The first call to DynamoDB after a quiet period takes over a second. Why?"
- "Compare `Query` and `GetItem` latency on `orders-prod` over the last 14 days."

### Prevention

- "Review the latency profile of `orders-prod` before Friday's peak."
- "We're moving `sessions-prod` to on-demand. What latency risks should we expect during the
  ramp?"
- "Which of these five tables has the worst tail latency?"

### Incident RCA

- "Latency on `payments-prod` tripled at 14:05. Classify it and tell me what the evidence
  supports."
- "Our dashboard shows normal DynamoDB latency but the service is timing out. Reconcile that."

### What it will decline to do

- Name the hot partition key, or measure item size distribution — both need evidence this skill
  does not collect
- Tell you which throttle ceiling was hit
- Recommend an index or a key-schema change
- Run its apparatus with no live table to read, or against a pasted report

## Related Links

- [Troubleshooting latency issues in Amazon DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html)
- [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)
- [Monitoring DynamoDB with Amazon CloudWatch](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Monitoring-metrics-with-Amazon-CloudWatch.html)
- [DynamoDB read consistency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html)
- [On-demand capacity mode](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)
- [In-memory acceleration with DAX](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.html)
