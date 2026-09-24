# Changelog

## 1.1.0

- Added Amazon SageMaker AI support via the `sagemaker-ops-review` skill — endpoints, training jobs, pipelines, notebooks, feature store, model registry, and Studio domains
- Documented that SageMaker AI reviews need `sagemaker-ops-review` uploaded with "All agents" selected, and that `AIDevOpsAgentAccessPolicy` covers every API it calls except the optional `savingsplans:DescribeSavingsPlans`
- Noted the `sagemaker-ops-review` report schema (eight pillars, verbatim AI Disclaimer, severity-ranked Executive Summary) in the report-schema deference guidance, and added a SageMaker artifact naming example

## 1.0.0

- Initial version
- System prompt with Goal/Approach/Constraints/Output structure
- Uses both `eks-operation-review` and `rds-operation-review` skills for domain knowledge
- Requires `use_aws` and `use_kubectl` tools for resource inspection
- Output includes executive summary, findings by category, priority matrix, and next steps
- Supports EKS clusters, RDS instances, and Aurora clusters
- Severity-based prioritization with effort/impact estimates
