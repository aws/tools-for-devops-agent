# Finding logic: verdict template, binding layer, escalation, review ratings

## Troubleshoot verdict template

Every troubleshoot answer uses these six headings in this order.

1. **Answer.** The question the user asked, answered first in one or two sentences. For example "Not stuck. The modification is in `optimizing`, which already applies the new IOPS."
2. **Evidence.** The values that support the answer, each with units and the time window (for example "average `<value>` IOPS, `<start>` to `<end>` UTC"). Throughput in MiB/s.
3. **Binding layer.** One of: Volume, Instance, Burst credits, Quota, Not EBS, AWS-side impairment, Not applicable.
4. **Recommendation.** Exact parameters (volume ID, dimension, target value, how the target was computed), or "No change". Mutating steps are proposals for a directed action.
5. **Separate findings.** Other true facts, labelled so they never change the Answer. For example a modification that succeeded on a volume whose instance caps delivered IOPS: the cap goes here, never as "the modification failed".
6. **Gaps.** What could not be checked and why (API denied, approval gate, metric absent).

## Binding-layer decision tree

Work through it in order. Use measured values and the limits read from the APIs. Do not use fixed percentage triggers.

1. Is the summed IOPS or MiB/s of all attached volumes flat at the instance EBS baseline, or are `EBSIOBalance%` / `EBSByteBalance%` draining or at 0?
   - Yes: **Instance**. Say "the volume has headroom; raising volume IOPS will not help; change the instance type". If a volume is also flat at its own limit, report both and fix the instance first, because volume changes cannot deliver above the instance ceiling.
2. Is the instance healthy and one volume flat at its own provisioned limit on the dimension its type is judged by?
   - Yes: **Volume**.
3. Is a gp2, st1 or sc1 volume's `BurstBalance` draining or at 0?
   - Yes: **Burst credits**.
4. Did an operation fail on a quota (error text names a limit)?
   - Yes: **Quota**. Use the Capacity and quota headroom section of [review-operational.md](review-operational.md).
5. Are all layers below their limits, latency at the volume's normal level, and queue length low?
   - Yes: **Not EBS**. Check CPU, memory, network and the application.
6. Are all layers below their limits but latency and `VolumeQueueLength` up while IOPS and throughput collapse?
   - Yes: **AWS-side impairment** (or injected latency). Never recommend more provisioning. Follow the escalation rules below.

### Qualitative attribution matrix for "is it storage?"

From the attribution draft, with the numeric CPU bands removed because no public source states them.

| CPU | Volume latency | Queue length | Likely attribution |
|---|---|---|---|
| High | High | High | Application drives heavy I/O. Both compute and storage are stressed |
| High | Normal | Low | Compute, not storage |
| Low | High | High | Storage. The application waits on I/O. Go to the decision tree |
| Low | Normal | Low | Neither. Check network, locks and the application |

"High" and "normal" mean compared with the same resource's own history and the type's documented expectation in [metrics-thresholds.md](metrics-thresholds.md).

## Escalation (shared capability)

Escalate to AWS Support when either is true:

- Scope signals: an open AWS Health event for the volume, Availability Zone or Region; several resources failing the same way; `DescribeVolumeStatus` reports the volume as impaired or a failing status check.
- A bounded investigation cannot explain the symptom: all layers below limits, no running AWS FIS experiment, no recent change, and the symptom persists.

Specific cases:

- Attach or detach stuck: the attachment stays in `attaching` or `detaching` and does not progress. Diagnose (instance state, device name, whether the volume is still mounted, any forced detach already tried), then escalate. A backend action can be needed.
- Modification in `optimizing` with `Progress` not increasing across several reads, or still optimizing after 24 hours. Tell the user the Amazon EBS User Guide says some performance changes take more than 24 hours, so this is a check, not a fault finding. Escalate with the evidence.
- Snapshot stuck in `pending` with no progress change over the same kind of window.

Evidence pack to include:

1. Account placeholder, Region, volume IDs, instance IDs, snapshot IDs as read from the APIs
2. The time window (first ALARM time, symptom start)
3. Metric evidence with units (IOPS, MiB/s, latency, queue length, `EBSIOBalance%`, `BurstBalance`)
4. Volume status and AWS Health results
5. `DescribeVolumesModifications` records, and AWS CloudTrail results if that optional lookup was available
6. What was ruled out and how
7. The Gaps list

## Review ratings

Each review finding has:

| Field | Values |
|---|---|
| Severity | `High`, `Medium`, `Low`, or `Indeterminate` (the data could not be read) |
| Evidence | The values and API that show it |
| Fix | A specific change with parameters |
| Mutating? | Yes or No. Yes means the fix is a proposal for a directed action |

Rate by impact if the risk happens, not by count. Severity guidance per area is in [review-operational.md](review-operational.md). The report layout is in [review-report-format.md](review-report-format.md).

Every Review mode response MUST begin with the Summary table that rates all six areas (capacity and quota headroom, observability, cost hygiene, resilience, encryption posture, deletion protection). The Summary table is required, not optional, and it comes before any per-area detail. Keep the six areas and the `High` / `Medium` / `Low` / `Indeterminate` scheme as written; do not invent new areas or ratings.

## Sources

- Volume status checks: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-status.html
- Detaching volumes: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-detaching-volume.html
- Monitoring volume modifications: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- Modification duration (more than 24 hours in some cases): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html and https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- Amazon EBS performance: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-performance.html
- Published S3 skill rating scale (format only): https://github.com/aws/tools-for-devops-agent
