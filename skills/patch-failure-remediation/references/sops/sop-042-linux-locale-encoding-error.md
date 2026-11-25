# SOP-042: Resolve Locale/Encoding Errors During Package Installation

| Field | Value |
|-------|-------|
| ID | SOP-042 |
| Category | locale_encoding_error |
| Severity | Low |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 60 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "perl: warning: Setting locale failed" during package install scriptlets
- "locale: Cannot set LC_ALL to default locale" in apt/dpkg output
- "bash: warning: setlocale: LC_ALL: cannot change locale"
- Package post-install scripts fail due to missing locale data
- "dpkg-reconfigure: unable to re-open stdin" during locale operations
- Man-db triggers fail with locale warnings causing dpkg to report errors
- "UnicodeDecodeError" in Python-based package scriptlets

## Root Cause

Locale/encoding errors during patching when:

- Locale packages were removed or never installed (glibc-langpack-*, locales)
- /etc/locale.gen missing entries for configured locale
- LANG/LC_ALL set to a locale that has not been generated
- Minimal container-based AMIs strip locale data to save space
- locale-gen was never run after locale package installation
- Python 3 scriptlets fail when LANG=C and filenames contain non-ASCII characters

## Related Failure Patterns

- SOP-029 (Package Scriptlet Failure) — locale errors are a common scriptlet failure cause

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)

## Diagnosis

Check locale configuration:

```bash
locale 2>&1; echo "---"; cat /etc/locale.conf 2>/dev/null || cat /etc/default/locale 2>/dev/null; echo "---"; locale -a 2>&1 | wc -l | awk '{print "Available locales: "$1}'
```

## Remediation Steps

### Step 1: Identify locale issue

```bash
locale 2>&1 | grep -i "cannot\|warning\|error" && echo "LOCALE ISSUES FOUND" || echo "Locale OK"
```

Expected output: "Locale OK" or "LOCALE ISSUES FOUND"
On failure: continue

### Step 2: Install locale packages

```bash
if command -v dnf &>/dev/null; then dnf install -y glibc-langpack-en glibc-locale-source 2>&1 | tail -3; elif command -v yum &>/dev/null; then yum install -y glibc-langpack-en 2>&1 | tail -3; elif command -v apt-get &>/dev/null; then apt-get install -y locales 2>&1 | tail -3; elif command -v zypper &>/dev/null; then zypper install -y glibc-locale 2>&1 | tail -3; fi; echo "Locale packages installed"
```

Expected output: "Locale packages installed"
On failure: continue

### Step 3: Generate locale

```bash
if command -v locale-gen &>/dev/null; then sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen 2>/dev/null; locale-gen en_US.UTF-8 2>&1; elif command -v localedef &>/dev/null; then localedef -i en_US -f UTF-8 en_US.UTF-8 2>&1; fi; echo "Locale generated"
```

Expected output: "Locale generated"
On failure: continue

### Step 4: Set default locale

```bash
if [ -f /etc/locale.conf ]; then echo "LANG=en_US.UTF-8" > /etc/locale.conf; elif [ -f /etc/default/locale ]; then echo "LANG=en_US.UTF-8" > /etc/default/locale; fi; export LANG=en_US.UTF-8; export LC_ALL=en_US.UTF-8; echo "Default locale set"
```

Expected output: "Default locale set"
On failure: continue

### Step 5: Verify locale is functional

```bash
locale 2>&1 | grep -ic "cannot\|warning\|error" | awk '{if ($1==0) print "LOCALE OK"; else print "STILL BROKEN"}'
```

Expected output: "LOCALE OK"
On failure: abort

## Validation

```bash
locale 2>&1 | grep -q "cannot\|warning" && echo "LOCALE ISSUES REMAIN" || echo "LOCALE CONFIGURED OK"
```

Expected: "LOCALE CONFIGURED OK"

## Rollback

```bash
echo "Locale installation is additive - no rollback needed"
```

## Escalation

If locale issues persist:
- For minimal AMIs: install full glibc-all-langpacks package
- For Debian/Ubuntu: `dpkg-reconfigure locales`
- Set LANG=C.UTF-8 as a fallback that works without generating locales
- If man-db triggers are the problem: `rm -f /var/lib/dpkg/info/man-db.postinst && dpkg --configure -a`
