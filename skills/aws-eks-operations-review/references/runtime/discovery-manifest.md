# Ordered discovery manifest

Load during the **Discovery phase** and execute every command through the AWS DevOps Agent MCP tool `use_kubectl`. “Discovery phase” is a workflow stage, not Amazon S3: do not upload, write, or persist any result to Amazon S3 or a file. Keep only bounded transient projections in conversation. Exact commands and extraction details are in `../kubectl-discovery-commands.md` (areas 1–27) and `../kubectl-discovery-commands-deep-dive.md` (28–49); read each only when its range executes. This manifest is the authoritative ordered area/cache/projection index.

## Cache contract

Cache only within one confirmed cluster/context/scope and record timestamp, resourceVersion where available, namespace scope, and command. Project immediately to bounded evidence and drop raw JSON after all dependent areas. CRD-specific/not-found probes are never inferred from a generic cache.

| Area | Name | Command source | Reusable fetch / required projection |
|---:|---|---|---|
| 1 | CLUSTER_INFO | core §1 | version/context → identity |
| 2 | NODES | core §2 | `NODE_JSON` → counts, conditions, capacity, provider IDs |
| 3 | NAMESPACES | core §3 | `NS_JSON` → count, labels |
| 4 | DEPLOYMENTS | core §4 | `DEPLOY_JSON` → replicas, strategy, images, resources, probes, SA |
| 5 | STATEFULSETS | core §5 | `STS_JSON` → replicas, strategy, PVCs, probes |
| 6 | DAEMONSETS | core §6 | `DS_JSON` → rollout, placement, resources |
| 7 | PODS | core §7 | `POD_JSON` if allowed; otherwise scoped projections → health counts/sample |
| 8 | SERVICES | core §8 | `SVC_JSON` → service counts/types |
| 9 | ENDPOINTS | core §9 | endpoint/EndpointSlice summaries |
| 10 | INGRESS | core §10 | `INGRESS_JSON` + bounded pod view → ingress/controllers |
| 11 | HPA | core §11 | `HPA_JSON` → counts/ranges |
| 12 | VPA | core §12 | CRD probe/VPA summary |
| 13 | KEDA | core §13 | CRD probes → KEDA features |
| 14 | PDB | core §14 | `PDB_JSON` → counts/coverage inputs |
| 15 | JOBS | core §15 | job summary |
| 16 | CRONJOBS | core §16 | cronjob schedules/counts |
| 17 | CONFIGMAPS | core §17 | metadata-only count |
| 18 | SECRETS | core §18 | metadata/type only; never Secret data |
| 19 | EVENTS | core §19 | bounded warning events/reasons |
| 20 | STORAGE | core §20 | `SC_JSON`, `PV_JSON`, PVC summary → storage/encryption/binding |
| 21 | NETWORKPOLICIES | core §21 | `NP_JSON` → namespace/default-deny coverage |
| 22 | RBAC | core §22 | `RBAC_PROJECTION`, `SA_PROJECTION` → privileged/wildcard/identity counts |
| 23 | CRDS | core §23 | `CRD_JSON` → groups/categories (hints only; named probes stay separate) |
| 24 | WEBHOOKS | core §24 | `WEBHOOK_PROJECTION` → scope/failure/timeout/certificate projections |
| 25 | CNI | core §25 | aws-node/CNI-specific probes → CNI type/config gates |
| 26 | NETWORKING_ADVANCED | core §26 | proxy/LBC/TGB + `COREDNS_PROJECTION` → modes/versions/targets |
| 27 | KUBE_SYSTEM_RESOURCES | core §27 | bounded kube-system inventory/auth metadata |
| 28 | AUTOSCALING_INFRA | deep §28 | reuse NODE/POD; NodePool/NodeClass/NodeClaim/CAS probes → autoscaling facts |
| 29 | OBSERVABILITY | deep §29 | reuse bounded POD; monitor CRD probes → tooling features |
| 30 | SERVICE_MESH | deep §30 | namespace/pod/CRD probes → mesh features |
| 31 | GITOPS | deep §31 | reuse bounded POD; Argo/Flux CRD probes → reconciliation facts |
| 32 | COST_OPTIMIZATION | deep §32 | reuse POD/NODE/SC → cost tooling, Spot, Arm, gp2 |
| 33 | THIRD_PARTY_CONTROLLERS | deep §33 | reuse bounded POD/CRD → controller features |
| 34 | SECURITY | deep §34 | reuse NS/POD/bindings/SA; policy-engine probes → security counts |
| 35 | RELIABILITY | deep §35 | reuse DEPLOY/POD/PDB; quota/limit projections → HA facts |
| 36 | DATA_PLANE | deep §36 | reuse NODE_JSON → instance/capacity/AZ/OS/accelerator/hybrid gates |
| 37 | SCALABILITY | deep §37 | reuse counts/CoreDNS/INGRESS/DEPLOY/POD; deprecated API probes |
| 38 | AI_ML_WORKLOADS | deep §38 | reuse NODE/DS/POD → accelerator/plugin/framework counts |
| 39 | IMAGE_SECURITY | deep §39 | reuse POD projection → registries/tags/pull policy |
| 40 | GATEWAY_API | deep §40 | Gateway CRD-specific probes → controller/resource health |
| 41 | DNS_CONFIG | deep §41 | reuse CoreDNS/POD; NodeLocal probe → DNS features |
| 42 | SECRETS_MANAGEMENT | deep §42 | bounded POD + SPC/CSI probes → integration/rotation |
| 43 | SERVICE_ACCOUNTS | deep §43 | reuse SA/POD + aws-node SA → IRSA/Pod Identity/CNI role |
| 44 | SCHEDULING | deep §44 | runtime/priority classes + POD projection → scheduling facts |
| 45 | BACKUP_DR | deep §45 | snapshot/Velero CRD probes → backup coverage |
| 46 | MULTI_TENANCY | deep §46 | reuse NS/NP + quotas → tenant isolation coverage |
| 47 | RESOURCE_OPTIMIZATION | deep §47 | reuse POD/DEPLOY; bounded top output → QoS/usage/singletons |
| 48 | NAMESPACE_SUMMARY | deep §48 | namespace-scoped names/counts → bounded summary |
| 49 | INVENTORY_ROLLUP | deep §49 | all projections → validated inventory schema |

## Scale rules

- `<100` nodes: full sequential sweep.
- `100–500` nodes: full sweep, sequential; no concurrent broad JSON calls.
- `500–2000` nodes: namespace samples plus aggregate projections; avoid whole-cluster pod JSON.
- `>2000` nodes: namespace projections and telemetry for fleet-wide signals.
- Independently, at **500+ pods**, never fetch/retain `pods -A -o json`; use namespace batches, field selectors, custom columns, and bounded samples.

## Area status

Every area gets exactly one `complete|partial|n/a` record. A cached extraction counts as attempted only when cache provenance matches the current identity/scope and the area-specific extraction ran. NotFound for an optional CRD is `complete` with feature=false. RBAC/timeout is `n/a` or `partial` with the exact error. More than 30% failures in a phase triggers the skill stop condition.