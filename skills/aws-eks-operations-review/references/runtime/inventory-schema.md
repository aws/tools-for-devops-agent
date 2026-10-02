# Runtime inventory contract

Load only in S4. Retain this bounded structure in the transient ledger; never create a file. Every value records source area and timestamp. `0`/`false` means the area was successfully observed and absent; `null` means unavailable, partial, denied, timed out, or outside scope and requires a reason.

## Required top-level keys

`identity{account,region,cluster,context,environment,namespace_scope,window}` · `coverage{area_id:complete|partial|n/a}` · `source_attempts[]` · `counts{}` · `features{}` · `gates{}` · `evidence{check_or_signal:{value,source,scope,timestamp,resource_id}}`.

## Required `counts.*`

| Group | Keys |
|---|---|
| Core | `nodes,namespaces,pods,deployments,statefulsets,daemonsets,services,ingresses,jobs,cronjobs,configmaps,secrets,networkpolicies,crds,pvs,pvcs,storageclasses,hpa,vpa,keda_scaledobjects,pdb` |
| Node/pod health | `nodes_notready,nodes_diskpressure,nodes_memorypressure,nodes_pidpressure,pods_pending,pods_failed,pods_crashloop,pods_imagepull,pods_oomkilled` |
| Reliability | `workloads_without_pdb,pdb_blocking,rollout_maxunavail_risky,single_az_nodes,containers_with_liveness,containers_without_liveness,containers_with_readiness,containers_without_readiness` |
| API scale | `endpointslices_in_use,deploys_unbounded_history,service_links_enabled,webhooks_on_pods,mutating_webhooks,validating_webhooks` |
| Security | `privileged_pods,hostnetwork_pods,hostpid_pods,hostipc_pods,hostpath_pods,privilege_escalation_allowed,capabilities_not_dropped,seccomp_not_runtimedefault,readonly_rootfs_true,readonly_rootfs_false,runasnonroot_true,kyverno_policies,gatekeeper_constraints` |
| Governance | `resourcequotas,limitranges,priorityclasses` |
| Fleet/gates | `karpenter_nodepools,karpenter_ec2nodeclasses,karpenter_nodeclaims,gpu_nodes,neuron_nodes,efa_nodes,coredns_replicas,node_azs,spot_nodes,ondemand_nodes,bottlerocket_nodes,windows_nodes,hybrid_nodes` |

## Required derived signals

| Keys | Canonical checks |
|---|---|
| `storageclasses_immediate_binding,lbfronted_no_prestop` | R19,R18 |
| `storageclasses_unencrypted,webhooks_high_timeout,webhooks_cabundle_expiring,secrets_store_csi_rotation_off,awsnode_uses_node_role` | S32–S36 |
| `nodepools_overlap_unweighted,spot_to_spot_consolidation_off,karpenter_ami_latest,karpenter_self_hosted,spot_nodepool_low_diversity,donotdisrupt_pods,cas_version_mismatch,cas_autodiscovery,automode_selfmanaged_dupes,dual_autoscaler` | Op27,Op28,Op11,Op20,Op22,OpM8,Op9,Op24/OpM2,Op17,Op18 |
| `initcontainer_request_inflation` | P14 |
| `hostnetwork_port_conflicts,gatewayapi_unhealthy` | N25,N26 |

## Required `features.*`

| Group | Keys |
|---|---|
| `autoscaling` | `hpa,vpa,keda,cluster_autoscaler,karpenter,eks_auto_mode` |
| `ingress_controllers` | `nginx,alb,traefik` |
| `cni` | `vpc_cni,calico,cilium,weave,flannel` |
| `cni_config` | `prefix_delegation,custom_networking,security_groups_for_pods,vpc_cni_network_policy,ipv6_cluster,external_snat,vpc_cni_version` |
| `networking` | `kube_proxy_mode,aws_lb_controller,nodelocaldns,dns_autoscaler,external_dns` |
| `service_mesh` | `istio,linkerd,appmesh` |
| `observability` | `prometheus,grafana,opentelemetry,cloudwatch_agent,fluentbit,kube_state_metrics,metrics_server,cni_metrics_helper,node_exporter,adot,xray,vector,datadog,dynatrace,newrelic,splunk,elastic,alertmanager,dcgm_exporter` |
| `gitops` | `argocd,fluxcd` |
| `cost_optimization` | `kubecost,goldilocks,opencost` |
| `security` | `kyverno,gatekeeper,falco,guardduty,irsa,pod_identity,aws_auth_present` |
| `third_party_controllers` | `ack,external_secrets,cert_manager,aws_lb_controller,crossplane,sealed_secrets,reloader,velero` |
| `gateway_controllers` | `vpc_lattice,envoy_gateway,contour,kong,ambassador,apisix` |
| `dns` | `nodelocaldns,dns_autoscaler,external_dns` |
| `compute` | `fargate` |
| `karpenter` | `nodepools,ec2nodeclasses,nodeclaims,provisioners_legacy,awsnodetemplates_legacy` |

## Validation

All 49 coverage entries are required. Every selected check's source key must be present or explicitly `null` with the source error. AWS-managed facts not observable in-cluster are `null`, never `false`. Record gate values for Auto Mode, IPv6, Fargate, CNI type, Windows, Hybrid, accelerators, EKS Anywhere, upgrade scope, and telemetry availability. Full background and examples are in [`../docs/operator-guides.md#inventory-schema`](../docs/operator-guides.md#inventory-schema); they are not runtime authority.