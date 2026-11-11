# Changelog

All notable changes to the `aws-fsxn-diagnostics` skill are documented here.

## [1.0.0] - 2026-11-04

Initial release of the Amazon FSx for NetApp ONTAP diagnostics skill.

- **Scope:** read-only, recommend-only diagnosis of Amazon FSx for NetApp ONTAP problems, built
  from AWS control-plane data: FSx configuration, `AWS/FSx` CloudWatch metrics, CloudTrail
  change history, and dependency state in AWS Directory Service, EC2/VPC networking, AWS KMS,
  AWS Backup and AWS Health. Covers all four deployment types (`SINGLE_AZ_1`, `MULTI_AZ_1`,
  `SINGLE_AZ_2`, `MULTI_AZ_2`). Not for FSx for Windows File Server, Lustre, OpenZFS or Amazon EFS,
  and not a best-practices posture audit.
  A concern with no clear symptom gets baseline checks for conditions that cause or precede
  incidents.
- **Six-step workflow:** identify and confirm the ONTAP target without asking for IDs; collect
  configuration and metrics; run the required checks and assign one severity
  (CRITICAL/HIGH/MEDIUM/LOW/INFO) per finding; recommend operator-run remediation; produce the
  report; validate the reply against a self-check list before sending it.
- **Failure-mode playbooks** (`references/REFERENCE.md`): SSD tier exhaustion, throughput-capacity
  undersizing and burst-credit depletion, SSD IOPS bottlenecks, data-tiering misconfiguration,
  SnapMirror failure and lag, NFS/SMB/Active Directory access failures, stuck lifecycle states
  and `AdministrativeActions`, SnapCenter triage, and an escalation-readiness packet for AWS Support.
- **Required checks** (`references/review-checks.md`): AD directory existence and DNS reachability
  for SVM joins, ONTAP's own AD-join error read from CloudTrail (`ontapErrorMessage`) before
  falling back to the ONTAP CLI, a full-configuration retry-join command for an SVM that never
  joined, backup-vs-maintenance window overlap computed field by field, retention and
  snapshot policy per volume, alarm coverage, and CloudTrail change history linked to findings.
- **FSx-ONTAP-specific correctness:** burst balances read as credits, not throttling; capacity
  read from `StorageCapacity` / `StorageUsed` rather than derived from percentages; gen2 hot HA
  pairs located by `FileServer` / `Aggregate`; deployment type checked before any ceiling is
  quoted; false-signal suppression rules (e.g. EC2-level CPU, utilization above 100% while
  bursting, tiering inside its cooling period).
- **Write boundary:** never performs or offers a change; change, resize and delete requests are
  answered with the current values, operator-run steps and their impact; backup or snapshot
  deletion is only suggested after its recovery impact is stated, ahead of any delete command,
  with backup-cost claims grounded in incremental-backup behaviour (including orphaned
  user-initiated backups whose source no longer exists). Read-only checks are made,
  not offered.
- **Severity on every finding:** each finding starts with its label, including lower-priority
  items and findings rewritten from a sub-agent. A narrow question still surfaces any CRITICAL or
  HIGH condition in the collected data.
- **Data-plane hand-off:** where the root cause needs ONTAP-side evidence, the reply includes a
  read-only ONTAP CLI command pack with the real SVM and volume names filled in, for the operator
  to run with their own credentials. The skill never runs ONTAP commands or takes credentials.
- Read-only IAM policy in `automation/`, plus structure, best-practices and functional evaluation
  results.
