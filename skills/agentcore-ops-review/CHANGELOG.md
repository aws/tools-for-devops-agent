# Changelog

## [1.0.1] - 2026-09-16

### Changed
- Clarified the data-boundary documentation: `bedrock-agentcore:ListMemoryRecords` is a data-plane call and its response can include PII-bearing memory `content`. The skill uses it **only** to count records (AC-MEM-2) and never reads, stores, or reproduces `content`. Updated SKILL.md, README (new "Memory record data handling" section), references, sample IAM policies, and the CloudFormation block to state this accurately, and separated the action into its own clearly-labeled IAM statement so it can be omitted for zero data-plane access.

## [1.0.0] - 2026-09-10

### Added
- Initial release of the `agentcore-ops-review` skill for AWS DevOps Agent.
- Runtime Resilience checks (AC-RUN-1..4): failed/stuck runtime and endpoint states, single-AZ VPC placement, endpoint version drift, and DEFAULT-endpoint-only deployments.
- Gateway Health check (GW-01): gateway status, target redundancy and health, policy engine attachment, and target synchronization freshness.
- Memory & Knowledge Effectiveness checks (AC-MEM-1..4): strategy-aware extraction-error, empty long-term memory, high ingestion error rate, and provisioned-but-never-populated detection.
- Resource Utilization & Operational Hygiene checks (AC-UTIL-1..3): idle resources, consolidation opportunities, and low overall utilization. Estate discovery covers runtimes, memories, gateways, browsers, code interpreters, and workload identities.
- Cross-pillar runtime observability from the `AWS/Bedrock-AgentCore` CloudWatch namespace (`SessionCount`, `Invocations`, `Throttles`, `CPUUsed-vCPUHours`, `MemoryUsed-GBHours`), with `ActiveSessionCount` preferred for the idle-resource signal where available.
- Two IAM modes: runtime-observability-only (CloudWatch only) and full control-plane (read-only `bedrock-agentcore:` set + `ec2:DescribeSubnets`). Missing permissions degrade affected checks to visibility limits rather than failing the review.
- Structured report artifact with executive summary, prioritized findings, KPI summary, per-pillar detail, visibility limits, and methodology (`references/report-template.md`).
- Sample IAM policies for observability-only, linked, and management accounts.
