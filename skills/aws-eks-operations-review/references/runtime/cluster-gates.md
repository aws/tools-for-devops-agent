# Runtime cluster gates

Load only in S5 after inventory assembly. Record every gate as true/false plus evidence. A gate changes applicability; it never removes scorecard rows.

| Gate | Detection | N/A/branch behavior |
|---|---|---|
| Auto Mode | `compute-type=auto` / `features.autoscaling.eks_auto_mode` | N/A managed checks: Op9–13, Op18–22, Op24, Op27–29; S13 node path/S24/S25/S28; N2/N6/N9/N14; Sc21; R15; U8/U15. Still grade workload checks and Op17 duplicate detection. |
| EKS Anywhere / non-cloud | no EKS API identity; anywhere labels/no AWS provider IDs | AX1–AX14 and CloudWatch-only rows N/A; grade in-cluster units. Apply non-VPC-CNI behavior if relevant. |
| IPv6-only | `features.cni_config.ipv6_cluster=true` | N3–N6, N8, AX7, and IPv4 framing in Sc11 N/A with a positive IPv6 reason. |
| Fargate-only | no EC2 nodes/nodegroups; only Fargate workloads | Node checks N/A: N1 nuance/N9; S24/S25/S28; R15; Op8–13/20–29 node-only portions; Sc4/5/11/22; P9. Workload/security/observability checks still apply. |
| Non-VPC-CNI | Cilium/Calico present and `aws-node` absent | N1–N8 N/A as VPC-CNI-specific; grade S15 against installed CNI policy CRDs. |
| Mixed Windows/Linux | both OS node types | Load Windows checklist; S4–S7 apply only to Linux pods where those Linux-only fields are meaningful. |
| Extended Support | `cluster.support_type=EXTENDED` | Load Upgrade 35 and deprecated API database. |
| Accelerator | `gpu_nodes>0 || neuron_nodes>0` | Load AI/ML 16. |
| Hybrid | `hybrid_nodes>0` | Load Hybrid 12. |

## Scale and payload gates

Fleet tiers use node count: small `<100`, medium `100–500`, large `500–2000`, XL `>2000`. The separate **500+ pod payload threshold** prohibits retaining/fetching whole-cluster `pods -A -o json`; use namespace projections and bounded samples. Both thresholds can apply simultaneously.

## Per-command robustness

A single timeout/RBAC error becomes an area N/A and discovery continues. Retry a huge result once with narrower scope. CRD NotFound means feature absent, not an execution failure. Stop only when the S2 probe fails or a phase exceeds the 30% error threshold.