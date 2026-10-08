---
name: ec2-patch-linux-host-preconditions
description: >-
  Recover a Linux EC2 instance whose patching is blocked by a host-level
  precondition rather than the package manager itself — filesystem and runtime
  faults beneath yum/dnf/apt: a read-only-remounted filesystem, inode exhaustion
  (disk "full" with free space showing), out-of-memory kills during patching,
  SELinux/AppArmor scriptlet denials, corrupt NSS crypto library
  (libfreeblpriv3.so) that segfaults yum itself, locale/corrupt-Python-stdlib
  errors, PAM misconfig, and systemd service-restart failures after patching. Use
  when a patch run fails with "Read-only file system", "No space left on device"
  while df shows free space, an OOM kill in dmesg, "avc: denied", or a
  Segmentation fault referencing libfreeblpriv3.so. The correct fix depends on
  the precondition — inode exhaustion needs `df -i` not `df -h`, a read-only FS
  from I/O errors must NOT just be remounted, and NSS corruption must be repaired
  with `rpm -ivh --force` because yum can't self-heal. This skill identifies the
  precondition and remediates it.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager, Amazon EBS"
  aws-devops-agent-skills.technical-domains: "Linux, Patching, Filesystem"
  domains: "EC2, SSM, Patch Manager, EBS, filesystem, SELinux, NSS, systemd"
  platforms: "Linux"
  supported-os: "Amazon Linux 2, Amazon Linux 2023, RHEL 7, RHEL 8, RHEL 9, Oracle Linux 7, Oracle Linux 8, Oracle Linux 9, CentOS 7, SLES 15, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04"
  operation-type: "read-and-mutate"
---

# Recover a Linux host-level precondition blocking patching

## When this applies
A patch operation fails because of a host/filesystem/runtime condition beneath
the package manager — not a corrupt package DB, dependency conflict, or repo
access issue (those are separate skills). Instance is Online in SSM.

## The key insight: identify the precondition — several mimic "disk full" or "package error"
- **Inode exhaustion**: "No space left on device" **while `df -h` shows free space**. The tell is `df -i` at ~100% — millions of small files (sessions, mail queue, tmp) ate the inodes. Free inodes, not bytes.
- **Read-only filesystem**: root/var remounted `ro`. This is often a **protective response to EBS I/O errors or FS corruption** — check `dmesg` for I/O errors FIRST. If there are I/O errors, do NOT just `remount,rw` (it can worsen corruption); the volume needs fsck/snapshot recovery.
- **OOM during patching**: the transaction was killed by the OOM killer (`dmesg | grep -i oom`) — free memory or raise it for the patch window, then retry.
- **NSS crypto library corruption**: yum/dnf/curl **segfault** referencing `libfreeblpriv3.so`. Because yum needs NSS for HTTPS/signatures, **it cannot self-repair** — reinstall the RPM with `rpm -ivh --force` (a local package file), bypassing yum.
- **SELinux/AppArmor**: package scriptlets fail with "SELinux is preventing"/"avc: denied" — restore contexts / update the policy package / set the profile to complain, then re-enforce.
- **Locale / corrupt Python stdlib**: `UnicodeDecode`/locale errors or a broken `locale` module break dnf (Python) — fix the locale / reinstall the stdlib piece.
- **PAM/PBIS & service restart**: auth misconfig blocking operations, or a systemd service that won't restart after its package updated.

## Diagnosis first
- [ ] Step 1: Classify the precondition before acting:
  ```bash
  df -h / /var /tmp; df -i / /var /tmp            # BYTES vs INODES — check both
  mount | grep -E ' ro,| rw,' | grep -vE 'proc|sys|cgroup|tmpfs'
  dmesg -T 2>/dev/null | grep -iE 'i/o error|remount|read-only|oom|segfault|libfreebl' | tail -20
  getenforce 2>/dev/null; ausearch -m AVC -ts recent 2>/dev/null | tail
  locale 2>&1 | head; python3 -c 'import locale' 2>&1
  ```
- [ ] Step 2: Route to the precondition (load the matching reference):
  - Read-only FS / EBS I/O error → read [filesystem integrity](reference/filesystem-integrity.md).
  - Inode exhaustion / disk pressure / OOM → read [space and memory](reference/space-and-memory.md).
  - NSS segfault / locale / corrupt Python stdlib → read [runtime library corruption](reference/runtime-library-corruption.md).
  - SELinux/AppArmor, PAM, service restart → read [security and services](reference/security-and-services.md).

## Ordered recovery
- [ ] Step 3: **Rule out hardware/volume first** — if `dmesg` shows EBS I/O or NVMe errors, treat the read-only FS as a volume problem (snapshot/fsck), not a remount. Don't mutate a failing volume.
- [ ] Step 4: **Free the blocking resource** — inodes (`df -i`-driven cleanup), memory (OOM), or space — as applicable, targeting the real exhausted resource.
- [ ] Step 5: **Repair a corrupt runtime** (NSS via `rpm -ivh --force`; locale/Python stdlib) so the package manager can run at all.
- [ ] Step 6: **Clear a security-policy block** (restore SELinux contexts / update policy / complain-mode AppArmor) then re-enforce, and restart any post-patch service.
- [ ] Step 7: **Verify** the host precondition is resolved and the package manager runs.

## Validation (check your own work before reporting success)
- [ ] The actual exhausted/broken resource was identified (e.g. inodes via `df -i`, not bytes), not a guess.
- [ ] A read-only FS was NOT force-remounted while `dmesg` showed I/O errors (that path escalates to volume recovery).
- [ ] For NSS: yum/dnf now runs without segfault (`rpm -V nss-softokn-freebl` clean; a `dnf repolist` succeeds).
- [ ] SELinux/AppArmor was returned to enforce mode (not left permissive/complain).
- [ ] `dnf check-update` / `apt-get -s upgrade` runs cleanly and the originally failing patch step no longer errors.
If any check fails, re-diagnose the precondition rather than forcing the patch.

## Gotchas
- **`df -h` looking healthy does not rule out "No space left on device"** — inode exhaustion needs `df -i`; free small files, not bytes.
- **A read-only root/var is usually protective** — check `dmesg` for EBS I/O / FS-corruption errors before `remount,rw`; remounting a failing volume can worsen corruption. Impaired EBS → snapshot/fsck/replace.
- **yum cannot fix its own NSS corruption** — `libfreeblpriv3.so` segfaults every NSS user including yum; reinstall via `rpm -ivh --force` from a local RPM, not `yum reinstall`.
- **Don't leave SELinux permissive or AppArmor in complain mode** after patching — re-enforce; a scoped policy module (`audit2allow`) is better than disabling enforcement.
- **OOM during patching recurs** unless addressed — check `dmesg | grep -i oom`; a small instance may need more memory for the transaction, or a swapfile for the patch window.
- **Locale/Python errors break dnf itself** (dnf is Python) — a corrupt stdlib/locale must be fixed before the package manager will run.
