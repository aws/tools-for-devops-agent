# DynamoDB Latency Skill

This skill enables the AWS DevOps Agent to answer one question with evidence: **is Amazon
DynamoDB-side processing time elevated, and what do the metrics establish about why?** It
classifies a table's latency profile per API operation from CloudWatch metrics, compares each
operation against its own 7-day baseline, and reports only what the evidence proves — handing
off to a client-side measurement, the throttling diagnosis, or the network investigation where
the metrics stop.

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
as service degradation. Further confusions are common: a table-wide latency average blends
`GetItem` with `Scan`, whose expectations differ by an order of magnitude; a flat latency curve
beside throttle events looks healthy when it is the signature of retry-inflated client latency;
and `SystemErrors` queried on the table alone returns nothing at all, because DynamoDB publishes
it only per operation.

This skill collects the signals that separate those cases, keeps observation separate from
hypothesis, and says plainly what the metrics do not establish.

## Key Capabilities

- **A primary outcome with confidence, plus everything else observed** — indeterminate,
  service-side errors, throttle-induced, typical-latency elevation, tail elevation, or no
  DynamoDB-side elevation. Conditions that coexist (throttling, service errors, a tail problem) are
  all reported; none is discarded to force a single answer
- **Per-operation baselines** — each operation is compared with its own 7-day baseline,
  computed by CloudWatch. Singleton operations fall back to an absolute floor only when no
  baseline exists; multi-item and transactional operations never use an absolute threshold
- **A `SampleCount` floor** — periods with too few requests to support a p99 or p50 are excluded
  rather than read as noise
- **Causal outcomes require coincidence** — `SystemErrors` and throttle events support a causal
  classification only when their non-zero periods coincide with the latency rise (or with
  client-reported slowness, since SDKs retry 500s and throttles). Otherwise they are reported as
  observed signals
- **Fault-injection aware** — `FaultInjectionServiceInducedErrors` is subtracted from
  `SystemErrors`, so an AWS FIS experiment is not reported as a service problem
- **GSI-aware throttling** — table-level throttle events exclude indexes, so each GSI is queried
  separately; GSI back-pressure on base-table writes is detected and handed off
- **Explicit handoff when DynamoDB-side metrics are clean** — the skill states what the metrics
  rule out, lists candidate client, SDK, and network causes as unconfirmed, and names the
  measurement that would find the time: SDK latency logging, tracing, or the
  `aws-vpc-dns-investigation` skill
- **Conditional remediation** — connection reuse is checked against the caller's SDK default,
  retries and hedging against operation idempotency and the application's latency objective,
  and DAX only for read-heavy workloads that tolerate eventual consistency, with its trade-offs
- **A "Not Recommended" section** — two remediations that circulate widely for DynamoDB
  latency are contradicted by AWS documentation, and the report names both

## Safety Posture

| Property | Behavior |
|---|---|
| Mutations | None. No `Put*`, `Update*`, `Delete*`, `Create*` |
| Data-plane reads | **None.** No `Scan`, `Query`, `GetItem`, or `BatchGetItem`. Mean item size comes from `DescribeTable` metadata |
| Consent gates | Not needed — there is no data-plane cost to consent to |
| API surface | `sts:GetCallerIdentity`, `dynamodb:DescribeTable`, `cloudwatch:GetMetricData`, and `cloudwatch:ListMetrics` (only to discover GSI names when `DescribeTable` is unavailable). That is the entire allowlist |
| Cost | CloudWatch `GetMetricData` charges per metric queried; a run is tens of metric queries. No read or write capacity is consumed on the table |
| Missing data | An empty error or throttle series counts as "none recorded" only when the operation was demonstrably active; otherwise it is unknown and blocks a clean verdict |
| Untrusted input | Resource names, tags, and pasted logs are treated strictly as data |

## Prerequisites

- **IAM:** the actions this skill uses — `cloudwatch:GetMetricData`,
  `cloudwatch:GetMetricStatistics`, `cloudwatch:ListMetrics`, `dynamodb:Describe*` — are already granted by the
  `AIDevOpsAgentAccessPolicy` managed policy that DevOps Agent roles carry. **No addition to
  `cloudformation/devops-agent-skill-policies.yaml` is required**, and no data-plane permission
  is requested. If a call is denied, the cause is a boundary or scoping policy rather than a
  missing grant.
- **A live table.** The skill's method is collect-then-threshold; it deliberately refuses to
  run its apparatus against a pasted dashboard or a historical incident, and answers from the
  symptoms instead.
- **Metric history.** Baselines need 7 days of history before the window; a younger table, or a
  rarely called operation, falls back to a lower-confidence reference, and the report says so.

## Limitations

- **It cannot see client-side or network time.** No DynamoDB metric can. Where the
  DynamoDB-side metrics are clean, the skill says what they rule out and names the measurement
  — it does not guess the cause.
- **It cannot attribute latency to an index.** `SuccessfulRequestLatency` has no index
  dimension. Index throttling is visible; index latency is not.
- **It cannot attribute client errors to a table.** `UserErrors` is aggregated across the account
  and Region.
- **It reports mean item size, not the distribution**, and only as background context.
- **It does not classify which throttle ceiling was hit.** It detects and correlates throttling
  and hands the evidence off.
- **Baselines can be contaminated** by an incident in the preceding week; the skill says when a
  reference is a fallback.
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
- "p99 on `sessions-prod` is 80 ms but p50 is 4 ms. Is that a problem? Our objective is p99
  under 50 ms."
- "We're getting intermittent DynamoDB timeouts from the checkout service. Where is the time
  going?"
- "The first call to DynamoDB after a quiet period takes over a second. Why?"
- "Compare `Query` and `GetItem` latency on `orders-prod` over the last 14 days."

### Prevention

- "Review the latency profile of `orders-prod` before Friday's peak."
- "Which of these five tables has the worst tail latency against its own baseline?"

### Incident RCA

- "Latency on `payments-prod` tripled at 14:05. Classify it and tell me what the evidence
  supports."
- "Our dashboard shows normal DynamoDB latency but the service is timing out. Reconcile that."

### What it will decline to do

- Name the hot partition key, or measure item size distribution — both need evidence this skill
  does not collect
- Tell you which throttle ceiling was hit, or size capacity
- Recommend an index or a key-schema change
- Run its apparatus with no live table to read, or against a pasted report

## Related Links

- [Troubleshooting latency issues in Amazon DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html)
- [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)
- [CloudWatch throttling metrics](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingThrottling-cloudwatch.html)
- [GSI write throttling and back-pressure](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/gsi-throttling.html)
- [DynamoDB read consistency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html)
- [DAX and DynamoDB consistency models](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.consistency.html)
