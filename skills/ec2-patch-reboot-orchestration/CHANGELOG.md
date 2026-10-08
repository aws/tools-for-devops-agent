# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Cross-platform (Linux + Windows) patch reboot-orchestration skill covering the two
  reboot-timing states: pending-reboot non-compliance (RebootOption=NoReboot) and the "a system
  shutdown is in progress" reboot race.
- Routing decision checklist in `SKILL.md` with two `reference/` files (pending-reboot, reboot-race).
- Self-validation loop, compliance/PingStatus gates, RebootIfNeeded/approval gating for controlled
  reboots, bounded-wait (never-loop) guidance for races, and gotchas.
- IAM policy in `automation/iam-policy.json` (SSM run command + patch-state reads + EC2 describe/reboot).
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
