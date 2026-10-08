---
name: ec2-patch-windows-policy-blockers
description: >-
  Use this skill when a Windows Server EC2 instance's patching is blocked by a
  policy or security control rather than the update mechanism — Group Policy
  disabling Windows Update, antivirus/EDR locking system files or a missing
  AV-compat registry key, BitLocker triggering recovery on a boot-critical update,
  the Server 2012 R2 SHA-2 signing prerequisite, execution policy, registry ACLs,
  or Credential Guard. Use it when a patch run fails with 0x8024002E ("WU disabled
  by policy"), 0x80070005/0x80070020 (access denied / file in use), a reboot that
  enters BitLocker recovery, 0x800B0101/0x80096010 (SHA-2 on 2012 R2), or "managed
  by your organization" — even when the user only says patches "won't apply". The
  fix depends on the control: a GPO edit is temporary (reverts on ~90-min refresh,
  so fix the GPO), BitLocker must be SUSPENDED before a boot-critical update or the
  reboot demands the recovery key, and 2012 R2 needs the SHA-2 KBs first. Apply it
  to identify the blocking control and remediate it.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Windows Server, Patching, Security"
  domains: "EC2, SSM, Patch Manager, GPO, BitLocker, antivirus, SHA-2"
  platforms: "Windows"
  supported-os: "Windows Server 2012 R2, 2016, 2019, 2022, 2025"
  operation-type: "read-and-mutate"
---

# Recover a Windows policy / security-control block on patching

## When this applies
A Windows patch fails because a policy or security control (GPO, AV/EDR,
BitLocker, execution policy, ACLs, DCOM, Credential Guard, SHA-2 prereq) is
blocking it — the update services, store, and connectivity are otherwise fine.
Instance is Online in SSM. If the failure is a hung/disabled service, CBS store
corruption, or connectivity, that is a different skill.

## The key insight: identify the control — several fixes are temporary or off-box
- **GPO disabling Windows Update** (`0x8024002E`, `NoAutoUpdate=1`, `DisableWindowsUpdateAccess=1`,
  "managed by your organization"): you can clear the registry values to patch **this cycle**, but a
  domain **GPO reverts them on the next refresh (~90 min)** — the durable fix is the GPO itself. Escalate to the AD/GPO owner.
- **Antivirus / EDR interference** (`0x80070005` access denied, `0x80070020` file in use, CBS
  "access denied" on WinSxS): AV real-time scanning locks files TrustedInstaller must replace, or
  the **Spectre/Meltdown `QualityCompat` registry key is missing** (Microsoft won't offer updates
  without it). Add WU-path exclusions / the QualityCompat key; third-party AV/EDR exclusions are set in the vendor console, not locally.
- **BitLocker** (reboot enters recovery, `0x80070032`, firmware/Secure-Boot update): boot-critical
  updates change TPM PCR measurements → **suspend BitLocker for one reboot** (`Suspend-BitLocker
  -RebootCount 1`) BEFORE patching, or the reboot demands the 48-digit recovery key. High-risk.
- **Server 2012 R2 SHA-2 prerequisite** (`0x800B0101`, `0x80096010`, scan returns 0 updates): since
  2019 all updates are SHA-2 signed; 2012 R2 needs KB4490628 (SHA-2 SSU) then KB4474419 (SHA-2 code
  signing) or **every** post-2019 update fails signature validation.
- **Execution policy / ACL / DCOM / Credential Guard / scheduled task / language pack**: narrower
  blockers — restore the specific control (see references).

## Diagnosis first
- [ ] Step 1: Classify the blocking control (read-only):
  ```powershell
  $wu='HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
  Get-ItemProperty "$wu\AU" -EA SilentlyContinue | Select NoAutoUpdate,UseWUServer
  Get-ItemProperty $wu -EA SilentlyContinue | Select DisableWindowsUpdateAccess
  Get-BitLockerVolume -EA SilentlyContinue | Select MountPoint,ProtectionStatus
  Get-Service | ? {$_.DisplayName -match 'CrowdStrike|Symantec|McAfee|Carbon|SentinelOne|Trend|Defender'} | Select Name,Status
  (Get-CimInstance Win32_OperatingSystem).BuildNumber   # 9600 = 2012 R2 (SHA-2 check)
  ```
- [ ] Step 2: Route to the control (load the matching reference):
  - GPO disabling/redirecting WU → read [gpo blocks](reference/gpo-blocks.md).
  - AV/EDR file locks / QualityCompat → read [av interference](reference/av-interference.md).
  - BitLocker / boot-critical update → read [bitlocker](reference/bitlocker.md).
  - 2012 R2 SHA-2 / exec-policy / ACL / DCOM / other → read [sha2 and misc blockers](reference/sha2-and-misc-blockers.md).

## Ordered recovery
- [ ] Step 3: **Establish the 2012 R2 SHA-2 baseline first** if applicable — nothing else patches on 2012 R2 until KB4490628 + KB4474419 are in.
- [ ] Step 4: **Suspend BitLocker for one reboot BEFORE** any boot-critical/firmware update (confirm the recovery key is available first).
- [ ] Step 5: **Clear the AV/policy block** — add the QualityCompat key / WU exclusions (or vendor-console exclusions), and clear the GPO registry values for this cycle.
- [ ] Step 6: **Verify** the block is cleared (write test to WU dirs, policy values cleared, BitLocker suspended) and note anything that will revert.

## Validation (check your own work before reporting success)
- [ ] The specific control was identified (GPO vs AV vs BitLocker vs SHA-2), not treated generically.
- [ ] For BitLocker: protection is **Suspended for the reboot** and the recovery key is confirmed available (never reboot a protected boot-critical patch blind).
- [ ] For AV: the QualityCompat key is present (2012 R2/2016) and a write test to `SoftwareDistribution`/`WinSxS` succeeds.
- [ ] For GPO: values are cleared for this cycle AND you have flagged that the GPO must be fixed (or it reverts in ~90 min).
- [ ] The originally failing scan/install no longer fails on the control.
If any check fails, re-classify; do not leave AV disabled or BitLocker suspended beyond the patch window.

## Gotchas
- **Clearing a GPO registry value is temporary** — a domain GPO restores it on the next refresh (~90 min / reboot). The durable fix is the GPO (or moving the instance to a patching OU) — escalate to the AD team.
- **BitLocker must be suspended BEFORE a boot-critical/firmware update, not after** — otherwise the reboot changes PCR measurements and demands the 48-digit recovery key (via serial console). Confirm the key is available first. High-risk.
- **Microsoft won't offer updates without the AV `QualityCompat` key** on 2012 R2/2016 (Spectre/Meltdown gate) — set `cadca5fe-...=0` before chasing other AV causes.
- **2012 R2 is a hard SHA-2 chicken-and-egg** — install KB4490628 (SSU) first, reboot, then KB4474419; without them every post-2019 update fails signature validation and the scan returns 0 updates.
- **Third-party AV/EDR exclusions are set in the vendor console** (Falcon/Carbon Black/Symantec), not locally — you can add Defender exclusions on-box but must coordinate third-party ones.
- **Re-enable AV real-time protection and resume BitLocker after the patch window** — don't leave protections off.
