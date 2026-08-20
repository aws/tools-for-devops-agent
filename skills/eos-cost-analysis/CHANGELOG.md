# Changelog

## 1.0.0 (2026-06-18)

- Initial release
- 5-phase workflow: Scope → Discover → Classify → Calculate → Report
- Service support: EKS, RDS/Aurora, Lambda, ElastiCache, OpenSearch
- EOS status classification: IN_EXTENDED_SUPPORT, APPROACHING_EOS, PAST_EXTENDED_SUPPORT
- Cost calculation with per-vCPU (RDS), per-cluster (EKS), per-node (ElastiCache/OpenSearch) formulas
- Multi-AZ cost doubling for RDS
- Year 1/2/3 pricing escalation
- Cross-account discovery via sts:AssumeRole
- Documentation validation via aws-knowledge-mcp-server
- CSV artifact output with upgrade recommendations

## 1.1.0 (2026-08-14)

- Replaced documentation-based pricing lookup with live AWS Pricing API (`pricing:GetProducts`)
- Added per-service usagetype patterns and region prefix mapping for Extended Support pricing
- Corrected pricing tiers: EKS flat $0.50/cluster/hr, RDS $0.10→$0.20/vCPU-hr (Yr3 2×), ElastiCache per-node (Yr3 2×), OpenSearch $0.0065/NIH single tier
- Clarified EKS $0.50 is the avoidable ES premium (standard $0.10 applies regardless)
- Added `pricing:GetProducts` / `pricing:GetAttributeValues` to prerequisites
- Added response-size guardrail: extract only pricePerUnit, never dump full PriceList
