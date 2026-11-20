# Changelog

## [1.0.0] - 2026-11-20

### Added

- Initial release of `storage-ebs-expertise` for AWS DevOps Agent.
- Troubleshoot mode with five paths: performance attribution, snapshots, encryption and AWS KMS, volume modification, and billing. Each returns a fixed verdict (Answer, Evidence, Binding layer, Recommendation, Separate findings, Gaps).
- Review mode with six rated areas: capacity and quota headroom, observability, cost hygiene, resilience, encryption posture, and deletion protection. Every Review response begins with a Summary table of the six areas.
- Quota headroom capability: per-quota intake questions with every proposed Service Quotas request and every drafted AWS Support case (IOPS or storage, Fast Snapshot Restore, archived snapshots per volume, in-progress snapshot archives, concurrent copy-volume operations, and Provisioned Rate for Volume Initialization), worded for the customer to answer. The two archive quotas surface their extra questions only when the requested value is more than 25, and keep the change-rate note and the archiving best-practices link. An approval caution on both paths states that an increase is not guaranteed and the amount is decided by AWS.
- Performance path reads `VolumeStalledIOCheck`; a failed check (value 1) is treated as an AWS-side impairment (escalate, never recommend adding IOPS).
- AWS Backup lookup requires `ManagedByAWSBackupOnly=true`, so manual snapshots are not treated as managed by AWS Backup.
- Shared references for read-only data collection, metric math, documented volume-type limits, finding logic, and Amazon EBS service rules.
- Agent types `CHAT` and `INCIDENT_RCA`.
- Read-only by design: mutating actions are proposals only and run only through operator-approved directed actions.
- Least-privilege read-only IAM permissions listed in README.md.
- Evals for chat, investigation, and negative (should not trigger) scenarios.
