# Metrics and thresholds by volume type

Use this file for any judgement about whether a volume or an instance is at a limit. Read the provisioned values from the APIs (`DescribeVolumes`, `DescribeInstanceTypes`). The numbers below are the documented service limits, not targets. Throughput is always in MiB/s.

## Which dimension binds, by volume type

| Type | Included or baseline | Maximum per volume | Ratio rules | Burst model | How to judge |
|---|---|---|---|---|---|
| gp3 | 3,000 IOPS and 125 MiB/s included at any size | 80,000 IOPS; 2,000 MiB/s | Up to 500 IOPS per GiB; up to 0.25 MiB/s per provisioned IOPS | No burst | Compare actual IOPS to `Iops` AND actual MiB/s to `Throughput`. Either can bind. For a sequential workload, check throughput first |
| gp2 | 3 IOPS per GiB, minimum 100 | 16,000 IOPS (reached at 5,334 GiB) | Size sets performance | Bursts to 3,000 IOPS while `BurstBalance` is above 0 | Compare actual IOPS to the baseline for the size. Check `BurstBalance` draining or at 0 |
| io2 (Block Express) | Provisioned `Iops` | 256,000 IOPS and 4,000 MiB/s. Up to 256,000 IOPS on Nitro-based instances; up to 32,000 IOPS on other instances | Up to 1,000 IOPS per GiB. Throughput limit = 0.256 MiB/s per provisioned IOPS, up to 4,000 MiB/s (reached at 16,000 IOPS or higher) | No burst | Compare actual IOPS to `Iops` AND actual MiB/s to the throughput limit computed from `Iops`. Either can bind |
| io1 | Provisioned `Iops` | 64,000 IOPS and 1,000 MiB/s. Up to 64,000 IOPS on Nitro-based instances; up to 32,000 IOPS on other instances | Up to 50 IOPS per GiB. Up to 32,000 provisioned IOPS: up to 500 MiB/s, with a maximum I/O size of 256 KiB (500 MiB/s is reached at 2,000 IOPS with 256 KiB I/O). Above 32,000 provisioned IOPS: 16 KiB per provisioned IOPS, so 1,000 MiB/s at 64,000 IOPS | No burst | Compare actual IOPS to `Iops` AND actual MiB/s to the throughput limit for the provisioned IOPS. Either can bind |
| st1 | 40 MiB/s per TiB baseline | 500 MiB/s | Burst 250 MiB/s per TiB | `BurstBalance` | Compare MiB/s to the baseline and burst for the size; check `BurstBalance` |
| sc1 | 12 MiB/s per TiB baseline | 250 MiB/s | Burst 80 MiB/s per TiB | `BurstBalance` | Compare MiB/s to the baseline and burst for the size; check `BurstBalance` |

The io1 and io2 values above are from the Provisioned IOPS SSD volumes page in Sources. Throughput on io1 and io2 is not provisioned separately; the limit follows from the provisioned IOPS as shown. Do not quote any other maximum from memory.

## Metric rules that change the verdict

- `VolumeThroughputPercentage` exists only for Provisioned IOPS SSD volumes. It reports the percentage of provisioned IOPS delivered, not MiB/s. Never use it as a throughput signal on io1 or io2. A healthy io2 volume can read 100% while its MiB/s is low.
- Judge io1, io2 and gp3 by both IOPS and throughput. For io1 and io2, compute the throughput limit from the provisioned IOPS with the rules in the table.
- `VolumeAvgIOPS`, `VolumeAvgThroughput`, `VolumeAvgReadLatency` and `VolumeAvgWriteLatency` need both the `VolumeId` and `InstanceId` dimensions and exist only for Nitro instances. `VolumeAvgThroughput` is in KiB/s; divide by 1,024 to get MiB/s.
- `VolumeStalledIOCheck` also uses the `VolumeId` and `InstanceId` dimensions and exists only for Nitro instances.
- `VolumeQueueLength` uses `VolumeId` only.
- `VolumeTotalReadTime` and `VolumeTotalWriteTime` are in seconds. Average latency in ms per operation = Sum(time) / Sum(ops) x 1,000.
- A 1-minute average hides sub-minute peaks. If the minute average is below a limit but latency and queue length rise, say that micro-bursting is possible and that headroom is not proven.

## Latency expectations (documented only)

| Type | Documented expectation |
|---|---|
| gp3 | Single-digit millisecond latency |
| io2 Block Express | Under 500 microseconds average latency for 16 KiB I/O |

For other types the public documentation does not give a latency number. Compare the volume against its own history in the same window on a normal day and against the type's documented expectation above.

## Not encoded on purpose

The drafts carried latency bands (for example "io2 below 1 ms, gp3 below 2 ms, st1 below 10 ms"), a queue length rule ("1 per 1,000 provisioned IOPS"), `VolumeIdleTime` bands, `BurstBalance` bands and percentage triggers ("below 95%", "above 90% of provisioned"). No public AWS source states these, so they are not in this skill.

## Saturation and impairment signatures

| Signature | What you see | What it means | What to recommend |
|---|---|---|---|
| Volume saturation | IOPS or MiB/s flat at the volume's provisioned limit. Latency modest. Instance layer healthy | The volume is the binding layer | Raise the bound dimension, sized within the instance's EBS baseline |
| Instance saturation | Sum across all attached volumes flat at the instance EBS baseline, or `EBSIOBalance%` / `EBSByteBalance%` draining or at 0. Each volume below its own limit | The instance is the binding layer | Change the instance type. Raising volume provisioning will not help |
| Burst credits exhausted | gp2, st1 or sc1 `BurstBalance` at or near 0, throughput or IOPS dropped to baseline | Burst credits are the binding layer | gp2 to gp3 migration, or a type or size change that gives the needed baseline |
| Impairment or injected latency | IOPS and throughput collapse while latency and `VolumeQueueLength` rise. Volume and instance below their limits | Not saturation. An AWS-side impairment, a fault injection, or a non-EBS cause. The pattern alone does not prove which | Never recommend more provisioning. Check volume status, `VolumeStalledIOCheck`, AWS Health and AWS FIS (see troubleshoot-performance.md Step 5). Name AWS-side impairment only with a direct signal; otherwise the cause stays Indeterminate |

## Sources

- gp3 and gp2: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html
- io1 and io2 (IOPS and throughput limits): https://docs.aws.amazon.com/ebs/latest/userguide/provisioned-iops.html
- Volume type comparison: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html
- st1 and sc1: https://docs.aws.amazon.com/ebs/latest/userguide/hdd-vols.html
- Amazon CloudWatch metrics for Amazon EBS (units, dimensions, `VolumeThroughputPercentage`): https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html
- Instance metrics `EBSIOBalance%` and `EBSByteBalance%`: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html
