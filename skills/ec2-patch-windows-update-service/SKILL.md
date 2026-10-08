---
name: ec2-patch-windows-update-service
description: >-
  Use this skill when a Windows Server EC2 instance's patching is blocked by a
  Windows update service or runtime fault rather than component-store corruption.
  Use it when a patch run fails with 0x80070422 ("the service cannot be started"),
  the scan hangs indefinitely, wuauserv StartType is Disabled, MSI errors
  0x80070643 or 0x80070652 appear, or the run reports "Could not load type ... from
  assembly AWSSDK.Core" — including when the user only says patching "won't start"
  or "hangs" without naming a service. It covers a hung or crashed Windows Update,
  BITS, or TrustedInstaller service; a broken Windows Installer (MSI) service; the
  Windows Update service set to Disabled; and the AWS-specific AWSSDK.Core assembly
  missing from the GAC, which breaks AWS-RunPatchBaseline itself. Apply it to
  re-enable a Disabled service (not just start it), reset a hung update agent and
  clear SoftwareDistribution, or re-register a missing AWSSDK.Core in the GAC.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Windows Server, Patching"
  domains: "EC2, SSM, Patch Manager, Windows Update, WUA, BITS, MSI, GAC"
  platforms: "Windows"
  supported-os: "Windows Server 2012 R2, 2016, 2019, 2022, 2025"
  operation-type: "read-and-mutate"
---

# Recover a Windows update-service / runtime fault blocking patching

## When this applies
A Windows patch scan/install fails because a service it depends on (Windows
Update/wuauserv, BITS, TrustedInstaller, Windows Installer/msiserver) is
hung/crashed/disabled, or the .NET runtime `AWS-RunPatchBaseline` needs is broken
(AWSSDK.Core missing from the GAC). Instance is Online in SSM. If the failure is
component-store corruption (CBS/SSU/pending transactions) or a connectivity/policy
blocker, that is a different skill.

## The key insight: identify the service/runtime fault — the fixes differ
- **wuauserv Disabled** (`0x80070422`, `StartType: Disabled`): SSM can start a *Stopped*/*Manual* service but **cannot start a Disabled one**. Re-enable it (`Set-Service -StartupType Automatic`) then start — and note a GPO may re-disable it on the next refresh.
- **WUA/BITS/TrustedInstaller hung** (scan hangs forever, wuauserv stuck Stopping, TiWorker pegged): stop the services, kill the hung processes, clear `SoftwareDistribution\Download`, re-register the WUA DLLs, restart. If the scan DB is corrupt, remove `DataStore.edb` (see the datastore path).
- **MSI service corrupt** (`0x80070643`, `0x80070652` ALREADY_RUNNING, msiexec stuck): kill stuck msiexec, re-register the installer (`msiexec /unregister` then `/regserver`), clear the InProgress state.
- **AWSSDK.Core missing from GAC** (`Could not load type ... 'AWSSDK.Core'`): `AWS-RunPatchBaseline` can't load AWS SDK types. Re-register `AWSSDK.Core.dll` into the GAC with `gacutil /i` (snapshot first).

## Diagnosis first
- [ ] Step 1: Classify the service/runtime fault before acting:
  ```powershell
  Get-Service wuauserv,bits,cryptSvc,msiserver,TrustedInstaller | Select Name,Status,StartType
  Get-Process TiWorker,wuauclt,msiexec,svchost -ErrorAction SilentlyContinue | ? {$_.CPU -gt 60}
  Get-WinEvent -LogName Application -MaxEvents 15 | ? {$_.ProviderName -match 'MsiInstaller|Update'} | Select TimeCreated,Message
  [System.Reflection.Assembly]::LoadWithPartialName("AWSSDK.Core")   # null = missing from GAC
  ```
- [ ] Step 2: Route to the fault (load the matching reference):
  - Service Disabled → read [service startup state](reference/service-startup-state.md).
  - WUA/BITS hung / scan never returns → read [wua bits hang](reference/wua-bits-hang.md).
  - MSI/Windows Installer failure → read [msi service](reference/msi-service.md).
  - AWSSDK.Core / AWS-RunPatchBaseline type-load error → read [awssdk gac](reference/awssdk-gac.md).

## Ordered recovery
- [ ] Step 3: **Confirm the service can run at all** — if `wuauserv` (or BITS) is Disabled, re-enable before anything else; a Disabled service makes every later step fail.
- [ ] Step 4: **Clear the hung state** — kill long-running TiWorker/msiexec, stop/reset the services, clear `SoftwareDistribution\Download` (and DataStore.edb if the scan DB is corrupt).
- [ ] Step 5: **Repair the runtime** — re-register WUA DLLs / re-register MSI / re-register AWSSDK.Core in the GAC, as applicable.
- [ ] Step 6: **Verify** a `Microsoft.Update.Session` search succeeds (or `AWS-RunPatchBaseline` scan runs) with no service error.

## Validation (check your own work before reporting success)
- [ ] `wuauserv` StartType is not Disabled and the service starts; BITS is running.
- [ ] A `CreateUpdateSearcher().Search(...)` completes without throwing (WUA healthy), or the patch scan runs.
- [ ] For MSI: no `InProgress` key remains and msiserver starts.
- [ ] For AWSSDK.Core: the assembly loads and `Amazon.Runtime.Internal.InvokeOptions` resolves (so AWS-RunPatchBaseline works).
- [ ] The originally failing scan/install no longer fails on the service/runtime error.
If any check fails, re-diagnose the specific service rather than rebooting blindly.

## Gotchas
- **Disabled ≠ Stopped.** SSM/patch baseline can start a Stopped/Manual service but not a Disabled one — `Set-Service -StartupType Automatic` first. And if a GPO disabled it, it will re-disable on refresh (~90 min) — the GPO is the real fix.
- **A hung WUA is often a symptom of a stale SSU or CBS store corruption** — if resetting the service doesn't hold, check the servicing store/SSU (separate skill).
- **AWSSDK.Core missing from the GAC breaks AWS-RunPatchBaseline itself** — the error is a .NET type-load exception, not an obvious "patch" error; re-register the DLL with `gacutil /i` (snapshot first, and exclude the SDK path from AV to prevent recurrence).
- **`DataStore.edb` deletion is only for a corrupt scan DB** — it forces a full re-scan; don't delete it reflexively.
- **Killing TiWorker mid-transaction can leave a pending servicing transaction** — if that happens, clear it (servicing-store skill) before retry.
- **BITS disabled/stopped blocks update downloads** even when wuauserv is fine — check BITS too.
