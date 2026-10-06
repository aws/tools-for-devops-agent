# Pillar: Control Plane Health

Canonical runtime definition for the mandatory 20-row Control Plane scorecard. Grade PASS / FAIL / N/A with bounded customer-visible evidence; apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) and [`../runtime/metrics-thresholds.md`](../runtime/metrics-thresholds.md). Background, rationale, and metric mappings are in [`../docs/control-plane-guide.md`](../docs/control-plane-guide.md) and are not runtime authority.

## Collection contract

1. Load [`../control-plane-health/metric-sources.md`](../control-plane-health/metric-sources.md), attempt CloudWatch logs/metrics, native EKS metrics, Prometheus, and connected observability sources, record detected/missing/errors, then drop it.
2. When logging is enabled, sequentially run and drop [`queries-cp01-cp09.md`](../control-plane-health/queries-cp01-cp09.md), [`queries-cp10-cp13.md`](../control-plane-health/queries-cp10-cp13.md), and [`queries-cp14-cp18.md`](../control-plane-health/queries-cp14-cp18.md). Load [`queries-cp19-cp25-diagnostics.md`](../control-plane-health/queries-cp19-cp25-diagnostics.md) only after a matching auth/write/change/WATCH/mutation/anonymous-access signal.
3. Always attempt public control-plane metrics. Disabled logging is a visibility FAIL but does not skip metric-backed rows. N/A is allowed only after the specific signal was attempted across available sources; cite the exact missing source/error. Empty output is unknown until logging, streams, delivery delay, filters, and window are verified.
4. Query IDs CP1–CP25 are not scorecard membership. Cluster Insights is AX1. EKS-managed hosts and etcd are not directly accessible.

## Canonical checks

| ID | Check | Source / pass predicate | Severity | Applicability / N/A |
|---|---|---|---|---|
| CP1 | etcd database size | `apiserver_storage_size_bytes` or `etcd_mvcc_db_total_size_in_use_in_bytes`; PASS <75% quota (8 GB Standard, 16 GB Provisioned) | High | N/A only when no size metric after source attempts; FP10/FP11. |
| CP2 | etcd growth rate | same series over 7d; PASS growth <10% | High | Needs comparable 7d points; otherwise N/A; FP10/FP11. |
| CP3 | etcd write concentration | audit writes by resource; PASS no resource >40% | High | Audit-log-only; N/A when logging unavailable after attempt; FP10/FP11. |
| CP4 | APF throttling, privileged | rejected requests for `system`/`leader-election`; PASS zero 429 | Critical | Metrics or audit; identify priority/reason/caller; FP6/FP11. |
| CP5 | APF throttling, workload | PASS no sustained workload-tier 429 >5m | Medium | Metrics or audit; isolated low-tier rejection may be healthy APF; FP6/FP11. |
| CP6 | API server 5xx | request totals/audit; PASS no sustained 5xx >5m | High | N/A only after metric/log attempt; FP5/FP11. |
| CP7 | API server LIST latency | request duration/audit; PASS average <1s and max <20s | High | Never average across API servers; N/A if no duration source; FP5/FP11. |
| CP8 | KCM QPS | KCM workqueue or audit caller rate; PASS no controller sustained >18 QPS | Medium | Native scheduler/KCM metrics require supported source/version; else audit or N/A. |
| CP9 | scheduler backpressure | `scheduler_pending_pods` plus pod age/events; PASS no unschedulable pod >10m | Medium | Distinguish capacity and constraints; FP1/FP11. |
| CP10 | eviction stalls | events/audit; PASS no pod failing eviction >30m | Medium | Log/event-only; N/A after both are unavailable. |
| CP11 | control-plane capacity mode | APF executing vs nominal seats; PASS no sustained saturation after workload-side fixes | High | Provisioned-mode recommendation only after noisy-client/APF fixes; FP11. |
| CP-M1 | etcd object counts | `apiserver_storage_objects`; PASS no abnormal dominant/rising resource | High | Requires metric series and actual size correlation; FP10/FP11. |
| CP-M2 | API inflight saturation | `apiserver_current_inflight_requests`; PASS not sustained near limits | High | Metrics-only; N/A if unavailable; FP5/FP11. |
| CP-M3 | large LIST responses | `apiserver_response_sizes` p99 by resource; PASS stable without memory pressure | Medium | Metrics-only; N/A if unavailable; correlate CP1/CP7. |
| CP-M4 | admission webhook health | rejection count and admission duration; PASS no sustained rejection and p99 <1s | High | Metrics-only; N/A if unavailable; correlate webhook inventory. |
| CP-M5 | etcd request latency | `etcd_request_duration_seconds` p99; PASS <1s | High | Metrics-only; N/A if unavailable; separates API from etcd latency. |
| CP-M6 | APF queue wait | request wait p99 by priority; PASS negligible privileged wait and no rising workload wait | High | Metrics-only; N/A if unavailable; FP6/FP11. |
| CPM1 | control-plane log types enabled | audited cluster configuration; PASS `api` and `audit` enabled | High | AWS read unavailable → N/A with required permission. |
| CPM2 | CloudWatch read access | query/read probe; PASS logs query and metric read succeed | High | Access denial → N/A with exact error and required permissions. |
| CPM3 | EKS control-plane metrics API reachable | `get --raw /apis/metrics.eks.amazonaws.com/v1/ksh/container/metrics`; PASS data on supported EKS | Medium | N/A on unsupported EKS version or explicit API/access error. |

## FAIL-only routing

After verdicts are fixed, route CP1/2/3/CP-M1/CP-M5 to [`remediations-etcd.md`](../control-plane-health/remediations-etcd.md); CP4/5/CP-M6 to [`remediations-apf.md`](../control-plane-health/remediations-apf.md); all other CP rows to [`remediations-apiserver.md`](../control-plane-health/remediations-apiserver.md). Load [`alerting.md`](../control-plane-health/alerting.md) only for customer-facing FAIL copy and [`procedures.md`](../control-plane-health/procedures.md) or the latency/429 decision tree only for unhealthy/ambiguous evidence. Prefer leaked-object/noisy-client fixes, then APF tuning, and Provisioned mode only after workload-side causes are exhausted. Never delete or mutate production resources without explicit approval.
