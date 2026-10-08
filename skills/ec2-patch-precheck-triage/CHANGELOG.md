# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Cross-platform (Linux + Windows) patch-operation triage skill covering:
  prerequisite-check failures (with dependency ordering), transient-vs-genuine failure gating and
  evidence-backed OpsItem auto-close, SSM-unreachable-instance handling (control-plane only), and
  patch timeout / maintenance-window sizing.
- Routing decision checklist in `SKILL.md` with four `reference/` files (precheck-failures,
  transient-vs-genuine, ssm-unreachable, timeout-and-window).
- Self-validation loop, mandatory compliance/PingStatus gates, and gotchas.
- IAM policy in `automation/iam-policy.json` (SSM run command + patch-state reads + OpsItem update
  + EC2/IAM control-plane reads for unreachable-instance triage).
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
