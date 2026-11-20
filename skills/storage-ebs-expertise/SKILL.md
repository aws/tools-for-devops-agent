---
name: storage-ebs-expertise
description: >
  Use this skill when a user wants to know why Amazon EBS storage is slow, why an
  EBS alarm fired, or whether their EBS setup is production-ready, even if they only
  say an app or database on EC2 got slower or ask whether to add IOPS. Use it for
  alarms on AWS/EBS metrics (VolumeReadOps, VolumeWriteOps, VolumeReadBytes,
  VolumeWriteBytes, VolumeQueueLength, VolumeTotalReadTime/WriteTime,
  VolumeAvgReadLatency, VolumeStalledIOCheck, BurstBalance) or
  EBSIOBalance%/EBSByteBalance%; for sizing
  IOPS or throughput changes; for a volume modification that looks stuck or failed;
  for deciding which snapshots or AMIs are safe to delete or how to recover them;
  for KMS errors on encrypted volumes; for EBS quota or limit errors; for a jump in
  the EBS bill; and for a pre-launch EBS review. Do not use it for S3, EFS, FSx,
  instance store, or EC2 problems unrelated to EBS.
metadata:
  author: dewavic
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "Amazon EBS, Amazon EC2, Amazon CloudWatch, AWS KMS, AWS CloudTrail, Service Quotas"
  aws-devops-agent-skills.technical-domains: "Storage"
---
# Amazon EBS Expertise

Use this skill to troubleshoot Amazon EBS problems and to review an account's Amazon EBS setup. It has two modes. Troubleshoot mode answers "something is wrong, why?" through one of five paths and returns a fixed verdict. Review mode answers "is my EBS setup healthy before something goes wrong?" and returns a rated report. Both modes are read-only and share the same volume-type rules, instance limits and service rules. Load only the reference files the request needs.

## When to Use This Skill

- Storage-related slowness, timeouts or high I/O latency on an Amazon EC2 instance.
- An alarm on AWS/EBS metrics or on instance `EBSIOBalance%` / `EBSByteBalance%`.
- A volume modification that looks stuck, failed, or did not improve performance.
- Snapshot, AMI, Amazon Data Lifecycle Manager, AWS Backup or Recycle Bin questions, including which snapshots are safe to delete.
- Encrypted-volume access errors and AWS KMS questions for Amazon EBS.
- Amazon EBS cost increases, idle or over-provisioned volumes.
- An operation that failed on an Amazon EBS quota, or "how close am I to my limits?"
- A request to review Amazon EBS posture before a launch, migration or peak event.

Do not use this skill for Amazon S3, Amazon EFS, Amazon FSx, instance store, or Amazon EC2 issues unrelated to Amazon EBS.

## Prerequisites

- Read-only permissions for the APIs listed in [references/data-collection.md](references/data-collection.md).
- AWS CloudTrail access is optional. The skill works without it.
- Mutating changes run only through directed actions (Agent Actions in the Operator Web App), which need their own role and operator approval on the approval card.

---

## Workflow

Copy this checklist and tick each step as you finish it:

- [ ] Step 1: Classify the request
- [ ] Step 2: Load the shared references
- [ ] Step 3: Run the path and draft the report
- [ ] Step 4: Check the draft, fix it, then present it

## Step 1: Classify the Request

| The user says or the alarm shows | Mode and path | Load |
|---|---|---|
| "My app is slow", high latency, an alarm on AWS/EBS metrics, `EBSIOBalance%` or `EBSByteBalance%`, "is it storage?", "how much IOPS do I need?" | Troubleshoot: performance | [references/troubleshoot-performance.md](references/troubleshoot-performance.md) |
| "My modification is stuck", "the new IOPS has not taken effect", a `ModifyVolume` error, resize, gp2 to gp3, extend the file system, shrink or cancel | Troubleshoot: volume modification | [references/troubleshoot-volume-modification.md](references/troubleshoot-volume-modification.md) |
| "Which snapshots can I delete?", snapshot copy did not arrive, AMI creation stuck, recover a deleted snapshot or volume, Amazon Data Lifecycle Manager, Recycle Bin | Troubleshoot: snapshots | [references/troubleshoot-snapshots.md](references/troubleshoot-snapshots.md) |
| "I can't attach my KMS-encrypted volume", share an encrypted snapshot or AMI, encryption by default, re-encrypt a volume | Troubleshoot: encryption | [references/troubleshoot-encryption.md](references/troubleshoot-encryption.md) |
| "Why did my EBS bill go up?", unexplained charges, idle or unattached volumes, pricing model | Troubleshoot: billing | [references/troubleshoot-billing.md](references/troubleshoot-billing.md) |
| "Limit exceeded", a quota error, "how close am I to my limits?" | Shared capability: quota headroom | [Capacity and quota headroom](references/review-operational.md#capacity-and-quota-headroom) |
| "Are my volumes backed up?" | Review: resilience area | [Resilience](references/review-operational.md#resilience) |
| "Review my EBS setup", "is my storage production-ready?" | Review | [references/review-operational.md](references/review-operational.md) and [references/review-report-format.md](references/review-report-format.md) |

If a request fits more than one row, answer the question the user asked first and treat the rest as Separate findings.

## Step 2: Load the Shared References

- Always load [references/data-collection.md](references/data-collection.md) (read-only APIs, metric math, errors and fallbacks).
- Load [references/metrics-thresholds.md](references/metrics-thresholds.md) for any metric judgement.
- Load [references/finding-logic.md](references/finding-logic.md) for the verdict, the binding layer, escalation and review ratings.
- Load [references/ebs-best-practices.md](references/ebs-best-practices.md) for service rules (Elastic Volumes, instance limits, quotas, snapshots, quirks).

## Step 3: Run the Path and Draft the Report

Follow the numbered procedure in the loaded path. Discover every value from the APIs. Then draft the report in the format below.

### Troubleshoot verdict format

1. **Answer:** the asked question, answered first.
2. **Evidence:** values with units and time window.
3. **Binding layer:** Volume, Instance, Burst credits, Quota, Not EBS, AWS-side impairment, or Not applicable.
4. **Recommendation:** exact parameters, or "No change".
5. **Separate findings:** other true facts that do not change the Answer.
6. **Gaps:** what could not be checked and why.

Review mode uses the rated report in [references/review-report-format.md](references/review-report-format.md). Every Review mode response MUST begin with its Summary table, which rates all six areas (capacity and quota headroom, observability, cost hygiene, resilience, encryption posture, deletion protection), even when an area has no findings or is `Indeterminate`. The Summary table is required, not optional. Do not open with prose or an offer to run the review; start with the table, then the per-area detail.

## Step 4: Check the Draft Before Presenting It

Review the draft from Step 3 against these checks. Fix anything that fails, then present it.

- Every number under Evidence came from an API call made in this session, has its unit and time window, and matches the resource ID it is attributed to.
- The Binding layer agrees with the Evidence: the named layer is the one at its limit, and the other layers were checked and shown to have headroom.
- Any Recommendation stays within the instance's EBS baseline and the volume type's documented limits, and it is not more provisioning for an impairment.
- Every "safe to delete" verdict is backed by the checks its tier requires; if one of those checks failed, the item is not safe to delete.
- A review answer starts with the Summary table and rates all six areas.
- Every API that failed or was not called is listed under Gaps.

---

## Critical Rules

- **Read-only.** Changes (ModifyVolume, DeleteSnapshot, quota requests) are proposed with exact parameters, cost and rollback, and run only through operator-approved directed actions (Agent Actions in the Operator Web App). Approval is given only on the approval card. A typed "approve" in chat is not approval.
- **Discover, don't assume:** read every configuration value from the APIs.
- **Rule EBS in or out before tuning it.**
- **Answer the asked question first;** other findings go under "Separate findings".
- **Review mode starts with the Summary table.** Every Review mode response begins with the Summary table of all six rated areas. The table is required, not optional.
- **Always check the instance layer** and size changes within the instance's EBS **baseline**.
- **Never recommend more provisioning for an impairment.**
- **Use current service rules:** up to 4 Elastic Volumes modifications per volume per rolling 24 hours. There is no fixed waiting period between modifications; the next one is allowed once the previous one completes.
- **No interpretation without data:** report what couldn't be checked and use fallbacks. AWS CloudTrail is optional; `DescribeVolumesModifications` is the change record.
- **Units:** MiB/s for throughput, stated every time.
- **Escalate** on scope signals or when the investigation can't explain the symptom.

## Error Handling

Errors, gated reads and missing metrics are handled with the fallback table in [references/data-collection.md](references/data-collection.md). Name every failed API under Gaps and continue with the rest.

## References

- [references/troubleshoot-performance.md](references/troubleshoot-performance.md): performance attribution, the live-tested procedure
- [references/troubleshoot-snapshots.md](references/troubleshoot-snapshots.md): safe-to-delete tiers, copy, AMI, lifecycle and recovery
- [references/troubleshoot-encryption.md](references/troubleshoot-encryption.md): AWS KMS access, sharing encrypted snapshots, default encryption
- [references/troubleshoot-volume-modification.md](references/troubleshoot-volume-modification.md): modification states, limits, errors, sizing, file system extension
- [references/troubleshoot-billing.md](references/troubleshoot-billing.md): cost breakdown, change records, right-sizing
- [references/review-operational.md](references/review-operational.md): Review mode checks and the quota headroom capability
- [references/data-collection.md](references/data-collection.md): read-only API allowlist, metric math, errors, fallbacks
- [references/finding-logic.md](references/finding-logic.md): verdict template, binding layer, escalation, review ratings
- [references/metrics-thresholds.md](references/metrics-thresholds.md): documented limits and how to judge each volume type
- [references/review-report-format.md](references/review-report-format.md): rated report layout for Review mode
- [references/ebs-best-practices.md](references/ebs-best-practices.md): volume-type rules, quotas, Elastic Volumes rules, quirks
