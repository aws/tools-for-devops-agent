# DevOps Agent skill IAM policies

Adds the extra IAM permissions individual skills need to a DevOps Agent role, on top
of the AWS managed policy
[`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html).

Attach the policies to a role you already have, or let the template create one. This
template creates **no** infrastructure — only IAM.

> This template does **not** create an Agent Space. Deploy the space separately and
> associate the role ARN from this stack's `DevOpsAgentRoleArn` output.

## Role: existing or new

| `ExistingRoleName` | Behaviour |
|--------------------|-----------|
| set to a role name | Attaches the inline policies to that existing role. |
| left empty (default) | Creates `DevOpsAgentRole-AgentSpace`, trusting `aidevops.amazonaws.com`, with `AIDevOpsAgentAccessPolicy` attached. |

The trust policy on the created role is scoped with `aws:SourceAccount` and
`aws:SourceArn` (`arn:aws:aidevops:*:<account>:agentspace/*`) for confused-deputy
prevention.

> **Multiple Agent Spaces:** the created role trusts all Agent Spaces in the account
> (`agentspace/*`), so one role can serve several spaces. Because the new-role name is
> fixed, the create-new path can only run once per account/Region. To give different
> spaces different permission sets, pre-create the roles and deploy this stack once per
> role with `ExistingRoleName`.

## Parameters

### Role configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ExistingRoleName` | `''` | Attach policies to this existing role. Empty creates `DevOpsAgentRole-AgentSpace`. |

### Skill activation

Each parameter is `'true'` / `'false'` and defaults to `'true'`. Set a skill to
`'false'` to leave out its policy.

| Parameter | Skill | Permissions added |
|-----------|-------|-------------------|
| `EnableAwsHealthEvents` | `aws-health-events` | `health:DescribeEventTypes` |
| `EnableSupportCases` | `support-cases` | `support:DescribeCommunications` |
| `EnableRdsOperationReview` | `rds-operation-review` | `rds:DownloadDBLogFilePortion`, `logs:GetLogEvents` |
| `EnableInvestigationCostGuardrail` | `investigation-cost-guardrail` | `pricing:GetProducts` |
| `EnableMskOperations` | `msk-operations` | `kafka:GetBootstrapBrokers` |
| `EnableServiceQuotaCheck` | `service-quota-check` | Service Quotas read + `RequestServiceQuotaIncrease`, `CreateSupportCase`; `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics` |
| `EnableDmsOperationReview` | `database-migration-service-expertise` | `dms:TestConnection` |
| `EnableEcsOperationReview` | `ecs-operation-review` | `compute-optimizer:GetECSServiceRecommendations` |
| `EnableAwsBackupCoverageReview` | `aws-backup-coverage-review` | `backup:GetSupportedResourceTypes`, `config:SelectResourceConfig`, `dsql:ListClusters`, `storagegateway:ListFileShares`, `storagegateway:ListGateways`, `storagegateway:ListVolumes` |
| `EnableAuroraIncidentBusinessContext` | `aurora-incident-business-context` | `config:GetResourceConfigHistory` |
| `EnableAgentCoreObservabilitySetup` | `agentcore-observability-setup` | `bedrock-agentcore:GetAgentRuntime`, `bedrock-agentcore:ListAgentRuntimes`, `xray:GetTraceSegmentDestination`, `logs:DescribeDeliveries`, `logs:DescribeDeliverySources`, `logs:DescribeDeliveryDestinations`, `logs:DescribeResourcePolicies`, `lambda:GetFunctionConfiguration`, `ecs:DescribeTaskDefinition`, `ecs:DescribeServices`, `ecs:ListTasks`, `eks:DescribeCluster` |
| `EnableAgentCoreOpsReview` | `agentcore-ops-review` | `bedrock-agentcore` read-only List/Get for runtimes, memories, gateways, browsers, code interpreters and workload identities; `bedrock-agentcore:ListMemoryRecords`; `ec2:DescribeSubnets` |
| `EnableSageMakerAIOpsReview` | `sagemaker-ai-ops-review` | `savingsplans:DescribeSavingsPlans` |
| `EnableLiveStreamingEventReadinessReview` | `live-streaming-event-readiness-review` | `mediatailor:ListPlaybackConfigurations`, `mediatailor:GetPlaybackConfiguration`, `mediatailor:ListPrefetchSchedules`, `route53-recovery-cluster:ListRoutingControls` |
| `EnableEosCostAnalysis` | `eos-cost-analysis` | `pricing:GetProducts`, `pricing:GetAttributeValues`, `pricing:DescribeServices`. Resource discovery is already covered by the managed policy |
| `EnableStorageEbsOperations` | `storage-ebs-operations` | `ec2:GetEbsEncryptionByDefault`, `ec2:GetEbsDefaultKmsKeyId`, `dlm:GetLifecyclePolicies`, `dlm:GetLifecyclePolicy`, `rbin:ListRules`, `rbin:GetRule`, `fis:GetExperiment`, `compute-optimizer:GetEBSVolumeRecommendations` |
| `EnableAwsPerformanceEfficiencyReview` | `aws-performance-efficiency-review` | `compute-optimizer:GetEnrollmentStatus`, `compute-optimizer:GetEC2InstanceRecommendations`, `compute-optimizer:GetAutoScalingGroupRecommendations`, `compute-optimizer:GetEBSVolumeRecommendations`, `compute-optimizer:GetLambdaFunctionRecommendations`, `compute-optimizer:GetECSServiceRecommendations`, `compute-optimizer:GetRDSDatabaseRecommendations`, `lambda:GetFunctionConcurrency`, `trustedadvisor:ListChecks`, `trustedadvisor:ListRecommendations`, `trustedadvisor:GetRecommendation`, `trustedadvisor:ListRecommendationResources` (Trusted Advisor needs a Business or higher Support plan) |
| `EnableEksOperationReview` | `aws-eks-operations-review` | None — already covered by the managed policy |
| `EnableEnrichWithSecurityAgent` | `enrich-with-aws-security-agent` | None — already covered by the managed policy |
| `EnableCrmInvestigationGuidelines` | `crm-production-investigation-guidelines` | None — already covered by the managed policy |
| `EnableSkipScheduledMaintenance` | `skip-scheduled-maintenance` | None — no IAM required |

The last four parameters exist so the skill list stays complete and self-documenting;
toggling them changes nothing in the stack.

`EnableAwsHealthEvents`, `EnableSupportCases` and the Trusted Advisor actions of
`EnableAwsPerformanceEfficiencyReview` need an AWS Business or Enterprise Support
plan for the underlying APIs to return data.

### Optional add-on permissions

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EnableConfigAthenaCiAnalysis` | `'false'` | For `config-cost-optimization`'s Athena CI-driver path: adds `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults`, `athena:GetWorkGroup`, `glue:GetDatabase`, `glue:GetTable`, `glue:GetPartitions`, and `s3:GetObject` on the Config delivery data. |
| `EnableSsmAutomationExecutionRead` | `'false'` | For the `aws-systems-manager` custom agent: adds read-only `ssm:GetAutomationExecution`, scoped to this account's automation executions, so the agent can inspect the per-location rate-control and alarm settings of multi-account executions. Without it those checks are reported as Not checked. |
| `ConfigDataBucketArn` | `''` | Config delivery bucket ARN; scopes the `s3:GetObject` grant to `<arn>/*`. Empty grants `s3:GetObject` on all buckets (testing only). Used only when `EnableConfigAthenaCiAnalysis=true`. |

The Athena path also needs a workgroup with Athena-managed query results, because the
role has no `s3:PutObject`; without the add-on the skill falls back to
`GetDiscoveredResourceCounts`.

### Optional resource scoping

| Parameter | Default | Description |
|-----------|---------|-------------|
| `AllowedRegions` | `''` | Comma-delimited Region list. Empty means all Regions. When set, adds a `Deny` on every action outside those Regions, excepting the global services `health`, `support`, and `ce`. |

## Always applied

One policy is added regardless of the skill toggles:

| Policy | Purpose |
|--------|---------|
| `AllowCreateResourceExplorerSLR` | `iam:CreateServiceLinkedRole` for `AWSServiceRoleForResourceExplorer`, required for topology discovery. |

## Deploy

Attach to an existing role:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies \
  --parameter-overrides ExistingRoleName=<YOUR-DEVOPS-AGENT-ROLE-NAME> \
  --capabilities CAPABILITY_NAMED_IAM
```

Create a new role instead, restricted to two Regions and without the Support-plan
skills:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      AllowedRegions="us-east-1,eu-west-1" \
      EnableAwsHealthEvents=false \
      EnableSupportCases=false
```

## Outputs

| Output | Description |
|--------|-------------|
| `DevOpsAgentRoleArn` | Role ARN to associate with your Agent Space. |
| `DevOpsAgentRoleName` | Role name. |
| `SkillPolicySummary` | Which skills got an inline policy, which are covered by the managed policy, and which need no IAM. |

## Adding a skill

When a new skill needs permissions beyond the managed policy, add a parameter, a
condition, and an `AWS::IAM::Policy` resource following the existing pattern, then
extend the `SkillPolicySummary` output.
