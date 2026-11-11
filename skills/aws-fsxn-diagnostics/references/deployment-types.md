# FSx for NetApp ONTAP — Deployment Types

**Sources:** public AWS FSx for NetApp ONTAP documentation (`docs.aws.amazon.com`). Public doc wins any conflict. Read-only, control-plane.

Users and screenshots use the **console names**. The API and CLI return only
the `OntapConfiguration.DeploymentType` **value**. Map one to the other before
analysis, and always report both ("Multi-AZ 2 (`MULTI_AZ_2`)").

| Console name | API value | Gen | AWS positioning (console / docs) |
|---|---|---|---|
| **Multi-AZ 2** (console: *Recommended*) | `MULTI_AZ_2` | 2 | Workloads that need **up to 6 GBps** throughput or **200K SSD IOPS**. Standby file server in a second AZ protects against file-server failure **and** AZ disruption. One HA pair. |
| **Single-AZ 2** | `SINGLE_AZ_2` | 2 | Workloads that need **over 6 GBps** or **over 200K IOPS**: 1–12 HA pairs, up to 72 GBps and 2.4M IOPS (6 GBps / 200K per pair). No AZ protection on its own. AWS's guidance is to **replicate to a file system in another AZ** (SnapMirror) for AZ resilience. |
| **Multi-AZ 1** | `MULTI_AZ_1` | 1 | First-generation Multi-AZ: one HA pair, up to 4 GBps and 160K IOPS, standby in a second AZ. |
| **Single-AZ 1** | `SINGLE_AZ_1` | 1 | First-generation Single-AZ: one HA pair, up to 4 GBps and 160K IOPS, single AZ. |

Sources:
[Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html),
[Managing HA pairs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/HA-pairs.html).
Gen1 file systems also return `HAPairs = 1` and `ThroughputCapacityPerHAPair`,
so decide the generation from the `_1` / `_2` suffix only.

## Which checks apply to which type

| Check / behavior | `SINGLE_AZ_1` | `MULTI_AZ_1` | `SINGLE_AZ_2` | `MULTI_AZ_2` | Where |
|---|---|---|---|---|---|
| Throughput tiers (MBps) | 128–4,096 | 128–4,096 | 384–6,144 (1 pair); 1,536 / 3,072 / 6,144 per pair (multi-pair) | 384–6,144 | `REFERENCE.md` §2 |
| Max SSD / SSD IOPS | 192 TiB / 160K | 192 TiB / 160K | 512 TiB (1 pair), 1 PiB total / 200K per pair, 2.4M total | 512 TiB / 200K | `REFERENCE.md` §1, `REFERENCE.md` §3 |
| Burst-balance metrics | Yes, if < 512 MBps (live) | Yes, if < 512 MBps (live) | Yes up to 1,536 MBps per pair, also per `FileServer` (live at 384 and 1,536; not on the gen2 doc page). None expected at 3,072 / 6,144 | Yes at 384 MBps, also per `FileServer` (live). None expected at 3,072 / 6,144 | `cloudwatch-metrics.md` |
| Network baseline table | Gen1 table (`REFERENCE.md` §2) | Gen1 table, Multi-AZ row in docs | Gen2 row in docs, plus write ceiling | Gen2 row in docs, plus write ceiling | `REFERENCE.md` §2 |
| Metric dimensions | `FileSystemId` | `FileSystemId` | `FileSystemId`, plus `FileServer` (2 per HA pair) / `Aggregate` (1 per HA pair) | `FileSystemId`, plus `FileServer` (`-01`, `-02`) / `Aggregate` (`aggr1`) | `cloudwatch-metrics.md` |
| Utilization denominator | File system | File system | One HA pair | One HA pair (= file system) | `cloudwatch-metrics.md` |
| Endpoints | In-VPC IPs | NFS/SMB/management floating (`EndpointIpAddressRange`); iSCSI and intercluster in-VPC | In-VPC IPs | NFS/SMB/management floating; iSCSI and intercluster in-VPC | `REFERENCE.md` §6 |
| `RouteTableIds` coverage check | — | **Required** | — | **Required** | `REFERENCE.md` §6 |
| Off-VPC access (peering / DX / VPN) | Works directly | Needs Transit Gateway | Works directly | Needs Transit Gateway | `REFERENCE.md` §6 |
| Survives AZ outage | No | Yes (automatic failover) | No, unless replicated to another AZ | Yes (automatic failover) | `REFERENCE.md` §9 |
| Failover scope | Whole file system | Whole file system, auto failback | **Per HA pair** | Whole file system, auto failback | `REFERENCE.md` §8 |
| SSD decrease | No | No | Yes (≥ 9%, ≤ 80% after) | Yes (≥ 9%, ≤ 80% after) | `REFERENCE.md` §1, `REFERENCE.md` §8 |
| 6-hour scaling cooldown | No (requests queue) | No (requests queue) | Yes | Yes | `REFERENCE.md` §2 |
| Add HA pairs (scale out) | No | No | **Yes** | No (always 1) | `REFERENCE.md` §2 |
| iSCSI / NVMe/TCP | iSCSI | iSCSI | iSCSI and NVMe if ≤ 6 HA pairs | iSCSI and NVMe | `REFERENCE.md` §6 |

## Multi-pair Single-AZ 2 volume gotcha

On a `SINGLE_AZ_2` with more than one HA pair, volumes are **FlexGroup**
volumes spread across aggregates, with a minimum of **100 GiB per
constituent** (default 8 constituents per aggregate). A small `CreateVolume`
fails with "Minimum storage capacity for ONTAP FlexGroup volumes is 100 GiB per
constituent" (verified live: a 100 GiB volume on 2 HA pairs failed). The fix is
a larger size or fewer constituents (`AggregateConfiguration`). Treat this
error as sizing, not a fault
([Volume styles](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html)).

## When the deployment type itself is the finding

The deployment type **cannot be changed after creation**. Moving between types
means migrating with SnapMirror, AWS DataSync, or backup-and-restore to a new
file system. Never recommend an in-place switch, and never recommend a
migration only because a file system is first-generation.

| Observation | Finding | Severity |
|---|---|---|
| `MULTI_AZ_*` or single-pair `SINGLE_AZ_2` saturated (`REFERENCE.md` §2/§3) **at its maximum tier** (6,144 MBps / 200K IOPS gen2, 4,096 / 160K gen1) | The workload has outgrown a single HA pair. Recommend **Single-AZ 2** with multiple HA pairs, plus SnapMirror to another AZ if AZ resilience is required. Migration is required. | HIGH if clients are degraded, otherwise MEDIUM |
| Multi-pair `SINGLE_AZ_2` saturated per pair | Add HA pairs (scale out) before migrating. Check whether one aggregate is hot first (data-plane rebalance, `ontap-cli-pack.md`). | Per `REFERENCE.md` §2/§3 |
| Gen1 saturated at 4,096 MBps / 160K IOPS | Move to gen2: **Multi-AZ 2** if ≤ 6 GBps / 200K IOPS covers it, **Single-AZ 2** if more | Per `REFERENCE.md` §2/§3 |
| `SINGLE_AZ_*` running a workload the user describes as production or business-critical, and no evidence of a SnapMirror destination in another AZ | AZ-resilience gap. The AWS-recommended pattern is SnapMirror to a file system in another AZ, or Multi-AZ 2 if ≤ 6 GBps / 200K IOPS covers it. Replication can't be proven from the control plane: a DP-type volume on another file system in a different AZ is suggestive, and `snapmirror show` (`ontap-cli-pack.md`) confirms it. | MEDIUM (LOW if the user says AZ loss is acceptable) |
| `MULTI_AZ_*` whose client subnets' route tables are not all in `RouteTableIds` | Clients cannot reach the floating endpoints, or lose access on failover (`REFERENCE.md` §6) | HIGH if clients are failing, otherwise MEDIUM |
