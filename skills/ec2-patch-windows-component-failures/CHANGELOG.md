# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering component-specific / role-specific Windows patch failures:
  .NET Framework update failure, Windows Update driver conflicts with the AWS ENA/NVMe/PV drivers,
  feature-update / in-place-upgrade limbo, language-pack conflicts, corrupt profiles, and failover-cluster nodes.
- Routing decision checklist in `SKILL.md` with four `reference/` files (driver-conflicts,
  dotnet-repair, feature-update-limbo, cluster-and-misc).
- Self-validation loop, AWS/role-specific guidance (exclude WU drivers, .NET is an OS component,
  drain a cluster node before reboot), and gotchas.
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
