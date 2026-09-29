# Operations remediations — shard 06

Canonical IDs: `Op29,Op30,Op31,Op32`

### Op29 — Node AMI age / rotation window *(AWS-API)*
**Why it matters:** Stale AMIs miss kernel/OS security patches. Op11 (Karpenter pinning) and U15 (AL2 EOL) don't flag a generally *old* self-managed / MNG custom AMI.
**How to verify / fix:** Resolve each node's AMI ID, then `aws ec2 describe-images --image-ids ${AMI} --query 'Images[0].CreationDate'`; flag > 90 days. Rebuild/rotate custom AMIs on a pipeline (EC2 Image Builder). **N/A** in kubectl-only mode; **N/A** on Auto Mode / Fargate.
**References:**
- [EKS User Guide — Amazon EKS optimized AMIs](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-amis.html)

### Op30 — CSI driver controller + node health
**Why it matters:** CSI driver failures silently break PVC binding and volume attach/mount — pods hang in `ContainerCreating` waiting for volumes that never come.
**Steps:**
1. Verify controller: `kubectl get deploy -n kube-system ebs-csi-controller` — all replicas Ready.
2. Verify node driver: `kubectl get ds -n kube-system ebs-csi-node` — all desired pods Ready.
3. Check CSINode registration: `kubectl get csinodes` — every schedulable node should list the driver.
4. If pods are failing: `kubectl describe pod -n kube-system <ebs-csi-controller-pod>` for events.
5. For EFS: repeat for `efs-csi-controller` and `efs-csi-node`.
**References:**
- [EKS User Guide — EBS CSI driver](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)
- [EKS User Guide — EFS CSI driver](https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html)

### Op31 — GitOps reconciliation health
**Why it matters:** GitOps drift means the deployed state doesn't match the declared desired state — manual changes bypass review, or reconciliation is failing silently.
**Steps:**
1. Argo CD: `kubectl get applications -A -o json` — check `.status.sync.status` (should be `Synced`) and `.status.health.status` (should be `Healthy`).
2. Flux: `kubectl get kustomizations -A` — check `Ready=True` condition. `kubectl get gitrepositories -A` for source health.
3. Investigate any `OutOfSync`, `Degraded`, or `Stalled` apps. Common causes: manual edits, failed hooks, dependency ordering.
4. Re-sync or fix the source and let GitOps reconcile.
**References:**
- [Flux — Core concepts](https://fluxcd.io/flux/concepts/)
- [Argo CD — Sync status](https://argo-cd.readthedocs.io/en/stable/user-guide/app_sync/)

### Op32 — Deployment rollback readiness
**Why it matters:** A `revisionHistoryLimit: 0` deletes all previous ReplicaSets, making `kubectl rollout undo` impossible — MTTR increases when you can't quickly roll back a bad deployment.
**Steps:**
1. Check: `kubectl get deploy -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}: {.spec.revisionHistoryLimit}{"\n"}{end}'`
2. Flag any deployment with `revisionHistoryLimit: 0`. Set to at least 2 (default 10 is fine for most cases).
3. Verify at least one previous ReplicaSet exists: `kubectl get rs -n <ns> -l app=<name>` — should show > 1 RS.
**References:**
- [Kubernetes — Deployment revision history](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#revision-history-limit)
