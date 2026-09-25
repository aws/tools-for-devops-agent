# Hybrid remediations — shard 02

Canonical IDs: `H9,H10,H11,H12`

### H9 — Single credential provider
**Why / fix:** Use SSM hybrid activations **or** IAM Roles Anywhere — not both. Confirm on the host/AWS side. Link: [Hybrid host credentials](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-host-creds.html).

### H10 — SSM agent version current
**Why / fix:** SSM agent ≥ 3.3.808.0 caps backoff at 30 min so creds recover faster post-disconnect. Check on the host. Link: [Hybrid host credentials](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-host-creds.html).

### H11 — Local troubleshooting access
**Why / fix:** Operators must be able to reach/restart the SSM agent and read `/var/log/amazon/ssm/...` on-site during a disconnect. Process check. Link: [Hybrid network disconnections](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-network-disconnections.html).

### H12 — Remote-AWS-service dependency review
**Why / fix:** On-prem workloads' dependencies on remote AWS services should be known and tolerate disconnection (cache/queue/degrade). Architecture review. Link: [Hybrid app network traffic](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-app-network-traffic.html).
