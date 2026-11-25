# SOP-046: Resolve Zypper Patch Category/Severity Filtering Issues on SUSE

| Field | Value |
|-------|-------|
| ID | SOP-046 |
| Category | zypper_patch_filtering |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | SLES 12, SLES 15 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `zypper patch` reports "No applicable patches found" despite known vulnerabilities
- Security patches not detected when using `--category security`
- "Patch is not in the specified category" skipping critical updates
- SUSE patches show as "not needed" when they clearly apply
- `zypper list-patches` shows patches but `zypper patch` skips them
- "Patch X is locked" or "interactive patch skipped in non-interactive mode"
- Patch baseline scan reports compliant but CVEs are not actually remediated

## Root Cause

Zypper patch filtering issues when:

- Patch metadata not refreshed — stale repo data shows incorrect patch applicability
- Patches marked as "interactive" require user confirmation that SSM cannot provide
- Package locks prevent patches from being applied even though they appear available
- Patch conflicts with another patch or installed pattern
- SUSE module providing the patch is not activated (patch exists but packages unavailable)
- `zypper patch` only applies patches, not individual package updates — some fixes require `zypper update`
- Patch was superseded by a newer patch but metadata still references the old one

## Related Failure Patterns

- SOP-013 (SUSE Repo Refresh) — stale metadata causes incorrect patch detection
- SOP-041 (Zypper Lock/Conflict) — locks prevent patch application
- SOP-031 (Expired Certificates) — expired creds prevent metadata refresh

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is SLES 12 or SLES 15
- SUSEConnect registration is active and repos are accessible

## Diagnosis

Check patch state and applicability:

```bash
zypper list-patches --category security 2>&1 | head -20; echo "---"; zypper patches --status needed 2>&1 | head -20; echo "---"; zypper locks 2>/dev/null; echo "---"; SUSEConnect --status-text 2>&1 | grep -E "Activated|Not"
```

## Remediation Steps

### Step 1: Refresh repository metadata

```bash
zypper --non-interactive refresh -f 2>&1 | tail -5; echo "Refresh exit: $?"
```

Expected output: "Refresh exit: 0"
On failure: abort (see SOP-013)

### Step 2: List applicable patches by category

```bash
echo "=== Security ==="; zypper list-patches --category security 2>&1 | grep -c "needed" | awk '{print "Security patches needed: "$1}'; echo "=== Recommended ==="; zypper list-patches --category recommended 2>&1 | grep -c "needed" | awk '{print "Recommended patches needed: "$1}'; echo "=== All ==="; zypper list-patches 2>&1 | grep -c "needed" | awk '{print "Total patches needed: "$1}'
```

Expected output: Patch counts by category
On failure: continue

### Step 3: Apply patches including interactive ones

```bash
zypper --non-interactive patch --with-interactive --auto-agree-with-licenses --category security 2>&1 | tail -10; echo "Patch exit: $?"
```

Expected output: "Patch exit: 0"
On failure: continue

### Step 4: Apply remaining patches that need individual package updates

```bash
STILL_NEEDED=$(zypper list-patches --category security 2>&1 | grep "needed" | awk '{print $3}' | head -10); if [ -n "$STILL_NEEDED" ]; then for patch in $STILL_NEEDED; do zypper --non-interactive install --type patch "$patch" --auto-agree-with-licenses 2>&1; done; echo "Individual patches applied"; else echo "No remaining patches"; fi
```

Expected output: "No remaining patches" or "Individual patches applied"
On failure: continue

### Step 5: Fall back to package-level update for stubborn patches

```bash
NEEDED=$(zypper list-patches --category security 2>&1 | grep "needed"); if [ -n "$NEEDED" ]; then zypper --non-interactive update --auto-agree-with-licenses 2>&1 | tail -10; echo "Package update exit: $?"; else echo "All patches applied"; fi
```

Expected output: "All patches applied" or update results
On failure: continue

### Step 6: Verify patch state

```bash
SEC_NEEDED=$(zypper list-patches --category security 2>&1 | grep -c "needed"); echo "Security patches still needed: $SEC_NEEDED"; [ "$SEC_NEEDED" -eq 0 ] && echo "ALL SECURITY PATCHES APPLIED" || echo "SOME PATCHES REMAINING"
```

Expected output: "ALL SECURITY PATCHES APPLIED"
On failure: abort

## Validation

```bash
zypper list-patches --category security 2>&1 | grep -c "needed" | awk '{if ($1==0) print "SUSE PATCHING OK"; else print "PATCHES REMAINING: "$1}'
```

Expected: "SUSE PATCHING OK"

## Rollback

```bash
echo "Patches can be reverted with:"
echo "  zypper rollback <snapshot-number>"
echo "Check available snapshots:"
snapper list 2>/dev/null | tail -10
```

## Escalation

If patches cannot be applied:
- Check if required SUSE modules are activated: `SUSEConnect --list-extensions`
- Activate missing modules: `SUSEConnect -p <module/version/arch>`
- For interactive patches that cannot be auto-applied: review patch details with `zypper patch-info <patch>`
- Check if snapper/btrfs snapshots are consuming space preventing patch file extraction
- Verify patch is not architecture-specific (s390x patches won't apply to x86_64)
- For superseded patches: `zypper patch --updatestack-only` to update the update stack first
