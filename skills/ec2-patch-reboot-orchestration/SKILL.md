---
name: ec2-patch-reboot-orchestration
description: >-
  Use this skill when an AWS patch (Linux or Windows EC2) has a reboot-timing
  problem rather than a patch-content failure. Use it when an instance is
  NON_COMPLIANT only because patches are installed pending a reboot
  (InstalledPendingRebootCount greater than zero with FailedCount=0 and
  MissingCount=0), patches sit in InstalledPendingReboot state, a Security Hub
  SSM.2 finding stays open after a successful install, or a patch fails
  immediately with "A system shutdown is in progress" / exit status 0xffffffff —
  including when the user only asks whether to reboot, retry, or clear
  pending-reboot compliance. These are reboot-timing states, not patch failures: a
  pending-reboot instance needs a controlled reboot in an approved window, only if
  the run used RebootIfNeeded — never re-patch or override a NoReboot policy; a
  shutdown-in-progress race needs a bounded wait for boot then a single retry,
  never an indefinite loop or a retry into a rebooting host. Apply it to route the
  reboot situation to the safe action.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Linux, Windows Server, Patching, Operations"
  domains: "EC2, SSM, Patch Manager, reboot, compliance, Security Hub"
  platforms: "Linux, Windows"
  supported-os: "All AMS-supported Linux; Windows Server 2012 R2, 2016, 2019, 2022, 2025"
  operation-type: "read-and-mutate"
---

# Orchestrate patch reboots and reboot-timing races (cross-platform)

## When this applies
The situation is about the **reboot** around a patch, not a patch-content failure:
either the instance is only non-compliant because a reboot is pending, or a patch
run collided with an in-progress shutdown/reboot. If patches are genuinely
Missing or Failed, that's a root-cause skill, not this one.

## The key insight: these are reboot-TIMING states, not patch failures — act safely
- **Pending-reboot ≠ failure** (`InstalledPendingRebootCount>0`, `FailedCount=0`, `MissingCount=0`,
  patches in `InstalledPendingReboot`, Security Hub **SSM.2** open): the patches installed but the
  run used **`RebootOption=NoReboot`** (deliberate in environments that control reboots separately to
  avoid unplanned downtime). The fix is a **controlled reboot in an approved change window**, NOT a
  re-patch. **Only reboot if the failed execution's `RebootOption` was `RebootIfNeeded`** — if it was
  `NoReboot`, that's the customer's deferred-reboot policy; don't make a disruptive change. Reboot
  cluster/quorum members **one at a time**.
- **"A system shutdown is in progress" is a race, not a fault** (`exit status 0xffffffff`, fails
  immediately at patch start with no install attempted, often right after a prior cycle's reboot): the
  patch started while the OS was **already rebooting**. Windows rejects new ops during shutdown. It's
  transient — do a **bounded wait** (≤ ~10 polls / ~10 min) for the agent to come back Online, confirm
  `RebootPending=False` + fresh uptime, then allow the next scheduled cycle / a **single** retry.
  **Never loop indefinitely and never retry into a still-rebooting host**; if it's not Online after the
  bounded wait, it's impaired — route to SSM-connectivity triage, don't keep retrying.

## Diagnosis first
- [ ] Step 1: Classify the reboot situation:
  - non-compliant only due to pending reboot / SSM.2 open → read [pending reboot](reference/pending-reboot.md).
  - "A system shutdown is in progress" / 0xffffffff at patch start → read [reboot race](reference/reboot-race.md).
- [ ] Step 2: Run the compliance gate — confirm `FailedCount=0 && MissingCount=0` (pending-reboot) or check `PingStatus`/uptime (race) BEFORE acting.

## Ordered recovery
- [ ] Step 3: **Pending-reboot:** confirm a reboot is actually pending in-guest, confirm an approved change window exists and the run used `RebootIfNeeded`, then perform ONE controlled reboot (cluster members one at a time).
- [ ] Step 4: **Reboot race:** run the bounded wait for boot to complete; do not touch the instance beyond waiting.
- [ ] Step 5: **Confirm readiness** — `RebootPending=False` + fresh uptime (race) / `PendingReboot=0` (pending-reboot) before declaring done or allowing a retry.
- [ ] Step 6: **Verify** compliance clears (`PendingReboot=0, Failed=0, Missing=0`) and let Security Hub SSM.2 auto-resolve on its next evaluation.

## Validation (check your own work before reporting success)
- [ ] Pending-reboot: you confirmed it's purely reboot-pending (`Failed=0, Missing=0`) AND the run used `RebootIfNeeded` AND an approved window exists before any reboot — you never re-patched or rebooted a `NoReboot` policy instance without approval.
- [ ] Race: the wait was **bounded** (no indefinite loop) and you never issued a retry while `RebootPending=True` or the agent was offline.
- [ ] After a controlled reboot, `PendingReboot=0`/`RebootPending=False` and compliance is clean.
- [ ] Cluster/quorum members were rebooted one at a time.
If any check fails, re-classify — a still-Missing/Failed count means it's a real patch problem, not a reboot state.

## Gotchas
- **A pending reboot is not a patch failure** — don't re-patch; schedule ONE controlled reboot in an approved window. Security Hub SSM.2 clears on its next evaluation after the reboot.
- **Respect `RebootOption`** — only reboot if the failed run used `RebootIfNeeded`; a `NoReboot` run reflects a deliberate deferred-reboot policy, so a reboot is a disruptive change requiring approval.
- **Never loop retries on a shutdown-in-progress race** — use a bounded wait (~10 polls) for boot, then a single retry; repeated retries won't fix an orchestration race.
- **Never retry a patch into a still-rebooting instance** — confirm `RebootPending=False` and fresh uptime first, or you just re-hit the same race.
- **If a raced instance never returns Online**, it's impaired, not racing — route to SSM-connectivity triage instead of retrying.
- **Reboot cluster/quorum members one at a time** — a simultaneous reboot risks quorum loss.
- **Prevent recurrence** — stagger reboot windows vs patch invocations (or `NoReboot` install + a controlled reboot after) and stop other automation from restarting instances during the window.
