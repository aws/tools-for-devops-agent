# SOP-010: Resolve Missing Python Blocking SSM Agent and Patching

| Field | Value |
|-------|-------|
| ID | SOP-010 |
| Category | python_missing |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, Ubuntu 20.04, Ubuntu 22.04 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- SSM agent fails to execute patch scripts due to missing Python
- "python: command not found" or "python3: command not found" in patch logs
- SSM Run Command returns "PluginNotFoundOnOS" errors
- Patch baseline scripts fail with interpreter errors
- "/usr/bin/env: 'python3': No such file or directory"
- "bad interpreter: /usr/bin/python: no such file or directory" for pre/post install scriptlets
- SSM agent reports "Failed to start plugin" in amazon-ssm-agent.log

## Root Cause

Python missing or broken when:

- System Python removed by accidental `yum remove python3*` during cleanup
- Python alternatives misconfigured after distro upgrade (alternatives --config python3 pointing to deleted version)
- Symlinks broken (/usr/bin/python3 -> target that was removed during package update)
- Python dependencies (libpython3.so, etc.) removed by overzealous dependency resolution
- AL2023/RHEL9 minimal AMIs ship without the `python3` unversioned symlink — only `python3.9` or `python3.11` exists
- Container-optimized AMIs stripped Python to reduce image size
- `pip install` corrupted the system Python by overwriting dist-packages

## Related Failure Patterns

- SOP-005 (Zstd Package) — similar pattern of missing core system utility
- SOP-015 (urllib3 Conflict) — pip-installed urllib3 can break system Python's requests library

## Prerequisites

- Instance is reachable via SSM (basic binary agent still works without Python for session manager)
- Package manager itself is functional (rpm/yum/dnf do not depend on Python for basic operations on RPM-based systems)

## Diagnosis

Check all Python-related binaries and symlinks:

```bash
ls -la /usr/bin/python* 2>/dev/null; alternatives --display python3 2>/dev/null; which python3.9 python3.11 python3.12 2>/dev/null
```

Check if Python libraries are intact:

```bash
ldconfig -p | grep libpython; rpm -V python3 2>/dev/null | head -10
```

## Remediation Steps

### Step 1: Check Python availability

```bash
which python3 2>/dev/null; which python 2>/dev/null; ls -la /usr/bin/python* 2>/dev/null; echo "Python check done"
```

Expected output: Python paths or empty, followed by "Python check done"
On failure: continue

### Step 2: Install Python3 via package manager

```bash
if command -v dnf &>/dev/null; then dnf install -y python3 2>/dev/null; elif command -v yum &>/dev/null; then yum install -y python3 2>/dev/null; elif command -v apt-get &>/dev/null; then apt-get install -y python3 2>/dev/null; fi; echo "Python3 install attempted"
```

Expected output: "Python3 install attempted"
On failure: go to Step 3

### Step 3: Install from RPM directly if package manager fails

```bash
ARCH=$(uname -m); TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); [ -z "$REGION" ] && { echo "ERROR: region unknown from IMDS - aborting"; exit 1; }; curl -sf --connect-timeout 2 --max-time 10 "https://amazonlinux.${REGION}.amazonaws.com" >/dev/null && dnf download python3 --destdir /tmp 2>/dev/null && rpm -ivh /tmp/python3*.rpm 2>/dev/null; echo "Direct RPM install attempted"
```

Expected output: "Direct RPM install attempted"
On failure: abort

### Step 4: Create python3 symlink if binary exists but symlink missing

```bash
if [ ! -L /usr/bin/python3 ] && [ ! -f /usr/bin/python3 ]; then PYTHON_BIN=$(find /usr/bin -name "python3.*" -type f 2>/dev/null | sort -V | tail -1); if [ -n "$PYTHON_BIN" ]; then ln -sf "$PYTHON_BIN" /usr/bin/python3; echo "Symlink created: $PYTHON_BIN"; else echo "No python3 binary found"; fi; else echo "python3 already exists"; fi
```

Expected output: Symlink status
On failure: continue

### Step 5: Verify Python is functional

```bash
python3 --version && python3 -c "import sys; print(sys.executable)" && echo "Python3 OK"
```

Expected output: Version string, path, "Python3 OK"
On failure: abort

## Validation

```bash
python3 --version && python3 -c "import json, os, sys; print('Modules OK')" && echo "PYTHON VALIDATED"
```

Expected: "PYTHON VALIDATED"

## Rollback

```bash
echo "No rollback required - Python installation is additive"
```

## Escalation

If Python cannot be installed or remains broken:
- Check if system RPM database is corrupted (SOP-004)
- Verify the package repository is accessible (SOP-003)
- For AL2023, the package is `python3.11` or `python3.9` — the unversioned `python3` is provided by `python3` meta-package
- If libpython is missing, reinstall: `dnf reinstall python3-libs`
- As a last resort, copy Python binaries from a known-good instance with the same OS version
