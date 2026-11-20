# Metrics and thresholds by volume type

Use this file for any judgement about whether a volume or an instance is at a limit. Read the provisioned values from the APIs (`DescribeVolumes`, `DescribeInstanceTypes`). The numbers below are the documented service limits, not targets. Throughput is always in MiB/s.

## Which dimension binds, by volume type

| Type | Included or baseline | Maximum per volume | Ratio rules | Burst model | How to judge |
|---|---|---|---|---|---|
| gp3 | 3,000 IOPS and 125 MiB/s included at any size | 80,000 IOPS; 2,000 MiB/s | Up to 500 IOPS per GiB; up to 0.25 MiB/s per provisioned IOPS | No burst | Compare actual IOPS to `Iops` AND actual MiB/s to `Throughput`. Either can bind. For a sequential workload, check throughput first |
| gp2 | 3 IOPS per GiB, minimum 100 | 16,000 IOPS (reached at 5,334 GiB) | Size sets performance | Bursts to 3,000 IOPS while `BurstBalance` is above 0 | Compare actual IOPS to the baseline for the size. Check `BurstBalance` draining or at 0 |
| io1 / io2 | Provisioned `Iops` | io2 Block Express: up to 256,000 IOPS and 4,000 MiB/s on supported Nitro instances | io2: up to 1,000 IOPS per GiB | No burst | Judge by IOPS only. Throughput is derived from IOPS x I/O size and is not provisioned separately |
| st1 | 40 MiB/s per TiB baseline | 500 MiB/s | Burst 250 MiB/s per TiB | `BurstBalance` | Compare MiB/s to the baseline and burst for the size; check `BurstBalance` |
| sc1 | 12 MiB/s per TiB baseline | 250 MiB/s | Burst 80 MiB/s per TiB | `BurstBalance` | Compare MiB/s to the baseline and burst for the size; check `BurstBalance` |

For io1 limits and for io2 on instances that are not supported for Block Express, read the provisioned IOPS page in Sources. Do not quote a maximum from memory.

## Metric rules that change the verdict

- `VolumeThroughputPercentage` exists only for Provisioned IOPS SSD volumes. It reports the percentage of provisioned IOPS delivered, not MiB/s. Never use it as a throughput signal on io1 or io2. A healthy io2 volume can read 100% while its MiB/s is low.
- Judge io2 by IOPS. Judge gp3 by throughput and IOPS.
- `VolumeAvgIOPS`, `VolumeAvgThroughput`, `VolumeAvgReadLatency` and `VolumeAvgWriteLatency` need both the `VolumeId` and `InstanceId` dimensions and exist only for Nitro instances. `VolumeAvgThroughput` is in KiB/s; divide by 1,024 to get MiB/s.
- `VolumeQueueLength` uses `VolumeId` only.
- A 1-minute average hides sub-minute peaks. If the minute average is below a limit but latency and queue length rise, say that micro-bursting is possible and that headroom is not proven.

## Latency expectations (documented only)

| Type | Documented expectation |
|---|---|
| gp3 | Single-digit millisecond latency |
| io2 Block Express | Under 500 microseconds average latency for 16 KiB I/O |

For other types the public documentation does not give a latency number. Compare the volume against its own history in the same window on a normal day and against the type's documented expectation above.

## Not encoded on purpose

The drafts carried latency bands (for example "io2 below 1 ms, gp3 below 2 ms, st1 below 10 ms"), a queue length rule ("1 per 1,000 provisioned IOPS"), `VolumeIdleTime` bands, `BurstBalance` bands and percentage triggers ("below 95%", "above 90% of provisioned"). No public AWS source states these, so they are not in this skill. They are listed as open questions for SME review in BUILD-REPORT.md.

## Saturation and impairment signatures

| Signature | What you see | What it means | What to recommend |
|---|---|---|---|
| Volume saturation | IOPS or MiB/s flat at the volume's provisioned limit. Latency modest. Instance layer healthy | The volume is the binding layer | Raise the bound dimension, sized within the instance's EBS baseline |
| Instance saturation | Sum across all attached volumes flat at the instance EBS baseline, or `EBSIOBalance%` / `EBSByteBalance%` draining or at 0. Each volume below its own limit | The instance is the binding layer | Change the instance type. Raising volume provisioning will not help |
| Burst credits exhausted | gp2, st1 or sc1 `BurstBalance` at or near 0, throughput or IOPS dropped to baseline | Burst credits are the binding layer | gp2 to gp3 migration, or a type or size change that gives the needed baseline |
| Impairment or injected latency | IOPS and throughput collapse while latency and `VolumeQueueLength` rise. Volume and instance below their limits | Not saturation. An AWS-side impairment, a fault injection, or a non-EBS cause | Never recommend more provisioning. Check volume status, AWS Health and AWS FIS (see troubleshoot-performance.md Step 5) |

## Sources

- gp3 and gp2: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html
- io1 and io2: https://docs.aws.amazon.com/ebs/latest/userguide/provisioned-iops.html
- Volume type comparison: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html
- st1 and sc1: https://docs.aws.amazon.com/ebs/latest/userguide/hdd-vols.html
- Amazon CloudWatch metrics for Amazon EBS (units, dimensions, `VolumeThroughputPercentage`): https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html
- Instance metrics `EBSIOBalance%` and `EBSByteBalance%`: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html
