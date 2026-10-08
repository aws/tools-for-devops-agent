# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering the Windows update-connectivity fault family:
  WSUS/Microsoft Update endpoint unreachable, proxy authentication in the SYSTEM context (HTTP 407),
  TLS 1.2 not enabled, outdated/missing root certificates, firewall/WPAD, and clock-skew cert errors.
- Routing decision checklist in `SKILL.md` with four `reference/` files (wsus-routing,
  proxy-system-context, tls-settings, root-certs-and-clock).
- Self-validation loop, source-classification (WSUS vs Microsoft Update) and escalate-don't-loop guidance, and gotchas.
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
