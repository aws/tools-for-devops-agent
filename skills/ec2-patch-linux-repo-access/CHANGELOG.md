# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering the Linux repository access/authentication fault family:
  RHUI client-certificate expiry (region-specific), subscription-manager / SUSE cloud registration,
  Oracle Linux yum/ULN access, expired repo TLS certificates / stale CA bundle, rotated or missing
  GPG signing keys, proxy misconfiguration, stale metadata cache, and NTP/time-skew.
- Routing decision checklist in `SKILL.md` with four `reference/` files.
- Self-validation loop, ordered recovery (clock → auth → CA → metadata), and gotchas.
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
