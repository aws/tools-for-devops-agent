# Upgrade Readiness remediations — shard 04

Canonical IDs: `U22,U23,U24,UM1,UM2,UM3,UM4`

### U22 — EC2 instance service-quota headroom *(AWS-API)*
**Why it matters:** Rolling node replacement launches **surge** instances before terminating old ones. If the EC2 vCPU / instance quota is near its ceiling, the surge can't launch and the node rollout stalls mid-upgrade.
**How to verify / fix:** Compare running instances against the relevant quota (`aws service-quotas get-service-quota --service-code ec2 --quota-code <vCPU quota>`); request an increase before upgrading if headroom is tight.
**References:**
- [Service Quotas — Requesting a quota increase](https://docs.aws.amazon.com/servicequotas/latest/userguide/request-quota-increase.html)
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U23 — EBS gp3 volume quota headroom *(AWS-API)*
**Why it matters:** As nodes cycle, EBS-backed PVs detach and re-attach on the replacement node. Insufficient gp3 volume / storage quota blocks PV re-attachment, leaving stateful pods stuck Pending.
**How to verify / fix:** Check the gp3 volume + storage quota (`aws service-quotas get-service-quota --service-code ebs ...`) against current usage plus the expected churn; request an increase if tight.
**References:**
- [Service Quotas — Amazon EBS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-resource-quotas.html)

### U24 — EBS gp2 volume quota headroom *(AWS-API)*
**Why it matters:** Same re-attachment risk as U23 for any remaining gp2 PVs during node replacement.
**How to verify / fix:** Check the gp2 volume + storage quota against usage; migrate gp2→gp3 (cheaper, faster — see cost pillar) and ensure quota headroom before upgrading.
**References:**
- [Service Quotas — Amazon EBS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-resource-quotas.html)

## Upgrade — manual / process (UM)

### UM1 — Run EKS Cluster Insights
**Why / fix:** Authoritative removed-API + readiness signal. [`ListInsights`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListInsights.html) / [`DescribeInsight`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeInsight.html) (`aws eks list-insights`) or console. Link: [Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html).

### UM2 — Control-plane logging on for the upgrade
**Why / fix:** Enable api/audit logs to catch upgrade-time errors. `aws eks update-cluster-config`. Link: [Auditing and Logging](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html).

### UM3 — Backup before upgrade
**Why / fix:** Take a Velero / etcd-level backup before upgrading (recommended). Link: [Velero](https://velero.io/docs/).

### UM4 — Non-prod rehearsal
**Why / fix:** Rehearse the upgrade in a lower environment / CI first. Process check.

