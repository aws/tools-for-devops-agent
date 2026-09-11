# Cost Architecture remediations — shard 04

Canonical IDs: `AM2,AM3,AM4,AM5,AM6`

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

