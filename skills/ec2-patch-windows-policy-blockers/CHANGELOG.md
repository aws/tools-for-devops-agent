# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering the Windows policy/security-control patch-blocker family:
  GPO disabling Windows Update, antivirus/EDR file locks + the Spectre/Meltdown QualityCompat gate,
  BitLocker on boot-critical updates, the Server 2012 R2 SHA-2 signing prerequisite, and misc
  blockers (execution policy, registry ACLs, DCOM/RPC, Credential/Device Guard, scheduled task, language pack).
- Routing decision checklist in `SKILL.md` with four `reference/` files (gpo-blocks, av-interference,
  bitlocker, sha2-and-misc-blockers).
- Self-validation loop, temporary-vs-durable-fix guidance (GPO reverts, suspend-BitLocker-first), and gotchas.
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
