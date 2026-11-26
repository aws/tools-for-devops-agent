# RDS / Aurora Security Best Practices Checklist

## Encryption at Rest

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 1 | Storage encryption enabled | `StorageEncrypted=true` | HIGH |
| 2 | Customer-managed KMS key (CMK) | CMK preferred over AWS-managed | LOW |
| 3 | CMK automatic rotation enabled | Key rotation = enabled | LOW |
| 4 | Snapshot encryption | All snapshots encrypted | HIGH |

## Encryption in Transit

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 5 | SSL/TLS enforced (PostgreSQL) | `rds.force_ssl=1` | MEDIUM |
| 6 | SSL/TLS enforced (MySQL) | `require_secure_transport=ON` | MEDIUM |
| 7 | Minimum TLS version | TLSv1.2 or higher | MEDIUM |
| 8 | Strong cipher suites | No weak ciphers (RC4, DES, 3DES) | LOW |

## Authentication & Access Control

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 9 | IAM database authentication | `IAMDatabaseAuthenticationEnabled=true` | MEDIUM |
| 10 | Secrets Manager for master password | Managed by Secrets Manager | MEDIUM |
| 11 | Secrets Manager rotation | Automatic rotation enabled | MEDIUM |
| 12 | Password encryption (PostgreSQL) | SCRAM-SHA-256 (not MD5) | MEDIUM |
| 13 | No superuser application access | App users don't have `rds_superuser` | HIGH |
| 14 | Principle of least privilege | Role-based access, no wildcard grants | MEDIUM |

## Network Security

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 15 | Public accessibility | `PubliclyAccessible=false` | CRITICAL |
| 16 | Security group — no open ingress | No `0.0.0.0/0` on DB port | CRITICAL |
| 17 | Security group — restricted sources | Only known application CIDR/SGs | MEDIUM |
| 18 | VPC placement | Database in private subnet | HIGH |
| 19 | DB subnet group — multi-AZ | Subnets span ≥ 2 AZs | MEDIUM |

## Audit Logging

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 20 | Database audit logging enabled | pgaudit (PG) / audit plugin (MySQL) | MEDIUM |
| 21 | Error logs exported to CloudWatch | In `EnabledCloudwatchLogsExports` | MEDIUM |
| 22 | Slow query logs exported | Exported for performance forensics | LOW |
| 23 | Connection logging (PostgreSQL) | `log_connections=on`, `log_disconnections=on` | LOW |
| 24 | Statement logging | `log_statement` or `pgaudit.log` configured | MEDIUM |

## Compliance Considerations

| Standard | Key Requirements for RDS |
|----------|------------------------|
| PCI-DSS | Encryption at rest + in transit, audit logging, network segmentation |
| HIPAA | Encryption, access logging, BAA in place, CMK rotation |
| SOC 2 | Access controls, monitoring, change management |
| GDPR | Encryption, access logging, data residency (region) |
