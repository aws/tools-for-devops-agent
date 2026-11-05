# Changelog

All notable changes to the `eks-guardian` skill will be documented in this file.

## [1.0.0] — 2026-08-13

### Added

- Initial release of EKS Operational Review skill
- 12 best-practice sections covering Security, Reliability, Networking, Scalability, Cost Optimization, Karpenter, Cluster Autoscaler, EKS Auto Mode, Cluster Upgrades, and conditional sections (Windows, Hybrid, AI/ML)
- 7-day CloudWatch metrics collection and analysis with severity thresholds
- 7-day CloudWatch Logs pattern detection (errors, throttling, OOMKilled, FailedScheduling, evictions)
- 7-day CloudTrail event analysis for configuration changes and security concerns
- EKS Upgrade Insights integration
- K8s API-first data collection with AWS API fallback
- Shareable Markdown report artifact per cluster
- Executive summary with health status and priority matrix
- Cluster scoring (A–F) per section and overall, with weighted grading
- Multi-cluster comparison mode and environment drift detection
- Historical delta analysis and risk score trending against previous reports
- Custom severity overrides with accepted-risk statements
- Auto-prioritization matrix (severity × blast radius × ease of fix)
- Compliance mapping (CIS, SOC2, PCI-DSS, HIPAA, NIST 800-53)
- Karpenter cost modeling, workload right-sizing, and FinOps analysis
- Namespace-level security report, network policy gap analysis, IRSA/Pod Identity audit
- Incident correlation, add-on vulnerability check, blast radius and toil reduction analysis
- Disaster recovery assessment and golden config target-state template
- Error handling for K8s API/CloudWatch unavailability, insufficient permissions, throttling, and partial failures
- Reference files: best-practices-checklist.md, metrics-thresholds.md, remediation-catalog.md, cross-account-scanning.md, compliance-mapping.md, upgrade-readiness-playbook.md, sample-report-excerpt.md
