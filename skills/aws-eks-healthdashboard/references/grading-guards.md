# Grading guards (false-positive controls)

Load this before grading any scorecard row (CA / CP / CP-M / CPM / NH). A guard blocks **only** the listed unsupported conclusion from a raw trigger — it never removes a check and never forces a PASS. When a guard applies to a verdict, record the guard ID alongside the status in the dashboard's detailed findings (e.g. "⚠️ ATTENTION (FP6 applied)").

These are the same false-positive controls the `aws-eks-operations-review` skill applies; the `Applies to` column is remapped to this skill's check IDs. IDs kept in sync with that skill for cross-consistency.

| Guard | Applies to | Trigger | Prohibited conclusion from trigger alone | Evidence required before concluding |
|---|---|---|---|---|
| FP1 | CP9, NH14, NH36 | `pods_pending > 0` | scheduler broken; add nodes now | Distinguish capacity/fragmentation, taints, selectors, affinity/spread, EBS AZ, scheduling gates, autoscaler failure, or scheduler error before blaming the scheduler. |
| FP2 | NH7, NH8, NH16 | node CPU/mem > 80% | add capacity | Check requests/limits, dominant workload, sustained duration, autoscaler headroom, and whether high use is healthy efficiency. |
| FP3 | NH12, NH37 | `OOMKilled` | application memory leak | Distinguish low limit, legitimate burst, sidecar use, node pressure, runtime/GC; a leak requires sustained growth over time. |
| FP4 | CP19 (and any 403 in diagnostics) | audit HTTP 403 | authentication failure | 403 is **authorization**; inspect RBAC / access policy / namespace / intentional deny. An authentication failure requires 401 evidence. |
| FP5 | CP6, CP7, CP-M2 | audit HTTP 409 | cluster unhealthy or application bug | Require sustained conflicts blocking one resource, unbounded workqueue retries, or controller convergence errors — not isolated optimistic-concurrency retries. |
| FP6 | CP4, CP5, CP-M6 | 429 spike | sustained API saturation; scale the control plane | Verify > 5-minute duration, priority level, `reason`, and caller. Low-tier rejection may be APF working as designed; fix a noisy caller before recommending Provisioned mode. |
| FP7 | CP10, CP17 (eviction) | missing PDB / eviction stall | always Critical/High | Weigh replicas, environment, workload type, and customer impact: higher for production multi-replica stateful/customer-facing; lower for stateless/dev/batch. |
| FP8 | NH7, NH8 | low utilization | remove capacity | Check peak history, DR/failover reserve, off-hours schedule, workload maturity, and autoscaler constraints; frame as a right-sizing opportunity, not a defect. |
| FP10 | CP1, CP2, CP3, CP-M1 | object-count growth | etcd near full | Correlate actual storage size, quota, 7-day growth rate, and the dominant resource; fail pressure only at > 75% quota or > 10% weekly growth. |
| FP11 | CP1–CP11, CP-M1–CP-M9, NH-P*, NET-P*, CA3 | empty log query / no metric data | no errors; healthy | Verify logging is enabled, the log group/stream exists, delivery delay, the query window, and the filter. **Missing telemetry is a visibility gap (⚪ N/A or a FAIL finding), never a PASS.** For NH-P/NET this means an absent KSM/node-exporter/CNI-metrics-helper source is a gap finding, not a PASS. |
| FP12 | CA10–CA12 | deprecated API in source/chart | deployed upgrade blocker | Confirm live usage through Cluster Insights, audit logs, live API objects, or Helm stored manifests; source-only references are code hygiene, not an active blocker. |

> FP9 (broad IAM permission ≠ active compromise) from the ops-review skill has no equivalent row here — this dashboard grades no IAM posture check. The ID is intentionally skipped to keep numbering aligned with `aws-eks-operations-review`.

## The empty-result rule (FP11 expanded)

This is the single most common false PASS in a health dashboard. A CloudWatch Logs Insights query returning **zero rows does not mean the signal is healthy** — it is *unknown* until you verify:

1. Control-plane logging is enabled (CA3 / CPM1) — `api` and `audit` at minimum.
2. The log group `/aws/eks/{cluster}/cluster` exists and has a live `kube-apiserver-audit` stream.
3. Delivery delay — audit events can lag; a query over the last 5 minutes may legitimately be empty.
4. The query window and filter are correct.

Only after all four check out is an empty result graded ✅. Otherwise it is ⚪ N/A with the real reason, or a FAIL finding that logging/telemetry is missing. The same rule applies to `GetMetricData` returning no datapoints for the CP-M metric-native checks.

## Confidence contract

Attach a confidence level to every non-trivial verdict:

- **High:** one authoritative source, or two independent correlated sources.
- **Medium:** one non-authoritative source, or a bounded inference.
- **Low:** partial, stale, conflicting, or untestable evidence.

Rules:

- Correlation is not root cause.
- Missing data cannot prove health or absence.
- Conflicting evidence forces **Low** confidence (and, per `metric-sources.md` §5, surfaces the disagreement as its own finding).
- Evidence older than seven days cannot override newer evidence.
