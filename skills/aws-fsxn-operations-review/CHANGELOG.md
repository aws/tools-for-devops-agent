# Changelog

All notable changes to the `aws-fsxn-operations-review` skill are documented here.

## [1.6.0] - 2026-10-14

Addressed FSxN domain-correctness feedback from the SME review on PR #117.

- **OPS-11 (aged snapshots):** `fsx describe-snapshots` returns OpenZFS/Windows snapshots, not ONTAP
  snapshots — the check now reports **Not evaluated — not available via public API** instead of a false
  Pass. ONTAP snapshot retention is covered by snapshot policy (OPS-06).
- **PERF-19 (FlexClone on tiered parent):** the public API does not expose a FlexClone's parent volume —
  the check now reports **Not evaluated — not available via public API** rather than guessing.
- **BKP-03 (SnapMirror/DP):** changed to **Informational**. A healthy DR design keeps the SnapMirror
  destination on a separate file system/Region/account that may be out of scope, so zero DP volumes on
  the source is no longer a Fail.
- **PERF-01 / PERF-04 (CPU / IOPS):** evaluate a **sustained** statistic (p95), not `Maximum`, so a
  single one-minute spike no longer produces a Critical.
- **PERF-04 (IOPS):** now reads both `FileServerDiskIopsUtilization` (throughput-tier limit) and
  `DiskIopsUtilization` (SSD disk IOPS limit) and recommends against the metric actually saturated —
  no longer recommends more SSD IOPS when the throughput tier is the constraint.
- **PERF-17 (capacity-pool tiering):** only fails an `ALL`-tiered RW volume when
  `CapacityPoolReadBytes > 0`; a genuine archive volume with no active capacity-pool reads is
  Informational, not Critical.
- **OPS-02 (unused volumes):** excludes `DP` (SnapMirror destination) and `LS` (load-sharing mirror)
  volumes from the unused/removal signal — they have no direct client I/O by design and must never be
  recommended for removal.
- **SEC-01 (required ports):** checks only the ports for the protocol(s) actually in use (SMB 445 vs
  NFS 2049/111/635/4045–4046), inferred from `SecurityStyle` / SVM AD config — no longer tells an
  SMB-only SVM to open NFS ports.
- **SEC-01 / SEC-02 / SEC-08 (security groups):** resolve the file system's security groups from its
  ENIs (`fsx describe-file-systems` `NetworkInterfaceIds` → `ec2 describe-network-interfaces` →
  `Groups`); adds `ec2:DescribeNetworkInterfaces` to the IAM policy.

## [1.5.0] - 2026-10-02

Initial public release of the Amazon FSx for NetApp ONTAP Operational Review skill.

- **Scope:** strict read-only, fully automated operational review of FSx for NetApp
  ONTAP (file system / SVM / volume / whole footprint) across five pillars —
  Backup, Observability, Operations, Performance, and Security — for production or
  pre-production. Self-discovers all ONTAP file systems in the account/region.
- **46 checks** driven entirely by public AWS APIs via `use_aws`
  (`fsx`, `cloudwatch`, `backup`, `ec2`): `Describe*` / `List*` / `Get*` and
  CloudWatch metric reads only. No manual steps and no ONTAP CLI.
- **Evidence guardrails:** every result is based solely on values returned during the
  run; missing/failed/empty data is reported as "Not evaluated" with a reason rather
  than a guessed Pass/Fail. No assumptions or inference of unobserved state.
- **References split by pillar** (`overview.md` + one file per pillar) for reliable
  context loading, plus a full report template under `assets/`.
- **Gen2 handling:** computes SSD utilization from per-tier `StorageUsed{SSD}` /
  `StorageCapacity{SSD}` because Gen2 file systems do not emit
  `StorageCapacityUtilization`.
- **SVM root volume** (`JunctionPath = "/"`) is detected from returned fields,
  excluded only where the metric is invalid (OPS-10), tagged elsewhere, and never
  treated as a deletion candidate.
- Least-privilege IAM policy and evaluation results (structure, best-practices,
  functional) included.
