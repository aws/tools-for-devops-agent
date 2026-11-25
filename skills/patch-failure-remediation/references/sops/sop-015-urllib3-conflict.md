# SOP-015: Resolve python-urllib3 Package Conflict During Patching

| Field | Value |
|-------|-------|
| ID | SOP-015 |
| Category | urllib3_conflict |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | Amazon Linux 2, RHEL 7, CentOS 7 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "Error unpacking rpm package python-urllib3 was supposed to be removed but is not!"
- YUM transaction errors involving python-urllib3 or python2-urllib3
- Package removal conflicts during security patch application
- "Transaction check error" referencing urllib3 dependencies
- "file /usr/lib/python2.7/site-packages/urllib3/__init__.py from install of python2-urllib3 conflicts with file from package python-urllib3"
- pip-installed urllib3 version conflicting with RPM-managed version
- "ImportError: cannot import name 'DEFAULT_CIPHERS' from 'urllib3.util.ssl_'" after partial update

## Root Cause

The python-urllib3 conflict occurs when:

- System has python-urllib3 (Python 2.7 era) installed alongside python2-urllib3 or python3-urllib3 — these packages own overlapping files
- Package replacement during patching fails because the old package cannot be cleanly removed (RPM scriptlet errors)
- RPM scriptlets for urllib3 fail due to stale .pyc files or directory ownership conflicts between the old and new package
- Third-party tools (or `pip install`) pinned urllib3 version that conflicts with system update — pip writes to the same site-packages directory
- AWS CLI v1 installed via pip bundled its own urllib3 that conflicts with system RPM
- The `requests` library depends on a specific urllib3 version range, creating a three-way conflict

This is a well-known issue on AL2 and RHEL 7/CentOS 7 where the Python 2 to Python 3 transition left conflicting package naming.

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — this is a specific, common instance of dependency conflicts
- SOP-010 (Python Missing) — aggressive urllib3 removal can accidentally break Python

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is Linux (Windows instances skip this remediation)

## Diagnosis

Map the complete urllib3 state across both pip and RPM:

```bash
rpm -qa | grep -i urllib3; echo "---"; pip list 2>/dev/null | grep -i urllib3; pip3 list 2>/dev/null | grep -i urllib3; echo "---"; rpm -ql python-urllib3 2>/dev/null | head -5; rpm -ql python2-urllib3 2>/dev/null | head -5; rpm -ql python3-urllib3 2>/dev/null | head -5
```

Check for pip-installed packages shadowing RPM packages:

```bash
pip show urllib3 2>/dev/null | grep Location; pip3 show urllib3 2>/dev/null | grep Location
```

## Remediation Steps

### Step 1: Identify urllib3 package state

```bash
rpm -qa | grep -i urllib3; pip list 2>/dev/null | grep -i urllib3; pip3 list 2>/dev/null | grep -i urllib3; echo "urllib3 check done"
```

Expected output: Package versions listed
On failure: continue

### Step 2: Remove conflicting python-urllib3 package

```bash
rpm -e --nodeps python-urllib3 2>/dev/null; rpm -e --nodeps python2-urllib3 2>/dev/null; echo "Old urllib3 packages removed"
```

Expected output: "Old urllib3 packages removed"
On failure: continue

### Step 3: Clean stale urllib3 files from site-packages

```bash
find /usr/lib/python2*/site-packages/urllib3* -type f -delete 2>/dev/null; find /usr/lib/python2*/site-packages/urllib3* -type d -empty -delete 2>/dev/null; echo "Stale files cleaned"
```

Expected output: "Stale files cleaned"
On failure: continue

### Step 4: Remove pip-installed urllib3 that conflicts with system package

```bash
pip uninstall -y urllib3 2>/dev/null; pip3 uninstall -y urllib3 2>/dev/null; echo "pip urllib3 removed"
```

Expected output: "pip urllib3 removed"
On failure: continue

### Step 5: Reinstall correct urllib3 version via package manager

```bash
yum install -y python3-urllib3 2>/dev/null || dnf install -y python3-urllib3 2>/dev/null; echo "urllib3 reinstall done"
```

Expected output: "urllib3 reinstall done"
On failure: continue

### Step 6: Verify package manager consistency

```bash
yum check 2>/dev/null || dnf check 2>/dev/null; echo "Package check exit: $?"
```

Expected output: "Package check exit: 0"
On failure: abort

## Validation

```bash
rpm -qa | grep urllib3; yum check-update --security 2>/dev/null | tail -5; echo "URLLIB3 REMEDIATION OK"
```

Expected: Clean urllib3 package state and "URLLIB3 REMEDIATION OK"

## Rollback

```bash
yum install -y python-urllib3 2>/dev/null || echo "Rollback: reinstall old urllib3 if needed"
```

## Prevention

To prevent this from recurring:
- Never use `pip install` on system Python for packages that are also managed by RPM
- Use virtual environments for application-specific Python dependencies
- If AWS CLI v1 is needed, install via the bundled installer rather than pip
- On AL2, prefer `amazon-linux-extras install aws-cli` over pip

## Escalation

If urllib3 conflict persists after cleanup:
- Check for other pip-installed packages that depend on urllib3: `pip show -f urllib3 2>/dev/null`
- The AWS SDK (botocore/boto3) bundles its own vendored urllib3 — this is normal and does not conflict
- For AL2, consider upgrading to AL2023 where this Python 2/3 package naming conflict does not exist
