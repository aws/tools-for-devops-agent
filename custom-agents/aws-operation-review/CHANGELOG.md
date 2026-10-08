# Changelog

## 1.1.0

- Migrated from `eks-operation-review` to `aws-eks-operations-review` skill (288 checks vs basic)
- The older `eks-operation-review` skill has been removed from the repository
- Added Amazon SageMaker AI support via the `sagemaker-ai-ops-review` skill — endpoints, training jobs, pipelines, notebooks, and Studio domains
- Documented that SageMaker AI reviews need `sagemaker-ai-ops-review` uploaded with "All agents" selected, and that `AIDevOpsAgentAccessPolicy` covers every API it calls except the optional `savingsplans:DescribeSavingsPlans`
- Noted the `sagemaker-ai-ops-review` report schema (eight pillars, verbatim AI Disclaimer, severity-ranked Executive Summary) in the report-schema deference guidance, and added a SageMaker artifact naming example
- Severity now defers to the selected skill's scale rather than a fixed `critical/high/medium/low` set, so a skill defining its own model — `sagemaker-ai-ops-review` uses High/Medium/Low plus Informational — is not re-scored onto a different one

## 1.0.0

- Initial version
- System prompt with Goal/Approach/Constraints/Output structure
- Uses both `eks-operation-review` and `rds-operation-review` skills for domain knowledge
- Requires `use_aws` and `use_kubectl` tools for resource inspection
- Output includes executive summary, findings by category, priority matrix, and next steps
- Supports EKS clusters, RDS instances, and Aurora clusters
- Severity-based prioritization with effort/impact estimates
