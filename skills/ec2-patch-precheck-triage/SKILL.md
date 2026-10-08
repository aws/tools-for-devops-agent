---
name: ec2-patch-precheck-triage
description: >-
  Triage AWS patch-operation readiness and outcomes across Linux and Windows EC2
  around a maintenance window — resolve pre-patch prerequisite-check failures,
  decide whether a bare failure is a transient cosmetic scan error or a genuine
  one, handle SSM-unreachable instances that can't be patched at all, and fix
  patch runs that time out or exceed the window. Use when the
  CheckPatchingPrerequisites automation reports Failed, a patch operation returns
  a bare "failed to run commands: exit status 1" while the instance is already
  compliant, an instance shows PingStatus ConnectionLost/Inactive, or a run
  reports TimedOut/DeliveryTimedOut. The value is triage order and gating — fix
  connectivity and repo health first because dependent checks are skipped
  otherwise; only auto-close a failure when a fresh scan proves FailedCount=0 and
  MissingCount=0; an SSM-unreachable instance has no remote path (control-plane
  checks and escalation only); and a timeout is window-sizing, not a bug.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Linux, Windows Server, Patching, Operations"
  domains: "EC2, SSM, Patch Manager, prechecks, OpsItems, maintenance windows"
  platforms: "Linux, Windows"
  supported-os: "Amazon Linux 2/2023, RHEL, Ubuntu, SLES, Oracle Linux, CentOS, Windows Server 2012 R2-2025"
  operation-type: "read-and-mutate"
---

# Triage patch readiness and outcomes (cross-platform)

## When this applies
The question is about the patch **operation/workflow**, not a specific in-OS root
cause: a prerequisite check failed, a run failed with no useful error while the
instance looks compliant, an instance is unreachable via SSM, or a run timed out
/ blew the window. If a specific package-manager, store, connectivity, or policy
error is named, route to the matching platform skill instead — this skill decides
*which* situation you're in and gates the next action.

## The key insight: triage order and gates matter more than any single fix
- **Precheck failures have dependencies — fix the right thing first.** If connectivity (S3/IMDS/
  credentials) or `UpdateServiceConfigurationStatus` (repo/subscription health) is failing, fix
  **those first** — several dependent checks auto-resolve or are **skipped** while they're unhealthy,
  so chasing them in isolation wastes effort. On Windows, a disk-space failure is often **WMI
  repository corruption** giving a false reading — check WMI before expanding a volume.
- **Not every failure is real — gate before auto-closing.** A bare `failed to run commands: exit
  status 1` with the instance **already compliant** (`FailedCount=0 && MissingCount=0`, no patches in
  Failed state) is a **transient post-scan cosmetic** failure — auto-close the OpsItem **with
  evidence**. But `FailedCount>0` or `MissingCount>0` means a **genuine** failure — do NOT close;
  route to the matching root-cause skill. `InstalledPendingRebootCount>0` (otherwise clean) → reboot scheduling, not a failure.
- **SSM-unreachable = no remote path at all.** If `PingStatus != Online`, Patch Manager can't scan or
  patch it and you have **no** Run Command / Session Manager into it. Triage is **control-plane only**
  (EC2 state, IAM instance profile, network) + customer escalation to restore the agent. The one
  remotely-fixable cause is a **missing IAM instance profile**. Hybrid (`mi-`) ghosts with stale
  LastPing inflate the non-compliant count — **exclude** them from the run, don't deregister.
- **A timeout is window-sizing/bandwidth, not a bug.** Split security-first, enable parallel
  downloads, pre-stage packages, or lengthen the window — after fixing any interrupted state.

## Diagnosis first
- [ ] Step 1: Classify the triage case:
  - a precheck reported Failed → read [precheck failures](reference/precheck-failures.md).
  - a bare failure but instance looks compliant → read [transient vs genuine](reference/transient-vs-genuine.md).
  - `PingStatus` not Online / unreachable → read [ssm unreachable](reference/ssm-unreachable.md).
  - TimedOut / window exceeded / many packages → read [timeout and window sizing](reference/timeout-and-window.md).
- [ ] Step 2: For the transient-vs-genuine and unreachable cases, run the **mandatory gate** (compliance state / PingStatus) BEFORE any close or exclude.

## Ordered recovery
- [ ] Step 3: **Precheck:** fix connectivity + repo health first, then re-run prechecks so dependent checks clear; on Windows verify WMI before trusting disk-space.
- [ ] Step 4: **Outcome gate:** confirm compliance (`FailedCount`/`MissingCount`) before auto-closing a bare failure; route genuine failures to the root-cause skill.
- [ ] Step 5: **Unreachable:** capture control-plane facts, fix a missing instance profile if that's the cause, exclude the instance from the current run, escalate to the owner to restore the agent.
- [ ] Step 6: **Timeout:** clear interrupted state, then reduce metadata/parallelize/pre-stage/split or lengthen the window.

## Validation (check your own work before reporting success)
- [ ] Precheck: the failing check(s) now pass on a **fresh** re-run, and connectivity/repo health were fixed before dependent checks.
- [ ] Auto-close: an OpsItem was only resolved after a fresh scan proved `FailedCount=0 && MissingCount=0` with the resolution note citing that evidence; no genuine failure was closed.
- [ ] Unreachable: the instance was excluded (not counted as a hard failure) and the owner escalation captured the control-plane facts; no hybrid instance was deregistered.
- [ ] Timeout: interrupted state was cleared first, and the recommendation matches the pending volume (split if 100+).
If any check fails, re-classify — don't auto-close a real failure or treat an unreachable ghost as patchable.

## Gotchas
- **Fix connectivity/repo health before other prechecks** — dependent checks are skipped or auto-resolve; the dry-run check is even skipped while `UpdateServiceConfigurationStatus` is unhealthy.
- **Windows disk-space failure is often WMI corruption** — `winmgmt /verifyrepository` before expanding a volume.
- **Never auto-close a failure without the compliance gate** — a bare `exit status 1` can be cosmetic (already compliant) OR genuine; only `FailedCount=0 && MissingCount=0` (and no Failed-state patches) permits an evidence-backed close.
- **SSM-unreachable has no in-guest path** — you cannot Run Command or Session Manager into it; only control-plane checks + customer escalation. Don't pretend an in-guest fix is possible.
- **Don't deregister hybrid `mi-` ghosts** — flag stale activations for customer review and exclude them from the run; deregistration is the customer's call.
- **A timeout isn't a defect** — it's window duration vs patch volume/bandwidth; lengthen the window or split security-first rather than "debugging" the patch.
