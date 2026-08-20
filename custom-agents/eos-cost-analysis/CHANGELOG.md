# Changelog

## 1.0.0 (2026-06-18)

- Initial release
- Support for 5 services: EKS, RDS/Aurora, Lambda, ElastiCache, OpenSearch
- Extended Support cost calculation with Year 1/2/3 tiered pricing
- Single-account and organization-wide (cross-account) analysis
- EOS date and pricing validation via aws-knowledge-mcp-server
- CSV artifact generation with per-resource cost breakdown
- Upgrade recommendations with AWS documentation links
- Lambda deprecated runtime flagging (security risk, no ES cost)

## 1.2.0 (2026-08-20)

- Reinforced per-version EOS date verification in constraints (never reuse one version's date for another, even within the same service) — aligns with skill v1.2.0
