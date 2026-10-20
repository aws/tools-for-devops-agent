# Changelog

## 1.0.2 (2026-10-19)

Maintainer PR review round 2 — docs build, trigger scoping, and an RDS pricing correctness fix.

- **RDS region-prefix fix (behavioral):** corrected the Pricing API guidance. RDS ExtendedSupport usagetypes are prefix-free ONLY in us-east-1; every other region carries a prefix (e.g. `USW2-ExtendedSupport:Yr1-Yr2:AuroraMySQL2`). The previous "RDS never has a prefix" rule caused `PRICING_UNAVAILABLE`/$0 for RDS and Aurora outside us-east-1. RDS now uses the same `pricing:GetAttributeValues` prefix resolution as the other services. Verified live against `AmazonRDS` in us-west-2. Supersedes the "region-prefix-free" note in 1.0.0.
- Fixed docs links for `mkdocs build --strict`: both READMEs now use absolute GitHub URLs for the cloudformation template and cross-skill/custom-agent references.
- Scoped the skill description to EOS cost and inventory (removed "upgrade planning") to avoid trigger overlap with `eks-upgrade-readiness`; added a disambiguation note and a `should_trigger: false` eval query ("Plan my EKS 1.30 to 1.31 upgrade").
- Updated the `rds-usagetype-*` functional eval to assert the correct region-prefix behavior.

## 1.0.1 (2026-10-19)

Maintainer PR review round 1 — repo conventions, mergeability, and correctness. No behavioral change to the discovery/pricing/reporting logic.

- Rebased onto current upstream `main` (resolved the `cloudformation/devops-agent-skill-policies.yaml` conflict, keeping all newer skill policies).
- Added skill evaluation tests: `.skilleval.yaml`, `evals/evals.json`, `evals/eval_queries.json`.
- Trimmed the CloudFormation IAM policy to only the AWS Pricing API gap; resource discovery is already covered by `AIDevOpsAgentAccessPolicy`.
- Added `eos-cost-analysis` entries to `llms.txt` (skill and custom agent).
- Restructured the skill README to the standard layout; added Limitations, Agent Types, and the required non-production disclaimer.
- Consolidated all reference rates into one validation-reference table (Pricing API remains the source of truth).
- Fixed the OpenSearch IAM prefix (`es:`) in the READMEs and noted it in SKILL.md.
- Corrected the error-handling table's pricing row to reference the Pricing API rather than documentation search.
- Cross-referenced the `eks-upgrade-readiness` and `analytics-opensearch-expertise` skills.

## 1.0.0 (2026-08-20)

Initial release.

Workflow:
- 5-phase workflow: Scope -> Discover -> Classify -> Calculate -> Report
- Works in regular Chat (ad-hoc) or as a Custom Agent (scheduled)
- Defaults to scanning all associated accounts, all regions (no confirmation gate); announces scope and estimates scan size with a large-scope heads-up (>10 accounts)

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
- Live pricing from the AWS Pricing API (`pricing:GetProducts`); never hardcoded
- Region prefix resolved via `pricing:GetAttributeValues`; RDS ExtendedSupport usagetype is region-prefix-free (regionCode filter only)
- OpenSearch NIH derived from instance type x count; small/micro sizes doc-verified, never extrapolated
- Year 1/2 vs Year 3 tiered pricing (boundary at >= 24 months); Multi-AZ cost doubling for RDS
- `jmespath_filter` guidance to avoid dumping large PriceList payloads

Reporting:
- Reactive (current) vs proactive (projected) cost split with cost-cliff metric
- CSV artifact with per-resource breakdown, `es_year` sentinel `N/A` for APPROACHING_EOS, and upgrade recommendations
- Documentation/upgrade lookups via `verify_aws_claim`
- Lambda deprecated runtimes flagged as security risk (no ES charge)
