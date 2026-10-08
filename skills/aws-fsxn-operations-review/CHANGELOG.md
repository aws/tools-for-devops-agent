# Changelog

All notable changes to the `aws-fsxn-operations-review` skill are documented here.

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
