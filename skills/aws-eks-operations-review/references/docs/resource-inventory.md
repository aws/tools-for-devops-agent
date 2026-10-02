# Resource Inventory — what each of the 49 areas discovers

This is the catalog of what each discovery area collects, so you can jump straight to the right kubectl query for a given question instead of running the whole sweep.

Execution is read-only. Every area feeds bounded counts/features into the runtime inventory contract in `../runtime/inventory-schema.md`.

> **Command-file split:** the *command* files split at 27/28 — areas **1–27** are in
> `kubectl-discovery-commands.md` and **28–49** in `kubectl-discovery-commands-deep-dive.md`.
> The two tables below group areas 1–24 / 25–49 by theme; areas 25–27 appear in the second
> table but their commands live in the core commands file.

## Core inventory (sections 1–24)

| # | Section | Discovers | Key resources / signals |
|---|---------|-----------|-------------------------|
| 1 | CLUSTER_INFO | Connection, context, server endpoint, K8s client/server version | `kubectl version`, current context |
| 2 | NODES | Node inventory, conditions, allocatable resources | node count, Ready/DiskPressure/MemoryPressure/**PIDPressure**/NotReady (→ Op25), CPU/mem/pods allocatable |
| 3 | NAMESPACES | Namespace listing + count | all namespaces |
| 4 | DEPLOYMENTS | Deployment inventory + detailed config | replicas, strategy, per-container image, **resource requests/limits**, **probes (liveness/readiness/startup)**, env count, volumes, serviceAccount |
| 5 | STATEFULSETS | StatefulSet inventory + config | replicas, updateStrategy, serviceName, resources, probes, volumeClaimTemplates |
| 6 | DAEMONSETS | DaemonSet inventory + config | updateStrategy, nodeSelector, tolerations, per-container resources |
| 7 | PODS | Pod inventory + problem triage | phase distribution; **Pending / Failed / CrashLoopBackOff / ImagePull / OOMKilled**; top restarters (>5); problematic pod describes |
| 8 | SERVICES | Services by type | ClusterIP / NodePort / LoadBalancer / ExternalName counts |
| 9 | ENDPOINTS | Endpoints + EndpointSlices | counts, first 50 of each |
| 10 | INGRESS | Ingress + IngressClasses; controller detection | nginx / ALB / traefik presence, ingress hosts |
| 11 | HPA | HorizontalPodAutoscalers | min/max/current replicas, detailed describe |
| 12 | VPA | VerticalPodAutoscalers | updateMode, presence |
| 13 | KEDA | KEDA ScaledObjects + TriggerAuthentications | scaledobject counts |
| 14 | PDB | PodDisruptionBudgets | minAvailable / maxUnavailable |
| 15 | JOBS | Job inventory | count, first 50 |
| 16 | CRONJOBS | CronJob inventory | schedules |
| 17 | CONFIGMAPS | ConfigMap inventory | count, first 100 |
| 18 | SECRETS | Secret **metadata only** (never values) | type distribution, count |
| 19 | EVENTS | Recent events | events by reason (top 20), Warning events (last 50) |
| 20 | STORAGE | StorageClasses, PVs, PVCs | provisioner, volume type (gp2/gp3), capacity, status |
| 21 | NETWORKPOLICIES | NetworkPolicies | count, per-namespace, policyTypes, detailed describe |
| 22 | RBAC | Roles/bindings summary | ClusterRoles, ClusterRoleBindings, Roles, RoleBindings, ServiceAccounts counts |
| 23 | CRDS | Custom Resource Definitions, categorized | by API group; autoscaling / networking / security / storage / gitops / observability CRDs |
| 24 | WEBHOOKS | Mutating + Validating webhook configs | service target, **failurePolicy**, sideEffects, rules (apiGroups/resources/operations), namespaceSelector |

## Deep-dive sections (25–49)

| # | Section | Discovers | Key signals |
|---|---------|-----------|-------------|
| 25 | CNI | Full CNI detection + config | **VPC CNI** (WARM_* targets, **prefix delegation**, **custom networking / ENIConfig**, **security groups for pods / ENABLE_POD_ENI**, network policy controller, **IPv6**, external SNAT, version), Calico (IPPools, BGP, FelixConfig, GlobalNetworkPolicies), Cilium (config, status, CiliumNetworkPolicies), Weave, Flannel |
| 26 | NETWORKING_ADVANCED | kube-proxy mode, LB controller, LBs, CoreDNS, IP utilization | **kube-proxy mode (iptables/IPVS)**, AWS LB Controller version + TargetGroupBindings, LoadBalancer services + target-type, Ingress ALB annotations, node network info, CoreDNS replicas/HPA, pods-per-node, service CIDR, pod CIDRs |
| 27 | KUBE_SYSTEM_RESOURCES | Everything in kube-system + infra namespaces | DaemonSets, Deployments, Services, ConfigMaps (aws-auth, coredns, kube-proxy), EBS/EFS CSI drivers, metrics-server, ServiceAccounts |
| 28 | AUTOSCALING_INFRA | EKS Auto Mode, Cluster Autoscaler, Karpenter | **Auto Mode** nodes/nodepools (managed Karpenter/LBC/EBS CSI — present-by-design, flag only self-managed dupes); **CAS** version-match, auto-discovery arg, flags, IRSA, single-replica/sharding note; **Karpenter** version, NodePools (limits, consolidation, expireAfter, disruption budgets), EC2NodeClasses (**AMI pinning / @latest check**, IMDS, tags), NodeClaims, **Spot interruption + instance diversity**, **controller placement (not self-hosted)**, **do-not-disrupt annotations**, requests=limits-for-consolidation |
| 29 | OBSERVABILITY | Metrics, logging, APM, tracing | Prometheus, kube-state-metrics, metrics-server, CNI metrics helper, node-exporter, Grafana, **CloudWatch Container Insights**, **ADOT/OTel**, X-Ray, Fluent Bit/Fluentd, Vector, Datadog, Dynatrace, New Relic, Splunk, Elastic, Hubble, ServiceMonitors/PodMonitors, Alertmanager, DCGM |
| 30 | SERVICE_MESH | Mesh detection | Istio, Linkerd, App Mesh |
| 31 | GITOPS | GitOps tooling | **ArgoCD** (Applications, AppProjects), **FluxCD** (GitRepositories, Kustomizations, HelmReleases) |
| 32 | COST_OPTIMIZATION | Cost tooling + efficiency signals | Kubecost, Goldilocks, OpenCost, KRR; **Spot %**, **Graviton/ARM64 %**, pods without requests, descheduler, gp2→gp3 candidates, unused PVCs, EFS vs EBS, cross-AZ/topology-aware routing, HPA min/max efficiency, node utilization, pod density |
| 33 | THIRD_PARTY_CONTROLLERS | Installed operators/controllers | ACK, External Secrets Operator, cert-manager, AWS LB Controller, Crossplane, Sealed Secrets, Reloader, Velero, plus generic controller/operator scan |
| 34 | SECURITY | Pod security + access posture | **PSS/PSA labels**, Kyverno (policies, PolicyReports), Gatekeeper (constraints), Falco, **privileged pods**, **allowPrivilegeEscalation**, **hostNetwork/hostPID/hostIPC**, **hostPath volumes**, readOnlyRootFilesystem, runAsNonRoot, **capabilities (drop ALL)**, AppArmor, **Seccomp (RuntimeDefault)**, GuardDuty, NetworkPolicies + default-deny, **IRSA**, **Pod Identity (preferred over IRSA)**, automountServiceAccountToken, secrets management (ESO/Sealed/CSI), image scanning tools, image pull policies + :latest, **aws-auth (deprecated) vs CAM API / Access Entries**, **cluster-admin bindings**, **wildcard RBAC** |
| 35 | RELIABILITY | HA + resilience posture | control-plane health (etcd size, super-admin SA), **topology spread + minDomains**, **pod anti-affinity**, ResourceQuotas, LimitRanges, pods without requests/limits, **deployments without PDB**, **blocking PDBs (maxUnavailable:0 / minAvailable:100%)**, **rollout sizing (maxUnavailable/maxSurge, Recreate)**, **probe coverage %**, terminationGracePeriod, preStop/postStart hooks, **singleton pods**, **single-replica deployments**, readiness gates, QoS classes, HPA coverage, node health monitoring, **EBS AZ alignment** |
| 36 | DATA_PLANE | Node configuration | node labels, **instance types**, **capacity type (Spot/On-Demand)**, taints, tolerations, nodegroups, **node AZ distribution**, **kubelet version consistency**, node age, Bottlerocket, Windows nodes, **GPU nodes**, Fargate |
| 37 | SCALABILITY | Scale metrics + limits | cluster size vs K8s thresholds (nodes/pods/services/namespaces), **services per namespace**, CoreDNS scaling + autoscaling + lameduck, NodeLocal DNSCache, ndots, metrics-server sizing, **instance type diversity**, **burstable (T-series) check**, pods-per-node vs 110, DaemonSet capacity impact, **upgrade readiness** (version skew, deprecated APIs — PSP, old Ingress), LB quotas |
| 38 | AI_ML_WORKLOADS | GPU/accelerator stack | **GPU nodes** (nvidia.com/gpu), **Neuron (Inferentia/Trainium)**, NVIDIA device plugin / GPU operator, Neuron device plugin, **EFA**, GPU/Neuron/EFA pod requests, FSx for Lustre, Mountpoint S3, Kubeflow, Ray, KServe, Triton, vLLM, TGI, training operators (PyTorchJob/TFJob/MPIJob), DCGM, GPU scheduling/Spot |
| 39 | IMAGE_SECURITY | Image hygiene | registries, **imagePullPolicy distribution**, **:latest / untagged**, ECR images, imagePullSecrets, SA pull secrets, unique images, init container images |
| 40 | GATEWAY_API | Gateway API + alternatives | GatewayClasses, Gateways (listeners, TLS), HTTPRoutes/GRPCRoutes/TCPRoutes/TLSRoutes/UDPRoutes, ReferenceGrants, **VPC Lattice** (ServiceNetworks, TargetGroupPolicies, IAMAuthPolicies), Envoy Gateway, Contour, Kong, Ambassador, APISIX |
| 41 | DNS_CONFIG | DNS stack | CoreDNS deployment + Corefile analysis + custom config + HPA, Cluster Proportional Autoscaler, kube-dns service, **NodeLocal DNSCache**, pod dnsPolicy distribution, custom dnsConfig (ndots), External DNS, CoreDNS error logs |
| 42 | SECRETS_MANAGEMENT | External secrets integration | Secrets Store CSI Driver + SecretProviderClasses, AWS Secrets Manager provider (ASCP), HashiCorp Vault |
| 43 | SERVICE_ACCOUNTS | SA + IAM integration | **IRSA** (role-arn annotations), **EKS Pod Identity** associations, token projection, automountServiceAccountToken=false (SAs and pods) |
| 44 | SCHEDULING | Advanced scheduling | RuntimeClasses + pods using them, preemptionPolicy, schedulerName distribution |
| 45 | BACKUP_DR | Backup / DR | VolumeSnapshotClasses, VolumeSnapshots, VolumeSnapshotContents, Velero (Backups, Restores, BackupStorageLocations, schedules) |
| 46 | MULTI_TENANCY | Isolation posture | namespace team/tenant labels, **NetworkPolicy coverage** per namespace, **ResourceQuota coverage** per namespace, cross-namespace ExternalName services |
| 47 | RESOURCE_OPTIMIZATION | Efficiency | Spot usage, node resource allocation, **BestEffort QoS pods**, QoS distribution, single-replica deployments, top pods by CPU/memory |
| 48 | NAMESPACE_SUMMARY | Per-namespace counts | pods / deployments / services per namespace |
| 49 | INVENTORY_ROLLUP | In-context rollup | all required counts + feature flags—assemble per `../runtime/inventory-schema.md` |

## Not observable in-cluster (graded by the AWS-API component)

These are not visible through kubectl. They are graded by the **AWS-API & Cluster Insights component** ([`../aws-api-checks.md`](../aws-api-checks.md), AX-series), which reads customer-visible EKS / EC2 / IAM APIs and EKS Cluster Insights through audited read-only operations. Without AWS access they stay **N/A** and are flagged for follow-up—never defaulted to PASS/FAIL.

- EKS Cluster Insights (upgrade readiness + misconfiguration) — **AX1**
- Access entries / authentication mode / aws-auth migration — **AX2, AX3**
- Managed nodegroup health & update status (`CREATE_FAILED`, stuck rollouts, bootstrap/AMI conflicts) — **AX4**
- EC2 instances that launch but never register as nodes — **AX8**
- Managed addon health, versions, and upgrade conflicts (CNI/CoreDNS/kube-proxy/CSI/pod-identity-agent) — **AX5**
- Pod Identity associations + agent presence — **AX6**
- Controller IAM permissions (AWS Load Balancer Controller, ExternalDNS, EBS CSI, Karpenter) — **AX9**
- Per-subnet IP availability / subnet CIDRs / VPC layout — **AX7**
- EKS control-plane logging configuration — **AX10**
- KMS envelope encryption of secrets (`encryptionConfig`) — **AX11**
- Cluster endpoint exposure (`publicAccessCidrs`) — **AX12**

Still genuinely out of scope (not graded by any component): VPC endpoints / NAT Gateway / ECR pull-through cache cost config, and the Karpenter Spot interruption SQS queue (controller CLI flag — partially inferred only). Flag these as manual follow-ups.
