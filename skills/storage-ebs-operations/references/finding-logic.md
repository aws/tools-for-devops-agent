# Finding logic: verdict template, binding layer, escalation, review ratings

## Troubleshoot verdict template

Every troubleshoot answer uses these six headings in this order.

1. **Answer.** The question the user asked, answered first in one or two sentences. For example "Not stuck. The modification is in `optimizing`, which already applies the new IOPS."
2. **Evidence.** The values that support the answer, each with units and the time window (for example "average `<value>` IOPS, `<start>` to `<end>` UTC"). Throughput in MiB/s.
3. **Binding layer.** One of: Volume, Instance, Burst credits, Quota, Not EBS, AWS-side impairment, Indeterminate, Not applicable.
4. **Recommendation.** Exact parameters (volume ID, dimension, target value, how the target was computed), or "No change". Mutating steps are proposals for a directed action, written as described in [Change proposals](#change-proposals).
5. **Separate findings.** Other true facts, labelled so they never change the Answer. For example a modification that succeeded on a volume whose instance caps delivered IOPS: the cap goes here, never as "the modification failed".
6. **Gaps.** What could not be checked and why (API denied, approval gate, metric absent).

## Limits table for performance verdicts

Every performance verdict puts the numbers side by side in one table under Evidence, so the reader can see which limit binds without doing the arithmetic. Use the values measured in this session, with the time window.

| Layer | Measured demand | Limit | Headroom | Binds? |
|---|---|---|---|---|
| Volume `<id>` IOPS | `<n>` IOPS | provisioned `<n>` IOPS | `<n>` IOPS | Yes or No |
| Volume `<id>` throughput | `<n>` MiB/s | `<n>` MiB/s (provisioned for gp3, computed from IOPS for io1 and io2) | `<n>` MiB/s | Yes or No |
| Each other attached volume, including the root volume | `<n>` IOPS, `<n>` MiB/s | its own limits | | |
| Instance EBS baseline (sum of all attached volumes) | `<n>` IOPS, `<n>` MiB/s | `<n>` IOPS, `<n>` MB/s from `DescribeInstanceTypes` = `<n>` MiB/s | `<n>` IOPS, `<n>` MiB/s | Yes or No |

Below the table:

- Show the tie-out arithmetic that links the numbers, for example "500 IOPS x 256 KiB average I/O size = 125 MiB/s, which is the provisioned throughput". Average I/O size = bytes / operations over the same period.
- Give the exact target and how it was computed, for example "instance baseline 149 MiB/s minus 8 MiB/s used by the other volumes = 141 MiB/s available, so the target is 140 MiB/s". Also give the next limit after the change (the instance baseline, or the type rule) and, when the instance becomes the next limit, the baseline of the next larger instance size from `DescribeInstanceTypes`.
- State the recent history: the alarm state history (`DescribeAlarmHistory`), the latest modification record and the AWS CloudTrail `ModifyVolume` events for the volume (or a Gap), and whether the same pattern appears earlier in a longer metric window (for example the last 24 hours at a 1-hour period).

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
6. Are all layers below their limits but latency and `VolumeQueueLength` up while IOPS and throughput collapse? This pattern alone does not prove an AWS-side impairment. Check for a direct signal:
   - `VolumeStalledIOCheck` failed (value 1) for the volume, or
   - `DescribeVolumeStatus` reports the volume as impaired or a status check as failed, or
   - an open AWS Health event for the volume, its Availability Zone or its Region.

   Then decide:
   - A running AWS FIS experiment targets the volume or instance: the latency is injected. Say so plainly; it ends with the experiment (see Step 5 of [troubleshoot-performance.md](troubleshoot-performance.md)). Never recommend more provisioning.
   - One or more direct signals: **AWS-side impairment**. Never recommend more provisioning. Follow the escalation rules below.
   - No direct signal and no FIS experiment: **Indeterminate**. Keep the cause open. Do not name AWS-side impairment and do not recommend more provisioning. Present the candidate causes as described in the next section. Tell the customer to check the AWS Health Dashboard for an ongoing AWS-side issue and to watch the volume status checks and `VolumeStalledIOCheck`. If the symptom persists, follow the escalation rules below.

## Indeterminate: candidate causes

An Indeterminate verdict is a short list of candidate causes, not a single sentence. The Binding layer stays Indeterminate. For each candidate give:

- a title that matches what the data shows (for a cause the data rules out, say so in the title, for example "Volume or instance limit: ruled out"),
- the supporting observations, with numbers derived from the measured or given values,
- the specific check that would confirm it or rule it out, and its result if you ran it.

Useful derived numbers for the observations:

- Percentage of each limit in use (measured IOPS and MiB/s against the volume and the instance limits).
- Time per I/O from queue length and IOPS (Little's law): time per I/O in ms = average queue length / IOPS x 1,000. A queue that grows while IOPS falls means each I/O takes longer, not that a rate limit was reached.
- Average I/O size = throughput / IOPS. A change in I/O size changes how much throughput a given IOPS value delivers.

List only the candidates that fit the volume type and the data. For example, burst credits apply to gp2, st1 and sc1, not to gp3 or io2. Typical candidates and their checks:

| Candidate | Check that confirms it or rules it out |
|---|---|
| A slowdown in the Amazon EBS storage path that the checks have not flagged | `DescribeVolumeStatus` (status and the I/O performance check, which covers attached io1, io2 and gp3 volumes), `VolumeStalledIOCheck` (1 means failed), AWS Health `DescribeEvents` for Amazon EBS and Amazon EC2 in the Region and Availability Zone. Recheck while the symptom lasts. If it persists with all checks clean, escalate to AWS Support with the evidence pack |
| Injected latency from a fault injection experiment | AWS FIS `ListExperiments` for a running experiment with `aws:ebs:volume-io-latency` or `aws:ebs:pause-volume-io` that targets the volume or instance |
| A change in the workload's I/O pattern (larger I/O, more random I/O, more writes) | Average I/O size and the read and write split before and during the alarm window, from `VolumeReadBytes`, `VolumeWriteBytes`, `VolumeReadOps` and `VolumeWriteOps` |
| A cause outside Amazon EBS on the instance (application locks, file system, CPU) | `CPUUtilization` and the attribution matrix below. OS-level data such as `iostat` is outside this skill, so ask the customer for it |
| Sub-minute bursts at a limit | Not visible in 1-minute data. Say that headroom is not proven from averages alone |
| Volume initialization after a restore from a snapshot | `DescribeVolumes` `SnapshotId` and `CreateTime` |
| Volume or instance limit | The limits table. When demand is far below every limit, title it as ruled out |

Close with the answer to the user's question (for example "adding IOPS will not help, because the volume uses 15 percent of its provisioned IOPS"), what to watch (AWS Health Dashboard, volume status checks, `VolumeStalledIOCheck`), and when to escalate.

When the user gives the values and asks you to treat them as given, build the candidates from those values only. Do not query the account for other resources and do not mix account data into the given facts. List under Gaps that the values were not read from the APIs.

### Qualitative attribution matrix for "is it storage?"

From the attribution draft, with the numeric CPU bands removed because no public source states them.

| CPU | Volume latency | Queue length | Likely attribution |
|---|---|---|---|
| High | High | High | Application drives heavy I/O. Both compute and storage are stressed |
| High | Normal | Low | Compute, not storage |
| Low | High | High | Storage. The application waits on I/O. Go to the decision tree |
| Low | Normal | Low | Neither. Check network, locks and the application |

"High" and "normal" mean compared with the same resource's own history and the type's documented expectation in [metrics-thresholds.md](metrics-thresholds.md).

## Change proposals

Every mutating change (`ModifyVolume`, an AWS KMS key or key policy change, a quota request, an instance type change) is a proposal. Include all of these:

1. **Whether the change will help,** from the measured data. If the data shows it will not help, say so first and say what will.
2. **The exact call,** as an AWS CLI command with every parameter filled in from the APIs, for example `aws ec2 modify-volume --volume-id <volume-id> --iops <target> --region <region>`. If the user named a target, give the command for that value. If a different value is better (for example the instance EBS baseline caps what the volume can deliver), also give the command for the recommended value and how it was computed.
3. **Expected effect,** including the next limit (for example "the instance baseline of `<n>` IOPS then caps delivered IOPS").
4. **For a volume modification:** the state sequence (`modifying`, `optimizing`, `completed`), the rule of up to 4 modifications per volume in a rolling 24-hour window with each one completing before the next, and how many remain after this change from the AWS CloudTrail `ModifyVolume` count (or say the count is unconfirmed and list it under Gaps).
5. **Rollback,** as the exact reverse command and when it is possible (after the change completes for a volume, and it counts toward the 4; size cannot be reduced).
6. **Cost direction,** with a link to the pricing page. Do not type a price.
7. **The approval statement,** in plain words: "A typed approval in chat is not approval. This change runs only as a directed action that an operator approves on the approval card." If directed actions are not available in this Agent Space, say so and say that the customer can run the command above with their own credentials.

Delete-class operations are never directed actions. Give them only as manual customer steps after the owner confirms.

## Escalation (shared capability)

Escalate to AWS Support when either is true:

- Scope signals: an open AWS Health event for the volume, Availability Zone or Region; several resources failing the same way; `DescribeVolumeStatus` reports the volume as impaired or a failing status check.
- A bounded investigation cannot explain the symptom: all layers below limits, no running AWS FIS experiment, no recent change, and the symptom persists.

Specific cases:

- Attach or detach stuck: the attachment stays in `attaching` or `detaching` and does not progress. Diagnose (instance state, device name, whether the volume is still mounted, any forced detach already tried), then contact AWS Support.
- Modification in `optimizing` with `Progress` not increasing across several reads, or still optimizing after 24 hours. Tell the user the Amazon EBS User Guide says some performance changes take more than 24 hours, so this is a check, not a fault finding. Escalate with the evidence.
- Snapshot stuck in `pending` with no progress change over the same kind of window.

Evidence pack to include:

1. Account placeholder, Region, volume IDs, instance IDs, snapshot IDs as read from the APIs
2. The time window (first ALARM time, symptom start)
3. Metric evidence with units (IOPS, MiB/s, latency, queue length, `EBSIOBalance%`, `BurstBalance`)
4. Volume status and AWS Health results
5. The latest `DescribeVolumesModifications` record per volume, and AWS CloudTrail `ModifyVolume` events if that optional lookup was available
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
- `VolumeStalledIOCheck`: https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html
- AWS Health Dashboard: https://docs.aws.amazon.com/health/latest/ug/what-is-aws-health.html
- Detaching volumes: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-detaching-volume.html
- Monitoring volume modifications: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- Modification duration (more than 24 hours in some cases): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html and https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- Amazon EBS performance: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-performance.html
- Published S3 skill rating scale (format only): https://github.com/aws/tools-for-devops-agent
