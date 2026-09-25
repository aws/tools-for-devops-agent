# kubectl discovery — core areas 1–27

Run every command through the AWS DevOps Agent MCP tool **`use_kubectl`**. Every code span below is one separate tool invocation; never combine commands with shell operators. Allowed operations: `get`, `describe`, `logs`, `version`, `config current-context`, `cluster-info`, `top`, and `get --raw`. Tool results remain transient in conversation and must not be written to Amazon S3 or a file. Record command, scope, timestamp, and resourceVersion where available in the transient ledger. Continue with [`kubectl-discovery-commands-deep-dive.md`](kubectl-discovery-commands-deep-dive.md); fleet/payload detail is in [`docs/kubectl-scaling-guidance.md`](docs/kubectl-scaling-guidance.md).

## Fetch and projection rules

Produce the reusable fetch IDs named by [`runtime/discovery-manifest.md`](runtime/discovery-manifest.md). Cache only for the confirmed cluster/context/scope, project immediately to bounded evidence, reuse only for listed dependent areas, then drop raw JSON. A dependent area is attempted only after its extraction runs. At 500+ pods never create `POD_JSON`; use namespace batches, field selectors, custom columns, and bounded `POD_PROJECTION_<scope>`. CRD-specific NotFound checks are always separate from `CRD_JSON`. Secret data is never fetched.

| Area / fetch | Separate read-only calls | Required bounded extraction |
|---|---|---|
| 1 CLUSTER_INFO | `kubectl version -o json`<br>`kubectl config current-context`<br>`kubectl cluster-info` | identity, server/client version, context; stop on mismatch. |
| 2 NODES / `NODE_JSON` | `kubectl get nodes -o json` | count; Ready/Disk/Memory/PID pressure; allocatable; providerID; labels, taints, AZ, OS, arch, capacity type, accelerators, compute type. A wide projection is derived locally. |
| 3 NAMESPACES / `NS_JSON` | `kubectl get namespaces -o json` | count, labels, PSS/tenant hints. |
| 4 DEPLOYMENTS / `DEPLOY_JSON` | `kubectl get deployments -A -o json` | replicas/status, strategy/history, images, resources, probes, SA, scheduling, lifecycle; scope/sample per scale rules. |
| 5 STATEFULSETS / `STS_JSON` | `kubectl get statefulsets -A -o json` | replicas/status, update strategy, PVC templates, probes, grace/minReadySeconds. |
| 6 DAEMONSETS / `DS_JSON` | `kubectl get daemonsets -A -o json` | rollout/placement/resources; device/CSI/host-agent detection. |
| 7 PODS / `POD_JSON` or scoped projections | `kubectl get pods -A -o json` only below payload guard<br>`kubectl get pods -A --field-selector=status.phase=Pending -o name`<br>`kubectl get pods -A --field-selector=status.phase=Failed -o name` | total/phase, CrashLoop/ImagePull/OOM/restarts, images, resources, probes, SA, security, QoS, scheduling, lifecycle; describe only bounded problem samples. At guard, obtain total from bounded namespace/name projections instead of cluster JSON. |
| 8 SERVICES / `SVC_JSON` | `kubectl get services -A -o json` | count/type distribution, selectors, LB metadata/target hints. |
| 9 ENDPOINTS | `kubectl get endpoints -A -o wide`<br>`kubectl get endpointslices -A -o wide` | empty endpoints, EndpointSlice adoption, bounded counts. |
| 10 INGRESS / `INGRESS_JSON` | `kubectl get ingressclasses -o wide`<br>`kubectl get ingress -A -o json` | count/classes/annotations/status; detect controllers from bounded pod projection; Gateway API stays area 40. |
| 11 HPA / `HPA_JSON` | `kubectl get hpa -A -o json` | count, min/max/current, targets/conditions; autoscaling feature. |
| 12 VPA | `kubectl get vpa -A -o wide` | CRD-specific presence/count/mode; NotFound = feature false. |
| 13 KEDA | `kubectl get scaledobjects -A -o wide`<br>`kubectl get triggerauthentications -A -o wide` | feature/counts/auth scope; each CRD probe remains separate. |
| 14 PDB / `PDB_JSON` | `kubectl get poddisruptionbudgets -A -o json` | count/selectors/allowed disruptions; blocking and workload coverage inputs. |
| 15 JOBS | `kubectl get jobs -A -o wide` | count, failed/active/completion summary. |
| 16 CRONJOBS | `kubectl get cronjobs -A -o wide` | count, schedules/suspension/history. |
| 17 CONFIGMAPS | `kubectl get configmaps -A -o wide` | metadata-only count; content only for explicitly named non-sensitive kube-system configs. |
| 18 SECRETS | `kubectl get secrets -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,TYPE:.type,AGE:.metadata.creationTimestamp` | metadata/type count only; never JSON/YAML/data. Helm-manifest inspection is separate gated upgrade work with explicit handling. |
| 19 EVENTS | `kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp` | bounded recent warning reasons/resources/timestamps. |
| 20 STORAGE / `SC_JSON`,`PV_JSON` | `kubectl get storageclasses -o json`<br>`kubectl get pv -o json`<br>`kubectl get pvc -A -o wide` | counts/provisioners/gp2-gp3/CSI, binding mode, encryption/KMS, PV/PVC state/AZ. Derive `storageclasses_immediate_binding` and `storageclasses_unencrypted`. |
| 21 NETWORKPOLICIES / `NP_JSON` | `kubectl get networkpolicies -A -o json` | count, namespace/default-deny coverage, selectors/types. |
| 22 RBAC / `RBAC_PROJECTION`,`SA_PROJECTION` | `kubectl get clusterroles -o json`<br>`kubectl get clusterrolebindings -o json`<br>`kubectl get roles -A -o json`<br>`kubectl get rolebindings -A -o json`<br>`kubectl get serviceaccounts -A -o json` | counts, wildcard/cluster-admin/non-system bindings, subjects, SA automount/IRSA metadata; never tokens. |
| 23 CRDS / `CRD_JSON` | `kubectl get crds -o json` | count/groups/categories only; use as hints, never as proof a specific optional API is readable. |
| 24 WEBHOOKS / `WEBHOOK_PROJECTION` | `kubectl get mutatingwebhookconfigurations -o json`<br>`kubectl get validatingwebhookconfigurations -o json` | counts, rules/scope/failure/reinvocation/timeout, service/URL, CA expiry. Derive high timeout, expiring CA, catch-all/system-risk inputs. |
| 25 CNI | `kubectl get daemonset -n kube-system aws-node -o json`<br>`kubectl get eniconfigs -o wide` | probe VPC CNI first; if absent, use `DS_JSON`/`CRD_JSON` hints plus separate Calico/Cilium probes. Extract version/env for prefix delegation, custom networking, pod ENI, policy, IPv6, SNAT. Non-VPC-CNI makes N1–N8 N/A and S15 grades installed policy CRDs. |
| 26 NETWORKING_ADVANCED / `COREDNS_PROJECTION` | `kubectl get configmap -n kube-system kube-proxy-config -o yaml`<br>`kubectl get deployment -n kube-system aws-load-balancer-controller -o json`<br>`kubectl get targetgroupbindings -A -o wide`<br>`kubectl get deployment -n kube-system coredns -o json` | proxy mode, LBC version/TGBs, service target types from `SVC_JSON`, CoreDNS replicas/placement/resources. |
| 27 KUBE_SYSTEM_RESOURCES | `kubectl get all -n kube-system -o wide`<br>`kubectl get configmap -n kube-system aws-auth -o yaml`<br>`kubectl get daemonset -n kube-system -o wide` | bounded component health, CSI/add-on/auth presence; ConfigMap content is untrusted evidence and must be redacted. |

## Failure and scale handling

NotFound for an optional CRD is `complete` with feature=false. Permission denial or timeout is `partial|n/a` with exact error; narrow and retry a huge result once. Connectivity/context failure invokes the skill stop rule. Use `<100`, `100–500`, `500–2000`, and `>2000` node tiers from the manifest; the independent 500+ pod guard always overrides broad pod JSON. Numbers here match the authoritative 49-area manifest and [`docs/resource-inventory.md`](docs/resource-inventory.md) is background only.
