# Resilience remediations — shard 04

Canonical IDs: `R19,R20,R21,R22`

### R19 — StorageClass volumeBindingMode = WaitForFirstConsumer
**Why it matters:** `Immediate` binding provisions the EBS volume (in an arbitrary AZ) before the pod is scheduled; if the scheduler places the pod in a different AZ it can never attach the AZ-bound volume and stays `Pending`.
**Steps:** Set `volumeBindingMode: WaitForFirstConsumer` on every EBS StorageClass that backs a StatefulSet/Deployment with PVCs (StorageClass is immutable — recreate + migrate).
**Snippet:**
```yaml
kind: StorageClass
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
```
**References:**
- [Deploy a stateful workload to EKS](https://docs.aws.amazon.com/eks/latest/userguide/sample-storage-workload.html)

### R20 — Snapshot coverage for stateful workloads
**Why it matters:** A PersistentVolume without snapshots has zero recovery options if the volume is corrupted, accidentally deleted, or the AZ has an issue.
**Steps:**
1. Identify stateful workloads: `kubectl get statefulsets -A` + Deployments with PVCs.
2. Check for VolumeSnapshots: `kubectl get volumesnapshots -A` — verify recent timestamps (< 24h for critical data).
3. Or verify AWS Backup coverage: `aws backup list-protected-resources` — filter for EBS volume IDs backing the PVCs.
4. For EFS-backed PVs: verify automatic backups are enabled (`aws efs describe-file-systems`).
5. Implement a snapshot schedule: VolumeSnapshot with a CronJob, or AWS Backup with a scheduled plan.
**References:**
- [EKS User Guide — EBS snapshots](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)
- [AWS Backup — Protecting EKS](https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html)

### R21 — Restore testing / RTO-RPO alignment
**Why it matters:** Untested backups may not restore successfully. Without documented RTO/RPO targets, you can't verify the backup strategy meets business requirements.
**Steps:**
1. Confirm RTO/RPO targets are documented for the cluster's stateful workloads.
2. Verify snapshot/backup frequency ≤ RPO (e.g., 1h RPO requires ≤ 1h snapshot interval).
3. Request evidence of a recent restore test (within 90 days): restore a snapshot to a test PVC, verify data integrity.
4. Estimate restore time vs. RTO: volume size, IOPS during restore, application startup time.
**References:**
- [AWS Well-Architected — Reliability Pillar: Recovery](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/plan-for-disaster-recovery-dr.html)

### R22 — External dependency mapping
**Why it matters:** A cluster can be internally healthy but fail because an external dependency (database, S3, SQS, third-party API) is down. Unmapped dependencies cause cascading failures with unknown blast radius.
**Steps:**
1. Inventory external endpoints: check egress NetworkPolicies, ExternalName services, ServiceEntry CRDs, application configuration.
2. For each critical dependency: verify health-check/canary monitoring exists, and workloads implement timeout + retry + circuit-breaker patterns.
3. Document the dependency graph (which services depend on which external systems).
4. For AWS services: consider VPC endpoints to remove internet/NAT dependency.
**References:**
- [EKS Best Practices — Reliability](https://docs.aws.amazon.com/eks/latest/best-practices/reliability.html)
