# Changelog

## [1.0.0] - 2026-11-20

### Added

- Initial release of `storage-ebs-expertise` for AWS DevOps Agent.
- Troubleshoot mode with five paths: performance attribution, snapshots, encryption and AWS KMS, volume modification, and billing. Each returns a fixed verdict (Answer, Evidence, Binding layer, Recommendation, Separate findings, Gaps).
- Review mode with six rated areas: capacity and quota headroom, observability, cost hygiene, resilience, encryption posture, and deletion protection. Every Review response begins with a Summary table of the six areas.
- Quota headroom capability: per-quota intake questions with every proposed Service Quotas request and every drafted AWS Support case (IOPS or storage, Fast Snapshot Restore, archived snapshots per volume, in-progress snapshot archives, concurrent copy-volume operations, and Provisioned Rate for Volume Initialization), worded for the customer to answer. The two archive quotas surface their extra questions only when the requested value is more than 25, and point to an archive cost comparison and the archiving best-practices link. An approval caution on both paths states that an increase is not guaranteed and the amount is decided by AWS.
- Performance path reads `VolumeStalledIOCheck`; a failed check (value 1) is treated as an AWS-side impairment (escalate, never recommend adding IOPS).
- Performance path names AWS-side impairment only with a direct signal (failed `VolumeStalledIOCheck`, impaired volume status, or an open AWS Health event). Rising latency with falling IOPS and no direct signal or running AWS FIS experiment is reported as Indeterminate, with the customer pointed to the AWS Health Dashboard and the volume status checks, and no extra provisioning.
- Snapshot path classifies snapshots by lineage. A snapshot whose source volume is gone is listed as Needs owner review, because it may be the only remaining copy of the data. No snapshot is recommended for deletion.
- Deletes are manual steps for the customer to run with their own credentials after the owner confirms, never directed actions.
- Modification history and the 24-hour modification count come from the optional AWS CloudTrail `ModifyVolume` events, because `DescribeVolumesModifications` returns only the latest modification per volume.
- AWS Backup lookup requires `ManagedByAWSBackupOnly=true`, so manual snapshots are not treated as managed by AWS Backup.
- Gotchas section in SKILL.md for Amazon EBS API and metric behavior that is easy to misread.
- Shared references for read-only data collection, metric math, documented volume-type limits, finding logic, and Amazon EBS service rules.
- Agent types `CHAT` and `INCIDENT_RCA`.
- Read-only by design: mutating actions such as raising IOPS or modifying a volume are proposals only and run only through directed actions approved on the approval card. A typed approval in chat is not approval.
- Least-privilege read-only IAM permissions listed in README.md, and an `EnableStorageEbsExpertise` option in `cloudformation/devops-agent-skill-policies` for the actions that `AIDevOpsAgentAccessPolicy` does not grant.
- README Limitations note that Amazon EBS Multi-Attach volumes are not covered.
- Evals for chat, investigation, an Indeterminate performance case, and negative (should not trigger) scenarios.
