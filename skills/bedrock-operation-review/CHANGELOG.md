# Changelog

## [1.0.0] - 2026-07-XX
### Added
- Initial release adapted from AWS Support Specialist skill
- Comprehensive Amazon Bedrock operational review aligned with the AWS Well-Architected Framework and Bedrock best practices
- Five review pillars: Security, Performance, Service Quotas, Cost Optimization, and Resilience
- Resource discovery across foundation models, guardrails, inference profiles, prompt routers, provisioned throughput, custom models, agents, knowledge bases, data sources, and Prompt Management
- CloudWatch metric collection and threshold-based classification (Normal/Warning/Critical) in the `AWS/Bedrock` namespace
- Service quota utilization analysis (RPM/TPM including CRIS) via Service Quotas API
- Cost optimization checks: prompt caching, model distillation, batch inference, provisioned throughput, intelligent prompt routing, and self-managed EC2 GPU utilization
- Cross-Region Inference (CRIS) adoption analysis for resilience
- Severity-ranked findings (CRITICAL, HIGH, MEDIUM, LOW, INFO) and a shareable Markdown report artifact
- AWS-API-only data collection (Bedrock, Bedrock Agent, CloudWatch, Service Quotas, EC2) with no data-plane model invocations and no prompt/response content read
- Reference files: best-practices checklist and CloudWatch metric thresholds
- Evaluation test cases (5 functional evals, 6 trigger queries)
