# analytics-dataops-expertise

A read-only **DataOps maturity assessment** skill for AWS DevOps Agent. Given an account ID and region, it runs control-plane API checks across the data platform, scores each dimension on a 1-5 maturity scale, and produces a structured scorecard with prioritized, doc-linked recommendations.

## What it does

Scores a customer's AWS data platform across five dimensions (26 maturity questions total):

1. **Architecture** — catalog/governance patterns, real-time processing, change data capture, capacity planning, fault tolerance & HA, disaster recovery
2. **Security & Governance** — metadata management, lineage, data classification, data protection (encryption/PITR), fine-grained access control
3. **Incident Management & Observability** — workload analytics, monitoring & alerting, application tracing, drift detection, SLA management, user experience
4. **Automation & Testing** — infrastructure pipelines (IaC/CI-CD), orchestration, version/patch management, data quality testing
5. **Cost** — resource tagging, chargeback/showback, storage lifecycle management, data-processing cost, unused-resource cleanup

Each question maps a set of read-only APIs to specific fields and a 1-5 rating rule. Questions that can't be fully confirmed from control-plane signals alone are **capped at 3** (existence of a resource ≠ mature use of it); the report states when a higher score needs conversational confirmation.

It is **100% control-plane / API-driven** — no data-plane access (no catalog/table/index queries), no external packages, and no AWS-internal data sources. That makes it compatible with DevOps Agent without a custom MCP server.

## Prerequisites

- **Account ID and region** for the assessment — the scorer is account + region scoped. If either is missing, the skill asks before running.
- **AWS resources:** one or more analytics/data services in the target account/region (Glue, Kinesis, MSK, DMS, DynamoDB, RDS, OpenSearch, Redshift, EMR, MWAA, etc.). Absence of a service is itself a valid low-maturity signal.
- **Cost Explorer** must be enabled and is called in `us-east-1` (used by the two cost questions Q37/Q39). If it's unavailable, those score from tagging signals with the gap noted.

**IAM permissions** the DevOps Agent execution role needs — all read-only. Most are covered by a ViewOnly/read-only managed policy; attach a supplemental policy for any gaps:

- Glue / Lake Formation: `glue:GetDatabases`, `glue:GetJobs`, `glue:GetCrawlers`, `glue:ListRegistries`, `glue:ListSchemas`, `glue:ListDataQualityRulesets`, `glue:ListDataQualityResults`, `glue:ListWorkflows`, `lakeformation:GetDataLakeSettings`, `lakeformation:ListPermissions`, `lakeformation:ListDataCellsFilter`
- Streaming: `kinesis:ListStreams`, `firehose:ListDeliveryStreams`, `kinesisanalyticsv2:ListApplications`, `kafka:ListClustersV2`
- Migration/CDC: `dms:DescribeReplicationTasks`, `dms:DescribeReplicationInstances`, `dms:DescribeEndpoints`, `dms:DescribeEventSubscriptions`
- Databases: `dynamodb:ListTables`, `dynamodb:DescribeTable`, `dynamodb:DescribeContinuousBackups`, `rds:DescribeDBInstances`, `rds:DescribeDBEngineVersions`, `redshift:DescribeClusters`, `es:DescribeDomain`, `es:ListDomainNames`
- Scaling: `application-autoscaling:DescribeScalableTargets`, `autoscaling:DescribeAutoScalingGroups`
- Resilience: `backup:ListBackupPlans`
- Observability: `cloudwatch:DescribeAlarms`, `cloudwatch:ListDashboards`, `cloudwatch:GetMetricData`, `sns:ListTopics`, `events:ListRules`, `xray:GetSamplingRules`, `xray:GetGroups`, `rum:ListAppMonitors`, `quicksight:ListDashboards`
- Automation: `cloudformation:ListStacks`, `codepipeline:ListPipelines`, `codecommit:ListRepositories`, `mwaa:ListEnvironments`, `states:ListStateMachines`, `ssm:DescribePatchBaselines`, `lambda:ListFunctions`
- Governance/Security: `macie2:GetMacieSession`, `macie2:ListClassificationJobs`, `kms:ListKeys`, `s3:ListAllMyBuckets`, `s3:GetBucketLifecycleConfiguration`, `iam:ListPolicies`, `config:DescribeConfigRules`, `config:DescribeComplianceByConfigRule`
- Cost: `resourcegroupstaggingapi:GetResources`, `ce:GetCostAndUsage`, `ce:GetTags`, `cost-optimization-hub:ListRecommendations`

## How to use it with DevOps Agent

1. Get this skill directory onto your machine (clone the repo, or use GitHub's **Code → Download ZIP**), then zip just this skill folder:
   ```bash
   cd tools-for-devops-agent/skills
   zip -r analytics-dataops-expertise.zip analytics-dataops-expertise
   ```
   The zip must contain `SKILL.md` at the top of the `analytics-dataops-expertise/` folder. ZIP only, max 6 MB, no `scripts/` directory (this skill has none).
2. In the DevOps Agent Operator Web App, go to **Knowledge → Skills → Add skill → Upload skill** and select the zip. Choose the agent types that can use it (Generic applies to all; or target Chat / Incident RCA / etc.). Confirm it shows as active.
3. Prompt in natural language without naming the skill, and include the account ID and region, e.g.:
   - "Assess the DataOps maturity of account `123456789012` in `eu-west-1`."
   - "Review our data platform's architecture, governance, and cost posture. Account `123456789012`, region `us-east-1`."
   - "How mature is our data pipeline observability and automation?"
4. Review the agent's reasoning trace to confirm the skill activated and the checks ran. Start a new chat after re-uploading a changed version so the latest skill loads.

If the agent does not invoke the skill, refine the `description` field in `SKILL.md` (see "Optimizing description" in the Agent Skills specification).

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.

## Maintainers

- prasadnu
- genealpe
