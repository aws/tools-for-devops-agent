# Changelog

All notable changes to the `ec2-patch-windows-servicing-store` skill are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-28
### Added
- Initial release. Domain skill covering the Windows component-servicing fault family:
  CBS/WinSxS store corruption, servicing stack (SSU) prerequisite ordering, pending
  servicing transactions, Windows Update datastore (DataStore.edb) corruption, and
  stalled feature-update state.
- Routing decision checklist in `SKILL.md` with five `reference/` files for per-sub-fault depth.
- Self-validation loop and ordered-recovery guidance (clear pending → SSU → RestoreHealth → SFC → reboot).
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (chat, investigation with bundled evidence fixtures, negative control).
