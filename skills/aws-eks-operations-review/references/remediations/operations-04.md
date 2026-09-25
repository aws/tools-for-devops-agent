# Operations remediations — shard 04

Canonical IDs: `OpM1,OpM2,OpM3,OpM4,OpM5,OpM6,OpM7,OpM8`

### OpM1 — Karpenter Spot interruption handling
**Why / fix:** If Spot NodePools exist, confirm Karpenter native interruption handling is active (it watches the EC2 rebalance/interruption signal) or an `--interruption-queue` → SQS is wired, so pods drain gracefully on a 2-minute Spot notice. Verify via the Karpenter controller args/config. Link: [Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html).

### OpM2 — CAS auto-discovery
**Why / fix:** Confirm `--node-group-auto-discovery` is set on the CAS deployment (also Op24 when args are readable). Link: [Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html).

### OpM3 — Control-plane logging enabled
**Why / fix:** API/audit/authenticator/controllerManager/scheduler logs are essential for incident forensics and upgrade debugging. Verify: `aws eks describe-cluster --name ${CLUSTER} --query cluster.logging`. Enable the needed types. Link: [Auditing and Logging](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html).

### OpM4 — Cluster auth mode
**Why / fix:** Standard is `API` (or `API_AND_CONFIG_MAP` during migration) with Access Entries, not the deprecated aws-auth ConfigMap. Verify: `aws eks describe-cluster --name ${CLUSTER} --query cluster.accessConfig.authenticationMode`. Link: [Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html).

### OpM5 — CAS IAM least privilege
**Why / fix:** The CAS IRSA role should scope `autoscaling:SetDesiredCapacity` + `TerminateInstanceInAutoScalingGroup` to cluster ASGs via `aws:ResourceTag` conditions. Review the role policy in IAM. Link: [Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html).

### OpM6 — CAS sharding for large clusters
**Why / fix:** CAS runs one active replica; beyond ~1000 nodes shard it across node groups to keep scaling decisions timely. Assess against node count. Link: [Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html).

### OpM7 — CoreDNS tuning under Karpenter
**Why / fix:** Fast node churn stresses DNS; ensure CoreDNS has enough replicas/autoscaling, `lameduck`, and topology spread. Inspect the CoreDNS deployment/Corefile. Link: [Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html).

### OpM8 — do-not-disrupt on critical pods
**Why / fix:** Critical/stateful pods should carry `karpenter.sh/do-not-disrupt: "true"` so consolidation/expiry won't evict them mid-work. Audit pod annotations. Link: [Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html).

