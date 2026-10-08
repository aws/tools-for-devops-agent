---
name: ec2-patch-linux-dependencies
description: >-
  Resolve a Linux EC2 patch failure caused by package dependency conflicts —
  where the package DB is intact and repos are reachable, but the transaction
  cannot solve: yum/dnf depsolve conflicts, DNF module-stream (modular filtering)
  problems on RHEL 8/9, multilib (i686 vs x86_64) protected-version conflicts,
  APT broken/unmet dependencies and held-back packages, versionlock/pinning
  blocking security updates, and third-party-repo version clashes. Use when a
  patch run fails with "Depsolve Error", "conflicting requests", "nothing
  provides X needed by Y", "filtered out by modular filtering", "Protected
  multilib versions", "unmet dependencies", "Broken packages", or "kept back".
  The correct lever depends on the conflict type — modular filtering needs
  `dnf module reset`/`switch-to`, multilib needs a matched-version `distro-sync`,
  and an APT hold/pin needs unhold/unpin — so a blind `install`/`--nodeps` makes
  it worse. This skill classifies the conflict and applies the right resolution.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Linux, Patching"
  domains: "EC2, SSM, Patch Manager, yum, dnf, apt, module streams, multilib"
  platforms: "Linux"
  supported-os: "Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, CentOS 7, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, Debian 11, Debian 12"
  operation-type: "read-and-mutate"
---

# Resolve Linux package dependency conflicts blocking patching

## When this applies
A yum/dnf/apt patch transaction fails to *solve* — dependency, module-stream,
multilib, or pinning conflict — with the package DB intact and repos reachable.
If the DB is corrupt or the repo is unreachable, that is a different skill.

## The key insight: classify the conflict — the lever differs by type
"Conflict" is not one thing, and the wrong lever makes it worse:
- **Plain depsolve conflict** (two repos/versions, EPEL vs base): `dnf distro-sync --skip-broken`, fix repo priority, or pick a version. Not `--nodeps`.
- **Module-stream / modular filtering** (RHEL 8/9, "filtered out by modular filtering"): the package is *deliberately excluded* by an enabled/wrong module stream. Fix with `dnf module reset <m>` / `dnf module switch-to <m>:<stream>` — you cannot "force-install" past modular filtering.
- **Multilib** ("Protected multilib versions", i686 vs x86_64): the 32-bit and 64-bit copies are at different versions. Sync the *pair* to one version (`distro-sync`), or remove the unneeded i686 — after checking nothing requires it.
- **APT unmet deps / kept-back / held**: `apt-get install -f`, `dpkg --configure -a`, and unhold/unpin (`apt-mark unhold`, `/etc/apt/preferences.d/`) — a "kept back" security package is usually a hold/pin, not a real conflict.
- **versionlock / exclude** (RPM): a lock is deliberately pinning an old version against the security update — review and clear it.

## Diagnosis first
- [ ] Step 1: Classify the conflict before acting:
  ```bash
  # RPM: depsolve vs modular vs multilib
  dnf check 2>&1 | head
  dnf check-update 2>&1 | grep -iE 'modular|filtered|multilib|protected|conflict' | head
  dnf module list --enabled 2>&1 | head        # module streams in play
  yum versionlock list 2>/dev/null || dnf versionlock list 2>/dev/null
  # APT: broken / held / pinned
  apt-get check 2>&1; apt-mark showhold 2>&1; cat /etc/apt/preferences.d/* 2>/dev/null
  ```
- [ ] Step 2: Route to the conflict type (load the matching reference):
  - Module-stream / modular filtering → read [module streams](reference/module-streams.md).
  - Multilib / architecture → read [multilib conflicts](reference/multilib-conflicts.md).
  - APT unmet deps / held / pinned → read [apt dependencies](reference/apt-dependencies.md).
  - Plain yum/dnf depsolve, versionlock, third-party repo → read [rpm depsolve](reference/rpm-depsolve.md).

## Ordered resolution (least-destructive first)
- [ ] Step 3: **Clean cache + check for an incomplete transaction** first — a stale cache or half-finished transaction produces false conflicts (`dnf clean all`; `dnf history`).
- [ ] Step 4: **Apply the type-correct lever** from the routed reference — module reset/switch-to, matched multilib distro-sync, APT unhold/`-f`, or a scoped `distro-sync --skip-broken`. Prefer resolution over removal.
- [ ] Step 5: **Escalate the aggressiveness only if needed** — `--allowerasing` / `--best`, `apt-get dist-upgrade`, or removing a specific unneeded i686/held package — after confirming what it will remove.
- [ ] Step 6: **Verify** the transaction now solves (`dnf check` / `apt-get -s upgrade`).

## Validation (check your own work before reporting success)
- [ ] The conflict type was correctly classified (depsolve vs modular vs multilib vs APT-hold/pin), not treated generically.
- [ ] No integrity bypass was used to force it (`--nodeps`, `--force-*`, permanent `--allowerasing` of needed packages).
- [ ] `dnf check` / `apt-get check` returns clean and `dnf check-update` / `apt-get -s upgrade` shows the security updates are now installable (not filtered/held).
- [ ] The originally failing patch scan re-run no longer reports the conflict.
If any check fails, re-classify rather than escalating to `--nodeps`.

## Gotchas
- **`--nodeps` / `--force-depends` is almost never the fix** — it bypasses resolution and leaves a broken graph that breaks the *next* patch run. Resolve the conflict instead.
- **Modular filtering is deliberate, not a bug** — a package "filtered out by modular filtering" needs `dnf module reset`/`switch-to`, not a forced install; forcing it desyncs the module.
- **Multilib: sync the pair, don't just upgrade one arch** — upgrading only x86_64 while i686 lags recreates the protected-multilib conflict; distro-sync both or remove the unneeded i686 (check `--whatrequires` first).
- **A "kept back" security package on APT is usually a hold or pin**, not a genuine conflict — check `apt-mark showhold` and `/etc/apt/preferences.d/` before deeper surgery.
- **A corrupt RPM DB or interrupted transaction shows up as false conflicts** — if `dnf check` is bizarre, recover the DB first (separate skill), then re-resolve.
- **`dnf distro-sync --allowerasing` can remove packages** — confirm the removal list before running it in production.
