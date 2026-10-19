# Changelog

## 1.1.0

Addresses the TFC review on the Project Nebula task (V2375108355). The theme of every change:
report only what the evidence proves, and hand off explicitly where it stops.

### Collection defects fixed (found while verifying the review against AWS documentation)

- **`SystemErrors` was queried on `TableName` alone, which DynamoDB never publishes.** The
  metric exists only on the `TableName` + `Operation` pair, so the 1.0.0 query always returned
  an empty series on a real table — `LT-01` could never fire, and a healthy table could never
  reach a clean verdict. Now queried per operation. The synthetic eval fixture had masked this.
- **`UserErrors` was treated as a table metric.** It is aggregated across the account and
  Region; it is no longer used as evidence about a table and is labelled account-wide if shown.
- **Empty event-counter series are now classified, not assumed.** DynamoDB publishes error and
  throttle counters only when events occur. An empty series is "none recorded" only when the
  query used the published dimensions and the operation was demonstrably active; otherwise it
  is unknown. 1.0.0 had no way to reach "measured zero" for these counters at all.
- `ThrottledRequests` is now queried per operation, and `Read`/`WriteThrottleEvents` for each GSI
  as well as the table — table-level throttle events exclude indexes.

### Classification

- **Outcomes are no longer exclusive.** Every outcome is evaluated; the first qualifying one is
  the primary outcome and every other qualifying condition, or signal present but not causal,
  is reported under **Also observed**. Each primary outcome carries a **confidence** with its
  reasons.
- **`LT-01` requires causal evidence.** Organic `SystemErrors` (FIS-induced errors subtracted
  via the new `FaultInjectionServiceInducedErrors` collection) must persist and coincide in time
  with elevated latency — or with client-reported slowness, since the SDKs retry 500s — or occur
  on an operation where no request succeeded at all (`SystemErrors` is now queried for every
  operation, so a total failure is no longer invisible). Errors that do not meet that bar are
  reported by the new `CF-05` as observed, not causal.
- **Baselines replace universal thresholds.** Each operation is compared with its own 7-day
  baseline, computed by CloudWatch as a single long-period datapoint. Singleton operations keep
  the 10 ms / 50 ms absolute floor only as a fallback without a baseline; multi-item and
  transactional operations never use an absolute number. A `SampleCount` floor excludes periods
  too sparse to read a percentile. Observation window, periods, persistence, and coincidence are
  now defined in one place.
- **`LT-04` tail elevation distinguishes isolated, recurring, and sustained tails,** and reports
  breaches of an SLO the user states. A recurring or sustained tail is actionable even with
  normal p50. The "slow first call" connection-cost clause was removed from it: client activity
  is excluded from `SuccessfulRequestLatency`, so a client cold start cannot raise its p99.
- Outcome names are canonical across the skill: Indeterminate, Service-side errors,
  Throttle-induced, Typical-latency elevation, Tail elevation, No DynamoDB-side elevation. The
  `description` now names all six (1.0.0 omitted indeterminate).

### Observations separated from hypotheses

- Every template is split into **Observed**, **Not established**, and **Next**.
- **`LT-05` and `CF-01` no longer attribute residual latency to the client.** A normal
  `SuccessfulRequestLatency` now reads as "no DynamoDB-side latency elevation"; candidate client,
  SDK, and network causes are listed as unconfirmed, with SDK latency logging, tracing, or the
  `aws-vpc-dns-investigation` skill as the next step. A pre-render check blocks "is
  client-side" as a conclusion.
- `CF-02` (mean item size from `TableSizeBytes / ItemCount`) is Info-only background context.
- `CF-03` no longer asserts that time "scales with work"; it uses the new `ReturnedItemCount`
  collection as evidence where available, and says when the returned count is flat.

### Remediation accuracy

- Connection-reuse advice is SDK-specific: JavaScript v3 reuses connections by default; Java 2.x
  and botocore pool per client; the keep-alive `GetItem` is noted as consuming read capacity.
- Retries and hedging are conditioned on operation idempotency and the application's latency
  objective; transaction client tokens are documented.
- DAX is recommended only for read-heavy workloads that tolerate eventual consistency, with its
  documented trade-offs: eventually consistent node replication, strongly consistent and
  transactional reads passed through uncached, a query cache not invalidated by item writes, and
  negative caching.
- The strongly-consistent-reads warning now uses the documented wording ("may increase
  latency") rather than "make things worse".

### Scope

- Throttling diagnosis moved out: the 1.0.0 on-demand-ramp and provisioned-ceiling factors and
  the pre-warm recommendation are replaced by `CF-04`, a structured handoff (table or GSI,
  operation, counters, periods, coincidence, capacity) that fires whenever throttling is
  recorded.

### Packaging

- SKILL.md uses a checklist workflow with an explicit pre-output validation step, and links each
  reference with the condition for loading it.
- Author metadata uses the GitHub handle.

### Correction to the 1.0.0 entry

The 1.0.0 live A/B is described below as identifying "DynamoDB-side tail queueing at the
capacity ceiling with burst-capacity absorption". That is a mechanism the metrics did not
establish. What the run showed: on a table whose successful-request latency rose with write
volume against a low provisioned ceiling and no recorded throttling, the no-skill agent called
it a client-side artifact, and the skill correctly kept it on the DynamoDB side.

## 1.0.0

- Initial version.
- Classifies a DynamoDB table's latency profile into exactly one of six outcomes —
  indeterminate, service-side, throttle-induced, systemic degradation, isolated tail spike, or
  nominal — in a fixed decision order, with `indeterminate` evaluated first so that a window
  without data cannot render as a healthy one.
- Collects `SuccessfulRequestLatency` as `Average`, p50, p90, p99, `Maximum` and `SampleCount`
  **per `Operation` dimension**; singleton operations are judged against absolute thresholds
  (10 ms sustained, 50 ms tail), multi-item operations against their own trailing baseline.
- Detects throttle-induced latency by intersecting elevated-latency period timestamps with
  throttle-event period timestamps, so it holds when the service-side curve stays flat —
  throttled requests are excluded from `SuccessfulRequestLatency` by definition.
- Nine contributing-factor rules: client-side connection cost, mean item size, multi-item
  request shape, on-demand ramp, provisioned ceiling, read-after-write consistency,
  client-to-endpoint distance, partial metric coverage, and an explicit "asked but not
  measurable" rule.
- Read-only with **no data-plane access**: allowlist is `sts:GetCallerIdentity`,
  `dynamodb:DescribeTable`, `cloudwatch:GetMetricData`. Requires no addition to
  `cloudformation/devops-agent-skill-policies.yaml` — those actions are already in the
  `AIDevOpsAgentAccessPolicy` managed policy.
- `references/dynamodb-facts.md` carries the documented mechanics this diagnosis depends on,
  each cited to AWS documentation, and records two remediations that circulate widely for
  DynamoDB latency and that the documentation contradicts: setting a very low socket timeout
  (the often-repeated 50 ms, which AWS gives as its anti-example), and switching to strongly
  consistent reads "for latency" (twice the throughput, possibly higher latency, unsupported on
  GSIs). Both appear in a mandatory "Not Recommended" report section.
- Corrects stale guidance that `SuccessfulRequestLatency` supports only Min/Max/Avg/SampleCount:
  `Percentile` is a valid statistic, including custom percentiles, which is what makes the
  p50-versus-p99 distinction available at all.
- Scope boundaries are explicit: no item sampling, no hot-key identification, no throttle-level
  classification, no data-model or index recommendations, no DNS or VPC diagnosis, no capacity
  sizing or quota requests. These are stated in the skill body rather than as a keyword list in
  the `description`, because the `description` is an activation surface: an earlier draft that
  listed the non-goals there ("does not … indexes … items") over-triggered on a data-level
  question at a measured rate of 0.67 across three runs, since the disclaimer supplied the very
  terms that attract activation. Rewriting it as a positive scope statement took that to 0.33
  while the latency queries held at 1.0.
- Trigger measurement note: single-run trigger evaluation is noisy enough to invert a verdict —
  an unrelated negative control ("reduce my S3 storage costs") failed at 1.0 on one run and
  measured 0.33 and then 0.0 over three. Boundary claims here rest on 3-run measurements.
- Live-validated against real AWS (us-west-2) before submission, not just skill-eval. Confirmed
  the load-bearing mechanics against live CloudWatch: `SuccessfulRequestLatency` returns the
  `Percentile` statistic (p50/p99), the `Operation` dimension resolves per-operation, and a
  metric that published nothing returns as a distinguishable empty series rather than a zero.
  A live A/B in a DevOps Agent space showed the skill correcting a wrong no-skill diagnosis: on
  a table whose successful-request latency rose in lockstep with writes, the no-skill agent
  called it a "client-side artifact", while with the skill it correctly identified DynamoDB-side
  tail queueing at the capacity ceiling with burst-capacity absorption and no throttling. In the
  same space, installed alongside the `dynamodb-data-health-inspection` skill, a data-health
  prompt ("which indexes are unused, is TTL reclaiming storage") routed to that skill and not to
  this one — no cross-activation. Every latency run made zero data-plane calls.
