# Changelog

## 1.0.0 (2026-10-27)

- Initial contribution to aws/tools-for-devops-agent: MediaLive Deep Investigation.
- Covers channel state, per input type diagnosis (MediaConnect, RTP/RTMP push, pull, Link input devices, SRT), encoding health (ActiveAlerts, DroppedFrames, FillMsec, SvqTime), per output group 4xx/5xx analysis, STANDARD pipeline synchronization, schedule verification including SCTE-35 schedule actions, and encoder log parsing.
- Read-only diagnostics throughout; write operations are surfaced as customer recommendations only.
- Shaped to the DevOps Agent skill-eval best practices: a step checklist the agent copies and ticks, a self-check before findings are presented, and the metric, status and field tables relocated to references/lookup-tables.md so they load only with the step that uses them.
- Per input type diagnostic patterns and per destination type checks moved to references/input-type-patterns.md and references/output-destination-checks.md, loaded for the type found.
