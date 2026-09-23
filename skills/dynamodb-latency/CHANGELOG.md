# Changelog

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
