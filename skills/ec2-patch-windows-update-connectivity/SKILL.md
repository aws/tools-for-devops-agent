---
name: ec2-patch-windows-update-connectivity
description: >-
  Use this skill when a Windows Server EC2 instance's patching fails because it
  cannot reach or authenticate to the update source — WSUS/Microsoft Update
  endpoint unreachable, proxy authentication failures in the SYSTEM context, TLS
  1.2 not enabled, outdated/missing root certificates, firewall/WPAD, or a wrong
  WUServer GPO. Use it when a patch run fails with 0x8024401C (WU HTTP timeout),
  "Windows Update is not reachable", 0x80072F8F/0x800B0109/0x800B010A (TLS/cert
  trust), 0x80072EFD/0x80244017 (HTTP 407 proxy auth), or a scan that times out
  reaching WSUS — even when the user only says patching "can't connect". The fix
  depends on the source: a WSUS instance (UseWUServer=1) that can't reach WSUS is
  an infrastructure problem to escalate, not an OS fix, so don't loop-retry; SSM
  patches run as SYSTEM with no cached proxy credentials so a proxy needs a WinHTTP
  config plus WU bypass; and a cert error is often a stale root store or a wrong
  clock. Apply it to classify the connectivity fault and fix it.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Windows Server, Patching, Networking"
  domains: "EC2, SSM, Patch Manager, Windows Update, WSUS, proxy, TLS, certificates"
  platforms: "Windows"
  supported-os: "Windows Server 2012 R2, 2016, 2019, 2022, 2025"
  operation-type: "read-and-mutate"
---

# Recover Windows update connectivity blocking patching

## When this applies
A Windows patch scan/install fails because the Windows Update Agent cannot reach
or authenticate to its update source (WSUS or Microsoft Update) — a timeout,
TLS/cert error, or proxy 407. The update services themselves are healthy and the
instance is Online in SSM. If the failure is a hung/disabled update service, CBS
store corruption, or a policy blocker (GPO/AV/BitLocker), that is a different skill.

## The key insight: identify the source and context — several fixes are off-box or context-specific
- **WSUS unreachable** (`UseWUServer=1`, `0x8024401C`, "Windows Update is not reachable"): the
  instance is GPO-pointed at an internal WSUS server. If WSUS/the network path is down, this is an
  **infrastructure problem to escalate** (WSUS owner / network), NOT an OS fix — **do not loop-retry**
  a patch against an unreachable server. A temporary `UseWUServer=0` fallback needs approval and reverts on GPO refresh.
- **Proxy auth (SYSTEM context)** (`0x80072EFD`, `0x80244017` = HTTP 407): SSM/patch baseline runs
  as **SYSTEM**, which has no cached proxy credentials — so it fails 407 even when logged-in users
  patch fine. Fix by setting the WinHTTP system proxy and a **WU bypass list**, or making the proxy
  allow unauthenticated access to the WU URLs.
- **TLS 1.2 not enabled** (handshake fails on modern endpoints): enable TLS 1.2 + `SchUseStrongCrypto`.
- **Outdated/missing root certs** (`0x800B0109`/`0x800B010A` untrusted chain): refresh the root store
  (`certutil -generateSSTFromWU` + `-addstore Root`), enable root auto-update.
- **Clock skew** (`0x80072F8F`): a wrong clock makes valid certs look invalid — fix time first.
- **Firewall / WPAD**: outbound 443 (or 8530/8531 for WSUS) blocked, or WPAD pointing at a bad proxy.

## Diagnosis first
- [ ] Step 1: Classify the connectivity fault before acting (read-only):
  ```powershell
  $wu='HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
  (Get-ItemProperty "$wu\AU" -Name UseWUServer -EA SilentlyContinue).UseWUServer
  (Get-ItemProperty $wu -Name WUServer -EA SilentlyContinue).WUServer
  netsh winhttp show proxy
  Get-Date; w32tm /stripchart /computer:time.aws.com /samples:1 /dataonly 2>&1 | tail   # clock
  $r=Get-ChildItem Cert:\LocalMachine\Root; "roots=$($r.Count) expired=$(($r|?{$_.NotAfter -lt (Get-Date)}).Count)"
  ```
- [ ] Step 2: Route to the fault (load the matching reference):
  - `UseWUServer=1` / WSUS timeout → read [wsus routing](reference/wsus-routing.md).
  - proxy 407 / SYSTEM-context proxy → read [proxy system context](reference/proxy-system-context.md).
  - TLS 1.2 / handshake → read [tls settings](reference/tls-settings.md).
  - untrusted cert chain / root store / clock → read [root certs and clock](reference/root-certs-and-clock.md).

## Ordered recovery
- [ ] Step 3: **Correct the clock first if skewed** — it makes every TLS/cert symptom worse and is the cheapest fix.
- [ ] Step 4: **Determine the source** — if `UseWUServer=1` and WSUS is unreachable, this is an infra escalation (stop; do not keep retrying). Otherwise it's a Microsoft-Update path issue (proxy/TLS/cert).
- [ ] Step 5: **Fix the transport** for Microsoft-Update: WinHTTP proxy + WU bypass (SYSTEM context), enable TLS 1.2, refresh the root cert store — as applicable.
- [ ] Step 6: **Verify** a `Microsoft.Update.Session` search / HTTPS to a WU endpoint succeeds.

## Validation (check your own work before reporting success)
- [ ] The source was correctly identified (WSUS vs Microsoft Update) — a WSUS-unreachable case was escalated, not force-retried.
- [ ] If proxy: the WU bypass is set in the **SYSTEM/WinHTTP** context (not just per-user IE), and the WU endpoints are reachable.
- [ ] A `CreateUpdateSearcher().Search(...)` (or HTTPS GET to a WU endpoint) succeeds with no 407/timeout/cert error.
- [ ] The originally failing scan no longer fails on connectivity.
If any check fails, re-classify — don't disable cert validation or loop-retry against an unreachable WSUS.

## Gotchas
- **`UseWUServer=1` + unreachable WSUS is an infrastructure problem, not an OS fix** — escalate to the WSUS/network owner; repeatedly re-running the patch fails identically and wastes the window. A `UseWUServer=0` fallback is temporary (GPO reverts it) and needs approval.
- **SSM patches as SYSTEM** — a proxy that works for interactive users can 407 for SYSTEM because it has no cached credentials; set the WinHTTP proxy + a WU bypass list, or make the proxy allow the WU URLs unauthenticated.
- **`0x80072F8F` is often a wrong clock, not a cert problem** — check `Get-Date`/NTP before touching the cert store.
- **Cert errors split two ways** — `0x80072F8F` (clock/TLS) vs `0x800B0109`/`0x800B010A` (untrusted root chain); the latter needs a root-store refresh, not a clock fix.
- **WU bypass must be in the WinHTTP (system) proxy**, not only WinINET/IE per-user — the WUA uses WinHTTP.
- **Don't disable TLS certificate validation to "fix" it** — enable TLS 1.2 and trust the correct roots instead.
