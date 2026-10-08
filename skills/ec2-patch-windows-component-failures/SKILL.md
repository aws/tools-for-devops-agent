---
name: ec2-patch-windows-component-failures
description: >-
  Use this skill when a Windows Server EC2 instance's update mechanism works but a
  specific patch fails because of the component it targets or the host's role — a
  .NET Framework update failing, a Windows Update driver that conflicts with the
  AWS ENA/NVMe/PV drivers (BSOD or lost connectivity), a stalled feature update /
  in-place upgrade leaving the OS stuck between builds, or a failover-cluster node
  that can't reboot without losing quorum. Use it when other patches install fine
  but one component fails with 0x80070643/0x80096004 (.NET), 0x800F0217 or a
  BSOD/unreachable instance after a driver update, 0xC1900101 (feature-update
  SAFE_OS/SECOND_BOOT), "not applicable to this image", or 0x80070426 (cluster
  service) — even when the user only says "one update keeps failing". The fix is
  component-specific: a WU driver over an AWS driver should be excluded from WU (not
  reinstalled), and a cluster node is drained and suspended before reboot. Apply it
  to classify and fix the failure.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Windows Server, Patching, Drivers"
  domains: "EC2, SSM, Patch Manager, .NET, drivers, feature update, failover cluster"
  platforms: "Windows"
  supported-os: "Windows Server 2012 R2, 2016, 2019, 2022, 2025"
  operation-type: "read-and-mutate"
---

# Recover a component-specific Windows patch failure

## When this applies
Most patches install, but a **specific component** fails (or the host's **role**
blocks the reboot): .NET Framework, a driver conflicting with the AWS
ENA/NVMe/PV drivers, a stalled feature update/in-place upgrade, a language pack,
a corrupt profile, or a failover-cluster node. The WU service, store, connectivity,
and policy are otherwise fine. If the whole store is corrupt, WU is disabled by
policy, or connectivity is down, that is a different skill.

## The key insight: the mechanism is fine — fix the component, and some fixes are AWS/role-specific
- **Driver update breaks EC2** (`0x800F0217`, BSOD/unreachable after a driver patch, ENA/NVMe/PV):
  Windows Update pushes a **generic driver that overrides the AWS-specific driver**, breaking network
  or the boot volume on Nitro. The fix is to **exclude drivers from WU** (`ExcludeWUDriversInQualityUpdate=1`
  + hide the driver updates), NOT to reinstall a generic driver. Recover an unreachable instance via
  Serial Console / a rescue instance. **High-risk.**
- **.NET Framework update fails** (`0x80070643`, `0x80096004`): .NET is an **OS component** on 2016+ —
  repair with `DISM /Online /Cleanup-Image /RestoreHealth` + resync NGen; don't chase a standalone reinstall first.
- **Feature update / in-place upgrade limbo** (`0xC1900101` SAFE_OS/SECOND_BOOT, `Windows.old`, "not
  applicable to this image", wrong build): an upgrade started but never finished; clear the
  `UpgradeInProgress`/`SetupType` flags + stale `$WINDOWS.~BT` staging and confirm the **actual** build
  before the LCU will apply.
- **Failover cluster node** (`0x80070426`, CSV locked, reboot blocked): the node owns clustered
  resources — **drain and suspend the node** (`Suspend-ClusterNode -Drain`) before any reboot, or
  quorum is lost. Never reboot the last online node; prefer Cluster-Aware Updating. **High-risk.**
- **Language pack / corrupt profile**: narrower — align the LP with the OS build; repair/recreate the profile.

## Diagnosis first
- [ ] Step 1: Classify the failing component (read-only):
  ```powershell
  # which component failed? sample signals:
  Get-WindowsDriver -Online | ? {$_.ProviderName -match 'Amazon|AWS'} | Select ClassName,ProviderName,Version   # AWS drivers
  Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP' -Recurse | Get-ItemProperty -Name Version -EA SilentlyContinue | Select PSChildName,Version
  Test-Path 'C:\Windows.old'; (Get-ItemProperty 'HKLM:\SYSTEM\Setup' -Name UpgradeInProgress -EA SilentlyContinue).UpgradeInProgress   # feature-update limbo
  Import-Module FailoverClusters -EA SilentlyContinue; Get-ClusterNode -EA SilentlyContinue | Select Name,State   # cluster
  ```
- [ ] Step 2: Route to the component (load the matching reference):
  - driver / BSOD / ENA-NVMe-PV → read [driver conflicts](reference/driver-conflicts.md).
  - .NET Framework update → read [dotnet repair](reference/dotnet-repair.md).
  - feature update / in-place upgrade / wrong build → read [feature update limbo](reference/feature-update-limbo.md).
  - failover cluster node / language pack / profile → read [cluster and misc](reference/cluster-and-misc.md).

## Ordered recovery
- [ ] Step 3: **If a cluster node** — drain + suspend it BEFORE anything that reboots (or quorum is lost).
- [ ] Step 4: **If a driver update** — exclude drivers from WU + hide the offending update rather than letting WU override the AWS driver; verify ENA/IMDS still reachable.
- [ ] Step 5: **Repair the component** — .NET via DISM RestoreHealth + NGen; feature-update limbo by clearing flags/staging and confirming the build; language pack/profile as applicable.
- [ ] Step 6: **Verify** the specific component now patches / the node is drained and safe to reboot.

## Validation (check your own work before reporting success)
- [ ] The failing component was correctly identified, not treated as a generic WU failure.
- [ ] For a driver: WU driver exclusion is set, the AWS ENA/NVMe/PV driver is intact, and IMDS/network is reachable (never leave an instance one reboot away from a lost boot volume).
- [ ] For a cluster: the node is **Paused/drained with 0 owned groups** before any reboot; the last online node is never rebooted.
- [ ] For a feature update: upgrade flags/staging are cleared and the actual build matches what the pending LCU targets.
- [ ] The originally failing component no longer fails.
If any check fails, re-classify — don't reboot a cluster node or an AWS-driver instance blind.

## Gotchas
- **Windows Update drivers can break EC2** — a generic WU driver over the AWS ENA/NVMe/PV driver causes BSOD or a lost boot volume on Nitro. Exclude drivers from WU (`ExcludeWUDriversInQualityUpdate=1`) and hide the update; get AWS drivers from the official EC2 driver downloads, not WU. Recover via Serial Console.
- **.NET is an OS component on 2016+** — repair with `DISM /Online /Cleanup-Image /RestoreHealth`, not a standalone reinstall as the first move.
- **Never reboot a clustered node without draining it** — `Suspend-ClusterNode -Drain` first; rebooting an active owner or the last node loses quorum / locks CSV. Prefer Cluster-Aware Updating over ad-hoc SSM reboots.
- **Feature-update limbo blocks the LCU** — `0xC1900101` / "not applicable to this image" with `Windows.old`/`$WINDOWS.~BT` means the OS is stuck between builds; clear the flags/staging and confirm the real build first.
- **WSUS/SCCM should not offer feature updates to LTSC servers** — if it is, that's the source of the conflict.
- **Resume/re-enable after the window** — `Resume-ClusterNode`, and only remove the driver exclusion if AWS driver management is otherwise ensured.
