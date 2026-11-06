# Runtime grading guards

Load once in S6. A guard blocks only the listed unsupported conclusion; it never removes a canonical row. Record applied guard IDs with each affected verdict. Detailed examples are in `../docs/false-positive-controls-guide.md` and are not runtime authority.

## N/A versus a failing verdict

N/A means the evidence could not be obtained — a denied API, a disabled log type, an absent telemetry source, a check that does not apply to this configuration. It never means the evidence was obtained and showed something missing.

A feature, control, or object observed to be **absent** is graded against its own row's pass criteria. Where the criteria read "X present" or "X enabled", observed absence is a FAIL with the observation as evidence, not N/A. Only where a row states its own N/A condition — for example a row that is explicitly N/A when the service is not enabled — does absence produce N/A, and then the row's wording governs. Two rows covering the same feature may therefore resolve differently on identical evidence; follow each row's text rather than generalising from the other.

| Guard | Applies to | Trigger | Prohibited conclusion from trigger alone | Evidence required before concluding |
|---|---|---|---|---|
| FP1 | CP9,O9,Sc23 | `pods_pending > 0` | scheduler broken; add nodes now | Distinguish capacity/fragmentation, taints, selectors, affinity/spread, EBS AZ, scheduling gates, autoscaler failure, or scheduler error; use pending-pods tree. |
| FP2 | O12,O15,P12,PM1,PM2,A6,AM3 | node CPU >80% | add capacity | Check requests/limits, dominant workload, sustained duration, autoscaler headroom, and whether high use is healthy efficiency. |
| FP3 | O7,P3,Op25 | `OOMKilled` | application memory leak | Distinguish low limit, legitimate burst, sidecar use, node pressure, runtime/GC; leak requires sustained growth over time; use OOM tree. |
| FP4 | S10,S12,AX2,AX3,CP diagnostics | audit HTTP 403 | authentication failure | 403 is authorization; inspect RBAC/access policy/namespace/intentional policy deny. Authentication failure requires 401 evidence. |
| FP5 | CP6,CP7,CP-M2,CP diagnostics | audit HTTP 409 | cluster unhealthy or application bug | Require sustained conflicts blocking one resource, unbounded workqueue retries, or controller convergence errors. |
| FP6 | CP4,CP5,CP-M6,ScM3,O17 | 429 spike | sustained API saturation; scale control plane | Verify >5-minute duration, priority level, reason, and caller. Low-tier rejection may be APF working; fix a noisy caller first. |
| FP7 | R6,R7,U9,A14 | missing PDB | always Critical/High | Use replicas, environment, workload type, and customer impact: high for production multi-replica stateful/customer-facing; lower for stateless/dev/batch. |
| FP8 | A6,A7,A8,AM3,P12,PM1,PM2,O12 | low utilization | remove capacity | Check peak history, DR/failover reserve, off-hours schedule, workload maturity, and autoscaler constraints; frame as right-sizing opportunity. |
| FP9 | S10,S11,S29,SM7,AX2 | broad permission | active compromise | Permission is posture/blast-radius evidence only. Compromise needs audit anomalies, unknown active identities/workloads, GuardDuty, or lateral movement. |
| FP10 | CP1,CP2,CP3,CP-M1,Sc3,R17 | object count growth | etcd near full | Correlate actual storage size, quota, 7-day growth rate, and dominant resource; fail pressure at >75% quota or >10% weekly growth. |
| FP11 | O4,O14,OM1,AX10,CP1–CP11,CP-M1–CP-M6 | empty log query | no errors; healthy | Verify logging enabled, log group/stream, delivery delay, window, and filters. Missing telemetry is a visibility gap, not PASS. |
| FP12 | U5,U5b,U5c,U5d,Sc14,Sc15,AX1 | deprecated API in source/chart | deployed upgrade blocker | Confirm live usage through Cluster Insights, audit logs, live API objects, or Helm stored manifests; source-only references are code hygiene. |

## Confidence contract

- **High:** one authoritative source or two independent correlated sources.
- **Medium:** one non-authoritative source or a bounded inference.
- **Low:** partial, stale, conflicting, or untestable evidence.
- Correlation is not root cause. Missing data cannot prove health or absence. Conflicting evidence forces Low confidence. Evidence older than seven days cannot override newer evidence.