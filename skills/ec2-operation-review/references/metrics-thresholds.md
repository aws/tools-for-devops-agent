# EC2 / EBS CloudWatch Metrics Thresholds Reference

All metrics are retrieved via `cloudwatch.GetMetricData` over a 14-day window
with `Period=3600` (1h). Severity reflects sustained values over the window, not
single spikes. Use p95/Maximum for saturation checks and Average/Maximum-of-low
for idle checks.

> **Detailed monitoring note:** With basic monitoring, EC2 metrics are 5-minute
> granularity. Right-sizing and saturation conclusions built on basic monitoring
> should be labelled MEDIUM confidence and note the granularity limit.

> **Memory & disk note:** `CPUUtilization`, network, and EBS metrics are emitted
> by the hypervisor automatically. Memory and in-guest disk usage are only
> available if the **CloudWatch agent** is installed (`CWAgent` namespace). If
> absent, report memory-based checks as `NOT_ASSESSED`, never as passing.

## Instance Metrics (Namespace: `AWS/EC2`, Dimension: `InstanceId`)

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| CPUUtilization | p95 (or Maximum) | < 70% | > 85% | > 95% sustained | CPU saturation — scale up/out |
| CPUUtilization | Maximum (idle check) | — | < 10% for 14d | < 5% for 14d | Idle / right-size candidate |
| CPUCreditBalance (T-family, standard) | Minimum | > baseline | trending to 0 | 0 sustained | Burst throttling — unlimited mode or fixed-perf family |
| CPUSurplusCreditsCharged (T-family, unlimited) | Sum | 0 | > 0 sustained | rapid growth | Paying surplus credits — right-size |
| NetworkIn | Average | < 70% class bandwidth | > 80% | > 95% | Network saturation |
| NetworkOut | Average | < 70% class bandwidth | > 80% | > 95% | Network saturation |
| StatusCheckFailed_System | Maximum | 0 | — | > 0 | Underlying hardware issue — Auto Recovery |
| StatusCheckFailed_Instance | Maximum | 0 | — | > 0 | Instance-level failure — investigate OS/network |
| StatusCheckFailed | Maximum | 0 | — | > 0 | Any failed status check |

## CloudWatch Agent Metrics (Namespace: `CWAgent`) — only if agent installed

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| mem_used_percent | Average | < 70% | > 85% | > 95% | Memory pressure — scale up or tune app |
| mem_used_percent (idle) | Maximum | — | < 30% for 14d | — | Overprovisioned memory — right-size |
| disk_used_percent | Maximum | < 75% | > 85% | > 95% | Disk filling — expand volume / clean up |
| swap_used_percent | Average | ~0 | > 0 sustained | > 25% | Swapping — memory undersized |

## EBS Volume Metrics (Namespace: `AWS/EBS`, Dimension: `VolumeId`)

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| VolumeReadOps / VolumeWriteOps | Sum → IOPS | < 70% provisioned | > 80% provisioned | > 95% provisioned | I/O saturation — raise IOPS or gp3/io2 |
| VolumeThroughputPercentage (io1/io2) | Average | < 80% | > 90% | 100% sustained | Hitting provisioned throughput |
| VolumeQueueLength | Average | < 5 | > 10 | > 20 | I/O queueing — increase IOPS |
| VolumeIdleTime | Average | — | high | near 100% | Idle volume — deletion candidate |
| BurstBalance (gp2/st1/sc1) | Minimum | > 50% | < 20% | 0 | Burst credits exhausted — gp3 or larger volume |

## Alarm Coverage Expectations

The skill flags any of these as **MEDIUM** when missing
(`cloudwatch.DescribeAlarmsForMetric` returns nothing for the resource + metric):

| Resource | Metric | Threshold (suggested) |
|---|---|---|
| Instance | StatusCheckFailed_System | >= 1 for 2 datapoints (pair with Auto Recovery) |
| Instance | StatusCheckFailed_Instance | >= 1 for 2 datapoints |
| Instance | CPUUtilization | > 85% for 5 minutes |
| Instance (with CW agent) | mem_used_percent | > 90% for 5 minutes |
| Instance (with CW agent) | disk_used_percent | > 90% |
| EBS volume | BurstBalance (gp2) | < 20% |

## Instance Status Events of Interest (`ec2.DescribeInstanceStatus`)

| Event / signal | Severity | Action |
|---|---|---|
| `instance-retirement` scheduled | HIGH | Plan stop/start or migration before the retirement date |
| `instance-reboot` / `system-reboot` scheduled | MEDIUM | Apply within the maintenance window |
| `system-maintenance` scheduled | MEDIUM | Confirm impact, schedule |
| Status check `impaired` | CRITICAL | Investigate immediately; consider Auto Recovery |
| `instance-stop` scheduled (prod) | HIGH | Verify intentional |
