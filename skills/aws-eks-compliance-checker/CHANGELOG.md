# Changelog

## 1.0.0

- Initial version. Grades the CIS Amazon EKS Benchmark v1.8.0 (control IDs, titles, and types per the kube-bench `eks-1.8.0` profile) from read-only Kubernetes and AWS evidence, adds nine supplementary AWS checks (three aligned with Security Hub EKS.2, EKS.8, and EKS.9), and maps results to NIST SP 800-53 Rev. 5, PCI DSS v4.0.1, SOC 2, and HIPAA.
- Split out of the compliance overlay drafted for `aws-eks-operations-review` in PR #159, at the maintainers' request, so that framework mapping has its own skill instead of depending on an operations review.
- Tested against a purpose-built EKS 1.37 cluster with planted CIS violations. Rule fixes from that testing: CIS 4.3.1 reads `--enable-network-policy` instead of the node agent's presence, CIS 5.5.1 accepts any IAM principal, AWS-6 handles images outside the account's ECR, AWS-2 uses `versionStatus` rather than `upgradePolicy.supportType`, crosswalk rows name the Security Hub control, and Inspector coverage reads page through results.
