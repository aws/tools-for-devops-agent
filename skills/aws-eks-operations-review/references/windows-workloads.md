# Cross-cutting checklist: Windows workloads

Not a pillar — a **conditional** checklist that applies **only when the cluster has Windows nodes** (`windows_nodes > 0` from discovery area 36). If there are no Windows nodes, skip it entirely. When Windows nodes exist, run this alongside the normal pillars — it captures Windows-specific constraints that the Linux-centric pillar checks miss or get wrong.

Grade **PASS / FAIL / N/A** with evidence, severity, recommendation. AWS-API / node-level items stay N/A in kubectl-only mode.

Anchor: [Windows Best Practices](https://docs.aws.amazon.com/eks/latest/best-practices/windows.html) (AMI, gMSA, hardening, image scanning, licensing, logging, monitoring, networking, OOM, patching, scheduling, security, storage).

Reads discovery areas: 2 NODES, 4/5 workloads, 7 PODS, 8 SERVICES, 36 DATA_PLANE, 39 IMAGE_SECURITY.

## Gate

Run only if discovery found Windows nodes (`kubernetes.io/os=windows`). Otherwise mark the whole checklist N/A — "no Windows nodes detected."

## Currency framing (read first)

- **Single ENI per Windows node** — IP-per-node is capped by one ENI; prefix delegation (`/28`, ×16 IPs) is the lever for pod density. Plan IP capacity accordingly.
- **No OOM killer on Windows** — Windows pages to disk instead of OOM-killing; memory pressure shows as slowdowns, not kills. Memory **requests + limits** and kubelet/system reservations matter more, not less.
- **Kernel build must match** — a Windows container's base-image build must match the node's Windows build; mixed builds need `node.kubernetes.io/windows-build` selectors.
- **>100 services risks port exhaustion** on Windows nodes (`hcnCreateLoadBalancer ... port already exists`) — mitigate with Direct Server Return (DSR).

## Scheduling & isolation (W1–W4)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| W1 | OS nodeSelector on Windows workloads | area 4/5/7 pod spec | Windows pods set `nodeSelector: kubernetes.io/os=windows` | High | Without it, pods may land on Linux nodes and fail. |
| W2 | Windows nodes tainted | area 2/36 node taints | Windows nodes carry `os=windows:NoSchedule` (with matching tolerations on Win pods) | High | Taints keep existing Linux deployments off Windows nodes without editing them. |
| W3 | windows-build matching | pod base image vs node `node.kubernetes.io/windows-build` | multi-build clusters use the build label in selectors | Medium | Container build must match node kernel build. |
| W4 | RuntimeClass for Windows | RuntimeClasses (area 44) | a Windows RuntimeClass simplifies selector/toleration sprawl | Low | Optional; reduces repetition in pod manifests. |

## Resource management (W5–W7)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| W5 | Memory requests + limits on Windows pods | area 4/5/7 container resources | Windows containers set memory requests **and** limits | High | No OOM killer on Windows — limits prevent one pod starving the node. |
| W6 | Realistic memory baseline | container memory requests | requests account for the Windows base image (NANO ~30MB / Server Core ~45MB + app + .NET/IIS) | Medium | Under-requesting Windows images causes scheduling/paging issues. |
| W7 | kubelet/system memory reservation | node config (AWS-API/bootstrap) | ≥2GB reserved for OS+kubelet via `--kube-reserved`/`--system-reserved` | Medium | Windows reserve flags shape NodeAllocatable; reserve to avoid node-wide paging. |

## Networking (W8–W10)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| W8 | IP capacity for pod density | area 26 + node max-pods | single-ENI IP math accounts for needed pod density | High | Windows = 1 ENI; default secondary-IP mode is tight. |
| W9 | Prefix delegation (Windows) | VPC Resource Controller config | enabled where higher Windows pod density is needed | Medium | `/28` prefixes ×16 IPs per node; the density lever on Windows. |
| W10 | Services-per-node port exhaustion | area 8 services count | watch nodes with >100 services; DSR enabled | Medium | Prevents `hcnCreateLoadBalancer` port-exhaustion failures. |

## Security & images (W11–W14)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| W11 | Windows pod security context | area 34 pod spec | Windows-valid securityContext (`runAsUserName`, no Linux-only fields) | Medium | Linux PSS fields (runAsNonRoot/seccomp) don't apply; use Windows options. |
| W12 | gMSA for AD-integrated workloads | CRDs / pod spec | apps needing AD use gMSA (`GMSACredentialSpec`), not embedded creds | Medium | gMSA is the supported Windows AD auth path on EKS. |
| W13 | Windows image hardening + scanning | area 39 images | Windows images scanned; minimal base (NANO/Server Core); non-default user | Medium | Same supply-chain hygiene as Linux, Windows-appropriate. |
| W14 | Windows worker node hardening | AWS-API / node config | CIS-aligned hardening of the Windows AMI/host | Low | Follow Windows node hardening guidance. |

## Operations (W15–W18, manual)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| W15 | EKS-optimized Windows AMI currency | AWS-API | Windows AMI is current (Microsoft patches monthly); plan node refresh cadence. |
| W16 | Patching strategy | process | Windows Server + container base images patched; node rotation/expiry covers AMI updates. |
| W17 | Licensing | AWS billing | Windows Server licensing model understood (included in EC2 Windows pricing). |
| W18 | Logging & monitoring agents | area 29 + node | Windows-capable log/metric agents deployed (Fluent Bit for Windows, CloudWatch agent). |

## How to run

Gate on `windows_nodes > 0`. Lead the report with W1/W2 (scheduling isolation) and W5/W8 (memory + IP capacity) — the most common Windows failure modes. Note clearly that several Linux-pillar findings are **N/A or different on Windows** (no OOM killer, Linux securityContext fields, single-ENI IP model) so the main pillar scorecards don't misgrade Windows nodes.
