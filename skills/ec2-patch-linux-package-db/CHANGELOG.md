# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering the Linux package-database fault family:
  RPM database corruption (BerkeleyDB vs SQLite, including the AL2023 total-loss
  repo-reconstruction path), dpkg status/journal corruption, incomplete yum/dnf/apt
  transactions, and RPM/DEB file conflicts.
- Routing decision checklist in `SKILL.md` with four `reference/` files for per-sub-fault depth.
- Self-validation loop, ordered recovery guidance, and gotchas.
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
