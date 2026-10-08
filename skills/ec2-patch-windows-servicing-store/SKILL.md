---
name: ec2-patch-windows-servicing-store
description: >-
  Recover a Windows Server (2012 R2, 2016, 2019, 2022, 2025) EC2 instance whose
  patching is blocked by a component-servicing fault — the family of failures
  rooted in CBS/WinSxS, the servicing stack (SSU), pending servicing
  transactions, the Windows Update datastore, or a stalled feature update. Use
  when a patch or Windows Update install fails with 0x80073712, 0x800F0831
  (CBS_E_STORE_CORRUPTION), 0x800F081F, 0x800F0922, 0x80073701, 0x80070BC9,
  0x8024400A/0x80244010, or 0xC1900101; when DISM/ScanHealth reports corruption
  or "packages are pending servicing"; when updates stick in
  "InstalledPendingReboot"/"Pending Install"; when DataStore.edb is oversized; or
  when Windows.old lingers after a failed in-place upgrade. This skill diagnoses
  WHICH servicing fault is present and applies the correct, ordered recovery —
  the sub-faults interact (a stale SSU and pending transactions both surface AS
  store corruption), so the naive "just run DISM /RestoreHealth" loops without
  converging.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Windows Server, Patching"
  domains: "EC2, SSM, Patch Manager, Windows Update, CBS, DISM, WinSxS, SSU"
  platforms: "Windows"
  supported-os: "Windows Server 2012 R2, 2016, 2019, 2022, 2025"
  operation-type: "read-and-mutate"
---

# Recover a Windows component-servicing fault blocking patching

## When this applies
A Windows patch / Windows Update install fails and the signature points at the
component-servicing subsystem (CBS/WinSxS, servicing stack, pending
transactions, WU datastore, or feature-update state). Instance is Online in SSM.
If the failure is a *connectivity* fault (WSUS/TLS/proxy) or a *policy* blocker
(GPO/AV/BitLocker), this is the wrong skill — those are separate domains.

## The key insight: diagnose the sub-fault first — they masquerade as each other
`0x800F0831` / "store corruption" is the most common *surface* symptom, but its
*cause* is often not store corruption at all:
- an **outdated servicing stack (SSU)** can't process a new LCU manifest → surfaces as store corruption;
- a **halted pending transaction** (interrupted reboot) → surfaces as store corruption;
- a **stalled feature update** leaves mixed package state → LCU "not applicable".

Running `DISM /RestoreHealth` blindly loops for hours when the real cause is a
stale SSU or a pending transaction. **Identify the sub-fault, then apply the
matching path in the correct order.**

## Diagnosis first (always)
- [ ] Step 1: Capture the failing error code and the servicing state before changing anything:
  ```powershell
  DISM /Online /Cleanup-Image /CheckHealth
  DISM /Online /Get-Packages /Format:Table | Select-String "Pending"
  Test-Path "$env:SystemRoot\servicing\Packages\pending.xml"
  (Get-Item "$env:SystemRoot\SoftwareDistribution\DataStore\DataStore.edb").Length/1MB
  Get-ChildItem "$env:SystemRoot\Windows.old","$env:SystemRoot\`$WINDOWS.~BT" -ErrorAction SilentlyContinue
  Get-Content "$env:SystemRoot\Logs\CBS\CBS.log" -Tail 80 | Select-String "ERROR|corrupt|pending|missing"
  ```
- [ ] Step 2: Route to the sub-fault by signature (load the matching reference for exact steps):
  - Pending transactions present (`pending.xml`, "Install Pending", `0x800F0922`) → read [pending transactions](reference/pending-transactions.md) — clear these BEFORE any DISM repair.
  - SSU outdated / `0x80070BC9` / `0x80073701` on LCU → read [SSU ordering](reference/ssu-ordering.md) — install SSU BEFORE the LCU and before RestoreHealth.
  - Genuine CBS/WinSxS corruption (`0x80073712`, `0x800F0831` with no pending/SSU cause) → read [CBS store repair](reference/cbs-store-repair.md).
  - WU datastore bloat/corruption (`0x8024400A`, `DataStore.edb` >1GB, ESENT 455/489) → read [WU datastore](reference/wu-datastore.md).
  - Stalled feature update (`0xC1900101`, lingering `Windows.old`) → read [feature update state](reference/feature-update.md).

## Ordered recovery (dependencies matter — do not reorder)
- [ ] Step 3: **Clear pending transactions first.** `DISM /Online /Cleanup-Image /RevertPendingActions`;
  rename a stale (`>24h`) `pending.xml`; clear `SessionsPending`. A pending transaction poisons every later step.
- [ ] Step 4: **Bring the servicing stack current.** Install any pending Servicing Stack Update BEFORE the LCU.
  An old SSU cannot process a new LCU manifest and will re-manifest as store corruption.
- [ ] Step 5: **Repair the component store** only after 3–4: `DISM /Online /Cleanup-Image /RestoreHealth`
  (add `/Source:WIM:<path>\install.wim:<idx> /LimitAccess` on isolated fleets where WU is blocked), then `sfc /scannow`.
- [ ] Step 6: **Reset WU components** if the datastore is implicated: stop `wuauserv,cryptSvc,bits,msiserver`;
  rename `SoftwareDistribution` and `catroot2`; restart. See the datastore reference for the `DataStore.edb` specifics.
- [ ] Step 7: **Reboot** to let TrustedInstaller finalize valid pending operations, then re-scan.

## Validation (check your own work before reporting success)
Do not report the instance patchable until you confirm each of these:
- [ ] `DISM /Online /Cleanup-Image /CheckHealth` reports the store **healthy** (not just "RestoreHealth exit 0").
- [ ] No packages remain "Install Pending"/"Uninstall Pending" and `pending.xml` is absent.
- [ ] No Servicing Stack Update is still pending (`Search("IsInstalled=0")` returns no "Servicing Stack" title).
- [ ] The original failing update/patch scan re-run no longer returns its original error code.
- [ ] `wuauserv` is Running.
If any check fails, consult the matching reference's escalation section rather than re-looping DISM.

## Gotchas
- **SSU installs are forward-only — they cannot be uninstalled.** Do not promise a rollback of the servicing stack.
- **Order is load-bearing:** pending-transaction clear → SSU → RestoreHealth → SFC → reboot. SFC before a healthy store just fails; RestoreHealth before clearing a pending transaction loops.
- **A recent `pending.xml` (<24h) may be valid** — renaming it can abort a legitimate in-flight servicing operation. Check age first.
- **`/Source` build must match the running OS build exactly** (`Version` + UBR); a mismatched WIM fails RestoreHealth with a generic error.
- **On an isolated/patched fleet, WU as the RestoreHealth source is blocked** — supply an explicit `/Source` with `/LimitAccess` or the repair silently retries WU and times out.
- **A stalled feature update is NOT store corruption** — running RestoreHealth against a half-upgraded image ("not applicable to this image") wastes the maintenance window; resolve the upgrade state first.
