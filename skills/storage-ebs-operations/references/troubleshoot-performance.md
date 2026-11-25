# Troubleshoot: performance attribution

## When this path applies

- The user reports slowness, timeouts or high I/O latency on an instance or application.
- A CloudWatch alarm fired on AWS/EBS metrics (`VolumeReadOps`, `VolumeWriteOps`, `VolumeReadBytes`, `VolumeWriteBytes`, `VolumeQueueLength`, `VolumeTotalReadTime`, `VolumeTotalWriteTime`, `VolumeAvgIOPS`, `VolumeAvgThroughput`, `BurstBalance`) or on instance `EBSIOBalance%` / `EBSByteBalance%`.
- A volume modification did not improve performance.
- The user asks how much IOPS or throughput to provision.

## Procedure

Discover everything from the alarm. Do not assume volume type, size, provisioned values, instance type, or tags; read them from the APIs.

### Step 1: Identify the alarmed volume(s)

- Get the alarm and its state history with `DescribeAlarmHistory` for the last 24 hours: when it first entered ALARM, and any earlier ALARM and OK transitions. Report earlier transitions as history, because they show whether the pattern recurs.
- Describe the impact in the symptom: the alarm name, metric, threshold, the datapoints that breached it, whether the alarm has actions configured, and the onset (the minute the metric left its normal level, for example "queue length rose from about 0 at `<time>` to 1.5 from `<time>`").
- Extract VolumeId from the alarm's metric dimensions. For metric-math alarms, read the VolumeId from each metric in the expression.
- If the alarm is on an instance metric (EBSIOBalance%, EBSByteBalance%), start from the InstanceId instead.
- If there is no alarm (a chat request such as "my app is slow"), start from the InstanceId the user gives, or ask for it.

### Step 2: Build the context

- DescribeVolumes on the alarmed volume: VolumeType, Size, Iops, Throughput, attachment InstanceId, tags (for naming only).
- DescribeInstances + DescribeInstanceTypes for that instance: instance type and its EBS baseline/maximum bandwidth (MiB/s) and IOPS.
- List ALL volumes attached to that instance (they share instance EBS bandwidth). Investigate this set, not the whole account.
- `DescribeInstanceTypes` reports throughput in MB/s. Convert to MiB/s before any comparison (see [data-collection.md](data-collection.md)).
- Always run `DescribeVolumeStatus` for every attached volume (volume status, status checks, scheduled events), whatever the alarm or request. Record the result as evidence. An impaired status or a failing check is a scope signal for escalation (see [finding-logic.md](finding-logic.md)), but still finish Steps 3 to 5.

### Step 2a: Read the exceeded checks

Read these four CloudWatch metrics early, for the alarm window, at a 1-minute period, with the `Maximum` statistic. They are the most direct evidence of which limit binds.

| Metric | Namespace and dimensions | A value of 1 means |
|---|---|---|
| `VolumeIOPSExceededCheck` | AWS/EBS, `VolumeId` AND `InstanceId` | The application tried to drive more IOPS than the volume's provisioned IOPS in that minute |
| `VolumeThroughputExceededCheck` | AWS/EBS, `VolumeId` AND `InstanceId` | The application tried to drive more throughput than the volume's provisioned throughput in that minute |
| `InstanceEBSIOPSExceededCheck` | AWS/EC2, `InstanceId` | The application tried to drive more IOPS than the instance's maximum EBS IOPS in that minute |
| `InstanceEBSThroughputExceededCheck` | AWS/EC2, `InstanceId` | The application tried to drive more throughput than the instance's maximum EBS throughput in that minute |

- Read the two volume checks for every attached volume, and the two instance checks for the instance. They exist only on Nitro instances (the instance checks not on bare metal), are not published for Multi-Attach volumes (volume checks), and are not available in AWS Outposts, Local Zones or Wavelength Zones.
- Report, for each check, the number of minutes at 1 and the window, for example "`VolumeIOPSExceededCheck` 1 in 37 of 37 minutes, `<start>` to `<end>` UTC".
- A volume check at 1 is direct evidence that the volume limit binds. An instance check at 1 is direct evidence that the instance limit binds; when both are at 1, the instance is fixed first (see [finding-logic.md](finding-logic.md)).
- If a query returns no datapoints, query again with both dimensions. If it is still empty, write "no datapoints", not 0, list it under Gaps, and judge the limit from the measured IOPS and MiB/s in Steps 3 and 4.
- Confirm the checks against the measured values in Steps 3 and 4. The limits table still shows the numbers.

### Step 2b: Rule EBS in or out (chat requests with no EBS alarm only)

This check runs only when the run did not start from an AWS/EBS alarm or an `EBSIOBalance%` / `EBSByteBalance%` alarm, for example a chat request such as "my app is slow, is it storage?". When an EBS alarm triggered the run, skip this step and run Steps 3 to 6 in full.

Read `CPUUtilization` for the instance, and the latency, `VolumeQueueLength`, `BurstBalance` (gp2, st1, sc1) and instance `EBSIOBalance%` / `EBSByteBalance%` (if published) for the volumes found in Step 2, over the same window. Use the qualitative attribution matrix in [finding-logic.md](finding-logic.md). Report "Not EBS" and stop tuning storage only if all of these hold: CPU is high, volume latency and queue length are normal, no `DescribeVolumeStatus` problem was found, and no burst or instance balance is draining or at 0. Otherwise continue with Step 3.

### Step 3: Measure each volume on the dimension(s) its type is limited by

Pull the last 30 minutes of AWS/EBS metrics at 1-minute granularity.

- Actual IOPS = (VolumeReadOps + VolumeWriteOps) / period seconds
- Actual throughput = (VolumeReadBytes + VolumeWriteBytes) / period, in MiB/s
- Avg latency in ms per operation = Sum(VolumeTotalReadTime) / Sum(VolumeReadOps) x 1,000, and the same for writes with VolumeTotalWriteTime and VolumeWriteOps. VolumeTotalReadTime and VolumeTotalWriteTime are in seconds, so the x 1,000 converts to milliseconds. `VolumeAvgReadLatency` and `VolumeAvgWriteLatency` are already in milliseconds
- VolumeQueueLength
- `VolumeAvgIOPS`, `VolumeAvgThroughput`, `VolumeAvgReadLatency` and `VolumeAvgWriteLatency` need both dimensions, `VolumeId` AND `InstanceId`, and exist only on Nitro instances. `VolumeAvgThroughput` is in KiB/s; divide by 1,024 for MiB/s. `VolumeQueueLength` uses `VolumeId` only. If `VolumeAvg*` returns nothing, use the Sum-based math above.
- Always read `VolumeIdleTime` (seconds in the period with no read or write submitted; `VolumeId` only). Idle percentage = Sum(`VolumeIdleTime`) / period seconds x 100. Report it as evidence for every volume. Near 0 means I/O was submitted for the whole period. That fits volume saturation, an instance limit and impairment, so use Steps 4 and 5 to tell them apart, and do not call the volume saturated on idle time alone. A volume that is mostly idle during the alarm window is unlikely to be the binding volume. There is no fixed band; compare with the volume's own history.

Apply the rule for the volume's type:

- gp3: IOPS and throughput are provisioned independently. Compare actual IOPS to Iops AND actual MiB/s to Throughput; either can bind.
- gp2: baseline IOPS = 3 x GiB (min 100), burst to 3,000 while BurstBalance > 0. Check BurstBalance draining or at 0.
- io1/io2 (incl. Block Express): compare actual IOPS to provisioned Iops AND actual MiB/s to the volume's throughput limit; either can bind. Throughput is not provisioned separately, but the documented throughput limit depends on the provisioned IOPS (see the io1 and io2 rows in [metrics-thresholds.md](metrics-thresholds.md)). Compute the limit from `Iops` with those rules, then compare. Do NOT use VolumeThroughputPercentage to judge throughput on io1/io2; it reports the % of provisioned IOPS delivered.
- st1/sc1: throughput-oriented with burst credits; compare MiB/s to the baseline/burst for the size and check BurstBalance.
- Judge io1, io2 and gp3 by both IOPS and throughput. Per-type limits are in [metrics-thresholds.md](metrics-thresholds.md).

### Step 4: Check the instance layer

- Sum actual IOPS and MiB/s across all attached volumes; compare to the instance type's EBS baseline from DescribeInstanceTypes.
- Aggregate across ALL attached volumes, including the root volume.
- Use the instance exceeded checks from Step 2a. `InstanceEBSIOPSExceededCheck` or `InstanceEBSThroughputExceededCheck` at 1 during the window is direct evidence that the instance is the binding layer.
- Check EBSIOBalance% / EBSByteBalance%. If they are draining or at 0, or the sum is at the instance limit, the INSTANCE is the binding layer and raising volume provisioning will not help.
- If instance metrics are healthy and a volume is at its own limit, the VOLUME is the binding layer.
- If `EBSIOBalance%` is absent, the instance size does not publish it. Use the summed values against the baseline.

### Step 5: Distinguish saturation from impairment

If queue length and latency are elevated but the volume and instance are both below their limits, this is NOT saturation. Suspect an impairment or injected latency; do NOT recommend increasing provisioning.

The impairment signature is IOPS and throughput collapsing while latency and `VolumeQueueLength` rise. Saturation looks different: metrics flat at the provisioned limit with modest latency. When you see the impairment signature, check in this order:

1. The `DescribeVolumeStatus` result from Step 2 (impaired status, failing checks, scheduled events). Read it again if the symptom started after Step 2.
2. The `VolumeStalledIOCheck` metric for the volume (dimensions `VolumeId` AND `InstanceId`, Nitro instances only; 0 passed, 1 failed). A failed check (value 1) means the volume's IO is stalled, which is an AWS-side impairment. Escalate per the rules in [finding-logic.md](finding-logic.md) and never recommend adding IOPS.
3. AWS Health `DescribeEvents` for Amazon EBS and Amazon EC2 events in the Region and Availability Zone.
4. AWS FIS `ListExperiments` for a running experiment that targets the volume or instance, with actions `aws:ebs:volume-io-latency` or `aws:ebs:pause-volume-io`. If one is running, say so plainly: the latency is injected and will end with the experiment.

Name AWS-side impairment only when item 1, 2 or 3 gives a direct signal (an impaired status or failed status check, a failed `VolumeStalledIOCheck`, or an open AWS Health event). If none of the four explains it, report the Binding layer as Indeterminate, keep the cause open, and present the candidate causes with their supporting observations and checks, as described in the Indeterminate section of [finding-logic.md](finding-logic.md#indeterminate-candidate-causes). Tell the customer to check the AWS Health Dashboard and the volume status checks, give the [detailed performance statistics](#detailed-performance-statistics-a-step-the-customer-runs) step for the customer to run during the symptom, and follow the escalation rules in [finding-logic.md](finding-logic.md).

If the user gives the values and asks you to treat them as given, run this step on those values only. Do not query the account for other volumes or alarms.

Filter the AWS FIS, AWS Health and AWS CloudTrail results to the volume, its instance and the volumes attached to that instance. Report only what applies to them, for example "no running AWS FIS experiment targets this volume or instance". Do not describe experiments, changes or alarms on other resources.

### Step 5b: Recent history

Run this step for every performance verdict.

- `DescribeVolumesModifications` for every attached volume. It returns only the most recent modification of each volume, so it shows the latest change and its state, not the full history.
- AWS CloudTrail `LookupEvents` for `ModifyVolume` on the affected volume over the last 24 hours, and for `AttachVolume`, `DetachVolume` and `ModifyInstanceAttribute` on the instance. The lookup is optional for the skill to work. If it is denied or empty, note under Gaps that only the latest modification per volume was checked, and continue.
- The affected volume's IOPS, MiB/s and latency over a longer window (the last 24 hours at a 1-hour period; when the volume is busy for that whole window, also the last 14 days at a 1-day period) to see whether the same pattern happened earlier.
- From that window, state two things. First, whether earlier peaks stopped at the same ceiling, which shows the limit is fixed. Second, the demand trend: demand that grew while latency per I/O stayed flat is growing load reaching a limit; latency per I/O that rose at the same demand points to a slowdown instead.
- Report the result as the history line in the Evidence, for example "never modified; the same 125 MiB/s plateau ran from `<start>` to `<end>` UTC; the alarm also fired at `<time>`".

### Step 6: Report

For each affected volume: type, provisioned vs actual, the binding dimension, and whether the volume or the instance is the binding layer. Recommend specific Elastic Volumes changes with target values (raise IOPS, raise gp3 throughput, change type, e.g. gp2 -> gp3), or an instance type change if the instance is the limit. Use MiB/s for throughput.

Write the report with the verdict template in [finding-logic.md](finding-logic.md) (Answer, Evidence, Binding layer, Recommendation, Separate findings, Gaps). Evidence always has the limits table from [finding-logic.md](finding-logic.md#limits-table-for-performance-verdicts), the tie-out arithmetic and the history line from Step 5b. In an investigation, the root cause finding description repeats the binding numbers, the history and the exact target, and the observations for the limits table, the instance check and the history are linked to it as supporting observations.

Elastic Volumes rules: up to 4 modifications per volume in a rolling 24-hour window; each must finish (modifying -> optimizing -> completed) before the next can start. There is no fixed waiting period between modifications; the next one is allowed once the previous one completes (January 2026 change). Rollback is possible once the modification completes, within that limit.

Sizing rules for any recommended target:

- Keep the SUM of all volumes attached to the instance within the instance's EBS BASELINE (DescribeInstanceTypes), not its burst maximum. If the target would exceed it, say so and lower the target, or recommend an instance type change.
- gp3 throughput must not exceed 0.25 MiB/s per provisioned IOPS.
- For io1 and io2, the throughput the volume can deliver depends on the provisioned IOPS. If measured MiB/s is at the throughput limit for the current IOPS, a higher IOPS value raises that limit, up to the documented maximum for the type (see [metrics-thresholds.md](metrics-thresholds.md)).
- State how the target was computed (measured demand, type rule, instance baseline minus other volumes' usage).

## Other performance topics

### Micro-bursting

AWS/EBS data is 1-minute. Sub-minute peaks can reach a limit while the minute average stays below it. If latency or queue length rises while the average is below the limit, say that micro-bursting is possible and that headroom is not proven. Do not claim headroom from the average alone.

Check the exceeded checks from Step 2a first. The Amazon EBS User Guide says `VolumeIOPSExceededCheck` and `VolumeThroughputExceededCheck` return 1 when the driven IOPS or throughput consistently exceeds the provisioned value for any second within the minute, so they show bursts that the minute averages hide. If the checks are 0 or have no datapoints and the question is still open, give the customer the detailed performance statistics step below.

### Detailed performance statistics (a step the customer runs)

Amazon EBS NVMe devices on Nitro instances keep detailed performance statistics that the customer reads on the instance, at up to 1-second granularity, for any volume type, at no extra cost. There is no AWS API for them, so the agent never runs this step. Give it to the customer as a step to run when the 1-minute CloudWatch data cannot settle the question, for example suspected micro-bursting, or an Indeterminate verdict.

Tell the customer to connect to the instance the volume is attached to, find the volume's NVMe device name (see the device mapping link in Sources), and run one of the documented commands:

- Linux, `nvme-cli` (included in Amazon Linux AMIs released after November 12, 2024; on older AMIs run `sudo yum install nvme-cli` first): `nvme amzn stats /dev/nvme0n1`
- Linux, the `ebsnvme` script from the amazon-ec2-utils GitHub repository:
  `wget https://raw.githubusercontent.com/amazonlinux/amazon-ec2-utils/refs/heads/main/ebsnvme`, then `sudo chmod +x ./ebsnvme`, then `sudo ./ebsnvme stats /dev/nvme0n1`
- Windows, AWSNVMe driver version 1.7.0 or later, as Administrator: `.\nvme_amzn.exe stats <disk_number>`

Replace `/dev/nvme0n1` or `<disk_number>` with the volume's device. The customer can also collect the statistics with the Amazon CloudWatch agent as custom metrics.

What to look at:

| Statistic | What it shows |
|---|---|
| `ebs_volume_performance_exceeded_iops`, `ebs_volume_performance_exceeded_tp` | Total time, in microseconds, that demand exceeded the volume's provisioned IOPS or throughput |
| `ec2_instance_ebs_performance_exceeded_iops`, `ec2_instance_ebs_performance_exceeded_tp` | Total time, in microseconds, that the volume exceeded the instance's maximum EBS IOPS or throughput |
| `volume_queue_length` | Read and write operations waiting to complete, at that point in time. Stalled or impaired I/O shows here |
| `read_io_latency_histogram`, `write_io_latency_histogram` | Completed operations per latency bin, in microseconds. Only completed I/O is counted |
| `total_read_ops`, `total_write_ops`, `total_read_bytes`, `total_write_bytes`, `total_read_time`, `total_write_time` | Completed operations, bytes, and time in microseconds |

The counters add up from the time the volume was attached, so ask for two readings taken a known number of seconds apart during the symptom and compare the difference. Exceeded time that grows between the readings shows the volume or instance limit binds for part of each second, even when the 1-minute averages are below it. No growth in exceeded time, together with a growing queue or a latency histogram that moves to higher bins, supports a slowdown rather than a limit.

### Volume initialization after restore

A volume created from a snapshot loads blocks from Amazon S3 the first time they are read, which adds latency until the volume is initialized. Check `DescribeVolumes` `SnapshotId` and `CreateTime`. If the volume was recently restored, explain initialization and point to fast snapshot restore (`DescribeFastSnapshotRestores`) and the initialization guide. This is not a provisioning problem.

### Burst credits

- Volume level: gp2, st1 and sc1 publish `BurstBalance`. Draining or at 0 means the volume has dropped or will drop to its baseline. Recommend gp2 to gp3 migration, or a size or type that gives the needed baseline.
- Instance level: some smaller instance sizes publish `EBSIOBalance%` and `EBSByteBalance%`. Draining or at 0 means the instance has dropped or will drop to its EBS baseline. Recommend an instance type whose baseline covers the measured demand.

### How much IOPS or throughput to provision

1. Measure peak demand per volume over a representative window (IOPS and MiB/s, Step 3 math).
2. Apply the type rules (gp3: up to 500 IOPS per GiB and 0.25 MiB/s per IOPS; io2: up to 1,000 IOPS per GiB, and throughput up to 0.256 MiB/s per provisioned IOPS; io1: up to 50 IOPS per GiB) from [metrics-thresholds.md](metrics-thresholds.md). For io1 and io2, check that the IOPS value also gives the throughput limit the workload needs.
3. Check the instance's remaining EBS baseline: baseline minus the measured usage of the other attached volumes.
4. Propose the smaller of the measured need and what the instance can deliver. If the need exceeds the instance baseline, say so and recommend an instance type change.
5. State how the target was computed.

## Decision rules

Use the binding-layer decision tree in [finding-logic.md](finding-logic.md). The signatures are in [metrics-thresholds.md](metrics-thresholds.md).

## What to report

The verdict template in [finding-logic.md](finding-logic.md). When the instance is the ceiling, the Answer says: "The volume has headroom; raising volume IOPS will not help; change the instance type." Never call a volume "saturated" when it is below its own limit.

## Safety rules

- This path is read-only. Any `ModifyVolume` or instance type change is a proposal with exact parameters, expected effect, cost direction and rollback, written as described in [Change proposals](finding-logic.md#change-proposals). It runs only through a directed action approved on the approval card.
- When the user asks to raise IOPS or modify a volume, first check from the data whether the change will help. Then give the full proposal, even when the user has typed an approval.
- Never recommend more provisioning for an impairment or an injected-latency signature.
- A typed "approve" in chat is not approval.

## Sources

- Amazon CloudWatch metrics for Amazon EBS: https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html
- Instance metrics: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html
- Amazon EBS-optimized instances: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimized.html
- Amazon EBS performance: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-performance.html
- Volume initialization: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-initialize.html
- Fast snapshot restore: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-fast-snapshot-restore.html
- Volume status checks: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-status.html
- AWS FIS actions: https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.html
- I/O characteristics, micro-bursting and the exceeded checks: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html
- Amazon EBS detailed performance statistics: https://docs.aws.amazon.com/ebs/latest/userguide/nvme-detailed-performance-stats.html
- Map Amazon EBS volumes to NVMe device names: https://docs.aws.amazon.com/ebs/latest/userguide/identify-nvme-ebs-device.html
- CloudWatch exceeded checks and `VolumeStalledIOCheck`: https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html and https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html#status-check-metrics
- Elastic Volumes: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html and https://aws.amazon.com/about-aws/whats-new/2026/01/amazon-ebs-up-to-four-volume-modifications/
- gp3, gp2, io1 and io2 rules, including io1 and io2 throughput limits: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html and https://docs.aws.amazon.com/ebs/latest/userguide/provisioned-iops.html
- DescribeVolumesModifications (most recent modification request only): https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeVolumesModifications.html
