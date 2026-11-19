# Changelog

## 1.0.0
- Initial version
- System prompt that routes GenAI and LLMOps questions to the OpsAI skills: `opsai-incident-triage`, `opsai-bedrock-review` (Bedrock configuration and knowledge bases), `opsai-bedrock-security` (permissions audit and guardrails), `opsai-capacity-cost`, `opsai-bedrock-agentcore`, and the quality-evaluation and SageMaker skills
- Three modes: incident triage (leads with a `TRIAGE:` line), on-demand investigation, and a scheduled proactive posture assessment
- Read-only; uses the `use_aws` tool
