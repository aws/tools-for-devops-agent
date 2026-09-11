# Changelog

## 1.0.0

- Initial version.
- Validates and bootstraps Amazon Bedrock AgentCore observability using a verify-where-reachable /
  prescribe-everywhere-else model.
- Covers Runtime agents, Memory and Gateway resources, built-in tools, and non-runtime hosts
  (Lambda, ECS, EKS, on-prem, multi-cloud).
- Three read-only IAM tiers with graceful degradation and scoped inline policy JSON.
- Check catalog and per-host remediation references (Transaction Search, ADOT SDK, unified span
  destination, X-Ray log-group resource policy, Memory/Gateway log & trace delivery).
