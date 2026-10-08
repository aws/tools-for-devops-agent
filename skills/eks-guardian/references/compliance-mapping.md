# EKS Guardian — Compliance Mapping

Maps EKS Guardian findings to industry compliance frameworks. Use this to generate compliance-aware reports for audit teams.

---

## CIS Amazon EKS Benchmark

| CIS Control | EKS Guardian Finding | Section |
|-------------|---------------------|---------|
| 2.1.1 | Enable audit logging | Security — Detective Controls |
| 2.1.2 | Minimize wildcards in Roles/ClusterRoles | Security — IAM |
| 2.1.3 | Minimize access to cluster-admin | Security — IAM |
| 3.1.1 | Client certificate authentication not used | Security — IAM |
| 3.1.2 | Service account token automount disabled | Security — Pod Security |
| 3.1.3 | Access to create pods limited | Security — IAM |
| 3.2.1 | Restrict RBAC subjects to least-privilege | Security — IAM |
| 3.2.2 | Minimize system:anonymous bindings | Security — IAM |
| 4.1.1 | Use HTTPS for kubelet | Networking |
| 4.1.2 | Anonymous auth disabled (kubelet) | Security — IAM |
| 4.2.1 | Restrict network traffic between pods | Networking — NetworkPolicies |
| 4.2.2 | Ensure namespaces have NetworkPolicies | Networking — NetworkPolicies |
| 4.3.1 | Secrets encrypted at rest (KMS) | Security — Encryption |
| 4.3.2 | Use external secrets management | Security — Encryption |
| 4.4.1 | Restrict container privileges | Security — Pod Security |
| 4.4.2 | Containers not run as root | Security — Pod Security |
| 4.5.1 | Limit node access to API server | Security — Infrastructure |
| 4.5.2 | Private endpoint access | Security — Infrastructure |
| 4.6.1 | Apply Pod Security Standards | Security — Pod Security |
| 4.6.2 | Restrict volume types | Security — Pod Security |
| 5.1.1 | Image provenance policies | Security — Image Security |
| 5.1.2 | ECR image scanning enabled | Security — Image Security |
| 5.2.1 | IMDSv2 enforced | Security — Infrastructure |
| 5.3.1 | EKS platform version current | Cluster Upgrades |
| 5.4.1 | IAM roles for service accounts (IRSA/Pod Identity) | Security — IAM |

## SOC 2 (Trust Services Criteria)

| SOC 2 Control | EKS Guardian Finding | Section |
|---------------|---------------------|---------|
| CC6.1 — Logical access security | RBAC least-privilege, no system:anonymous | Security — IAM |
| CC6.2 — Authentication mechanisms | Authentication mode API, no CONFIG_MAP only | Security — IAM |
| CC6.3 — Authorization mechanisms | Access Entries, no wildcard ClusterRoles | Security — IAM |
| CC6.6 — Encryption in transit | VPC endpoints, TLS for service mesh | Networking |
| CC6.7 — Encryption at rest | KMS envelope encryption, EBS encryption | Security — Encryption |
| CC6.8 — Vulnerability management | ECR scan-on-push, addon version currency | Security — Image Security |
| CC7.1 — Monitoring and detection | Control plane logging (all 5 types) | Security — Detective Controls |
| CC7.2 — Anomaly detection | CloudTrail events, AccessDenied monitoring | Security — Detective Controls |
| CC7.3 — Incident response | Pod restarts, OOMKilled, FailedScheduling alerts | Reliability |
| CC8.1 — Change management | Cluster version currency, upgrade insights | Cluster Upgrades |
| A1.1 — Availability controls | Multi-AZ, PDBs, auto-scaling | Reliability |
| A1.2 — Recovery mechanisms | TopologySpreadConstraints, graceful shutdown | Reliability |

## PCI-DSS v4.0

| PCI-DSS Req | EKS Guardian Finding | Section |
|-------------|---------------------|---------|
| 1.2.1 | NetworkPolicies (restrict inter-pod traffic) | Networking |
| 1.3.1 | Private endpoint, no public exposure | Security — Infrastructure |
| 1.4.1 | VPC endpoints for AWS service traffic | Networking |
| 2.2.1 | Pod Security Standards (no privileged) | Security — Pod Security |
| 2.2.2 | Non-root containers, read-only rootfs | Security — Pod Security |
| 3.5.1 | KMS envelope encryption for secrets | Security — Encryption |
| 3.6.1 | KMS key rotation | Security — Encryption |
| 6.2.1 | Addon/image vulnerability scanning | Security — Image Security |
| 6.3.1 | ECR immutable tags, image provenance | Security — Image Security |
| 7.1.1 | RBAC least-privilege, IRSA/Pod Identity | Security — IAM |
| 7.2.1 | Access Entries, no system:masters | Security — IAM |
| 8.2.1 | Authentication mode API, MFA for console | Security — IAM |
| 8.3.1 | IMDSv2 enforced (credential protection) | Security — Infrastructure |
| 10.1.1 | Control plane audit logging | Security — Detective Controls |
| 10.2.1 | CloudTrail EKS API events | Security — Detective Controls |
| 10.3.1 | Log integrity, retention policies | Security — Detective Controls |
| 11.3.1 | VPC Flow Logs enabled | Networking |
| 12.6.1 | Version currency, patching strategy | Cluster Upgrades |

## HIPAA (Security Rule)

| HIPAA Safeguard | EKS Guardian Finding | Section |
|-----------------|---------------------|---------|
| §164.312(a)(1) — Access control | RBAC, Access Entries, least-privilege | Security — IAM |
| §164.312(a)(2)(i) — Unique user identification | IRSA/Pod Identity per workload | Security — IAM |
| §164.312(a)(2)(iv) — Encryption at rest | KMS envelope encryption | Security — Encryption |
| §164.312(b) — Audit controls | All 5 log types, CloudTrail | Security — Detective Controls |
| §164.312(c)(1) — Integrity | ECR immutable tags, image scanning | Security — Image Security |
| §164.312(d) — Authentication | Authentication mode API | Security — IAM |
| §164.312(e)(1) — Transmission security | VPC endpoints, TLS, private endpoint | Networking |
| §164.312(e)(2)(ii) — Encryption in transit | VPC CNI encryption, service mesh TLS | Networking |
| §164.308(a)(5)(ii)(C) — Monitoring | CloudWatch alerts, pod restart monitoring | Reliability |
| §164.308(a)(7) — Contingency plan | Multi-AZ, PDBs, auto-scaling | Reliability |

## NIST 800-53 (Selected Controls)

| NIST Control | EKS Guardian Finding | Section |
|-------------|---------------------|---------|
| AC-2 | Access Entries, RBAC management | Security — IAM |
| AC-3 | Least-privilege roles, no wildcards | Security — IAM |
| AC-4 | NetworkPolicies, VPC segmentation | Networking |
| AC-6 | IRSA/Pod Identity (least-privilege) | Security — IAM |
| AU-2 | Control plane logging (all types) | Security — Detective Controls |
| AU-3 | CloudTrail event detail | Security — Detective Controls |
| AU-6 | CloudWatch log analysis, anomaly detection | Security — Detective Controls |
| CM-6 | Pod Security Standards, SecurityContext | Security — Pod Security |
| IA-2 | Authentication mode API | Security — IAM |
| IA-5 | IMDSv2, credential rotation | Security — Infrastructure |
| SC-7 | Private endpoint, VPC endpoints | Networking |
| SC-8 | Encryption in transit (TLS) | Networking |
| SC-13 | KMS encryption, strong algorithms | Security — Encryption |
| SC-28 | Encryption at rest (EBS, secrets) | Security — Encryption |
| SI-2 | Patching, version currency | Cluster Upgrades |
| SI-4 | Monitoring, alerting, container restarts | Reliability |

---

## Using Compliance Mapping in Reports

When generating a report, include a compliance section if the user mentions any framework:

```markdown
## Compliance Status

### CIS EKS Benchmark
* Controls assessed: 25
* Passing: 18 (72%)
* Failing: 5 (20%)
* Not applicable: 2 (8%)

| Status | Control | Finding | Remediation |
|--------|---------|---------|-------------|
| ❌ FAIL | 4.3.1 | Secrets not encrypted with KMS | Enable KMS envelope encryption |
| ❌ FAIL | 4.2.1 | No NetworkPolicies in default namespace | Apply default-deny policy |
| ✅ PASS | 2.1.1 | Audit logging enabled | — |
```
