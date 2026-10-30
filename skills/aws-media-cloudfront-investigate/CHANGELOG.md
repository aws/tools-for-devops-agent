# Changelog

## 1.0.0 (2026-10-27)

- Initial contribution to aws/tools-for-devops-agent: CloudFront Investigation for Media Delivery (MediaPackage v1 and v2 origins).
- Locates the distribution by ID or MediaPackage egress domain, reads AWS/CloudFront metrics in us-east-1 as percentages, attributes every elevated error rate as CDN-side or origin-surfaced against MediaPackage egress metrics, inspects cache behaviors and cache-key hygiene for the manifest versus segment split, Origin Shield placement, origin protocol and SNI, distribution-side origin auth (OAC on v2, CDNIdentifier origin header on v1), and standard logging v2 access logs.
- The origin's auth verdict (CDNAuthorizationStatusDetails, endpoint policy, secret) routes to aws-mediapackage-investigate; ad insertion to aws-mediatailor-investigate; CDN cost to aws-media-cost-optimize.
- Read-only diagnostics throughout; write operations are surfaced as customer recommendations only.
- Shaped to the DevOps Agent skill-eval best practices: a step checklist the agent copies and ticks, a self-check before findings are presented, and the metric, status and field tables relocated to references/lookup-tables.md so they load only with the step that uses them.
