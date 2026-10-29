# Finding Logic

Evaluate every finding against the collected data, then report the primary
cause with the priority order at the end. Use the fixed wording in each
finding, substituting only the values in angle brackets.

Before you start, compute for each volume and each minute of the window:

| Value | How |
|---|---|
| IOPS | `(VolumeReadOps + VolumeWriteOps) / 60` |
| Volume throughput (MiB/s) | `(VolumeReadBytes + VolumeWriteBytes) / 60 / 1,048,576`. Volume limits are in MiB/s. |
| Instance throughput (MB/s) | `(EBSReadBytes + EBSWriteBytes) / period / 1,000,000`. Instance limits from `DescribeInstanceTypes` are in MB/s. |
| Average I/O size (KiB) | `(VolumeReadBytes + VolumeWriteBytes) / (VolumeReadOps + VolumeWriteOps) / 1024` |
| Latency (ms) | `VolumeAvgReadLatency` / `VolumeAvgWriteLatency`, or `VolumeTotalWriteTime / VolumeWriteOps * 1000` (same for reads) |
| Before and after | The median of each value for the 15 minutes before `T0`, and for the minutes after `T0` |

"Flat at a limit" means within 5% of the limit for at least 5 consecutive
minutes. Compare values in the same unit as the limit: MiB/s for volumes,
MB/s for instances.

If you can't find `T0` in the metrics, say so in the answer, and use the
start time the user gave.

## F1. Change made in the account

Confirmed when one of these holds:

- A mutating CloudTrail event on the instance or one of its volumes has an
  `eventTime` at `T0` or up to 2 minutes before it, and the change can produce
  the symptom (see the table below).
- An AWS FIS experiment that targets the instance or one of its volumes (from
  `fis:ListExperimentResolvedTargets`) was running at `T0`, and its action
  (from `fis:GetExperimentTemplate`) can produce the symptom. This holds even
  when CloudTrail doesn't show the call yet: CloudTrail can take several
  minutes to deliver an event.

| Change | Symptom it can explain |
|---|---|
| `DetachVolume`, `StopInstances`, `RebootInstances` | I/O errors, or a device that disappears |
| `ModifyInstanceAttribute` changing the instance type | A lower instance EBS limit after the next start (then check F4) |
| `PauseVolumeIO` (FIS action `aws:ebs:pause-volume-io`) | A stall, with the same signals as F2 |
| `InjectVolumeIOLatency` (FIS action `aws:ebs:volume-io-latency`) | Higher latency while ops keep completing |

`ModifyVolume` has its own rules in F7.

A Session Manager login, a console sign-in, a deployment or an unrelated API
call near `T0` is not a cause by itself. List it under "Changes in the window"
only.

Wording: "The slowdown follows a change made in the account, not a problem in
EBS: `<event>` on `<resource>` at `<time>` by `<caller>`."

Fix: "If the change wasn't intended, undo or adjust it, and review who can make
it." For an AWS FIS experiment, add: "The effect ends when the experiment ends
or is stopped. Experiment `<experiment-id>` is `<state>`, and its action
started at `<action start>` for `<duration>`, so it ends at about `<end>`."
Take the action start from the CloudTrail `eventTime` of the FIS call when
it's there (see `references/data-collection.md`). Don't recommend a support
case.

## F2. Stalled volume

Confirmed when at least one of these holds, for a volume, for at least 1
minute:

- `VolumeStalledIOCheck` = 1.
- Completed ops = 0 while `VolumeQueueLength` > 0, for 2 or more consecutive
  minutes.
- `DescribeVolumeStatus` shows `io-performance` = `stalled`, or an event of
  type `io-performance:stalled`.
- `AttachedEbsStatus` is `impaired`, or `StatusCheckFailed_AttachedEBS` = 1,
  and one of the signals above points to the volume.

A stalled volume can look idle: 0 IOPS, 0 ms latency (no op completed) and a
high `VolumeIdleTime`. A queue above 0 with no completed ops is the
difference.

Wording: "Volume `<volume-id>` (`<device>`) stopped completing I/O from
`<start>` to `<end or 'now'>`: `<signals with values>`."

Recovery: the stall is over when `VolumeStalledIOCheck` is back to 0, ops
complete again and the volume status is `ok` (the event has a `NotAfter`). The
first minute after a stall often shows a burst of completed ops with high
average latency: that is the backlog draining, not ongoing slowness. Judge
recovery from the minutes after that.

Fix, in this order (from the AWS documentation on attached EBS status checks):

1. If F1 explains it, use F1 instead.
2. Wait a few minutes. EBS usually diagnoses and recovers the volume by
   itself. Watch `VolumeStalledIOCheck` return to 0.
3. If it doesn't recover, stop and start the instance (not reboot) to move it
   to a new host. Before you do, know that:
   - data on instance store volumes is lost;
   - the public IPv4 address changes, unless it's an Elastic IP address;
   - if the instance is in an Auto Scaling group, the group can replace it
     instead, unless you suspend health checks or put it in standby first.
4. If the volume still has issues after that, create a snapshot and replace
   the volume with a new one created from it.
5. If the workload can't wait, fail over to a standby instance or Availability
   Zone.
6. After recovery, check the file system and the application data.
7. Open an AWS Support case with the evidence (see `assets/report-format.md`).

Never recommend force-detaching the volume: it can lose data. Don't recommend
detaching or reattaching while I/O is stuck.

## F3. I/O disabled

Confirmed when `io-enabled` = `failed`, or a volume event says I/O is
disabled, because EBS found the data potentially inconsistent.

Wording: "EBS disabled I/O on `<volume-id>` at `<time>` because it detected
potential data inconsistency."

Fix: "Decide whether to keep using the volume. To use it, enable I/O on the
volume, then check the file system (`fsck` on Linux, `chkdsk` on Windows)
before the application uses it. Otherwise, restore from a snapshot." The skill
doesn't call `EnableVolumeIO`.

## F4. Instance EBS limit

Confirmed when all of these hold:

- `InstanceEBSThroughputExceededCheck` or `InstanceEBSIOPSExceededCheck` = 1,
  or, where these aren't published, the instance total throughput (in MB/s)
  or IOPS (`EBSReadOps + EBSWriteOps`) is flat at the instance type's maximum
  or baseline from `DescribeInstanceTypes`.
- No single volume is flat at its own limit.

Cite the instance `*ExceededCheck` value first in the evidence, then the
instance total against the limit, then the per-volume values against their own
limits.

Supporting signals: `EBSByteBalance%` or `EBSIOBalance%` fell to 0 at `T0`
(burstable sizes only), and the throughput or IOPS of several volumes dropped
in the same minute.

Wording: "The instance reached its EBS `<throughput|IOPS>` limit:
`<instance-type>` allows `<baseline>` baseline and `<maximum>` burst, and the
attached volumes together drove `<value>` from `<time>`. Each volume stayed
under its own limit."

Fix: "Move to an instance type whose EBS baseline is above `<observed
value>` (for example `<type with baseline>`), or reduce or spread the I/O
across instances. `<observed value>` is what the limit allowed, so the
workload may need more. Adding volumes or raising volume IOPS or throughput on
the same instance doesn't help, because the limit is per instance. Alarm on
`EBSByteBalance%` or `EBSIOBalance%` below 20%." Take the example type and its
baseline from `DescribeInstanceTypes`; don't quote figures from memory.

## F5. Volume burst credits exhausted (gp2, st1, sc1)

Confirmed when `BurstBalance` reached 0 at `T0` and, from then on, the volume's
IOPS (gp2) or throughput (st1, sc1) is flat at its baseline.

On gp2, `VolumeIOPSExceededCheck` compares with the baseline IOPS, so it can
read 1 during the burst too. It shows demand above the baseline, not the time
the slowdown started. Use `BurstBalance` for the timing.

Wording: "Volume `<volume-id>` (`<type>`, `<size>` GiB) used up its burst
credits at `<time>` and dropped to its baseline of `<baseline>`. It had been
running at `<burst rate>`."

Fix: "Move the volume to gp3 with at least `<burst rate>` IOPS and
`<observed throughput>` throughput (gp3 has no burst bucket), or increase the
gp2 size to raise the baseline (3 IOPS per GiB). Alarm on `BurstBalance` below
20%." The burst rate is capped at 3,000 IOPS on gp2, so the workload may want
more: say so.

## F6. Volume at its own limit, with credits left or no burst bucket

Confirmed when the instance total isn't at the instance limit, and one of
these holds for 5 or more minutes:

| Type | Limit reached |
|---|---|
| gp3 | IOPS or throughput flat at the provisioned `Iops` or `Throughput` |
| io1, io2 | IOPS flat at the provisioned `Iops`, or `VolumeThroughputExceededCheck` = 1 (`DescribeVolumes` has no `Throughput` for these types) |
| gp2 under 1 TiB | IOPS flat at the 3,000 burst ceiling while `BurstBalance` is above 0 |
| gp2 of 1 TiB or more | IOPS flat at the baseline of 3 IOPS per GiB, with `BurstBalance` at 100% |
| gp2, any size | Throughput flat at the size's cap: 128 MiB/s up to 170 GiB, up to 250 MiB/s above |
| st1, sc1 | Throughput flat at the size's burst maximum while `BurstBalance` is above 0 |

`VolumeIOPSExceededCheck` or `VolumeThroughputExceededCheck` at 1 supports
the finding. On gp2 it compares with the baseline, so on its own it doesn't
prove the volume is at its ceiling.

Wording: "Volume `<volume-id>` (`<type>`, `<size>` GiB) is at its
`<IOPS|throughput>` limit of `<value>` from `<time>`, and the workload is
asking for more."

Fix, by type: "Raise the provisioned `<IOPS|throughput>`" (gp3, io1, io2);
"move to gp3 with at least `<observed demand>`" (gp2); "move to a larger
volume or to gp3" (st1, sc1). Size the new value above what was observed at
the limit, which is the minimum demand. Check the instance EBS limit first so
the new value can be used.

## F7. Volume modification in progress

Confirmed when `DescribeVolumesModifications` shows a modification that
started before `T0` and was in `modifying` or `optimizing` during the window,
and it lowered the volume's IOPS or throughput, or changed its type to one
with a lower limit. While optimizing, performance is no lower than the source
values (or the target values when you lower them), so a modification that
raised the limits doesn't explain a slowdown.

Wording: "Volume `<volume-id>` was being modified from `<start>`
(`<original>` to `<target>`, state `<state>`, `<progress>`%), and the new
`<IOPS|throughput>` of `<value>` is below what the workload drives."

Fix: "Set the volume's `<IOPS|throughput>` back to at least `<observed
demand>` once the modification completes. A volume can be modified again only
after the current modification completes, and up to four times in a rolling
24-hour period."

## F8. Snapshot initialization

Confirmed when the volume has a `SnapshotId` and fast snapshot restore isn't
`enabled` for that snapshot in the volume's Availability Zone
(`DescribeFastSnapshotRestores`), and one of these holds:

- For a problem happening now: `VolumeStatus.Details` has
  `initialization-state` = `initializing`, or
  `InitializationStatusDetails.Progress` is below 100. Either is enough: EBS
  can take up to 5 minutes to publish the initialization details after the
  volume is created.
- For a problem in the past: the volume's `CreateTime` is no more than 24
  hours before `T0`, and the slow I/O is mostly reads. The current `Progress`
  shows today's state, not the state at the time, so a value of 100 doesn't
  rule this out. Say so in the answer.

While a volume initializes, `io-performance` can show `warning`, `degraded` or
`severely-degraded`, with an `io-performance` event, on any volume type that
has the check. This is expected: report it under this finding, say in the
answer that the status is caused by initialization, and don't report it as F9
or recommend a support case.

Wording: "Volume `<volume-id>` was created from snapshot `<snapshot-id>` and is
`<progress>`% initialized. Blocks not yet initialized load from Amazon S3 on
first access, which makes those reads slower."

Fix: "Initialize the volume by reading all its blocks (for example with `dd`
or `fio`), or use fast snapshot restore or a provisioned initialization rate
for volumes that need full performance at once." No support case.

## F9. Degraded performance with no limit, stall or change

Confirmed when latency after `T0` is at least 3 times the median before `T0`
for 5 or more minutes, ops keep completing, and F1 to F8 are all ruled out.

Check the average I/O size first: if it grew at `T0`, higher latency per op is
expected, and the cause is a workload change.

Wording: "Latency on `<volume-id>` rose from `<before>` ms to `<after>` ms at
`<time>` with no volume or instance limit, no stall and no change in the
account. `<io-performance status if gp3, io1 or io2>`."

Fix: "Monitor the volume. If latency stays high or the volume status shows
`warning`, open an AWS Support case with the evidence."

## F10. EBS is not the cause

Confirmed when all of these hold:

- F1 to F9 are all ruled out.
- Every volume status is `ok`, and the attached EBS status check passed.
- No volume or instance `*ExceededCheck` metric was 1 in the window. Ignore
  `VolumeIOPSExceededCheck` on a gp2 volume while its `BurstBalance` is above
  0: it compares with the baseline, so it reads 1 during a normal burst.
- Latency, IOPS and throughput after `T0` are close to their medians before
  `T0`, and the window starts before the problem did. If the problem may have
  started before the window, widen the window or say the "before" values can't
  be trusted.

Wording: "The EBS volumes and the instance's EBS path look healthy during the
window: no limit reached, no stall, no change, latency `<value>` ms."

Fix: "Look at the operating system and the application: CPU, memory and
swap, file system, and application locks. `iostat` output from the instance
would confirm whether the OS sees the same."

## No finding confirmed

If no finding from F1 to F10 is confirmed, don't force one. Answer "Not
confirmed": say what was checked, which signals are unusual and why they don't
fit a finding, list the data gaps, and say what extra data would decide it (for
example `iostat` from the instance, or a wider time window).

## Limits and latency (F4, F5, F6)

When the primary cause is F4, F5 or F6, also say in the answer:

- The latency before and after `T0`, with values.
- That the application waits longer than CloudWatch shows: I/O above the
  limit waits on the instance before EBS sees it, so CloudWatch latency and
  queue length stay low.
- That the value held at the limit is the minimum demand, and the fix is
  sized above it.

## Changes in the window

List every mutating CloudTrail event in the window under "Changes in the
window" in the report, with time, event, caller and target, whether or not it
is the cause.

## Priority order

When several findings are confirmed, the primary cause is the first in this
list, and the others are reported as contributing:

1. F1 Change made in the account
2. F3 I/O disabled
3. F2 Stalled volume
4. F7 Volume modification in progress
5. F4 Instance EBS limit
6. F5 Volume burst credits exhausted
7. F6 Volume at its own limit
8. F8 Snapshot initialization
9. F9 Degraded performance
10. F10 EBS is not the cause

If an AWS Health event covers the volume, the instance or EBS in that
Availability Zone during the window, report it with F2 or F9 and say the
problem is on the AWS side.

## Answer to "Is EBS the cause?"

| Primary finding | Answer |
|---|---|
| F1 Change made in the account | Partly: the disk is where it shows, but the cause is the change |
| F4 Instance EBS limit | Partly: the instance's EBS limit, not the volumes |
| F10 EBS is not the cause | No |
| F2, F3, F5, F6, F7, F8, F9 | Yes |
| No finding confirmed | Not confirmed |

## Escalation

Recommend an AWS Support case only for F2, F3 and F9 with no account-side
cause. Never for F1, F4, F5, F6, F7, F8 or F10.
