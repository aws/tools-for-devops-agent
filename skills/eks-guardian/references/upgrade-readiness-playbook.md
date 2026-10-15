# EKS Guardian — Upgrade Readiness Playbook

Step-by-step checklist for safely upgrading an EKS cluster, customized based on the cluster's current assessment findings.

---

## Pre-Upgrade Checklist

### Phase 1: Assessment (1–2 weeks before)

- [ ] **Identify target version**: Current → Target (check [EKS release calendar](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html))
- [ ] **Review EKS Upgrade Insights**: Check UPGRADE_READINESS and MISCONFIGURATION insights
- [ ] **Check deprecated API usage**: Run `kubectl deprecations` or `pluto detect-all-in-cluster`
- [ ] **Verify addon compatibility**: Check each addon's compatible versions for target K8s version
- [ ] **Review release notes**: Check [EKS changelog](https://github.com/aws/containers-roadmap/issues) for breaking changes
- [ ] **Check Karpenter compatibility**: Verify Karpenter version supports target K8s version
- [ ] **Audit webhooks**: List all MutatingWebhookConfigurations and ValidatingWebhookConfigurations — failing webhooks block upgrades

### Phase 2: Preparation (3–5 days before)

- [ ] **Ensure PDB coverage**: All production workloads must have PodDisruptionBudgets
- [ ] **Verify health probes**: All deployments should have liveness/readiness probes
- [ ] **Check node group capacity**: Ensure enough headroom for rolling node updates
- [ ] **Update IAM policies**: Verify node role has permissions for new K8s version features
- [ ] **Backup critical state**: etcd snapshot (if self-managed), Velero backup of critical namespaces
- [ ] **Document rollback plan**: Know how to revert (note: control plane cannot be rolled back)
- [ ] **Notify stakeholders**: Communicate maintenance window

### Phase 3: Execution

#### Step 1: Update Control Plane

```bash
aws eks update-cluster-version \
  --name <cluster-name> \
  --kubernetes-version <target-version>

# Monitor (takes 20-40 minutes)
aws eks describe-update \
  --name <cluster-name> \
  --update-id <update-id>
```

#### Step 2: Update Add-ons

Update in this order (dependencies matter):

1. **CoreDNS**
2. **kube-proxy**
3. **VPC CNI (aws-node)**
4. **EBS CSI Driver**
5. **Other add-ons**

```bash
# Check compatible versions
aws eks describe-addon-versions \
  --kubernetes-version <target-version> \
  --addon-name <addon-name>

# Update
aws eks update-addon \
  --cluster-name <cluster-name> \
  --addon-name <addon-name> \
  --addon-version <compatible-version> \
  --resolve-conflicts PRESERVE
```

#### Step 3: Update Node Groups

```bash
# Managed node groups
aws eks update-nodegroup-version \
  --cluster-name <cluster-name> \
  --nodegroup-name <nodegroup-name>

# Karpenter nodes: trigger rolling replacement
# Option A: Update EC2NodeClass AMI
# Option B: Add annotation to trigger drift
kubectl annotate nodeclaim --all karpenter.sh/voluntary-disruption=upgrade
```

#### Step 4: Validate

```bash
# Check all nodes are Ready and on new version
kubectl get nodes -o wide

# Check all pods running
kubectl get pods -A --field-selector status.phase!=Running,status.phase!=Succeeded

# Check system pods
kubectl get pods -n kube-system

# Verify API server version
kubectl version --short
```

### Phase 4: Post-Upgrade Validation

- [ ] **All nodes on target version**: `kubectl get nodes`
- [ ] **No CrashLoopBackOff pods**: `kubectl get pods -A | grep -v Running`
- [ ] **CoreDNS resolving**: `kubectl run test --image=busybox --rm -it -- nslookup kubernetes`
- [ ] **HPAs functioning**: `kubectl get hpa -A` (check TARGETS column)
- [ ] **Ingress/Services accessible**: Test external endpoints
- [ ] **Metrics pipeline working**: Check CloudWatch Container Insights
- [ ] **No API throttling**: Check control plane logs for 429s
- [ ] **Webhooks operational**: Test admission webhooks

---

## Version-Specific Notes

### Upgrading to 1.28

- Pod Security admission enforced by default (if using PSS labels)
- Deprecated: `flowcontrol.apiserver.k8s.io/v1beta2` → `v1beta3`

### Upgrading to 1.29

- Non-graceful node shutdown GA
- ReadWriteOncePod PVC access mode GA
- Check: `batch/v1beta1 CronJob` removed (use `batch/v1`)

### Upgrading to 1.30

- Node swap support beta
- Structured authorization configuration
- Check: `autoscaling/v2beta2 HPA` removed (use `autoscaling/v2`)

### Upgrading to 1.31+

- Always check [EKS release notes](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html) for the specific version

---

## Conditional Checks (Based on Assessment Findings)

### If Karpenter is installed

- [ ] Check Karpenter version compatibility matrix
- [ ] Verify NodePool `disruption.budgets` allow rolling replacement
- [ ] Ensure EC2NodeClass `amiFamily` will pick up new AMI
- [ ] Test: `kubectl get nodeclaims` — verify new nodes launch on target version

### If Cluster Autoscaler is installed

- [ ] Update CAS image to version compatible with target K8s version
- [ ] Verify `--balance-similar-node-groups` still appropriate
- [ ] Check ASG launch template AMI is EKS-optimized for target version

### If using Istio/Service Mesh

- [ ] Check Istio version compatibility with target K8s version
- [ ] Plan sidecar injection restart after upgrade
- [ ] Verify CRDs don't use deprecated APIs

### If using custom webhooks

- [ ] Test all MutatingWebhookConfigurations against target version
- [ ] Test all ValidatingWebhookConfigurations against target version
- [ ] Ensure webhook cert validity extends past upgrade window
- [ ] Consider adding `failurePolicy: Ignore` temporarily for non-critical webhooks

---

## Rollback Strategy

| Component | Rollback Method |
|-----------|----------------|
| Control plane | ❌ Cannot be rolled back — must upgrade forward |
| Add-ons | `aws eks update-addon --addon-version <previous-version>` |
| Managed node groups | Launch new node group with previous AMI, drain old |
| Karpenter nodes | Revert EC2NodeClass AMI, let Karpenter replace |
| Application issues | Rollback via deployment revision: `kubectl rollout undo` |

---

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Webhook blocking upgrade | Medium | High | Audit webhooks pre-upgrade, set timeouts |
| Deprecated API usage breaks workloads | Medium | High | Run `pluto` pre-upgrade, fix in advance |
| Node group update causes capacity shortage | Low | High | Ensure surge capacity, use PDBs |
| Add-on incompatibility | Low | Medium | Check versions before upgrading |
| DNS resolution failure post-upgrade | Low | High | Verify CoreDNS health immediately |
