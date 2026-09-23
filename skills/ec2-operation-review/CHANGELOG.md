# Changelog

All notable changes to the `ec2-operation-review` skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-05

### Added
- Initial release.
- Read-only EC2 operational review across five Well-Architected pillars:
  Security, Reliability, Performance Efficiency, Cost Optimization, and
  Operational Excellence.
- Discovery of EC2 instances, Auto Scaling groups, EBS volumes, security groups,
  networking, Elastic IPs, and key pairs.
- 14-day CloudWatch metrics analysis with severity thresholds
  (`references/metrics-thresholds.md`), including `CWAgent` memory/disk when the
  CloudWatch agent is present.
- Best-practices checklist (`references/best-practices-checklist.md`) covering
  IMDSv2, security-group exposure, EBS encryption, Multi-AZ ASG, snapshots,
  right-sizing, gp2→gp3, Graviton, and tagging/alarm coverage.
- Per-resource report artifact named `ec2-review-<instance-or-scope>-<YYYY-MM-DD>.md`.
