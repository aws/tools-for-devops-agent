# Changelog

## [1.0.0] - 2026-09-22

### Added
- Initial release of the database-audit-automation skill.
- Guided CloudFormation deployment of the Database Auditing Automation Solution.
- Aurora PostgreSQL audit configuration via pgAudit (parameter group + setup SQL).
- RDS SQL Server audit configuration via native SQL Server audit (option group + setup SQL).
- CloudWatch Logs export enablement for audit log streaming.
- Audit log collection and normalization pipeline (CloudWatch Logs → Lambda → S3).
- AI-based anomaly detection over recent audit activity using Amazon Bedrock (Claude 3.5 Sonnet).
- Compliance report generation (SOX, PCI-DSS, HIPAA) with SNS alerting for high-severity findings.
- Audit log pipeline troubleshooting guidance.
