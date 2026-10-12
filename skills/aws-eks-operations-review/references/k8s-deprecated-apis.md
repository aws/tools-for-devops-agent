# Kubernetes deprecated / removed API database

Reference data for **U5 / U5b / U5c** (deprecated-API checks) in [`upgrade-readiness.md`](upgrade-readiness.md). When grading a target Kubernetes version, flag any live resource, CRD, webhook, or Helm-stored manifest still using an `apiVersion` whose **removed-in** is ≤ the target version (**Critical** — the object becomes unservable after upgrade), and warn on any whose **deprecated-in** ≤ target but **removed-in** > target (**Medium** — proactive).

Source: derived from the [FairwindsOps/pluto `versions.yaml`](https://github.com/FairwindsOps/pluto/blob/master/versions.yaml). This is a **prebaked cache** — re-resolve against pluto / `kubectl deprecations` / EKS Cluster Insights (AX1) at report time, since new removals land each release. EKS Cluster Insights remains the authoritative removed-API signal; this table is the fast offline first pass.

## How to use

1. From discovery: list CRD/webhook/FlowSchema/etc. `apiVersion`s (area 23/24) and, for the Helm path, decode release-secret manifests (see U5c).
2. For the **target** minor version, match observed `apiVersion`+`kind` against the tables below.
3. `removed-in ≤ target` → **Critical** FAIL (migrate before the control-plane upgrade). `deprecated-in ≤ target < removed-in` → **Medium** warning.
4. Use `replacement-api` for the remediation (`kubectl-convert`, or bump the chart/CRD).

## Kubernetes core APIs

| Removed in | apiVersion | Kind | Deprecated in | Replacement |
|-----------|-----------|------|---------------|-------------|
| v1.16 | extensions/v1beta1 | Deployment | v1.9 | apps/v1 |
| v1.16 | apps/v1beta1, apps/v1beta2 | Deployment | v1.9 | apps/v1 |
| v1.16 | apps/v1beta1, apps/v1beta2 | StatefulSet | v1.9 | apps/v1 |
| v1.16 | extensions/v1beta1, apps/v1beta2 | DaemonSet | v1.9 | apps/v1 |
| v1.16 | extensions/v1beta1, apps/v1beta1, apps/v1beta2 | ReplicaSet | — | apps/v1 |
| v1.16 | extensions/v1beta1 | NetworkPolicy | v1.9 | networking.k8s.io/v1 |
| v1.16 | extensions/v1beta1 | PodSecurityPolicy | v1.10 | policy/v1beta1 |
| v1.17 | scheduling.k8s.io/v1alpha1 | PriorityClass | v1.14 | scheduling.k8s.io/v1 |
| v1.22 | extensions/v1beta1, networking.k8s.io/v1beta1 | Ingress | v1.14 / v1.19 | networking.k8s.io/v1 |
| v1.22 | networking.k8s.io/v1beta1 | IngressClass | v1.19 | networking.k8s.io/v1 |
| v1.22 | scheduling.k8s.io/v1beta1 | PriorityClass | v1.14 | scheduling.k8s.io/v1 |
| v1.22 | apiextensions.k8s.io/v1beta1 | CustomResourceDefinition | v1.16 | apiextensions.k8s.io/v1 |
| v1.22 | admissionregistration.k8s.io/v1beta1 | Mutating/ValidatingWebhookConfiguration | v1.16 | admissionregistration.k8s.io/v1 |
| v1.22 | rbac.authorization.k8s.io/v1alpha1, v1beta1 | ClusterRole(Binding), Role(Binding) | v1.17 | rbac.authorization.k8s.io/v1 |
| v1.22 | storage.k8s.io/v1beta1 | CSINode, CSIDriver, StorageClass, VolumeAttachment | v1.6–v1.19 | storage.k8s.io/v1 |
| v1.22 | apiregistration.k8s.io/v1beta1 | APIService | v1.10 | apiregistration.k8s.io/v1 |
| v1.22 | authentication.k8s.io/v1beta1 | TokenReview | v1.6 | authentication.k8s.io/v1 |
| v1.22 | certificates.k8s.io/v1beta1 | CertificateSigningRequest | v1.19 | certificates.k8s.io/v1 |
| v1.22 | coordination.k8s.io/v1beta1 | Lease | v1.14 | coordination.k8s.io/v1 |
| v1.22 | authorization.k8s.io/v1beta1 | (Self/Local)SubjectAccessReview, SelfSubjectRulesReview | v1.19 | authorization.k8s.io/v1 |
| v1.24 | audit.k8s.io/v1alpha1, v1beta1 | Policy | v1.21 | audit.k8s.io/v1 |
| v1.25 | policy/v1beta1 | PodSecurityPolicy | v1.21 | (removed — use PSA/policy engine) |
| v1.25 | policy/v1beta1 | PodDisruptionBudget | v1.21 | policy/v1 |
| v1.25 | node.k8s.io/v1beta1 | RuntimeClass | v1.22 | node.k8s.io/v1 |
| v1.25 | autoscaling/v2beta1 | HorizontalPodAutoscaler | v1.22 | autoscaling/v2 |
| v1.25 | batch/v1beta1 | CronJob | v1.21 | batch/v1 |
| v1.25 | events.k8s.io/v1beta1 | Event | v1.19 | events.k8s.io/v1 |
| v1.25 | discovery.k8s.io/v1beta1 | EndpointSlice | v1.21 | discovery.k8s.io/v1 |
| v1.26 | autoscaling/v2beta2 | HorizontalPodAutoscaler | v1.23 | autoscaling/v2 |
| v1.26 | flowcontrol.apiserver.k8s.io/v1beta1 | FlowSchema, PriorityLevelConfiguration | v1.23 | flowcontrol.apiserver.k8s.io/v1beta2 |
| v1.27 | storage.k8s.io/v1beta1 | CSIStorageCapacity | v1.24 | storage.k8s.io/v1 |
| v1.29 | flowcontrol.apiserver.k8s.io/v1beta2 | FlowSchema, PriorityLevelConfiguration | v1.24 | flowcontrol.apiserver.k8s.io/v1beta3 |
| v1.32 | flowcontrol.apiserver.k8s.io/v1beta3 | FlowSchema, PriorityLevelConfiguration | v1.29 | flowcontrol.apiserver.k8s.io/v1 |
| v1.33 | admissionregistration.k8s.io/v1alpha1 | ValidatingAdmissionPolicy, ValidatingAdmissionPolicyBinding | v1.28 | admissionregistration.k8s.io/v1 |
| v1.34 | resource.k8s.io/v1alpha3 | ResourceSlice, ResourceClaim, DeviceClass, ResourceClaimTemplate | v1.32 | resource.k8s.io/v1beta1 |
| v1.35 | storage.k8s.io/v1alpha1 | VolumeAttributesClass | v1.31 | storage.k8s.io/v1 |
| v1.35 | storagemigration.k8s.io/v1alpha1 | StorageVersionMigration | v1.35 | storagemigration.k8s.io/v1beta1 |
| v1.36 | resource.k8s.io/v1beta1 | ResourceSlice, ResourceClaim, DeviceClass, ResourceClaimTemplate | v1.33 | resource.k8s.io/v1beta2 |

## Third-party CRDs

| Component | Removed in | apiVersion | Kind | Replacement |
|-----------|-----------|-----------|------|-------------|
| Istio | v1.4 | rbac.istio.io | ServiceRole / ServiceRoleBinding / ClusterRbacConfig | `security.istio.io/v1beta1` AuthorizationPolicy |
| Istio | v1.6 | authentication.istio.io/v1alpha1 | (all) | security.istio.io/v1beta1 |
| cert-manager | v0.11 | certmanager.k8s.io/v1alpha1 | Certificate, Issuer, ClusterIssuer | cert-manager.io/v1alpha2 |
| cert-manager | v1.6 | cert-manager.io/v1alpha2, v1alpha3, v1beta1 | Certificate, Issuer, ClusterIssuer, CertificateRequest | cert-manager.io/v1 |
| cert-manager | v1.6 | acme.cert-manager.io/v1alpha2, v1beta1 | Order, Challenge | acme.cert-manager.io/v1 |

These map to upgrade-readiness **U5d** (third-party API deprecations). Cross-check the component's own version against its compatibility matrix (Karpenter / Istio / cert-manager / AWS LB Controller) as well — a CRD apiVersion that is still served can still require a controller upgrade.
