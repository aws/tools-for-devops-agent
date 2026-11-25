# SOP-049: Resolve Package Manager Plugin Errors Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-049 |
| Category | package_manager_plugin_error |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Amazon Linux 2, Amazon Linux 2023, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Plugin error: Could not load plugin" at yum/dnf startup
- "subscription-manager plugin threw exception" blocking transactions
- "Error: Loading plugins: product-id, subscription-manager" 
- "ImportError: No module named 'dnf_plugin_*'"
- "Could not import Python module 'subscription_manager'" 
- APT hook errors: "E: Problem executing scripts APT::Update::Post-Invoke-Success"
- "Error: Failed to initialize RHSM plugin" preventing any dnf operation
- "zypper: plugin 'zypp-plugin-spacewalk' failed" on SUSE

## Root Cause

Package manager plugin errors when:

- subscription-manager Python module corrupted or incompatible with current Python version
- Plugin Python dependencies removed during a previous partial update
- product-id plugin fails when certificate directory is empty or corrupt
- APT post-invoke hooks reference scripts that no longer exist or have syntax errors
- Unattended-upgrades hook misconfigured
- Amazon Linux extras plugin throws exception blocking all DNF operations
- Plugin config in /etc/dnf/plugins/ or /etc/yum/pluginconf.d/ has invalid syntax
- SELinux denying plugin file access

## Related Failure Patterns

- SOP-010 (Python Missing) — Python issues break Python-based plugins
- SOP-029 (Scriptlet Failure) — plugin failures are similar to scriptlet failures
- SOP-027 (SELinux Block) — SELinux can deny plugin file access

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)

## Diagnosis

Identify the failing plugin:

```bash
dnf --verbose repolist 2>&1 | grep -iE "error|exception|cannot|failed" | head -10; echo "---"; ls /etc/dnf/plugins/ 2>/dev/null || ls /etc/yum/pluginconf.d/ 2>/dev/null; echo "---"; cat /etc/apt/apt.conf.d/*hook* 2>/dev/null | head -10
```

## Remediation Steps

### Step 1: Identify the problematic plugin

```bash
if command -v dnf &>/dev/null; then DNF_OUT=$(dnf repolist 2>&1); echo "$DNF_OUT" | grep -iE "error|exception|plugin|cannot load" | head -10; PROBLEM_PLUGIN=$(echo "$DNF_OUT" | grep -oP "plugin[: ]+\K\w+" | head -1); echo "Problem plugin: ${PROBLEM_PLUGIN:-unknown}"; elif command -v apt-get &>/dev/null; then apt-get update 2>&1 | grep -i "hook\|script\|error" | head -10; fi; echo "Plugin check done"
```

Expected output: Problematic plugin identified
On failure: continue

### Step 2: Disable problematic plugin (RPM-based)

```bash
if command -v dnf &>/dev/null; then PLUGIN_TRACK=/var/tmp/sop049-plugins.txt; : > "$PLUGIN_TRACK"; for plugin_conf in /etc/dnf/plugins/*.conf; do PNAME=$(basename "$plugin_conf" .conf); if ! dnf --disableplugin="$PNAME" repolist 2>&1 | grep -qi "error\|exception"; then echo "Disabling broken plugin: $PNAME"; sed -i 's/^enabled.*=.*1/enabled=0/' "$plugin_conf"; echo "$plugin_conf" >> "$PLUGIN_TRACK"; fi; done 2>/dev/null; dnf repolist 2>&1 | grep -qi "error" && echo "Still errors" || echo "Plugin errors resolved"; fi
```

Expected output: "Plugin errors resolved"
On failure: continue

### Step 3: Fix subscription-manager plugin specifically

```bash
if rpm -q subscription-manager &>/dev/null; then dnf reinstall -y subscription-manager python3-subscription-manager-rhsm 2>&1 | tail -3; echo "subscription-manager reinstalled"; elif [ -f /etc/dnf/plugins/subscription-manager.conf ]; then sed -i 's/^enabled.*=.*1/enabled=0/' /etc/dnf/plugins/subscription-manager.conf; echo /etc/dnf/plugins/subscription-manager.conf >> /var/tmp/sop049-plugins.txt; echo "subscription-manager plugin disabled (not installed)"; else echo "subscription-manager not applicable"; fi
```

Expected output: Plugin status
On failure: continue

### Step 4: Fix APT hook errors (Debian-based)

```bash
if command -v apt-get &>/dev/null; then HOOK_TRACK=/var/tmp/sop049-hooks.txt; : > "$HOOK_TRACK"; UPD_ERR=$(apt-get update 2>&1); if echo "$UPD_ERR" | grep -qiE "Problem executing scripts|Post-Invoke|Pre-Invoke|sub-process.*returned an error"; then echo "apt-get update is failing on a Post/Pre-Invoke hook - disabling hook scripts to unblock (recorded for Rollback):"; for hook in $(find /etc/apt/apt.conf.d/ -type f -exec grep -l "Post-Invoke\|Pre-Invoke" {} \; 2>/dev/null); do mv "$hook" "${hook}.disabled" && echo "$hook" >> "$HOOK_TRACK" && echo "  disabled: $hook"; done; echo "Re-testing:"; apt-get update 2>&1 | tail -3; else echo "apt-get update succeeded - APT hooks are not the problem; leaving them intact (do NOT syntax-check/disable working hooks like unattended-upgrades or needrestart)"; fi; else echo "Not Debian-based"; fi
```

Expected output: "APT hooks checked"
On failure: continue

### Step 5: Verify package manager works without plugin errors

```bash
if command -v dnf &>/dev/null; then dnf repolist 2>&1 | grep -ic "error\|exception" | awk '{if ($1==0) print "DNF PLUGINS OK"; else print "PLUGIN ERRORS REMAIN"}'; elif command -v apt-get &>/dev/null; then apt-get update 2>&1 | grep -ic "error\|hook" | awk '{if ($1==0) print "APT HOOKS OK"; else print "HOOK ERRORS REMAIN"}'; fi
```

Expected output: "DNF PLUGINS OK" or "APT HOOKS OK"
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf check-update -q 2>&1 | head -1; echo "Exit: $?"; dnf repolist 2>&1 | grep -qi "error" && echo "STILL BROKEN" || echo "PLUGINS OK"; elif command -v apt-get &>/dev/null; then apt-get update -qq 2>&1 && echo "PLUGINS OK" || echo "STILL BROKEN"; fi
```

Expected: "PLUGINS OK"

## Rollback

```bash
# Re-enable ONLY the plugins this SOP disabled in Steps 2-3 (recorded in the tracking file) - never blindly flip every plugin conf, which would clobber plugins the customer had already disabled
PLUGIN_TRACK=/var/tmp/sop049-plugins.txt
if [ -f "$PLUGIN_TRACK" ]; then
  while read -r conf; do [ -n "$conf" ] && [ -f "$conf" ] && sed -i 's/^enabled.*=.*0/enabled=1/' "$conf" 2>/dev/null && echo "Plugin re-enabled: $conf"; done < "$PLUGIN_TRACK"
  rm -f "$PLUGIN_TRACK"
else
  echo "No tracked plugins to re-enable"
fi
# Re-enable ONLY the APT hooks this SOP disabled in Step 4 (recorded in the tracking file)
HOOK_TRACK=/var/tmp/sop049-hooks.txt
if [ -f "$HOOK_TRACK" ]; then
  while read -r hook; do [ -n "$hook" ] && [ -f "${hook}.disabled" ] && mv "${hook}.disabled" "$hook" 2>/dev/null && echo "Hook re-enabled: $hook"; done < "$HOOK_TRACK"
  rm -f "$HOOK_TRACK"
else
  echo "No tracked APT hooks to re-enable"
fi
echo "Plugins re-enabled"
```

## Escalation

If plugin errors persist:
- Remove and reinstall the plugin package: `dnf remove <plugin-package> && dnf install <plugin-package>`
- For subscription-manager on non-RHSM systems: permanently disable with `enabled=0` in the conf
- For Amazon Linux extras plugin: `dnf reinstall amazon-linux-extras` 
- Check Python path: `python3 -c "import dnf"` to verify Python/DNF integration
- For APT: `apt-get -o APT::Update::Post-Invoke-Success="" update` to bypass hooks temporarily
