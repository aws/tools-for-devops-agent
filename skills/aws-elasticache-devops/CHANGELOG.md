# Changelog

## 1.0.0

- Initial version: reference files for root-cause analysis of ElastiCache incidents:
  deployment discovery, ElastiCache for Valkey OpenTelemetry metrics (PromQL), classic
  CloudWatch metrics, events and CloudTrail changes, parameters, slow and engine logs,
  engine commands for the operator, and engine error replies.
- Safety rules for every investigation: classic metrics where OpenTelemetry has no
  equivalent, no data-losing fix without the condition that the data is safe to lose,
  only engine commands that do not hurt the node, and no capacity change for a hot key,
  an unbounded collection or a client-side cause.
- Approval-gated mitigation (Step 6 and `references/propose-mitigation.md`): when the operator
  asks in chat, the agent proposes one directed action with a pre-check, applies it after
  approval, verifies it and reports the rollback.
