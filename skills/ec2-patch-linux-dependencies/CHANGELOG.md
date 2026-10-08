# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering the Linux dependency-resolution fault family:
  yum/dnf depsolve conflicts, DNF module-stream (modular filtering) problems, multilib
  (i686 vs x86_64) protected-version conflicts, APT broken/unmet dependencies and held/pinned
  packages, versionlock/exclude, and third-party-repo version clashes.
- Routing decision checklist in `SKILL.md` with four `reference/` files (module-streams,
  multilib-conflicts, apt-dependencies, rpm-depsolve).
- Self-validation loop, least-destructive-first ordered resolution, and gotchas.
- Least-privilege IAM policy in `automation/iam-policy.json`.
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
