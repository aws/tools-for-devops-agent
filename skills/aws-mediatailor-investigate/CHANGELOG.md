# Changelog

## 1.0.0 (2026-10-27)

- Initial contribution to aws/tools-for-devops-agent: MediaTailor Investigation (SSAI and Channel Assembly).
- SSAI path: Step 0 symptom router with an explicit no-match rule, configuration and logging precheck (PercentEnabled, LEGACY_CLOUDWATCH vs VENDED_LOGS chain, ExcludeEventTypes, DEBUG mode), metric analysis with dimension discovery, the three-way fill diagnostic split (ADS, transcode, avail suppression and personalization threshold), prefetch check, player-facing status triage and session log analysis.
- Channel Assembly path (Steps C1 to C4: channel and output state, schedule, programs and sources, ListAlerts, metrics and As-Run log) moved verbatim to references/channel-assembly-procedure.md, loaded when Step 0 routes a Channel Assembly symptom, to keep the SKILL.md body under 500 lines.
- Explicit origin handoff to aws-mediapackage-investigate and ADS-owner handoff; evidence carries coordinates in Step F.
- Read-only diagnostics throughout; write operations are surfaced as customer recommendations only.
- Shaped to the DevOps Agent skill-eval best practices: a step checklist the agent copies and ticks, a self-check before findings are presented, and the metric, status and field tables relocated to references/lookup-tables.md so they load only with the step that uses them.
- The SSAI and Channel Assembly report outlines moved to references/report-outlines.md, loaded at Step F.
