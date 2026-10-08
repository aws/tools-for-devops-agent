# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering the Windows update-service / runtime fault family:
  hung/crashed Windows Update (WUA) / BITS / TrustedInstaller, corrupt Windows Installer (MSI)
  service, Windows Update service set to Disabled, and AWSSDK.Core missing from the GAC (breaking
  AWS-RunPatchBaseline).
- Routing decision checklist in `SKILL.md` with four `reference/` files (service-startup-state,
  wua-bits-hang, msi-service, awssdk-gac).
- Self-validation loop, Disabled-vs-Stopped guidance, and gotchas.
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
