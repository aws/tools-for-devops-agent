# Changelog

## 1.0.0
- Initial version
- System prompt that routes GenAI and LLMOps questions to the OpsAI skills: `opsai-incident-triage`, `opsai-bedrock-review` (Bedrock configuration and knowledge bases), `opsai-bedrock-security` (permissions audit and guardrails), `opsai-capacity-cost`, `opsai-bedrock-agentcore`, `opsai-ml-eval-check` (Bedrock and SageMaker evaluation), `opsai-sagemaker-inference` (endpoints, batch transform and endpoint cost) and `opsai-sagemaker-training` (training and Model Registry)
- Three modes: incident triage (leads with a `TRIAGE:` line), on-demand investigation, and a scheduled proactive posture assessment
- Read-only; uses the `use_aws` tool
- Check-ids are unchanged across the consolidation (LLM-EVAL, LLM-SM, LLM-SM-SERVE, LLM-SM-BATCH, LLM-SM-EVAL, LLM-SM-TRAIN, LLM-SM-REG and the Bedrock families).
