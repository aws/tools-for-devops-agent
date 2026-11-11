# CloudWatch Metrics — All FSx ONTAP Deployment Types

**Sources:** public AWS FSx for NetApp ONTAP documentation (`docs.aws.amazon.com`). Public doc wins any conflict. Read-only, control-plane.

All metrics publish to the `AWS/FSx` namespace. Read this file before querying
or interpreting any metric. Failure-mode thresholds and severity live in
`REFERENCE.md` §1–§3. This file covers **what each metric is, where it exists,
and how to query it** for each deployment type.

## Quick rules (all types)

1. Decide the generation from `DeploymentType` (`*_1` = gen1, `*_2` = gen2)
   before choosing dimensions (`deployment-types.md`).
2. Query every `*Utilization` metric on **`Maximum`**. FSx emits one datapoint
   per active file server or aggregate, even under `FileSystemId` alone, so
   `Average` hides a hot HA pair.
3. Empty series = **InsufficientData**, never zero or healthy. Run
   `cloudwatch:ListMetrics` for the file system to confirm which metric and
   dimension combinations exist before calling anything missing.
4. `Data*OperationTime` is in **seconds**. Average latency =
   Sum(`Data*OperationTime`) / Sum(`Data*Operations`) over the same period.
5. Gen2: locate the problem by `FileServer` / `Aggregate`, and size against
   **per-HA-pair** limits. Odd-numbered file servers carry client traffic.
   Even-numbered standbys still show background CPU and network, so a busy
   standby is not by itself evidence of failover.

## Collection checklist (Step 2)

Metric names are the same on
every deployment type. Gen1 (Multi-AZ 1, Single-AZ 1) metrics take
`FileSystemId` (plus `VolumeId` / `StorageTier` / `DataType` where noted).
**Gen2** (Multi-AZ 2, Single-AZ 2) also publishes network, CPU, and
file-server metrics per `FileServer` and disk / storage metrics per
`Aggregate`, and its utilization metrics are **% of one HA pair**. On every
type, query `*Utilization` metrics on **`Maximum`**: FSx emits one datapoint
per active file server or aggregate, so `Average` hides a hot HA pair. On gen2,
use `FileServer` / `Aggregate` to locate the hot pair. Odd-numbered file
servers carry client traffic, and even-numbered standbys still show background
load. See
"Gen1 vs gen2 metrics" below. Confirm what exists with
`cloudwatch:ListMetrics` before concluding a metric is missing.
- `StorageCapacityUtilization` — SSD tier fill % per aggregate (detailed metric,
  dimensions `StorageTier=SSD`, `DataType=All`; alert threshold: >75%)
- `FileServerDiskThroughputBalance` / `FileServerDiskIopsBalance` — % of
  **burst credits** remaining. Documented on the gen1 metrics page for
  throughput capacity **< 512 MBps**. Gen2 also emits them, per `FileSystemId` and per
  `FileServer`, even though the gen2 metrics page doesn't list them (verified
  live at 384 MBps and at 1,536 MBps per HA pair). The performance table
  documents disk burst only for gen2 tiers up to 1,536 MBps per pair, so expect
  no balance series at 3,072 / 6,144 MBps per pair (unverified: check
  `ListMetrics`). A declining balance means the
  workload is bursting above baseline. Throttling to baseline occurs only as
  the balance approaches **0**. Do NOT treat <100% alone as throttling.
- `FileServerDiskThroughputUtilization` / `FileServerDiskIopsUtilization` —
  file-server disk throughput / IOPS as % of the throughput-capacity limit
- `DiskIopsUtilization` — SSD IOPS as % of provisioned SSD IOPS
- `NetworkThroughputUtilization` — network saturation
- `CPUUtilization` — file-server CPU (use `AWS/FSx` metric only, not EC2-level)
- `DataReadBytes` / `DataWriteBytes` and `DataReadOperations` /
  `DataWriteOperations` — client I/O (Sum ÷ period seconds = per-second rate)
- `DataReadOperationTime` / `DataWriteOperationTime` — client latency
  (Sum ÷ Sum of matching Operations = average latency)


## Metric basics

From
[Monitoring with CloudWatch](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html)
and [File system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-system-metrics.html)):
all FSx for ONTAP metrics publish to the **`AWS/FSx`** namespace at **1-minute**
periods, except `FileServerDiskThroughputBalance` and `FileServerDiskIopsBalance`
which publish at **5-minute** intervals; CloudWatch retains them for **15
months**. Two read-side metrics are useful alongside the saturation metrics:

- `FileServerCacheHitRatio` — percentage of read requests served from the file
  server's RAM and NVMe caches (higher is better). A falling ratio means more
  reads miss cache and fall through to SSD/the capacity pool. Dimensions:
  `FileSystemId`, **and also per `FileServer` on first-generation** — verified
  live on a `SINGLE_AZ_1` file system, where `ListMetrics` returned
  `FileServer`-dimensioned entries. The docs imply this breakdown is
  second-generation only; it is not. Same lesson as the gen2 burst balances:
  **confirm dimensions with `ListMetrics`, don't infer them from the
  generation.**
- `CapacityPoolReadBytes` / `CapacityPoolReadOperations` — reads served from the
  capacity pool tier (dimensions `FileSystemId` **and per `VolumeId`**, verified
  live — use the per-volume series to find which volume is pulling from the
  pool). Sustained activity here means
  the working set no longer fits SSD or a tiering policy is pulling hot data
  from the capacity pool on access.


## Gen1 vs gen2 metrics — what differs
([Second-generation file system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/so-file-system-metrics.html),
[File system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-system-metrics.html)).
Multi-AZ 1 and Single-AZ 1 share one metric set (the set verified live). Multi-AZ 2
and Single-AZ 2 share the gen2 set. Metric **names** are the same. The
differences are in dimensions, denominators, and what one datapoint means:

| Aspect | Gen1 (`*_1`) | Gen2 (`*_2`) |
|---|---|---|
| Network, CPU, `FileServerDisk*Utilization` | `FileSystemId` | `FileSystemId` + **`FileServer`** (e.g. `FsxId…-01`). One datapoint per file server, **including standbys** |
| `FileServerCacheHitRatio` | `FileSystemId` **+ `FileServer`** (verified live on gen1 — not gen2-only) | `FileSystemId` + `FileServer` |
| `DiskRead/Write*`, `DiskIopsUtilization` | `FileSystemId` | `FileSystemId` + **`Aggregate`** (`aggr1`…, one per HA pair) |
| Detailed storage (`StorageCapacityUtilization`, `StorageUsed`, `StorageCapacity`) | `FileSystemId`, `StorageTier`, `DataType` | Same, optionally + `Aggregate` |
| Utilization denominator | The file system | **One HA pair**: `NetworkThroughputUtilization` and `FileServerDisk*Utilization` are % of one pair's capacity. `DiskIopsUtilization` is % of (total provisioned IOPS ÷ `HAPairs`) |
| Burst-balance metrics | `FileServerDiskThroughputBalance` / `FileServerDiskIopsBalance` below 512 MBps | Not on the gen2 metrics page, but **emitted live** at 384 and 1,536 MBps per HA pair, per `FileSystemId` and per `FileServer`. 3,072 / 6,144 per pair have no documented burst (unverified) |
| SSD decrease in progress | — | Disk and storage metrics are reported for **both `aggr1_old` and `aggr1`**. Don't double-count capacity, and expect the new aggregate to read high temporarily |
| Statistics | `NetworkSent/ReceivedBytes`: Sum only | `NetworkSent/ReceivedBytes`: Sum/Average/Min/Max. `DiskWriteOperations`: docs list Sum and Average (Maximum also returned data live; use Sum/Average) |

How to query gen2 correctly:

- The `FileSystemId`-only metrics are still available on gen2 (the gen2 page
  says so). For any `*Utilization` metric, FSx emits **one datapoint per active
  file server or aggregate** even under `FileSystemId` alone. So `Maximum`
  shows the hottest HA pair, and `Average` blends pairs and **hides** a hot one.
  Use `FileSystemId` + `Maximum` to detect a problem, then `FileServer` /
  `Aggregate` to locate it.
- Odd-numbered file servers are preferred and even-numbered are standby. The
  docs say standbys "typically show less utilization". Live, at idle, the
  standby's CPU and network ran at ~85–100% of the preferred server's, because
  of background activity. So:
  - attribute **client** load (`Data*`, `Metadata*`) to the preferred server;
  - judge saturation on the **higher** of the pair (`Maximum`), not the average;
  - never flag a standby as idle **or** as anomalous just for being busy;
  - a sustained load shift from odd to even (client throughput moving, with
    the odd server dropping) is a **failover hint** only. Confirm it with the
    failover triggers in `REFERENCE.md` §8 (a throughput change, maintenance
    window, `AdministrativeActions`, or AWS Health) before reporting failover.
- On gen2, the `FileSystemId`-only value for a utilization metric equalled the
  **highest** file server or aggregate, not the average. On 2 HA pairs,
  file-system `CPUUtilization` equalled `-01` (the busiest server), and
  file-system `DiskIopsUtilization` equalled `aggr1` (the busier aggregate).
  So `FileSystemId` + `Maximum` detects a hot pair, and the dimensions locate
  it.
- File server names are `FsxId<file-system-id-without-"fs-">-NN`, e.g.
  `FsxId0123456789abcdef0-01`. Aggregates are `aggr1` … `aggrN`.
- Multi-AZ 2 has exactly two file servers (`-01` preferred AZ, `-02` standby
  AZ) and one aggregate. Single-AZ 2 with *N* HA pairs has 2*N* file servers and
  *N* aggregates. A per-pair saturation finding names the file server or
  aggregate.
- Size against **per-pair** limits (6 GBps / 200K IOPS per pair), not the file
  system total. A multi-pair file system at 50% overall can have one pair at 100%.
- Client-side (`Data*`, `Metadata*`), capacity-pool, efficiency, and volume
  metrics are documented the same way for both generations.


## Units and publishing intervals

**Latency units:** `DataReadOperationTime` / `DataWriteOperationTime` are
reported in **seconds**. Average latency per op = Sum(`Data*OperationTime`) /
Sum(`Data*Operations`) for the same period (multiply by 1000 for ms). Treating
the raw value as milliseconds understates latency 1000x.

The two balance metrics are published at **5-minute** intervals (all other
`AWS/FSx` metrics at 1 minute) and in whole percent, so a slow drain can look
flat for several datapoints. Judge the trend over 30+ minutes.


## Live-verified metric inventory per deployment type

Captured with `cloudwatch:ListMetrics` on real test file systems (us-east-1,
Oct 2026). Use these to confirm which metric and dimension combinations exist.
Anything not listed for a type is unverified for that type, so check
`ListMetrics` before relying on it.

**`SINGLE_AZ_1`** (128 MBps, 1 SVM, 3 volumes). All metrics below take
`FileSystemId`; the extra dimension sets are shown in brackets.
- File system: `CPUUtilization`, `NetworkThroughputUtilization`,
  `NetworkSentBytes`, `NetworkReceivedBytes`, `FileServerDiskThroughputUtilization`,
  `FileServerDiskIopsUtilization`, `FileServerDiskThroughputBalance`,
  `FileServerDiskIopsBalance`, `FileServerCacheHitRatio`,
  `DiskIopsUtilization`, `DiskRead/WriteBytes`, `DiskRead/WriteOperations`,
  `StorageEfficiencySavings`, `LogicalDataStored`, `StorageUsed`.
- Client / capacity pool (also per `VolumeId`): `DataRead/WriteBytes`,
  `DataRead/WriteOperations`, `DataRead/WriteOperationTime`,
  `MetadataOperations`, `MetadataOperationTime`,
  `CapacityPoolRead/WriteBytes`, `CapacityPoolRead/WriteOperations`.
- Storage: `StorageCapacityUtilization`, `StorageCapacity`, `StorageUsed`
  [`StorageTier`, `DataType`]; per `VolumeId` [± `StorageTier`, `DataType`];
  `FilesCapacity`, `FilesUsed` [`VolumeId`].
- **No** `FileServer` or `Aggregate` dimensions on this type.

**`MULTI_AZ_1`** (128 MBps, 1 SVM, 2 volumes): **identical metric and
dimension set to `SINGLE_AZ_1`**, with no `FileServer` or `Aggregate`
dimensions. Burst balances are present (128 MBps < 512).

**`SINGLE_AZ_2`** (1 HA pair, 384 MBps) and **`MULTI_AZ_2`** (384 MBps): the
same metric **names** as gen1, plus these dimension sets:
- `[FileServer]` for `-01` and `-02`: `CPUUtilization`,
  `NetworkThroughputUtilization`, `NetworkSentBytes`, `NetworkReceivedBytes`,
  `FileServerDiskThroughputUtilization`, `FileServerDiskIopsUtilization`,
  `FileServerCacheHitRatio`, **`FileServerDiskThroughputBalance`,
  `FileServerDiskIopsBalance`**.
- `[Aggregate=aggr1]`: `DiskIopsUtilization`, `DiskReadBytes`,
  `DiskWriteBytes`, `DiskReadOperations`, `DiskWriteOperations`.
- `[StorageTier, DataType, Aggregate]`: `StorageCapacityUtilization`,
  `StorageCapacity`, `StorageUsed` (SSD and `StandardCapacityPool`).
- Every metric above also exists under `FileSystemId` alone.
- Client, capacity-pool, `Files*`, and per-volume metrics are identical to
  gen1.
- `MULTI_AZ_2` and single-pair `SINGLE_AZ_2` produced the same 106 series. Gen1
  types produced 79 series for a comparable layout.

**`SINGLE_AZ_2` with 2 HA pairs** (1,536 MBps per pair = 3,072 total, 2 TiB):
110 series. File servers `-01` … `-04` (`-01`/`-02` = pair 1, `-03`/`-04` =
pair 2) and aggregates `aggr1`, `aggr2`. Every `[FileServer]` metric listed
above exists for all four servers, **including both burst balances**. Every
`[Aggregate]` metric exists for both aggregates, and detailed storage metrics
exist per aggregate. N HA pairs means `-01` … `-(2N)` servers and `aggr1` …
`aggrN`. At idle, standbys `-02`/`-04` ran at ~80% of their preferred
partner's CPU.

**Per-volume storage breakdown (all four types).** `StorageUsed` per
`VolumeId` with `StorageTier=All` and `DataType` = `User` / `Snapshot` /
`Other` splits volume usage into active data, snapshots, and metadata. Use
`DataType=Snapshot` as **control-plane evidence of snapshot spill**
(`REFERENCE.md` §1) before asking for `volume show-space` (`ontap-cli-pack.md`).

**Not yet verified live:** gen2 at 3,072 / 6,144 MBps per HA pair (no burst is
documented, so the balance series are expected to be absent) and more than 2 HA
pairs (the naming pattern above should extend). Confirm with `ListMetrics`.
