# Config Inventory & Cost Signal Collection

Reference for the read-only APIs used to inventory the AWS Config setup (Step 2) and
the cost/volume signals used to size opportunities (Step 3). Load this when you need
the precise API names, what each returns, and which signal to prefer.

All calls are read-only (`Describe*`, `Get*`, `List*`).

## Step 2 — Inventory the Config setup (per Region)

```
config.DescribeConfigurationRecorders          # recorder config: allSupported,
                                               # includeGlobalResourceTypes, recordingMode
                                               # (per-resource-type frequency overrides),
                                               # resourceTypes list, exclusion list
config.DescribeConfigurationRecorderStatus     # is the recorder running?
config.DescribeDeliveryChannels                # S3 bucket + SNS destination
config.DescribeConfigRules                     # active managed + custom rules
config.DescribeConformancePacks                # conformance packs
config.DescribeConfigurationAggregators        # org/multi-account aggregation
config.GetDiscoveredResourceCounts             # resource-type inventory (CI-generating
                                               # surface, by resource type)
```

**Capture:** recording mode (continuous vs daily, globally and per-resource-type
overrides), whether `allSupported` is on, whether `includeGlobalResourceTypes` is on
and in how many Regions, the recorded/excluded resource-type lists, the number of
active rules and conformance packs, and the delivery bucket.

## Step 3 — Collect cost and volume signals

- **Cost Explorer** (`ce.GetCostAndUsage`, filtered to the `AWSConfig` service,
  grouped by `USAGE_TYPE`) to split spend across `ConfigurationItemRecorded`, rule
  evaluations, and conformance-pack evaluations. This is the most direct dollar
  signal — prefer it when the role has Cost Explorer access.
- **CI drivers**: identify which resource types generate the most CIs. The
  authoritative method is an Athena query over the Config S3 data (see
  [Identifying resources with the most configuration changes](https://aws.amazon.com/blogs/mt/identifying-resources-most-configuration-changes-aws-config/)).
  **The Athena path is optional and requires setup that is not present by default** —
  attempt it only when all of the following hold, and otherwise fall straight back to
  `GetDiscoveredResourceCounts` without attempting an Athena query:
  - An **Athena workgroup configured with Athena-managed query results**. The DevOps
    Agent role has no `s3:PutObject`, so it cannot write query results to a customer
    output bucket; managed results let Athena own the result location and return rows
    via `GetQueryResults`.
  - **Read access to the Config S3 data** (`s3:GetObject` on the Config delivery
    bucket) and the **Glue Data Catalog** (`glue:GetDatabase`, `glue:GetTable`,
    `glue:GetPartitions`) for the table that maps the Config data, plus
    `athena:GetWorkGroup`.
  - These are **not** granted by `AIDevOpsAgentAccessPolicy` (which carries only
    `s3:ListBucket` on `AWSLogs/` prefixes, no `s3:GetObject`) nor by the base
    config-cost-optimization policy. They are granted only when the
    `EnableConfigAthenaCiAnalysis` add-on is enabled in
    [`cloudformation/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies.yaml).
    Without them the query returns **AccessDenied**.

  When Athena is not available, use `GetDiscoveredResourceCounts` plus known
  high-churn types (Auto Scaling groups, EC2 instances/ENIs/volumes during scaling,
  spot fleets) as a directional signal, and label it as approximate.
- **S3 delivery bucket size** (`s3.ListObjectsV2` / CloudWatch `BucketSizeBytes`) for
  the storage component.

If Cost Explorer is unavailable, report configuration findings and label dollar
impact as "not quantified — enable Cost Explorer for sizing".
