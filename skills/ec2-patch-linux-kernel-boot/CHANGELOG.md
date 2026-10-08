# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering the Linux kernel-patching / boot fault family:
  full /boot partition, GRUB2/BLS regeneration failures, kernel headers / DKMS module
  rebuild for third-party modules, and Oracle Linux UEK-vs-RHCK dual-kernel conflicts.
- Routing decision checklist in `SKILL.md` with four `reference/` files (boot-space,
  grub-and-bls, kernel-headers-dkms, uek-rhck-conflict).
- Backup-first / preserve-running-kernel guidance, validate-before-reboot loop, and gotchas
  for this high-risk (potentially unbootable) domain.
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
