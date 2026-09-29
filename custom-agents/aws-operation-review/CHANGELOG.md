# Changelog

## 1.1.0

- Migrated from `eks-operation-review` to `aws-eks-operations-review` skill (288 checks vs basic)
- The older `eks-operation-review` skill has been removed from the repository

## 1.0.0

- Initial version
- System prompt with Goal/Approach/Constraints/Output structure
- Uses both `eks-operation-review` and `rds-operation-review` skills for domain knowledge
- Requires `use_aws` and `use_kubectl` tools for resource inspection
- Output includes executive summary, findings by category, priority matrix, and next steps
- Supports EKS clusters, RDS instances, and Aurora clusters
- Severity-based prioritization with effort/impact estimates
