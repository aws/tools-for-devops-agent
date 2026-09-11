# Security Network Nodes remediations — shard 03

Canonical IDs: `SM1,SM2,SM3,SM4,SM5,SM6,SM7,S32`

### SM1 — KMS envelope encryption
**Why / fix:** Secrets should be envelope-encrypted with a customer-managed KMS key, not just etcd-at-rest. Verify: `aws eks describe-cluster --name ${CLUSTER} --query cluster.encryptionConfig`. Enable if absent. Link: [Data encryption and secrets management](https://docs.aws.amazon.com/eks/latest/best-practices/data-encryption-and-secrets-management.html).

### SM2 — Audit logging enabled
**Why / fix:** The API audit log is the primary forensic record. Verify: `aws eks describe-cluster --name ${CLUSTER} --query cluster.logging` (audit type on). Link: [Auditing and Logging](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html).

### SM3 — Endpoint exposure
**Why / fix:** A public API endpoint open to `0.0.0.0/0` is internet-reachable. Verify: `aws eks describe-cluster --name ${CLUSTER} --query cluster.resourcesVpcConfig` — restrict `publicAccessCidrs` or go private. Link: [Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html).

### SM4 — EBS/EFS encryption at rest
**Why / fix:** Default StorageClass should set `encrypted: true`; EFS file systems should be encrypted. Check the SC parameters and EFS config. Link: [Data encryption and secrets management](https://docs.aws.amazon.com/eks/latest/best-practices/data-encryption-and-secrets-management.html).

### SM5 — ECR immutable tags + Inspector
**Why / fix:** `imageTagMutability=IMMUTABLE` prevents tag overwrite; Inspector ECR scanning catches CVEs. Verify in ECR repo settings. Link: [Image Security](https://docs.aws.amazon.com/eks/latest/best-practices/image-security.html).

### SM6 — mTLS between workloads
**Why / fix:** Sensitive east/west traffic should be mutually authenticated/encrypted via a service mesh (Istio PeerAuthentication STRICT, or Linkerd). Confirm mesh mTLS posture. Link: [Network Security](https://docs.aws.amazon.com/eks/latest/best-practices/network-security.html).

### SM7 — Node IAM least privilege
**Why / fix:** The node instance role should carry only required managed policies (or the Auto Mode minimal policy) — not broad admin. Review the role in IAM. Link: [Identity and Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html).

### S32 — StorageClass encryption enabled
**Why it matters:** A StorageClass without `parameters.encrypted: "true"` provisions **unencrypted** EBS volumes for every PVC that uses it — silent data-at-rest exposure.
**Steps:** Set `parameters.encrypted: "true"` on all provisioning StorageClasses; add `parameters.kmsKeyId` for a customer-managed key.
**Snippet:**
```yaml
parameters: { type: gp3, encrypted: "true", kmsKeyId: ${KMS_KEY_ARN} }
```
**References:**
- [EKS Best Practices — Data Encryption & Secrets Management](https://docs.aws.amazon.com/eks/latest/best-practices/data-encryption-and-secrets-management.html)

