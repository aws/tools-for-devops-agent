# Troubleshoot: Elastic Volumes modification

## When this path applies

- "My modification is stuck", "the new IOPS has not taken effect", "how long will optimizing take?"
- A `ModifyVolume` call failed with an error.
- Sizing a resize, an IOPS or throughput change, or a gp2 to gp3 migration.
- Extending the file system after a size increase.
- Shrinking a volume or cancelling a modification.

## Procedure

1. **Find the volume.** Use the volume ID the user gives, or discover it with `DescribeVolumes` (by instance attachment or by the volumes that have recent modifications). Never pick a volume by its Name tag alone; confirm the ID with the user if more than one matches.
2. **Read the latest modification record.** `DescribeVolumesModifications` for the volume: `ModificationState`, `Progress`, original and target values (size, type, IOPS, throughput), `StartTime`, `EndTime`, `StatusMessage`. This API returns only the most recent modification request for each volume. Use it for the current or latest modification state, not for history.
3. **Answer the asked question first, in plain words.**
   - `modifying` or `optimizing`: not stuck. In `optimizing` the new configuration already applies and performance is between the source and the target. It completes on its own.
   - `completed`: done. The new values apply.
   - `failed`: read `StatusMessage` and translate it (step 5).
   - Duration is best effort. The Amazon EBS User Guide says a 1 TiB volume typically takes up to about six hours to modify, and some performance changes take more than 24 hours, for example when the volume is not fully initialized.
4. **Count the modifications in the rolling 24 hours.** Up to 4 per volume in a rolling 24-hour period. There is no fixed waiting period between modifications; the next one is allowed once the previous one completes. `DescribeVolumesModifications` cannot give this count, because it returns only the latest modification. Count the `ModifyVolume` events for the volume in the last 24 hours with the optional AWS CloudTrail `LookupEvents` call (filter on the volume ID as the resource name, or on the event name `ModifyVolume`). Report how many remain in the current window. As a cross-check, the latest record from step 2 should appear among those events if its `StartTime` is in the last 24 hours. If the lookup is denied or unavailable, record a Gap ("the number of modifications in the last 24 hours could not be confirmed") and do not state how many remain.
5. **Translate errors.**
   - io2 "Iops to volume size ratio of ... is too high; maximum is 1000": io2 allows up to 1,000 IOPS per GiB. To reach the target IOPS, the size must be at least target IOPS / 1,000 GiB. Propose that size together with the IOPS.
   - gp3: up to 500 IOPS per GiB, and throughput up to 0.25 MiB/s per provisioned IOPS. If a request breaks either rule, give the size or IOPS that satisfies it.
   - Size decrease: not allowed. Size can only increase. To get a smaller volume, create a new volume and copy the data.
   - Cancel: a submitted modification cannot be cancelled. Wait for it to complete; a reverse change then counts toward the 4 in 24 hours.
   - Limit reached: the 4 modifications in the window are used. The next one is possible when the oldest falls out of the rolling 24-hour window.
   - Older instance types or MBR volumes: check the Elastic Volumes requirements page.
6. **Size a new target.**
   - Keep it within the instance's remaining EBS baseline: `DescribeInstanceTypes` baseline (converted to MiB/s) minus the measured usage of the other attached volumes.
   - gp2 to gp3: keep at least the gp2 volume's current baseline IOPS (3 x GiB, minimum 100) and its measured throughput. gp3 includes 3,000 IOPS and 125 MiB/s at any size; provision more only if measured demand needs it.
   - State how the target was computed.
7. **File system extension after a size increase.** Give the commands for the operator to run on the instance. Never execute them.
   - `lsblk` to see the device and partition
   - `sudo growpart /dev/<device> <partition-number>` if the volume has a partition
   - `sudo xfs_growfs -d <mount-point>` for XFS, or `sudo resize2fs /dev/<device-or-partition>` for ext4
   - Point to the extend-the-file-system guide for Windows and other cases.
8. **Separate findings.** If the instance caps what the volume can deliver, write that under Separate findings. Never phrase it as "the modification failed" when the record shows `optimizing` or `completed`.

## Decision rules

- The modification record decides the Answer. Performance metrics never override it.
- An instance ceiling is a Separate finding with its own recommendation (instance type change).
- Use the binding-layer tree in [finding-logic.md](finding-logic.md) only when the user also asks about performance.

## What to report

The verdict template in [finding-logic.md](finding-logic.md). The Answer names the state and what it means. Evidence lists the record fields. Recommendation gives the exact next call, if any. Gaps list anything unreadable.

## Safety rules

- The agent never runs `ModifyVolume` on its own. It proposes it as a directed action, approved on the approval card. A typed "approve" in chat is not approval.
- The proposal includes: the exact call (`--volume-id`, and only the changed fields among `--size`, `--volume-type`, `--iops`, `--throughput`), the expected state sequence (`modifying`, `optimizing`, `completed`), how many of the 4 modifications in the rolling 24 hours remain after this change (only when step 4 confirmed the count; otherwise say it is unconfirmed), cost direction, and rollback.
- Rollback: after the change completes, a reverse change of IOPS, throughput or type is possible and counts toward the 4. Size cannot roll back.
- Recommend a snapshot before a type change or a large resize on a volume with data the user cannot lose.

## Sources

- Modify a volume: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html
- January 2026 What's New post: https://aws.amazon.com/about-aws/whats-new/2026/01/amazon-ebs-up-to-four-volume-modifications/
- Monitoring modifications: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- DescribeVolumesModifications (most recent modification request only): https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeVolumesModifications.html
- AWS CloudTrail LookupEvents: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html
- Modification duration (1 TiB, about six hours, more than 24 hours): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html and https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- Requirements: https://docs.aws.amazon.com/ebs/latest/userguide/modify-volume-requirements.html
- Extend the file system: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/recognize-expanded-volume-linux.html
- gp3 and gp2: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html
- io2: https://docs.aws.amazon.com/ebs/latest/userguide/provisioned-iops.html
- Amazon EBS-optimized instances: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimized.html
