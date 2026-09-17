# Sample Report Excerpt

This is a condensed example showing the structure of an EKS Guardian report. A real report will be longer and contain cluster-specific data.

---

```markdown
# EKS Operational Review — prod-cluster
Account: 123456789012 | Region: us-east-1 | Date: 2026-08-13 | K8s Version: 1.30

## Executive Summary

### Health Status: ⚠️ WARNINGS (Grade: C)

### Key Metrics
┌────────────────────────────────────────────────────────┐
│  Cluster: prod-cluster   Region: us-east-1             │
│  K8s Version: 1.30       Nodes: 12                     │
│  Pods: 87                Namespaces: 6                  │
└────────────────────────────────────────────────────────┘

### Risk Summary
| | Critical | High | Medium | Low | Total |
|-|----------|------|--------|-----|-------|
| Findings | 0 | 3 | 8 | 5 | 16 |

### Section Grades
Security: C | Reliability: B | Networking: A | Scalability: B
Cost: C | Upgrades: B | Karpenter: A | **Overall: C (78/100)**

### Top 3 Actions Required
1. 🔴 **[HIGH]** Enable KMS envelope encryption for secrets — data at risk
2. 🔴 **[HIGH]** Restrict public endpoint to known CIDRs — attack surface
3. 🔴 **[HIGH]** Add PDBs to production workloads — upgrade disruption risk

### Cost Optimization Opportunity
* Estimated monthly savings: $1,240
* Quick wins: gp2→gp3 migration ($320/mo), Spot for stateless workloads ($620/mo)

### 7-Day Operational Health
* API latency: ✅ Normal (avg 45ms)
* Pod restarts: ⚠️ 73 restarts (investigate top 3 pods)
* Node failures: ✅ None
* Throttling (429): ✅ None detected

---

## Cluster Scorecard

| Section | Score | Grade | Critical | High | Medium | Low |
|---------|-------|-------|----------|------|--------|-----|
| Security | 72 | C | 0 | 2 | 3 | 2 |
| Reliability | 85 | B | 0 | 1 | 1 | 1 |
| Networking | 95 | A | 0 | 0 | 1 | 0 |
| Scalability | 82 | B | 0 | 0 | 2 | 1 |
| Cluster Upgrades | 85 | B | 0 | 0 | 1 | 1 |
| Cost Optimization | 70 | C | 0 | 0 | 3 | 0 |
| Karpenter | 93 | A | 0 | 0 | 1 | 0 |
| **Overall** | **78** | **C** | **0** | **3** | **8** | **5** |

---

## Add-ons Inventory

| Add-on | Version | Type | Status | Notes |
|--------|---------|------|--------|-------|
| vpc-cni | v1.18.1 | EKS Managed | ACTIVE | ✅ Current |
| coredns | v1.11.1 | EKS Managed | ACTIVE | ✅ Current |
| kube-proxy | v1.30.0 | EKS Managed | ACTIVE | ✅ Current |
| aws-ebs-csi-driver | v1.28.0 | EKS Managed | ACTIVE | ✅ Current |
| karpenter | v0.37.0 | Self-managed | Running | ⚠️ v1.0+ available |

---

## Findings — Security (Grade: C, Score: 72/100)

| # | Finding | Severity | Current State | Recommendation |
|---|---------|----------|---------------|----------------|
| 1 | KMS envelope encryption not enabled | HIGH | Secrets stored without KMS | Enable KMS encryption: `aws eks associate-encryption-config` |
| 2 | Public API endpoint unrestricted | HIGH | 0.0.0.0/0 allowed | Restrict to known CIDRs or switch to private endpoint |
| 3 | aws-auth ConfigMap still in use | MEDIUM | Mixed auth mode | Migrate to Access Entries (API mode) |
| 4 | Control plane audit logging disabled | MEDIUM | 3 of 5 log types enabled | Enable all 5: api, audit, authenticator, controllerManager, scheduler |
| 5 | IMDSv2 not enforced on nodes | MEDIUM | httpTokens=optional | Set httpTokens=required in node group launch template |
| 6 | ServiceAccounts without IRSA | LOW | 4 SAs using node role | Add IRSA annotations or migrate to Pod Identity |
| 7 | No Pod Security Standards enforced | LOW | Labels missing on namespaces | Add `pod-security.kubernetes.io/enforce: baseline` labels |

---

## CloudWatch Metrics (7-Day)

| Metric | Category | 7-Day Avg | 7-Day Max | Status | Finding |
|--------|----------|-----------|-----------|--------|---------|
| node_cpu_utilization | Compute | 42% | 78% | ✅ Normal | — |
| node_memory_utilization | Compute | 61% | 89% | ⚠️ Warning | Approaching saturation on peak |
| pod_number_of_container_restarts | Reliability | 10.4/day | 31 | ⚠️ Warning | Top offender: payment-service (OOMKilled) |
| apiserver_request_duration_seconds | Control Plane | 45ms | 120ms | ✅ Normal | — |
| cluster_failed_node_count | Data Plane | 0 | 0 | ✅ Normal | — |

---

## Priority Matrix

| Rank | Finding | Priority Score | Severity | Blast Radius | Fix Effort | ETA |
|------|---------|---------------|----------|-------------|-----------|-----|
| 1 | Enable KMS encryption | 22 | HIGH (4) | Cluster (4) | One cmd (4) | 1h |
| 2 | Restrict public endpoint | 20 | HIGH (4) | Cluster (4) | Config (3) | 30m |
| 3 | Add PDBs to prod workloads | 19 | HIGH (4) | Multi-ns (3) | Config (3) | 2h |
| 4 | Enable all control plane logs | 16 | MEDIUM (3) | Cluster (4) | One cmd (4) | 15m |
| 5 | Enforce IMDSv2 | 15 | MEDIUM (3) | Cluster (4) | Config (3) | 1h |

---

## Next Steps

### Immediate (CRITICAL/HIGH — within 7 days)
1. Enable KMS envelope encryption for secrets
2. Restrict public API endpoint to known CIDRs
3. Add PodDisruptionBudgets to all production deployments

### Short-term (MEDIUM — within 30 days)
4. Enable all 5 control plane log types
5. Enforce IMDSv2 on all node groups
6. Migrate from aws-auth to Access Entries
7. Investigate payment-service OOMKilled restarts
8. Migrate gp2 volumes to gp3

### Long-term (LOW — within 90 days)
9. Add IRSA to remaining ServiceAccounts
10. Enforce Pod Security Standards on all namespaces
```

---

**Note:** This is a shortened excerpt. A full report for a production cluster typically includes 100–300 lines depending on cluster complexity and number of findings.
