# Changelog

## 1.0.0 (2026-10-27)

- Initial contribution to aws/tools-for-devops-agent: MediaPackage Deep Investigation (v1 and v2).
- Auto-detects v1 vs v2, then covers ingest health (WebDAV credentials vs SigV4), egress error breakdown with the correct per version dimensions, origin-side CDN authorization (CDNAuthorizationStatus, endpoint policy grants for CloudFront and OAC, secret and role faults), ForceEndpointError awareness, latency and stuck endpoint reset assessment.
- ActiveInput interpretation, MQCS quality metrics, harvest jobs, origin endpoint configuration verification and access log checks moved to references/secondary-checks.md, loaded on demand, to keep the SKILL.md body under 500 lines.
- Read-only diagnostics throughout; mediapackagev2 ResetChannelState and ResetOriginEndpointState are surfaced as customer recommendations only and are not granted.
- Shaped to the DevOps Agent skill-eval best practices: a step checklist the agent copies and ticks, a self-check before findings are presented, and the metric, status and field tables relocated to references/lookup-tables.md so they load only with the step that uses them.
- The ForceEndpointError diagnosis tree moved to references/secondary-checks.md, loaded on a high 404 rate.
