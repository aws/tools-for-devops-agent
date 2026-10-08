# Kernel headers / DKMS module rebuild

**Signatures:** "DKMS module build failed", "Unable to find kernel headers for the running kernel",
"ERROR: Cannot open /lib/modules/<ver>/build", third-party modules (ENA, EFA, NVIDIA, CrowdStrike)
fail to compile, kernel patch completes but functionality is degraded post-reboot from missing modules.

**Headers must match the RUNNING kernel version** (`uname -r`), not just any installed headers.

## Diagnose
```bash
KERN=$(uname -r); echo "running: $KERN"
rpm -qa | grep -E 'kernel-devel|kernel-headers' 2>/dev/null || dpkg -l | grep linux-headers
test -d /lib/modules/$KERN/build && echo "build dir OK" || echo "build dir MISSING"
dkms status 2>/dev/null
```

## Install matching headers
```bash
KERN=$(uname -r)
dnf install -y "kernel-devel-$KERN" "kernel-headers-$KERN" 2>&1 \
  || apt-get install -y "linux-headers-$KERN" 2>&1 \
  || zypper install -y kernel-default-devel 2>&1
# Oracle UEK:
uname -r | grep -q uek && dnf install -y "kernel-uek-devel-$KERN" 2>&1
```

## Rebuild DKMS modules
```bash
command -v dkms >/dev/null && dkms autoinstall -k "$(uname -r)" 2>&1
```

## Verify
```bash
KERN=$(uname -r); test -f /lib/modules/$KERN/build/Makefile && echo "KERNEL HEADERS OK" || echo "MISSING"
dkms status 2>/dev/null
```

## Escalation
- Kernel from a third-party repo (Oracle UEK, elrepo) → enable the matching `-devel` repo.
- Headers unavailable for the running kernel (too old) → update the kernel first, then rebuild DKMS against the new one.
- Module still won't build → capture `/var/lib/dkms/<mod>/<ver>/build/make.log` for the compile error.
