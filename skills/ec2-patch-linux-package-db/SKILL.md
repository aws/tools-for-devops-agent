---
name: ec2-patch-linux-package-db
description: >-
  Recover a Linux EC2 instance whose patching is blocked by a corrupt package
  database or interrupted package transaction — failures rooted in the RPM
  database (BerkeleyDB or SQLite), the dpkg status/journal, incomplete
  yum/dnf/apt transactions, or RPM/DEB file conflicts. Use when a patch run fails
  with "rpmdb: BDB0113", "rpmdb open failed", "database disk image is malformed",
  "cannot open Packages database", "dpkg was interrupted", a dpkg status parse
  error, "unfinished transactions remaining", half-installed packages, or "file X
  conflicts with file from package Y". The correct recovery depends on the
  packager AND the RPM backend — the naive `rpm --rebuilddb` is wrong on a totally
  corrupt AL2023 sqlite database (it rebuilds from on-disk headers that no longer
  exist, leaving an empty DB), and clearing dpkg journal files differs from
  restoring a corrupt dpkg status. This skill diagnoses which fault and packager
  is present and applies the correct, ordered, backup-first recovery.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Linux, Patching"
  domains: "EC2, SSM, Patch Manager, RPM, dpkg, yum, dnf, apt, zypper"
  platforms: "Linux"
  supported-os: "Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, CentOS 7, SLES 12, SLES 15, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, Debian 11, Debian 12"
  operation-type: "read-and-mutate"
---

# Recover a corrupt Linux package database blocking patching

## When this applies
A yum/dnf/apt/zypper patch operation fails with a package-database or
interrupted-transaction signature (see the description for the full list).
The instance is Online in SSM. If the failure is a *repository/connectivity*
issue (mirror unreachable, cert/GPG, proxy) or a pure *dependency conflict*,
this is the wrong skill — those are separate domains.

## The key insight: identify the packager AND the backend first
The correct recovery is not one command — it depends on what is actually broken:
- **RPM + SQLite backend** (AL2023, RHEL 9, OL 9, SLES 15): `rpmdb.sqlite`. A stale
  index rebuilds fine, but a *totally corrupt* sqlite ("file is not a database")
  has **no headers to rebuild from** — `rpm --rebuilddb` leaves an EMPTY db and you
  must reconstruct the inventory from the repositories (`rpm --initdb` + `dnf reinstall '*'`).
- **RPM + BerkeleyDB backend** (AL2, RHEL 7/8, CentOS 7, OL 7, SLES 12): `Packages` + `__db.*`.
  Drop the cached environment (`__db.*`) then `rpm --rebuilddb`.
- **dpkg journal corruption** (Ubuntu/Debian): unparseable files in `/var/lib/dpkg/updates/`
  → remove them, then `dpkg --configure -a`.
- **dpkg status corruption**: `/var/lib/dpkg/status` parse error → restore from
  `/var/lib/dpkg/status-old`, then `dpkg --configure -a`. (Different fix from journal corruption.)
- **Incomplete transaction**: complete or roll back (`dnf distro-sync` / `dpkg --configure -a`).
- **File conflict**: remove duplicates / force-overwrite / reinstall the owning package.

## Diagnosis first (always, and back up before mutating)
- [ ] Step 1: Detect packager, RPM backend, and corruption extent before changing anything:
  ```bash
  # packager + rpm backend
  command -v dnf yum rpm dpkg apt-get zypper 2>/dev/null
  ls -la /var/lib/rpm/rpmdb.sqlite /var/lib/rpm/Packages /var/lib/rpm/__db.* 2>/dev/null
  rpm --verifydb 2>&1 | head; RC=$?; echo "VERIFYDB_EXIT:$RC"   # capture RC before any pipe
  # incomplete transactions / broken state
  command -v dnf >/dev/null && dnf history list --last 3 2>&1
  command -v dpkg >/dev/null && dpkg --audit 2>&1 | head
  ls -la /var/lib/dpkg/updates/ /var/lib/dpkg/status /var/lib/dpkg/status-old 2>/dev/null
  df -h /var
  ```
- [ ] Step 2: **Back up first** — never mutate the DB without a verified backup:
  RPM: `cp -a /var/lib/rpm /var/lib/rpm.backup.$(date +%s)`; dpkg: `cp /var/lib/dpkg/status /var/lib/dpkg/status.bak`.
- [ ] Step 3: Route to the sub-fault (load the matching reference for exact commands):
  - RPM DB corrupt → read [rpm db recovery](reference/rpm-db-recovery.md) — pick the sqlite vs BDB path, and the sqlite total-loss path.
  - dpkg journal/status corrupt → read [dpkg recovery](reference/dpkg-recovery.md).
  - Incomplete transaction → read [incomplete transactions](reference/incomplete-transactions.md).
  - File conflict → read [file conflicts](reference/file-conflicts.md).

## Ordered recovery (backend/packager-correct — do not shortcut)
- [ ] Step 4: **Clear stale locks** (safe, do first): remove `/var/lib/rpm/.rpm.lock`, `.dbenv.lock`
  (RPM) or ensure no dpkg/apt process holds the lock (Ubuntu). Confirm no rpm/dnf/apt process is running.
- [ ] Step 5: **Apply the backend/packager-correct rebuild** from the routed reference — NOT a blind
  `rpm --rebuilddb`. On sqlite, verify the rebuild produced a non-empty DB; if it is empty, take the
  repo-reconstruction path.
- [ ] Step 6: **Complete or roll back any incomplete transaction** and clear duplicate packages so the
  package manager returns to a consistent state.
- [ ] Step 7: **Verify** the package manager is healthy before handing back to the patch run.

## Validation (check your own work before reporting success)
Do not report the database recovered until you confirm each of these:
- [ ] A backup was taken before any mutation (`ls -d /var/lib/rpm.backup.* ` or `/var/lib/dpkg/status.bak`).
- [ ] The backend/packager-correct path was used (sqlite total-loss → `initdb`+repo reconstruct, NOT `--rebuilddb`).
- [ ] `rpm -qa | wc -l` (or `dpkg -l`) returns a **sane, non-zero** package count (RPM hosts typically 300–1500).
- [ ] `dnf check` / `apt-get check` / `zypper verify` completes without a database error.
- [ ] The originally failing patch scan re-run no longer errors on the database.
If any check fails, restore from the Step 2 backup and re-diagnose rather than reporting success.

## Gotchas
- **Never `rm -rf /var/lib/rpm` or delete `/var/lib/dpkg/status` without a verified backup** — you lose the package inventory.
- **`rpm --rebuilddb` is the WRONG tool for a totally corrupt AL2023 sqlite DB** — it rebuilds from on-disk headers that are gone and silently leaves an empty database. Confirm the count after; if 0, use `rpm --initdb` + `dnf reinstall '*'` to rebuild from repos.
- **BDB-only recovery (`rm __db.*`) will NOT fix a corrupt `rpmdb.sqlite`**, and vice versa — detect the backend first.
- **dpkg journal corruption ≠ dpkg status corruption.** Clearing `/var/lib/dpkg/updates/*` fixes the journal; a `status` parse error needs a restore from `/var/lib/dpkg/status-old`.
- **The AMS `AWSManagedServices-PatchInstance` built-in recovery does not recognize AL2023** ("Failed to recognize operating system") — use this skill's sqlite path on AL2023, not the runbook's built-in.
- **Capture `rpm --verifydb`'s exit code before piping to `head`** — otherwise `$?` reports `head`'s status (0) and masks real corruption.
- **A disk-full `/var` is a common root cause** — if `df -h /var` shows 100%, free space first or the rebuild re-corrupts.
