# Changelog

## 1.0.0 (2026-10-28)

Initial release.

Workflow:
- 5-phase workflow: Scope -> Discover -> Classify -> Calculate -> Report
- Works in regular Chat (ad-hoc) or as a Custom Agent (scheduled)
- Defaults to scanning all associated accounts, all regions (no confirmation gate); announces scope and estimates scan size with a large-scope heads-up (>10 accounts)
- Scoped to EOS cost and inventory; upgrade planning and readiness are left to `eks-upgrade-readiness`, with a disambiguation note in the skill

Discovery:
- Services: EKS, RDS/Aurora, Lambda, ElastiCache, OpenSearch
- RDS covers standalone instances AND Aurora clusters (`DescribeDBClusters`, authoritative cluster EngineVersion)
- ElastiCache covers redis, valkey, and memcached across node clusters (`DescribeCacheClusters`), replication groups (`DescribeReplicationGroups`), and serverless caches (`DescribeServerlessCaches`)
- Lambda deprecated-runtime detection verified at runtime (no hardcoded runtime list)
- Mandatory pagination across all discovery APIs
- Discovery summary proves which APIs ran and accounts for SUPPORTED resources (not just affected ones)

Classification & pricing:
- EOS status: IN_EXTENDED_SUPPORT, APPROACHING_EOS, PAST_EXTENDED_SUPPORT, SUPPORTED
- Per-version EOS date verification from AWS documentation (no guessing, no date-bleed across versions/engines)
- OpenSearch Elasticsearch vs OpenSearch engine families verified independently (separate EOS calendars)
- Live pricing from the AWS Pricing API (`pricing:GetProducts`); never hardcoded. A single us-east-1 validation-reference rate table is a sanity check only
- Pricing usagetypes checked against the live Pricing API: RDS and OpenSearch have no region prefix in us-east-1 and a prefix everywhere else (`APS3-ExtendedSupport:Yr1-Yr2:MySQL8.0`, `EU-OpenSearchExtendedSupport`), while EKS and ElastiCache carry a prefix in every region (`USE1-` in us-east-1). RDS usagetypes end in the engine plus major version (`MySQL8.0`, `PostgreSQL13`, `AuroraMySQL2`). Prefixes not in the common list are resolved with `pricing:GetAttributeValues`, and `pricing:DescribeServices` confirms ServiceCode and attribute names when a lookup returns empty
- RDS Extended Support is limited to MySQL, PostgreSQL and the two Aurora engines, the only ones with a Pricing API usagetype
- Year 1/2 vs Year 3 tiered pricing (boundary at >= 24 months); Multi-AZ cost doubling for RDS
- When a resource's Year 3 usagetype is not yet published, Year 3 is projected from the documented escalation (RDS/ElastiCache 2×, EKS/OpenSearch flat) and labeled as derived, rather than reported as `PRICING_UNAVAILABLE`
- OpenSearch NIH derived from instance type x count; small/micro sizes doc-verified, never extrapolated
- `jmespath_filter` guidance to avoid dumping large PriceList payloads

Reporting:
- Reactive (current) vs proactive (projected) cost split with cost-cliff metric
- CSV artifact with per-resource breakdown, `es_year` sentinel `N/A` for APPROACHING_EOS, and upgrade recommendations
- Documentation/upgrade lookups via `verify_aws_claim`
- Lambda deprecated runtimes flagged as security risk (no ES charge)

Packaging:
- IAM: discovery is covered by `AIDevOpsAgentAccessPolicy`; the `EnableEosCostAnalysis` toggle in `cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml` adds only the Pricing API actions
- Evaluation tests (`.skilleval.yaml`, `evals/evals.json`, `evals/eval_queries.json`) with reports from a run against live resources across us-east-1, eu-west-1 and ap-south-1
- Companion custom agent in `custom-agents/eos-cost-analysis` for scheduled runs
