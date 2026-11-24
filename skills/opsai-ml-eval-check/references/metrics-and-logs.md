# Metrics & Logs Reference — evaluation and quality signals

How to **collect** the quality signals this skill reasons about. The analysis of what a
finish-reason shift means lives in `references/finish-reason-analysis.md`; this file is the
collection mechanics — which log group, which field, which query, which metric.

Trimmed deliberately to the evaluation set. Guardrail, agent, SageMaker endpoint, cost and triage
metrics are **not** this skill's scope: a finding built on them fails the scope rule. SageMaker-side
evaluation job signals are in scope and are in §7.

All metric names are as published by AWS. Thresholds are never invented here — the only
numeric bar in this domain is the **derived** >10pp finish-reason bar recorded in
`references/finish-reason-analysis.md`.

---

## 1. The invocation log group — resolve it, never assume it

`stopReason` is **not** a CloudWatch metric. There is no `AWS/Bedrock` metric for finish
reasons, so the only honest route to a measured finish-reason distribution is a query against
the Bedrock **model invocation logs**.

**Always probe the logging configuration first.** The log group name is a customer choice and
differs per account:

```
bedrock:GetModelInvocationLoggingConfiguration     (read-only, no arguments)
```

Read three fields from the response:

| Field | Why it decides the answer |
|---|---|
| `cloudWatchConfig.logGroupName` | the group to query; absent → CloudWatch delivery is off |
| `textDataDeliveryEnabled` | `false` → records arrive without prompt/response text |
| `s3Config.bucketName` | S3-only delivery → query with Athena, not Logs Insights |

Then branch, and say which branch you took:

- **Logging enabled** → query the named group (below) and report the distribution with
  **both** the current and the baseline share (LLM-EVAL-012).
- **Enabled but the query is denied or returns nothing in the window** → name the group, say
  the query was attempted, say what came back, and say the consequence. That is an honest
  answer and a complete one.
- **Logging disabled** → state that finish-reason drift **cannot be confirmed** from metrics
  alone, name what would be needed (invocation logging with text delivery, or the
  LLM-EVAL-013 metric filter), and claim **no measurement**. A quantified drift claim with
  logging off is a fabrication.

If `GetModelInvocationLoggingConfiguration` itself is denied, that is a disclosed gap — report
the API and resource you could not read, and do not infer the logging state from the absence
of an error.

## 2. Invocation-log record schema — the fields this skill reads

One record per invocation. Only the quality-relevant fields are listed; a record carries more.

| Field | Meaning | Feeds |
|---|---|---|
| `timestamp` | invocation time, used to bound the window | every finding's window column |
| `modelId` | the invoked model; the distribution is **per model** | LLM-EVAL-012 |
| `output.outputBodyJson.stopReason` | why generation stopped — the finish reason | LLM-EVAL-012 |
| `input.inputTokenCount` | prompt size; a rising value crowds the output budget | LLM-EVAL-012 cause |
| `output.outputTokenCount` | generated tokens | LLM-EVAL-014 |
| `errorCode` | present only on failures; absent on success | excluded from the distribution |
| `schemaType` / `schemaVersion` | record shape | field-path drift |

Two collection traps, both of which silently distort a distribution:

- **The `stopReason` path is not fixed across model families.** Converse-shaped records carry
  it at `output.outputBodyJson.stopReason`; some invoke-shaped records nest it differently and
  some older records use `stop_reason`. Probe one record before trusting a `stats` query, and
  if the field resolves on a different path, say so next to the number.
- **Error records have no finish reason.** A record with `errorCode` set never reached
  generation. Leaving it in the denominator understates every share. Filter on
  `ispresent(stopReason)`, not on `not ispresent(errorCode)`.

Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html

## 3. The finish-reason distribution query

CloudWatch Logs Insights, against the group resolved in §1. Report the **window** you ran it
over alongside every share.

```
fields @timestamp, modelId, output.outputBodyJson.stopReason as stopReason
| filter ispresent(stopReason)
| stats count(*) as calls by stopReason, modelId
| sort calls desc
```

Collected read-only through `logs:StartQuery` + `logs:GetQueryResults` (or
`logs:FilterLogEvents` for a small window). Convert counts to shares yourself — the query
returns counts, and LLM-EVAL-012 is stated in percentage points.

**The baseline share is not optional.** Run the same query twice over two windows — the
incident window and a comparable earlier window of the same length — and report both. One
number is not a drift measurement, and `## Before You Present` fails an answer that carries
only the current share.

S3-only delivery: the same shape in Athena over the delivered JSON, with `stopReason`
projected out of the nested `output` struct.

## 4. The two AWS/Bedrock metrics in this skill's scope

Namespace `AWS/Bedrock`, dimension `ModelId`, read with
`cloudwatch:GetMetricData` / `GetMetricStatistics`. Reference:
https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html

| Metric | Unit | Statistic | What it tells this skill |
|---|---|---|---|
| `OutputTokenCount` | Count | Sum, Average | rising with flat `Invocations` is the truncation **precursor** (LLM-EVAL-014) |
| `Invocations` | Count | Sum | the flat-denominator half of LLM-EVAL-014 |

These two are **LLM-EVAL-014, a correlated precursor — not a measurement of truncation.**
Asserting a `max_tokens` share from them alone is a fabricated finding and the most likely way
this skill produces a confidently wrong answer. The share comes from §3 or it does not exist.

**"No datapoints" is not a measured zero** (`references/api-quirks.md` §10). No datapoints
usually means no traffic in the window or the metric was never emitted. Record each signal as
one of three states — `measured <value>` / `no-datapoints` / `not-queried` — and never collapse
the last two into "healthy".

## 5. The metric filter (LLM-EVAL-013) is a different question

Whether anything is *watching* finish reasons is answered from the log group's metric filters,
not from the distribution:

```
logs:DescribeMetricFilters --log-group-name <the group from §1>
```

An absent `{ $.output.outputBodyJson.stopReason = "max_tokens" }` filter (or one written on the top-level `$.stopReason`, which never matches) is LLM-EVAL-013 — the shift is invisible,
which is a finding in its own right even when the current distribution looks fine. The filter's
definition and the derived alarm bar are in `references/finish-reason-analysis.md`; the
telemetry-coverage view of the same filter is outside this skill.

## 6. Every call on this page is read-only

`GetModelInvocationLoggingConfiguration`, `StartQuery`, `GetQueryResults`, `FilterLogEvents`,
`DescribeMetricFilters`, `GetMetricData`, `GetMetricStatistics`. Nothing here creates a metric
filter, an alarm or a log group — those are recommendations the operator runs.

`bedrock:ApplyGuardrail` is **not** a collection call. It is billable, it invokes a guardrail
rather than describing one, and it must never be called by this skill.

## 7. SageMaker-side evaluation job signals

A SageMaker-side evaluation runs as a **recipe-driven training job** (a Nova eval recipe or an LLM-as-judge job), so it is **one-shot** and its health is read from the **describe API status plus the job's CloudWatch Logs group** (`/aws/sagemaker/TrainingJobs`), not a dedicated native metric namespace. Read `DescribeTrainingJob` (`TrainingJobStatus`, `FailureReason`) for a bad eval-dataset path, a malformed recipe, or a judge-model access error (LLM-SM-EVAL-002).

Eval scores are not native CloudWatch metrics — publish them to the `OpsAI/Evaluation` custom namespace and retain the eval output prefix so run-over-run comparison is possible (LLM-SM-EVAL-003). Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html
