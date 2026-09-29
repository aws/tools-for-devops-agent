# Networking remediations — shard 04

Canonical IDs: `NM1,NM2,NM3,NM4,NM5`

### NM1 — Multi-AZ subnets + NAT per AZ
**Why / fix:** Cluster subnets should span ≥2 AZs, with a NAT gateway per AZ for resilient (and cheaper cross-AZ-free) egress. Verify in VPC config. Link: [Subnets/VPC](https://docs.aws.amazon.com/eks/latest/best-practices/subnets.html).

### NM2 — Nodes in private subnets
**Why / fix:** Worker subnets should have `MapPublicIpOnLaunch=false`; nodes egress via NAT, not public IPs. Verify in subnet config. Link: [Subnets/VPC](https://docs.aws.amazon.com/eks/latest/best-practices/subnets.html).

### NM3 — Cluster endpoint exposure
**Why / fix:** Review public/private endpoint config; `publicAccessCidrs` should not be `0.0.0.0/0`. `aws eks describe-cluster --query cluster.resourcesVpcConfig`. Link: [Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html).

### NM4 — Subnet IP headroom / sizing
**Why / fix:** Cluster + pod subnets must be sized for growth; add secondary CIDRs if tight. Check subnet CIDR utilization. Link: [IP Optimization](https://docs.aws.amazon.com/eks/latest/best-practices/ip-opt.html).

### NM5 — VPC endpoints for AWS services
**Why / fix:** ECR/S3/STS/EC2/logs interface+gateway endpoints keep traffic off NAT (cost + security). Verify endpoints exist. Link: [cost-opt networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html).

