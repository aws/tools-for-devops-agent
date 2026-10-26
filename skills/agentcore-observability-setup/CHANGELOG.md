# Changelog

## 1.0.2
- README: corrected the agent types to the names the operator app shows (`Chat tasks`, `Incident triage`, `All agents`) and removed `Evaluation` and `On-demand`, which are not agent types.

## 1.0.1
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## 1.0.0

- Initial version.
- Validates and bootstraps Amazon Bedrock AgentCore observability using a verify-where-reachable /
  prescribe-everywhere-else model.
- Covers Runtime agents, Memory and Gateway resources, built-in tools, and non-runtime hosts
  (Lambda, ECS, EKS, on-prem, multi-cloud).
- Three read-only IAM tiers with graceful degradation and scoped inline policy JSON.
- Check catalog and per-host remediation references (Transaction Search, ADOT SDK, unified span
  destination, X-Ray log-group resource policy, Memory/Gateway log & trace delivery).
