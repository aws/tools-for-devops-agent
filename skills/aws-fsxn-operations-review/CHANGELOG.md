# Changelog

All notable changes to the `aws-fsxn-operations-review` skill are documented here.

## [1.0.0] - 2026-10-14

Initial release of the Amazon FSx for NetApp ONTAP Operational Review skill.

- **Scope:** strict read-only, fully automated operational review of FSx for NetApp ONTAP
  (file system / SVM / volume / whole footprint) across five pillars — Backup, Observability,
  Operations, Performance, and Security — for production or pre-production. Self-discovers all ONTAP
  file systems in the account/region.
- **46 checks** driven entirely by public AWS APIs via `use_aws` (`fsx`, `cloudwatch`, `backup`,
  `ec2`): `Describe*` / `List*` / `Get*` and CloudWatch metric reads only. No manual steps, no ONTAP
  CLI.
- **Evidence guardrails:** every result is based solely on values returned during the run;
  missing/failed/empty data is reported as "Not evaluated" with a reason rather than a guessed
  Pass/Fail. Checks that cannot be answered from a public AWS API (individual ONTAP snapshot ages,
  FlexClone parentage) report "Not evaluated — not available via public API".
- **FSxN-specific correctness:** Gen2 SSD utilization computed from per-tier `StorageUsed{SSD}` /
  `StorageCapacity{SSD}` (Gen2 does not emit `StorageCapacityUtilization`); CPU/IOPS evaluated on a
  sustained p95, not a single-minute maximum; capacity-pool tiering flagged only with observed
  `CapacityPoolReadBytes > 0`; SVM root and `DP`/`LS` volumes evaluated but never recommended for
  removal; security-group checks resolve the file system's SGs via its ENIs and check only the ports
  for the protocol(s) in use.
- **References** split by pillar (`overview.md` + one file per pillar) for reliable context loading,
  plus a full report template under `assets/`.
- Least-privilege IAM delivered through the shared `cloudformation/devops-agent-skill-policies`
  template, and structure / best-practices / functional evaluation results included.
