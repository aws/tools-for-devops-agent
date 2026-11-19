# Changelog

## 1.0.0

- Initial version: root-cause analysis for ElastiCache incidents using ElastiCache for
  Valkey OpenTelemetry metrics (PromQL), classic CloudWatch metrics, events, parameter
  groups and delivered slow logs.
- Approval-gated mitigation (Step 7 and `references/mitigation.md`): when the operator
  asks in chat, the agent proposes one directed action with a pre-check, applies it after
  approval, verifies it and reports the rollback.
