# Changelog

## [1.0.0] - 2026-11-20

### Added

- Initial release of `storage-ebs-operations` for AWS DevOps Agent.
- Troubleshoot mode with five paths: performance attribution, snapshots, encryption and AWS KMS, volume modification, and billing. Each returns a fixed verdict (Answer, Evidence, Binding layer, Recommendation, Separate findings, Gaps).
- Review mode with six rated areas: capacity and quota headroom, observability, cost hygiene, resilience, encryption posture, and deletion protection. Every Review response begins with a Summary table of the six areas.
- Quota headroom capability: per-quota intake questions with every proposed Service Quotas request and every drafted AWS Support case (IOPS or storage, Fast Snapshot Restore, archived snapshots per volume, in-progress snapshot archives, concurrent copy-volume operations, and Provisioned Rate for Volume Initialization), worded for the customer to answer. The two archive quotas surface their extra questions only when the requested value is more than 25, and point to an archive cost comparison and the archiving best-practices link. An approval caution on both paths states that an increase is not guaranteed and the amount is decided by AWS.
- Performance path reads `VolumeStalledIOCheck`; a failed check (value 1) is treated as an AWS-side impairment (escalate, never recommend adding IOPS).
- Performance path reads the CloudWatch exceeded checks `VolumeIOPSExceededCheck`, `VolumeThroughputExceededCheck`, `InstanceEBSIOPSExceededCheck` and `InstanceEBSThroughputExceededCheck` early, with both `VolumeId` and `InstanceId` for the volume checks. A value of 1 is direct evidence that the volume or instance limit binds, and "no datapoints" is reported as a gap, not as 0.
- Amazon EBS detailed performance statistics are given as a step the customer runs on the instance, with the documented `nvme amzn stats`, `ebsnvme stats` and `nvme_amzn.exe stats` commands, when the 1-minute CloudWatch data is inconclusive (for example suspected micro-bursting or an Indeterminate verdict). The agent never runs it.
- Performance path names AWS-side impairment only with a direct signal (failed `VolumeStalledIOCheck`, impaired volume status, or an open AWS Health event). Rising latency with falling IOPS and no direct signal or running AWS FIS experiment is reported as Indeterminate, with the customer pointed to the AWS Health Dashboard and the volume status checks, and no extra provisioning.
- An Indeterminate result states "Binding layer: Indeterminate" with the answer to the user's question first, then a short list of candidate causes without overlap, each with its supporting observations and the check that confirms it or rules it out (volume status checks, `VolumeStalledIOCheck`, AWS Health, AWS FIS, the shared instance EBS limit, a change in workload I/O size). AWS-side impairment is never named as the cause without a direct signal.
- When the user gives the values and asks to treat them as given, the skill reasons from those values and does not query unrelated account resources.
- Performance verdicts show a side-by-side limits table (per-volume demand against the volume limit, summed demand against the instance EBS baseline, which one binds, and the exact target with its computation) and the recent history (alarm history, modification history, earlier occurrences).
- Investigations open the root cause finding with "Binding layer:" and put the binding numbers, the exceeded checks, the history and the exact recommended change, marked as a proposal for operator approval, in that finding. The symptom carries the alarm impact and onset. Supporting observations are linked to each finding, gaps only to the findings they affect, and the investigation stays on the resource the user asked about.
- Performance history covers earlier peaks at the same ceiling and the demand trend over a longer window.
- Every proposed change gives the exact AWS CLI command, expected effect, the modifications left in the 24-hour window, rollback, cost direction, and a plain statement that a typed approval in chat is not approval.
- Encryption path gives exact commands for each fix (enable the key, cancel key deletion, key policy statements, or moving the data to another key).
- Snapshot answers open with every snapshot, its tier and the evidence behind it, and the evidence table shows source volume state, AMI reference, sharing, lock, Amazon Data Lifecycle Manager, AWS Backup and Recycle Bin for each snapshot.
- Billing path states the gp3 included baseline and always reads Amazon Data Lifecycle Manager, AWS Backup and Recycle Bin.
- Chat answers return the finished verdict or report in one reply instead of a "started" message from a background sub-agent or a question that holds back the proposal.
- Snapshot path classifies snapshots by lineage. A snapshot whose source volume is gone is listed as Needs owner review, because it may be the only remaining copy of the data. No snapshot is recommended for deletion.
- Deletes are manual steps for the customer to run with their own credentials after the owner confirms, never directed actions.
- Modification history and the 24-hour modification count come from the optional AWS CloudTrail `ModifyVolume` events, because `DescribeVolumesModifications` returns only the latest modification per volume. The rule of up to 4 modifications per volume in a rolling 24-hour window is stated whenever a modification is in progress or proposed.
- AWS Backup lookup requires `ManagedByAWSBackupOnly=true`, so manual snapshots are not treated as managed by AWS Backup.
- Gotchas section in SKILL.md for Amazon EBS API and metric behavior that is easy to misread.
- Shared references for read-only data collection, metric math, documented volume-type limits, finding logic, and Amazon EBS service rules.
- Agent types `CHAT` and `INCIDENT_RCA`.
- Read-only by design: mutating actions such as raising IOPS or modifying a volume are proposals only and run only through directed actions approved on the approval card. A typed approval in chat is not approval.
- Least-privilege read-only IAM permissions listed in README.md, and an `EnableStorageEbsOperations` option in `cloudformation/devops-agent-skill-policies` for the actions that `AIDevOpsAgentAccessPolicy` does not grant.
- README Limitations note that Amazon EBS Multi-Attach volumes are not covered.
- Evals for chat, investigation, an Indeterminate performance case, and negative (should not trigger) scenarios.
