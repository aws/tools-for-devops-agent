# Oracle Linux UEK vs RHCK kernel conflict

**Signatures:** "Error: Package kernel-uek conflicts with kernel", "cannot install both kernel-uek-X
and kernel-X", protected-multilib errors involving kernel packages, ksplice errors blocking kernel
updates, "No package kernel-uek-devel available". Cause: both the UEK (Unbreakable Enterprise Kernel)
and RHCK (Red Hat Compatible Kernel) repos enabled → the patch baseline tries to update both streams,
producing an unsolvable transaction.

## Diagnose which stream is running
```bash
uname -r | grep -q uek && echo "running UEK" || echo "running RHCK"; uname -r
dnf repolist 2>/dev/null | grep -iE 'uek|rhck|ksplice|oracle'
rpm -qa | grep -i kernel | sort
```

## Disable the UNUSED kernel repo (keep the one matching uname -r)
```bash
if uname -r | grep -q uek; then
  dnf config-manager --set-disabled 'ol*_RHCK' 2>/dev/null || yum-config-manager --disable 'ol*_RHCK'
else
  dnf config-manager --set-disabled 'ol*_UEK*' 2>/dev/null || yum-config-manager --disable 'ol*_UEK*'
fi
# ksplice interfering? stop it for the patch window:
rpm -q ksplice-tools >/dev/null 2>&1 && { systemctl stop uptrack 2>/dev/null; dnf config-manager --set-disabled 'ol*_ksplice' 2>/dev/null; }
dnf clean all; dnf makecache
```

## Verify
```bash
dnf check 2>&1 && dnf check-update 'kernel*' 2>&1 | tail && echo "KERNEL CONFIG OK"
```

## Rollback
```bash
dnf config-manager --set-enabled 'ol*_UEK*' 'ol*_RHCK' 2>/dev/null
rpm -q ksplice-tools >/dev/null 2>&1 && { dnf config-manager --set-enabled 'ol*_ksplice' 2>/dev/null; systemctl start uptrack 2>/dev/null; }
```

## Escalation
- Decide definitively which stream the workload needs; consider removing the unused one entirely (`dnf remove kernel-uek` or `dnf remove kernel`).
- Wrong UEK branch (UEK6 vs UEK7) → enable the correct `olN_UEKn` repo.
- Duplicate/conflicting repo defs in `/etc/yum.repos.d/oracle-linux-ol*.repo` → dedupe.
- ksplice patches applied → `uptrack-remove --all` before the standard kernel update.
