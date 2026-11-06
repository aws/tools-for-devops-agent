# Cost Architecture remediations — shard 02
Canonical IDs: `AM2,AM3,AM4,AM5,AM6,AM7,A24,A25,A26`

### AM2 — ECR pull-through cache
**Why / fix:** A pull-through cache reduces NAT charges for public image pulls. Configure in ECR. Link: [Cost Optimization: Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html).

### AM3 — Node utilization / idle spend
**Why / fix:** Use `kubectl top nodes`; persistently low-utilization nodes → enable consolidation / right-size. Link: [Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html).

### AM4 — Savings Plans / RI / EDP coverage
**Why / fix:** A steady On-Demand baseline should be covered by Compute Savings Plans/RIs. Review Cost Explorer recommendations. Link: [Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html).

### AM5 — Cost allocation / showback
**Why / fix:** CUR + Split Cost Allocation Data for EKS (or Kubecost/OpenCost) attributing spend to teams/namespaces. Confirm it's set up. Link: [Cost Optimization: Awareness](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-awareness.html).

### AM6 — NAT Gateway data-processing spend
**Why / fix:** High NAT processing → add VPC endpoints / pull-through cache (AM1/AM2). Review NAT cost in Cost Explorer. Link: [Cost Optimization: Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html).

### AM7 — Scheduled / off-hours scaling
**Why / fix:** Scale non-prod down off-hours (scheduled scaling / `kube-downscaler`). Confirm a schedule exists. Link: [Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html).

### A24 — Cost allocation tooling presence
**Why it matters:** Without workload-level cost attribution, teams can't identify which namespaces/workloads drive spend. Cost optimization requires visibility first.
**Steps:**
1. Deploy OpenCost or Kubecost: `helm install opencost opencost/opencost` (or Kubecost).
2. Or enable AWS Split Cost Allocation Data (SCAD) for EKS in the CUR settings.
3. Verify the tool is producing allocation data: check the OpenCost/Kubecost UI or CUR for EKS pod-level costs.
4. Integrate with team/namespace labels (Op5) for per-team showback.
**References:**
- [EKS Best Practices — Cost Awareness](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-awareness.html)
- [OpenCost](https://www.opencost.io/)
- [AWS Split Cost Allocation Data for EKS](https://docs.aws.amazon.com/cur/latest/userguide/split-cost-allocation-data.html)

### A25 — Log ingestion cost awareness
**Why it matters:** Control-plane audit logs on busy clusters generate 10–100+ GB/day at $0.50/GB ingest — this can be the #1 EKS cost line item without the team realizing it.
**Steps:**
1. Check CW Logs ingestion: `aws cloudwatch get-metric-data` for `IncomingBytes` on `/aws/eks/{cluster}/cluster`.
2. If > 50 GB/day: review which log types are enabled (api, audit, authenticator, controllerManager, scheduler) — disable non-essential types in non-prod.
3. For high-volume logs: use a Firehose delivery stream to S3 (cheaper long-term storage) with a CW Logs subscription filter.
4. Set log retention (default is infinite): `aws logs put-retention-policy` — 30 days for audit, 7 days for controller/scheduler in non-prod.
**References:**
- [EKS Best Practices — Cost Optimization Observability](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-observability.html)
- [CloudWatch Logs pricing](https://aws.amazon.com/cloudwatch/pricing/)

### A26 — Non-production operating schedule
**Why it matters:** Running dev/staging clusters 24/7 wastes ~65% of compute cost (nights + weekends). Scheduling scale-down is the simplest cost win.
**Steps:**
1. Identify non-prod clusters: check `Environment` tag or namespace labels.
2. Implement scheduled scaling: CronJob that scales replicas to 0 at 7PM, back up at 7AM; or Karpenter with aggressive `consolidateAfter` + `expireAfter` so nodes drain after idle.
3. For entire clusters: consider `eksctl` or Terraform with scheduled lifecycle rules, or simply scale nodegroups to 0 off-hours.
4. Verify no production workloads run on the non-prod cluster (check for external traffic, cron dependencies).
**References:**
- [EKS Best Practices — Cost Optimization Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)
