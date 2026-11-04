# Hidden limits that look like headroom

Some resources are throttled while their headline utilization metric looks moderate, because the real limit is a credit balance, a baseline rate or a burst allowance that the common dashboards do not show. A resource at or past one of these limits reads as under-used and is easy to misdiagnose as idle.

Every number below is a **starting figure to verify** against the current AWS documentation page named in the row, because baselines, earn rates and allowances change by instance family, size, generation and Region. Confirm the figure for the exact resource before you put it in a report.

For each limit: what the limit is, the metric that shows it, how it disguises itself, and how to confirm it.

## Burstable EC2 (T-family: T2, T3, T3a, T4g)

- **The limit.** A burstable instance earns CPU credits at a fixed rate and is guaranteed only a **baseline** fraction of a vCPU. Above baseline it spends credits. The baseline percent per vCPU and the credit earn rate depend on the size (for example a t3.medium baseline is a small percent of two vCPUs; to verify against "CPU credits and baseline utilization for burstable performance instances"). In **standard** credit mode, once `CPUCreditBalance` hits zero the instance is capped at baseline. In **unlimited** mode (the default for T3/T3a/T4g; to verify against "Burstable performance instances - unlimited mode") it keeps bursting but accrues **surplus** credits that are charged, and is capped only if surplus also runs out.
- **Time-to-zero arithmetic.** Drain time ≈ `CPUCreditBalance` / (earn rate - spend rate), where spend rate ≈ (observed CPU% - baseline%) × vCPUs × (credits per vCPU-minute). When demand sits above baseline, the balance falls on a straight line to zero; project the onset of throttling from the slope.
- **The metric.** `AWS/EC2` `CPUCreditBalance` (Minimum, falling to zero), `CPUSurplusCreditBalance` (rising when in unlimited mode and out of earned credits), `CPUSurplusCreditsCharged` (surplus that was billed, i.e. sustained over-baseline running).
- **How it disguises itself.** A throttled standard-mode instance shows `CPUUtilization` pinned near its **baseline** percent, not near 100%, so it looks under-used while it is actually capped. Latency rises with no obvious CPU saturation.
- **How to confirm.** Read the credit mode with `ec2:DescribeInstanceCreditSpecifications`. Correlate `CPUCreditBalance` reaching zero (standard) or `CPUSurplusCreditsCharged` climbing (unlimited) with the latency onset. Verify baseline and earn rate against "CPU credits and baseline utilization for burstable performance instances".

## EBS gp2 burst balance

- **The limit.** gp2 volumes get a baseline of 3 IOPS per GiB and can burst to a higher ceiling by spending a burst balance; small volumes have a low baseline (to verify against "General Purpose SSD volumes (gp2)").
- **The metric.** `AWS/EBS` `BurstBalance` (Minimum), falling toward zero.
- **How it disguises itself.** IOPS and throughput look fine while the balance lasts, then drop to the low baseline when it empties; the volume is not "full" and `VolumeQueueLength` may be the only other hint.
- **How to confirm.** `BurstBalance` trending to zero at the latency onset; compare observed IOPS against the baseline the volume size allows.

## EBS gp3 baseline and provisioned limits

- **The limit.** gp3 gives a fixed baseline (for example 3,000 IOPS and 125 MB/s to verify against "General Purpose SSD volumes (gp3)") with no burst bucket; more must be explicitly provisioned, and throughput-to-IOPS ratios are capped.
- **The metric.** `VolumeReadOps` + `VolumeWriteOps` per period against provisioned IOPS; `VolumeReadBytes` + `VolumeWriteBytes` against provisioned throughput.
- **How it disguises itself.** There is no burst balance metric to watch, so a volume sitting exactly at its provisioned ceiling looks "steady" rather than throttled.
- **How to confirm.** Read provisioned IOPS and throughput from the volume configuration; compare the computed rate against them.

## Instance-level EBS bandwidth burst (smaller instance sizes)

- **The limit.** Smaller sizes in a family get a baseline EBS bandwidth and IOPS with an ability to burst for a limited time (to verify against "Amazon EBS-optimized instances"). The volume can be well within its own limits while the instance's EBS attachment is the cap.
- **The metric.** `AWS/EC2` `EBSReadBytes`/`EBSWriteBytes` and `EBSIOBalance%` / `EBSByteBalance%` where published (to verify which sizes publish them).
- **How it disguises itself.** Per-volume metrics look healthy; the aggregate across all attached volumes hits the instance ceiling, so no single volume looks saturated.
- **How to confirm.** Sum throughput and IOPS across all volumes on the instance and compare with the instance's documented EBS baseline; watch `EBSByteBalance%`/`EBSIOBalance%` fall.

## "Up to" network bandwidth burst and ENA allowances

- **The limit.** Many instance sizes advertise "up to" a network bandwidth (for example "up to 10 Gbps"), which is a burst sustained only for a limited time before dropping to a lower baseline (to verify against "Amazon EC2 instance network bandwidth"). The ENA driver also enforces per-flow and aggregate allowances.
- **The metric.** ENA allowance-exceeded counters: `bw_in_allowance_exceeded`, `bw_out_allowance_exceeded`, `pps_allowance_exceeded`, `conntrack_allowance_exceeded`, `linklocal_allowance_exceeded`. **How these are exposed is to verify**: they come from the ENA driver and are read either via `ethtool -S <iface>` on the instance or through the CloudWatch agent's `ethtool`/network-performance collector when configured (to verify against "Monitor network performance for your EC2 instance" and the CloudWatch agent ENA metrics documentation).
- **How it disguises itself.** `NetworkIn`/`NetworkOut` (bytes) look below the headline "up to" number, because the cap is the baseline after the burst window, not the advertised peak; packets are shaped, not dropped at the interface counters most people watch.
- **How to confirm.** Non-zero and rising `*_allowance_exceeded` counters aligned with the latency onset; compare sustained throughput against the instance's baseline (not the "up to") bandwidth.

## DynamoDB per-partition throughput

- **The limit.** A single partition serves a bounded throughput (for example up to 3,000 RCU and 1,000 WCU to verify against "DynamoDB adaptive capacity" / "Partitions and data distribution"). A hot key can be throttled while the table's provisioned or on-demand total is far from exhausted.
- **The metric.** `AWS/DynamoDB` `ThrottledRequests`, `ReadThrottleEvents`, `WriteThrottleEvents` (including per `GlobalSecondaryIndexName`), while `ConsumedReadCapacityUnits`/`ConsumedWriteCapacityUnits` stay below the table total.
- **How it disguises itself.** Table-level consumed capacity looks well under the limit, so the table looks under-used while one partition (one hot key) is throttled.
- **How to confirm.** Throttle events present with total consumed capacity below provisioned; identify the hot key from the access pattern or CloudWatch Contributor Insights (to verify).

## Lambda concurrency and burst

- **The limit.** Account concurrency is shared across functions; a function may also have reserved or provisioned concurrency. There is also a **burst** limit on how fast concurrency can ramp (to verify against "Lambda concurrency" and "Lambda scaling behavior").
- **The metric.** `AWS/Lambda` `ConcurrentExecutions` (Maximum) against the limit, `Throttles` (Sum) non-zero, `Duration` p99 against timeout.
- **How it disguises itself.** Average duration and invocation counts look normal; throttling shows up as 429s or dropped async events upstream, not as high CPU anywhere.
- **How to confirm.** `Throttles` > 0 with `ConcurrentExecutions` at the reserved or account ceiling; read reserved concurrency with `lambda:GetFunctionConcurrency` and provisioned concurrency with `lambda:ListProvisionedConcurrencyConfigs`. Before calling the cap the cause, compute effective concurrency (completion rate x duration) and attempts per originating request; if callers retry into the cap and the magnitude test passes (originating rate x 1 attempt fits the cap's served rate while the amplified attempt rate exceeds it; `diagnosis-rules.md`, Retry amplification), the retry policy is the cause and raising the cap is masking. `Throttles` are not counted in `Invocations`.

## SQS consumer visibility timeout and polling

- **The limit.** A received message stays hidden for the visibility timeout. A consumer that succeeds deletes it on completion; only a consumer that crashes, hangs or never deletes holds it for the whole timeout. Too long: a failed consumer's messages stay hidden for the full timeout, which delays retry and inflates age of oldest. Too short (below the processing-time tail): the message becomes visible mid-processing and is delivered again, so work is duplicated, consumer and downstream load rise, and a message can reach the dead-letter queue through `maxReceiveCount` after it was processed. `maxReceiveCount` is the redrive threshold (receives before a message moves to the dead-letter queue), not a drain-rate limit. Short polling and small batches add empty receives and per-message overhead (to verify against "Amazon SQS visibility timeout" and "Amazon SQS short and long polling").
- **The metric.** `AWS/SQS` `NumberOfMessagesReceived` well above `NumberOfMessagesSent`; `ApproximateNumberOfMessagesNotVisible` against busy consumers; dead-letter queue `ApproximateNumberOfMessagesVisible` growing; `ApproximateAgeOfOldestMessage`. Message attribute `ApproximateReceiveCount` above 1, visible in consumer logs if logged. `NumberOfMessagesDeleted` counts every successful delete with a valid receipt handle, including repeat deletes of a redelivered message, so it can overstate unique completions (to verify on the SQS CloudWatch metrics page).
- **How it disguises itself.** With a short timeout, consumers look busy and throughput looks healthy while much of the work is repeated; adding consumers makes it worse, because more idle consumers pick up the redelivered copies. With a long timeout, backlog age grows behind failed consumers while the healthy ones look idle.
- **How to confirm.** Compare processing-time p99 (consumer logs or traces) with the queue's visibility timeout, and receives with sends. For a Lambda event source mapping, compare the visibility timeout with the function timeout and the batch window; AWS recommends a visibility timeout of six times the function timeout plus `MaximumBatchingWindowInSeconds` (AWS Lambda Developer Guide, page `lambda/latest/dg/services-sqs-configure.html`).
- **Fix direction.** Set the visibility timeout from the measured processing p99 plus a margin, or extend visibility during long work with a `ChangeMessageVisibility` heartbeat, and make processing idempotent. More consumers and a higher `maxReceiveCount` are masking.

## Aurora Serverless v2 maximum ACU

- **The limit.** Serverless v2 scales between a configured minimum and **maximum** ACU; at the maximum it behaves like a fixed-size instance and cannot scale further (to verify against "Aurora Serverless v2 capacity").
- **The metric.** `AWS/RDS` `ServerlessDatabaseCapacity` (current ACU) and `ACUUtilization` (Maximum) pinned at the configured maximum, with `DBLoad` above the vCPU that the ACU cap provides.
- **How it disguises itself.** The cluster looks "serverless, so it will just scale", so capacity is assumed infinite; at the ACU ceiling it is simply undersized.
- **How to confirm.** `ServerlessDatabaseCapacity` flat at the maximum ACU during the latency window; read the configured maximum ACU from the cluster.

## ElastiCache network allowance

- **The limit.** Each node size has a network bandwidth allowance; smaller nodes have lower allowances and can be shaped before CPU or memory is a problem (to verify against "ElastiCache supported node types" / network limits).
- **The metric.** `AWS/ElastiCache` `NetworkBandwidthOutAllowanceExceeded` / `NetworkBandwidthInAllowanceExceeded` and `NetworkConntrackAllowanceExceeded` (Sum), non-zero.
- **How it disguises itself.** `EngineCPUUtilization` and `DatabaseMemoryUsagePercentage` look fine; latency rises only because packets are shaped at the node's network allowance.
- **How to confirm.** Non-zero allowance-exceeded counters aligned with the latency onset; compare node throughput against the node type's documented allowance.

## Service quotas and account limits

- **The limit.** Most AWS services enforce per-account, per-Region quotas (API request rates, resource counts, concurrency). A workload can hit a quota while its own resource metrics look healthy, because the cap is on the service side, not the instance.
- **The metric.** Service Quotas gives the applied value (`servicequotas:GetServiceQuota` and `ListServiceQuotas`); the `AWS/Usage` CloudWatch namespace publishes current usage for many quotas so usage can be charted against the limit. Throttling shows as 429 or `ThrottlingException` in client logs.
- **How it disguises itself.** The affected resource is not saturated at all; the requests are refused upstream, so CPU, memory and connections look fine while callers see errors or added latency from retries.
- **How to confirm.** Compare `AWS/Usage` against the applied quota from Service Quotas; correlate throttle errors in logs with usage reaching the quota. Verify which quotas publish to `AWS/Usage` against "AWS usage metrics" and the service's quota page.

## Auto Scaling group at its maximum

- **The limit.** An Auto Scaling group cannot grow past its configured maximum size, so a tier can be "fully scaled" and still short of demand. Scaling also has lag: launch, boot and health-check time mean it reacts slowly to a sudden spike.
- **The metric.** `AWS/AutoScaling` `GroupInServiceInstances` sitting at `GroupMaxSize` (also `GroupDesiredCapacity` pinned at the maximum), with per-instance utilization high and scaling activities showing no further launches.
- **How it disguises itself.** Per-instance CPU looks like a plain capacity problem; the real cap is the group maximum, so adding load just raises latency rather than triggering more instances.
- **How to confirm.** `autoscaling:DescribeAutoScalingGroups` for min, max and desired; `DescribeScalingActivities` for the last scaling action; compare `GroupInServiceInstances` with `GroupMaxSize` over the window.

## Application-level pools and descriptors

- **The limit.** Thread pools, connection pools (database, HTTP client), and the operating-system file-descriptor limit cap concurrency inside the process, below any AWS limit. When a pool is exhausted, new work queues or is rejected while host CPU and memory look moderate.
- **The metric.** Usually application-emitted: active versus maximum pool size, pool wait time, rejected or timed-out acquisitions, open file descriptors against the `ulimit`. Database-side connection count (`DatabaseConnections`) against `max_connections` is the server view of a client pool.
- **How it disguises itself.** The host is not busy; the bottleneck is a software limit, so infrastructure dashboards show headroom while requests wait for a slot. By Little's law a pool pinned at its maximum is often just `rate x latency` for a slow dependency, not an independent cause.
- **How to confirm.** Read pool configuration and pool metrics from the application; compare pool-at-maximum timing with downstream latency; check file-descriptor use against the limit.

## Lambda memory sets CPU share

- **The limit.** Lambda allocates CPU in proportion to configured memory, and at 1,769 MB a function has the equivalent of one vCPU (AWS Lambda Developer Guide, page `lambda/latest/dg/configuration-memory.html`). A function set to low memory can therefore be CPU-bound even when it uses little memory. Raising memory raises CPU and can cut duration (and sometimes cost) for CPU-bound work. Inference, not stated on that page: at 1,769 MB the function has one vCPU's worth, so code that runs on one thread is not expected to gain CPU above it; confirm by measuring. The same page notes that network-bound functions can also benefit from more memory; measure that effect rather than assuming a ratio.
- **The metric.** `AWS/Lambda` `Duration` (p99 against timeout) high while the function is not memory-constrained; compare duration across memory settings with a benchmark.
- **How it disguises itself.** Memory use looks low, so memory seems oversized, while the function is actually starved of CPU; the fix is more memory, not less.
- **How to confirm.** Read `MemorySize` from the function configuration, or the `Memory Size` field of the `REPORT` log lines if that read fails. Compare with a twin on the same code at a different memory size, or benchmark several settings, and apply the Lambda magnitude check in `diagnosis-rules.md`, section "Lambda memory and CPU" (inverse effective memory ratio, with min(memory, 1,769 MB) for single-threaded code, as an upper bound of the gain on the CPU-bound part; then the predicted post-change duration against the timeout, confirmed by measuring after the change).
- **Masking.** Raising the function's own timeout or adding provisioned or reserved concurrency does not shorten CPU-bound work; rank them below the memory change and never in the same command.
