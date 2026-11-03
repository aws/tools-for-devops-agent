# Changelog

## 1.0.0 (2026-10-27)

- Initial contribution to aws/tools-for-devops-agent: MediaConnect Deep Investigation.
- Covers flow state and error messages, source connectivity, protocol-layered packet loss (ARQ/FEC recovery), TR 101 290 transport stream health, per-output health, content quality monitoring, entitlements, bridges and gateways, Router inspection and EventBridge events.
- Router inspection corrected to the real MediaConnect Router API: get-router-input, get-router-output, get-router-input-source-metadata and get-router-input-thumbnail (all take --arn); the IAM actions now match (mediaconnect:GetRouterInput, GetRouterOutput, GetRouterInputSourceMetadata, GetRouterInputThumbnail).
- Content quality monitoring and bridge/gateway inspection moved to references/secondary-checks.md, loaded on demand, to keep the SKILL.md body under 500 lines.
- Read-only diagnostics throughout; write operations are surfaced as customer recommendations only.
- Shaped to the DevOps Agent skill-eval best practices: a step checklist the agent copies and ticks, a self-check before findings are presented, and the metric, status and field tables relocated to references/lookup-tables.md so they load only with the step that uses them.
- Review round, from the SME's field cases: Link device sources (encoder pause versus network loss, separated by SourceNotRecoveredPackets), how to read PCR errors (100 ms ISO limit in CloudWatch versus 40 ms DVB limit on analyzers), an SRT MinLatency rule of 3 to 4 times RTT, and a cross-Region topology check; four eval cases cover them; medialive:ListInputDevices and DescribeInputDevice added to the IAM policy.
