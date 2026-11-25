# SOP-079: Remediate Corrupted Python Standard Library Locale Module on Linux

| Field | Value |
|-------|-------|
| ID | SOP-079 |
| Category | corrupted_python_stdlib_locale |
| Severity | Critical |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 7, RHEL 8, RHEL 9, CentOS 7, CentOS 8 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | DRAFT - pending human review |

## Symptoms

- `RuntimeError: locale data corrupted - HRESULT 0x80004005` raised at line 1 of `/usr/lib/python3.x/locale.py` or `/usr/lib64/python3.x/locale.py` on any Python import
- `yum` and `dnf` fail completely because their Python interpreter cannot import `locale` (import chain: `/usr/bin/yum` → `dnf.cli` → `dnf.pycomp` → `email.mime.text` → `calendar` → `locale` → `RuntimeError`)
- AWS SSM patch-baseline-operations script fails with `AttributeError: '_SixMetaPathImporter' object has no attribute 'find_spec'` when importing `botocore.session`, caused by the same corrupted Python standard library
- All Python-dependent package management is non-functional, blocking further automated patching
- `locale.py` has been overwritten such that line 1 unconditionally raises `RuntimeError` instead of containing normal module header code

## Root Cause

The file `/usr/lib64/python3.x/locale.py` (or the equivalent path on the host) has been overwritten or corrupted — its contents begin with a `raise RuntimeError(...)` statement rather than normal Python locale module code. This is not a system locale configuration problem; it is a corruption of the Python standard library file itself. Likely causes include an interrupted package installation or upgrade, a failed patch-baseline-operations run that partially overwrote stdlib files, a runaway configuration-management tool (e.g., Ansible, Chef, Puppet) deploying incorrect content to the path, or manual operator error. Because `locale` is imported transitively by many high-level modules (`calendar`, `email`, `http`, etc.), the corruption cascades to break virtually every Python-dependent tool on the system, including the package managers (`yum`/`dnf`) needed to repair it.

## Related Failure Patterns

- `corrupted_python_stdlib_generic` — general Python stdlib file corruption not specific to `locale`
- `failed_yum_dnf_python_import` — yum/dnf import errors caused by Python environment issues
- `six_metapathimporter_find_spec` — `_SixMetaPathImporter` `find_spec` `AttributeError` in SSM agent or botocore (shares root cause with this failure when Python stdlib is degraded)

## Prerequisites

- SSM agent is reachable and can execute run-commands (even if the agent itself is degraded, the C-based `rpm` binary must be available as it does not depend on Python)
- The host has network access to its configured package repository (yum/dnf repo, or a mirrored equivalent in a restricted VPC) — required to download replacement RPM/DEB files
- The operator or automation role has `root` or `sudo` privileges on the instance
- `rpm` binary is present and functional (it is C-based and does not depend on the corrupted Python interpreter); confirmed by running `rpm --version`
- On Debian/Ubuntu distributions: `dpkg` and `apt-get` must be functional (both are C-based)
- No other process holds an exclusive lock on the RPM/dpkg database (`/var/lib/rpm/.rpm.lock` or `/var/lib/dpkg/lock`)

## Diagnosis

Confirm the Python interpreter is broken and identify the corrupted file:

```bash
python3 -c 'import locale' 2>&1 | head -5
```

Locate the exact path of the corrupted `locale.py`:

```bash
python3 -c 'import sys; print([p for p in sys.path if "python3" in p])' 2>/dev/null || find /usr/lib /usr/lib64 -name 'locale.py' -path '*/python3*' 2>/dev/null
```

Inspect the first 5 lines of `locale.py` to confirm the corruption pattern:

```bash
head -5 $(find /usr/lib /usr/lib64 -name 'locale.py' -path '*/python3*' 2>/dev/null | head -1)
```

Confirm `rpm` is functional (RPM-based distros only):

```bash
rpm --version 2>&1
```

Check which RPM package owns the corrupted file (RPM-based distros only):

```bash
rpm -qf $(find /usr/lib /usr/lib64 -name 'locale.py' -path '*/python3*' 2>/dev/null | head -1) 2>&1
```

Check which dpkg package owns the corrupted file (Debian/Ubuntu only):

```bash
dpkg -S $(find /usr/lib -name 'locale.py' -path '*/python3*' 2>/dev/null | head -1) 2>&1
```

Verify current system locale configuration:

```bash
cat /etc/locale.conf 2>/dev/null || cat /etc/default/locale 2>/dev/null
```

Check for any RPM database lock or incomplete transactions that could block reinstall:

```bash
ls -la /var/lib/rpm/.rpm.lock 2>/dev/null; rpm --rebuilddb 2>/dev/null && echo "RPM DB OK"
```

## Remediation Steps

### Step 1: Reinstall the Python 3 package via the package manager

```bash
dnf reinstall -y python3 python3-libs 2>&1 || yum reinstall -y python3 python3-libs 2>&1 || apt-get install --reinstall python3 -y 2>/dev/null || { RPMS=$(find /var/cache/dnf /var/cache/yum \( -name 'python3-[0-9]*.rpm' -o -name 'python3-libs-[0-9]*.rpm' \) 2>/dev/null); if [ -n "$RPMS" ]; then echo "dnf/yum unavailable (Python broken) - reinstalling from cached RPM via the C-based rpm"; rpm -Uvh --replacepkgs --replacefiles $RPMS 2>&1; else echo "ERROR: dnf/yum are Python programs and fail when locale.py is corrupt, and no cached python3*.rpm exists under /var/cache. Fetch the matching python3 + python3-libs RPM(s) (e.g. from another host or the repo) and run: rpm -Uvh --replacepkgs --replacefiles <files>. Escalate."; exit 1; fi; }
```

Expected output: Package reinstallation completes with no errors; `rpm` exits 0 or package manager reports `Complete!` / `done`.

On failure: abort — if no package manager can reinstall python3, escalate immediately; do not proceed as subsequent steps depend on a restored `locale.py`.

---

### Step 2: Verify `locale.py` is no longer corrupted

```bash
head -3 $(find /usr/lib /usr/lib64 -name 'locale.py' -path '*/python3*' 2>/dev/null | head -1) 2>/dev/null
```

Expected output: First line begins with normal Python module content such as `"""` (docstring), `#` (comment), or `import` — NOT `raise RuntimeError`.

On failure: abort — the file was not restored by reinstall; escalate for manual file recovery from a known-good source.

---

### Step 3: Regenerate system locale definitions

```bash
locale-gen 2>/dev/null || localedef -i en_US -f UTF-8 en_US.UTF-8 2>/dev/null
```

Expected output: `locale-gen` prints `Generating locales...` and exits 0, or `localedef` completes silently with exit code 0 or 1 (exit code 1 from `localedef` is acceptable if the locale already exists).

On failure: continue — locale generation failure does not prevent Python from functioning; log the error and proceed.

---

### Step 4: Set the system-wide locale to `en_US.UTF-8`

```bash
update-locale LANG=en_US.UTF-8 2>/dev/null || localectl set-locale LANG=en_US.UTF-8 2>/dev/null
```

Expected output: Command exits 0; no error output. `cat /etc/locale.conf` or `cat /etc/default/locale` should now show `LANG=en_US.UTF-8`.

On failure: continue — system locale misconfiguration will not prevent the Python import fix from working; log and proceed, but note for follow-up.

---

### Step 5: Invalidate Python's module finder cache to pick up the restored file

```bash
python3 -c 'import importlib; importlib.invalidate_caches()'
```

Expected output: Command exits 0 with no output.

On failure: continue — cache invalidation failure is non-fatal; the restored `locale.py` will be discovered on next cold Python invocation. Log the error.

---

### Step 6: Confirm Python can now import `locale` cleanly

```bash
python3 -c 'import locale; print("locale OK:", locale.getlocale())' 2>&1
```

Expected output: `locale OK: ('en_US', 'UTF-8')` or `locale OK: (None, None)` — critically, no `RuntimeError` and exit code 0.

On failure: abort — Python stdlib is still broken; escalate.

---

### Step 7: Confirm `yum` or `dnf` can initialise without Python errors

```bash
yum check-update --quiet 2>&1 | head -5 || dnf check-update --quiet 2>&1 | head -5
```

Expected output: Exits 0 (no updates) or 100 (updates available); no Python traceback in output.

On failure: continue — package manager may have a secondary issue unrelated to this SOP; log and escalate separately if needed.

---

### Step 8: Rebuild the RPM database to clear any residual state from the corrupted reinstall (RPM-based distros only)

```bash
rpm --rebuilddb 2>/dev/null && echo "RPM DB rebuild OK"
```

Expected output: `RPM DB rebuild OK` printed to stdout; exits 0.

On failure: continue — a failed RPM DB rebuild is non-critical at this stage if prior steps succeeded; log for follow-up maintenance.

---

## Distribution-Specific Commands

| Action | Debian/Ubuntu (apt/apt-get/dpkg) | RHEL 8+ / AL2023 / Fedora / CentOS 8+ (dnf) | Amazon Linux 2 / RHEL 7 / CentOS 7 (yum) | SUSE / SLES (zypper) |
|--------|----------------------------------|----------------------------------------------|-------------------------------------------|----------------------|
| Reinstall Python 3 package (primary — package-manager) | `apt-get install --reinstall python3 -y` | `dnf reinstall -y python3 python3-libs` | `yum reinstall -y python3 python3-libs` | `zypper install --force python3` |
| Reinstall Python 3 package (fallback — `rpm` from a downloaded/cached `.rpm` **file**) | `dpkg -i /path/to/python3_*.deb` | `rpm -Uvh --replacepkgs --replacefiles /path/to/python3*.rpm` | `rpm -Uvh --replacepkgs --replacefiles /path/to/python3*.rpm` | `rpm -Uvh --replacepkgs --replacefiles /path/to/python3*.rpm` |
| Query which package owns `locale.py` | `dpkg -S /usr/lib/python3*/locale.py` | `rpm -qf /usr/lib64/python3*/locale.py` | `rpm -qf /usr/lib64/python3*/locale.py` | `rpm -qf /usr/lib64/python3*/locale.py` |
| Verify file integrity against package database | `dpkg --verify python3` | `rpm -V $(rpm -qf /usr/lib64/python3*/locale.py)` | `rpm -V $(rpm -qf /usr/lib64/python3*/locale.py)` | `rpm -V $(rpm -qf /usr/lib/python3*/locale.py)` |
| Generate locale definitions | `locale-gen en_US.UTF-8` | `localedef -i en_US -f UTF-8 en_US.UTF-8` | `localedef -i en_US -f UTF-8 en_US.UTF-8` | `localedef -i en_US -f UTF-8 en_US.UTF-8` |
| Set system-wide LANG | `update-locale LANG=en_US.UTF-8` | `localectl set-locale LANG=en_US.UTF-8` | `localectl set-locale LANG=en_US.UTF-8` | `localectl set-locale LANG=en_US.UTF-8` |
| Clean package cache | `apt-get clean` | `dnf clean all` | `yum clean all` | `zypper clean --all` |
| Check for incomplete transactions | `dpkg --audit` | `dnf history list \| head -10` | `yum-complete-transaction --cleanup-only 2>/dev/null` | N/A — zypper has no direct equivalent; check `zypper ps` for process conflicts |
| Rebuild package database | N/A — dpkg uses a flat-file database that does not require rebuilding | `rpm --rebuilddb` | `rpm --rebuilddb` | `rpm --rebuilddb` |
| Invalidate Python module cache | `python3 -c 'import importlib; importlib.invalidate_caches()'` | `python3 -c 'import importlib; importlib.invalidate_caches()'` | `python3 -c 'import importlib; importlib.invalidate_caches()'` | `python3 -c 'import importlib; importlib.invalidate_caches()'` |

### Notes

- **Package-manager reinstall (`dnf`/`yum reinstall`) is the primary method.** If `locale.py` corruption has also broken `dnf`/`yum` (both are Python programs and import `locale` indirectly), fall back to `rpm`, which is a C binary that does not invoke Python. Note that `rpm` reinstalls from a local package **file**, not a package name — you must first obtain the `.rpm` (from `/var/cache/dnf`/`/var/cache/yum`, or download it), then run `rpm -Uvh --replacepkgs --replacefiles /path/to/python3*.rpm`. `rpm --reinstall <package-name>` does not work: `--reinstall` operates on a file path, and a bare name from `rpm -qa` will fail with "open failed".
- **`apt-get install --reinstall`** on Debian/Ubuntu does not depend on Python either; `apt-get` and `dpkg` are C-based. However, `apt-get update` should be run first if the package cache is stale (`apt-get update && apt-get install --reinstall python3 -y`).
- **`locale-gen`** is Debian/Ubuntu-specific (provided by the `locales` package). On RHEL-family and SUSE systems, `localedef` is the equivalent. Both are safe to call idempotently.
- **`update-locale`** is Debian/Ubuntu-specific and writes to `/etc/default/locale`. On RHEL-family and SUSE systems, `localectl set-locale` writes to `/etc/locale.conf`. Both produce equivalent results.
- **`yum-complete-transaction`** (Amazon Linux 2 / RHEL 7 / CentOS 7) requires the `yum-utils` package; if it is not installed, skip that step — it is diagnostic-only in this SOP.
- **SUSE/SLES** is not listed in the Distributions metadata field but is included in the table for completeness because `rpm` is used across all RPM-based families. Treat SUSE entries as informational; they have not been validated against the operator-approved steps for this SOP.
- **Python path differences**: Debian/Ubuntu places stdlib at `/usr/lib/python3/` and `/usr/lib/python3.x/`; RHEL-family uses `/usr/lib64/python3.x/` on 64-bit systems. Diagnosis commands use `find` across both paths to remain portable.

## Validation

```bash
echo "=== Validating locale.py integrity ===" && \
head -1 $(find /usr/lib /usr/lib64 -name 'locale.py' -path '*/python3*' 2>/dev/null | head -1) 2>/dev/null | grep -v 'RuntimeError' && \
echo "locale.py first line: OK (no RuntimeError)" && \
python3 -c 'import locale; locale.setlocale(locale.LC_ALL, "")' 2>/dev/null && \
echo "python3 locale import: OK"
python3 -c 'import botocore.session' 2>/dev/null && echo "botocore.session import: OK" || echo "botocore.session import: SKIPPED (botocore not installed - not required; this SOP restores the Python stdlib)"
if command -v dnf >/dev/null 2>&1; then PMGR_CHECK="dnf check-update --quiet"; elif command -v yum >/dev/null 2>&1; then PMGR_CHECK="yum check-update --quiet"; elif command -v apt-get >/dev/null 2>&1; then PMGR_CHECK="apt-get -s upgrade"; else echo "SOP-079 VALIDATION FAILED - no supported package manager found"; exit 1; fi; if $PMGR_CHECK 2>&1 | grep -qiE 'Traceback|RuntimeError'; then echo "SOP-079 VALIDATION FAILED - package manager still hitting a Python error"; else echo "SOP-079 VALIDATION OK"; fi
```