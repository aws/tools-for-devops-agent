# Performance — Check Definitions

> **Read `overview.md` first.** It holds the Severity Model, Status Values, the Evidence
> Guardrails (observed-data-only), and the public AWS API / `AWS/FSx` metric reference that
> govern every check below. Load this pillar file when you run this pillar's checks.

## Performance (17 checks)

### PERF-01 — CPU utilization below 85%

- **Severity**: Critical
- **API**: `cloudwatch get-metric-data` — `CPUUtilization` (`Maximum`), dim `FileSystemId`
- **Logic**: Evaluate peak CPU over the window.
- **Status**: Pass — CPU < 85%. Fail — CPU ≥ 85%.
- **Recommendation (Fail)**: Investigate CPU consumers; consider adding HA pairs to add compute. Sustained
  high CPU raises latency across all volumes on the file system.
- **Fields**: `fileSystemId`, `cpuMaxPct`, `status`, `severity`

### PERF-02 — Throughput configuration matches workload

- **Severity**: High
- **API**: `fsx describe-file-systems` (`ThroughputCapacity`) + `cloudwatch get-metric-data`
  (`FileServerDiskThroughputUtilization`, `NetworkThroughputUtilization`)
- **Logic**: Compare sustained throughput utilization against provisioned capacity.
- **Status**: Pass — utilization < 80%. Warning — 80–95% or burst-balance alarm. Fail — > 95% sustained
  or consistently hitting burst limits.
- **Recommendation (Fail/Warning)**: Increase throughput capacity, or investigate the workload pattern
  driving sustained high utilization.
- **Fields**: `fileSystemId`, `throughputCapacity`, `throughputUtilPct`, `status`, `severity`

### PERF-03 — IOPS not over-provisioned

- **Severity**: Medium
- **API**: `fsx describe-file-systems` (`DiskIopsConfiguration`)
- **Logic**: Confirm provisioned IOPS is within the throughput-capacity tier maximum.
- **Status**: Pass — within tier max. Warning — provisioned above what the tier supports.
- **Recommendation (Warning)**: Ensure provisioned IOPS does not exceed the throughput-capacity tier
  maximum — paying for IOPS the tier cannot deliver.
- **Fields**: `fileSystemId`, `iopsMode`, `provisionedIops`, `status`, `severity`

### PERF-04 — IOPS utilization below 80%

- **Severity**: High
- **API**: `cloudwatch get-metric-data` — `FileServerDiskIopsUtilization` (`Maximum`), dim `FileSystemId`
- **Logic**: Evaluate peak disk IOPS utilization over the window.
- **Status**: Pass — < 80%. Warning — 80–90%. Fail — > 90%.
- **Recommendation (Fail/Warning)**: Increase provisioned IOPS or investigate write amplification
  (ONTAP writes in 4 KB blocks — a 1 MB write becomes 256 physical IOPS).
- **Fields**: `fileSystemId`, `iopsUtilMaxPct`, `status`, `severity`

### PERF-05 — SSD capacity below 80%

- **Severity**: High
- **API**: `cloudwatch get-metric-data` — `StorageCapacityUtilization` (`Maximum`), dim
  `FileSystemId`. On **first-generation** file systems this metric reflects **primary (SSD) tier**
  utilization (it backs the FSx "low primary storage" alarm). **On second-generation file systems
  (`DeploymentType` ending in `_2`), `StorageCapacityUtilization` is not emitted** — fall back to the
  detailed per-tier metrics and compute `StorageUsed{StorageTier=SSD,DataType=All}` ÷
  `StorageCapacity{StorageTier=SSD,DataType=All}` (× 100). Treat a `StorageCapacityUtilization` query
  that returns no datapoints as "use the detailed-metric fallback," never as 0%.
- **Logic**: Evaluate peak SSD (primary tier) utilization.
- **Status**: Pass — < 80%. **Warning — 80–90%. Critical — > 90% (tiering promotion stops; hot data
  stays in the capacity pool at 15–25 ms latency).**
- **Recommendation (Fail)**: Increase SSD capacity or review tiering policies before promotion stalls.
- **Fields**: `fileSystemId`, `ssdUtilMaxPct`, `status`, `severity`

### PERF-06 — Volume tiering policies appropriate

- **Severity**: High
- **API**: `fsx describe-volumes` (`OntapConfiguration.TieringPolicy.Name`)
- **Logic**: Inventory tiering policy per volume and flag mismatches against general guidance:
  `NONE`/`SNAPSHOT_ONLY` for latency-sensitive active data, `AUTO` for general-purpose, `ALL` only for
  archive/migration.
- **Status**: Info — report all policies; flag `ALL` on an active RW volume for review.
- **Recommendation**: Match tiering policy to the data's access pattern; `ALL` on active data forces
  every read from the capacity pool (15–25 ms).
- **Fields**: `volumeId`, `tieringPolicy`, `ontapVolumeType`, `status`, `severity`

### PERF-08 — Aggregate workload balanced

- **Severity**: Medium
- **API**: `fsx describe-volumes` (`AggregateConfiguration`)
- **Logic**: Check volume distribution across aggregates for gross imbalance.
- **Status**: Pass — even distribution. Warning — skew across aggregates.
- **Recommendation (Warning)**: Redistribute volumes for even I/O distribution across aggregates.
- **Fields**: `fileSystemId`, `aggregateDistribution`, `status`, `severity`

### PERF-09 — FlexGroup constituent balance

- **Severity**: Medium
- **API**: `fsx describe-volumes` (`AggregateConfiguration.ConstituentsPerAggregate`)
- **Logic**: For FlexGroup volumes, check constituent counts are evenly distributed across aggregates.
- **Status**: Pass — even. Warning — uneven constituent distribution.
- **Recommendation (Warning)**: Rebalance FlexGroup constituents for even capacity and I/O distribution.
- **Fields**: `volumeId`, `constituentsPerAggregate`, `status`, `severity`

### PERF-11 — Network path optimized (preferred subnet)

- **Severity**: Medium
- **API**: `fsx describe-file-systems` (`OntapConfiguration.PreferredSubnetId`) + `ec2 describe-subnets`
- **Logic**: Report the preferred subnet and its AZ so client placement can be reviewed (cross-AZ adds
  ~1–2 ms per I/O).
- **Status**: Info — report preferred subnet / AZ.
- **Recommendation**: Place latency-sensitive compute in the same AZ as the file system's preferred
  subnet.
- **Fields**: `fileSystemId`, `preferredSubnetId`, `availabilityZone`, `status`, `severity`

### PERF-15 — Client throughput within nominal values

- **Severity**: High
- **API**: `cloudwatch get-metric-data` — `DataReadBytes`, `DataWriteBytes` (`Sum`), dim `FileSystemId`
- **Logic**: Confirm client throughput metrics are emitting and within the expected range for the
  provisioned tier.
- **Status**: Pass — within expected range. Warning — approaching tier limit. Not evaluated — metric not
  emitting.
- **Recommendation (Warning)**: Investigate if metrics are not emitting or throughput is approaching the
  provisioned tier limit.
- **Fields**: `fileSystemId`, `readThroughput`, `writeThroughput`, `status`, `severity`

### PERF-16 — File-system generation appropriate

- **Severity**: High
- **API**: `fsx describe-file-systems` (`DeploymentType`, `FileSystemTypeVersion`, `ThroughputCapacity`)
- **Logic**: Infer generation from `DeploymentType` — `SINGLE_AZ_2` / `MULTI_AZ_2` indicate
  second-generation file systems (higher per-HA-pair throughput and scale-out HA pairs).
- **Status**: Info — report generation; flag first-generation systems that are throughput-constrained.
- **Recommendation**: Second-generation file systems are recommended for high-throughput workloads
  (greater per-HA-pair throughput and scale-out HA pairs).
- **Fields**: `fileSystemId`, `deploymentType`, `generation`, `throughputCapacity`, `status`, `severity`

### PERF-17 — Capacity-pool tiering only for archive data

- **Severity**: Critical
- **API**: `fsx describe-volumes` (`OntapConfiguration.TieringPolicy.Name`, `OntapVolumeType`)
- **Logic**: Flag RW volumes with `TieringPolicy = ALL`.
- **Status**: Pass — no active RW volume uses `ALL`. Fail — an RW volume uses `ALL`.
- **Recommendation (Fail)**: `ALL` tiering on an active volume forces every read from the capacity pool
  (15–25 ms). Change to `AUTO` or `NONE` for active data; reserve `ALL` for archive/migration.
- **Fields**: `volumeId`, `tieringPolicy`, `ontapVolumeType`, `status`, `severity`

### PERF-18 — HA pair count sufficient

- **Severity**: High
- **API**: `fsx describe-file-systems` (`OntapConfiguration.HAPairs`)
- **Logic**: Report HA pair count; aggregate throughput and IOPS scale with HA pairs (per-HA-pair SSD
  write ceiling is 1,024 MBps and cannot be raised by changing the throughput tier alone).
- **Status**: Info — report HA pair count; flag single-HA-pair systems that are throughput-constrained.
- **Recommendation**: For high-throughput workloads, add HA pairs to increase aggregate throughput and
  IOPS. Note the 1,024 MBps per-HA-pair SSD write ceiling.
- **Fields**: `fileSystemId`, `haPairs`, `status`, `severity`

### PERF-19 — FlexClone not referencing tiered parent data

- **Severity**: High
- **API**: `fsx describe-volumes` (clone volumes whose parent uses `AUTO`/`ALL` tiering) +
  `cloudwatch get-metric-data` (`CapacityPoolReadBytes` on the parent)
- **Logic**: Flag FlexClone volumes whose parent volume uses `AUTO`/`ALL` tiering and shows
  `CapacityPoolReadBytes > 0`.
- **Status**: Pass — no clone references tiered parent data. Fail — clone of a tiered parent with active
  capacity-pool reads.
- **Recommendation (Fail)**: FlexClone on tiered parent data has no read-ahead — per-block S3 fetches at
  15–25 ms. Restore from backup instead, or promote the parent's tiered data first.
- **Fields**: `volumeId`, `parentVolumeId`, `parentTieringPolicy`, `capacityPoolReadBytes`, `status`, `severity`

### PERF-21 — No unexpected capacity-pool reads on active volumes

- **Severity**: High
- **API**: `cloudwatch get-metric-data` — `CapacityPoolReadBytes` (`Sum`), dims `FileSystemId`,
  optionally `VolumeId`
- **Logic**: Evaluate average capacity-pool read rate on file systems with active RW volumes.
- **Status**: Pass — 0 or negligible (< 1 GB/hr avg). Warning — 1–10 GB/hr (some cold data accessed).
  Fail — > 10 GB/hr sustained (active reads from capacity pool causing latency impact).
- **Recommendation (Fail/Warning)**: Identify which volumes generate capacity-pool reads and change
  tiering to `NONE` for latency-sensitive active data; for volumes that must use `AUTO`, reduce the
  cooling period or promote data.
- **Fields**: `fileSystemId`, `volumeId`, `capacityPoolReadBytesPerHr`, `status`, `severity`

### PERF-22 — Cache hit ratio

- **Severity**: Medium
- **API**: `cloudwatch get-metric-data` — `FileServerCacheHitRatio` (`Average`/`Minimum`), dim
  `FileSystemId`
- **Logic**: Evaluate the percentage of reads served from the file server's RAM/NVMe cache. A low ratio
  means most reads miss cache and hit disk/capacity-pool, raising latency.
- **Status**: Pass — healthy cache hit ratio (high). Warning — depressed ratio with active read traffic.
  Not evaluated — file system idle (no reads).
- **Recommendation (Warning)**: Investigate the low cache hit ratio — the working set may exceed the
  cache available at the current throughput-capacity tier; consider a larger tier or review which
  volumes drive the most reads.
- **Fields**: `fileSystemId`, `cacheHitRatioPct`, `status`, `severity`

### PERF-23 — Latency monitoring

- **Severity**: Medium
- **API**: `cloudwatch get-metric-data` — read latency = `DataReadOperationTime` ÷ `DataReadOperations`,
  write latency = `DataWriteOperationTime` ÷ `DataWriteOperations`, metadata latency =
  `MetadataOperationTime` ÷ `MetadataOperations` (dims `FileSystemId`, optionally `VolumeId`). Op-time
  is in **seconds**; multiply by 1000 for ms.
- **Logic**: Compute average read/write/metadata latency and flag values outside the expected range.
  Elevated latency on a volume reading from the capacity pool (15–25 ms) correlates with tiering (see
  PERF-21).
- **Status**: Pass — latency within range. Warning — elevated latency with active traffic. Not
  evaluated — file system idle (no operations to divide by).
- **Recommendation (Warning)**: Investigate the latency source — SSD pressure (PERF-05), IOPS
  saturation (PERF-04), or capacity-pool reads (PERF-21). Always label the unit (ms).
- **Fields**: `fileSystemId`, `readLatencyMs`, `writeLatencyMs`, `metadataLatencyMs`, `status`, `severity`

---
