# Changelog

## [1.0.0] - 2026-09-29
### Added
- Initial release. Domain skill covering the Linux host-precondition fault family:
  read-only-remounted filesystem / EBS I/O errors, inode exhaustion, OOM during patching,
  SELinux/AppArmor scriptlet denials, NSS crypto-library (libfreeblpriv3.so) corruption that
  segfaults yum, locale/encoding and corrupt Python stdlib, PAM/PBIS misconfig, and post-patch
  systemd service-restart failures.
- Routing decision checklist in `SKILL.md` with four `reference/` files (filesystem-integrity,
  space-and-memory, runtime-library-corruption, security-and-services).
- Self-validation loop, rule-out-hardware-first ordering, and gotchas.
- Least-privilege IAM policy in `automation/iam-policy.json` (adds EC2 volume-status describes for the read-only-FS path).
- Eval definitions in `evals/evals.json` (three chat-shaped positive evals with inline evidence + negative control).
