# DNF/YUM module-stream (modular filtering) conflicts (RHEL 8/9, OL 8/9, AL2023)

**Signatures:** "package X is filtered out by modular filtering", "Modular dependency problems",
"No available modular metadata for modular package X", "Module <name>:<stream> profiles ... not
available", "module stream is enabled but packages are not installed", security patch for a modular
package won't apply due to stream pinning.

**Key point:** modular filtering is a **deliberate exclusion** — an enabled (or wrong) module stream
hides packages from other streams. You cannot "force-install" past it; fix the stream state.

## Diagnose
```bash
dnf module list --enabled 2>&1
dnf module list --installed 2>&1
dnf check-update 2>&1 | grep -iE 'modular|filtered'
```

## Fix
```bash
# reset the problematic module (clears the stream pin), then re-enable the intended stream:
dnf module reset <module> -y
dnf module enable <module>:<stream> -y          # or switch streams cleanly:
dnf module switch-to <module>:<stream> -y
# then re-solve:
dnf distro-sync -y
```

## Verify
```bash
dnf check 2>&1; dnf check-update 2>&1 | grep -qi 'modular\|filtered' && echo "MODULAR ISSUES REMAIN" || echo "MODULE STREAMS OK"
```

## Escalation
- List all streams for a module: `dnf module list --all <module>`.
- Forced transition: `dnf --allowerasing module switch-to <module>:<stream> -y`.
- Deeply conflicting: `dnf module reset <module> && dnf distro-sync`.
- On Oracle Linux, confirm the `olN_appstream` repo matches the OS release — a mismatched appstream provides wrong modular metadata.
- A third-party repo providing modular metadata can break resolution — disable it to test.
