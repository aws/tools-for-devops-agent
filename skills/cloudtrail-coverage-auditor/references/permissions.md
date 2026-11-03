# Permissions for CloudTrail Coverage Auditor

Load this file when a call returns `AccessDenied` or when the user asks what
the skill needs. Every action the skill calls is a read, and every one of them
is granted by the AWS managed policy
[`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html)
(checked against policy version v12, October 2026). No inline policy, no
`--additional-permissions-file` for the skill evaluation tool, and no
CloudFormation delta policy are needed.

## Actions used

| Action | Granted by | Used for |
|---|---|---|
| `cloudtrail:DescribeTrails`, `cloudtrail:ListTrails` | `cloudtrail:Describe*`, `cloudtrail:List*` | Trail inventory including shadow trails |
| `cloudtrail:GetTrail`, `cloudtrail:GetTrailStatus`, `cloudtrail:GetEventSelectors`, `cloudtrail:GetInsightSelectors` | explicit | Trail configuration, delivery health, selectors, Insights |
| `cloudtrail:ListEventDataStores`, `cloudtrail:GetEventDataStore` | `cloudtrail:List*`, explicit | CloudTrail Lake stores as coverage sources |
| `s3:ListAllMyBuckets`, `s3:GetBucketLocation` | explicit | Bucket inventory and Region |
| `s3:GetBucketVersioning`, `s3:GetBucketObjectLockConfiguration`, `s3:GetBucketPublicAccessBlock` | explicit | E2 optional destination bucket context |
| `lambda:ListFunctions` | `lambda:List*` | Function inventory and ARNs (`GetFunction` is not used) |
| `dynamodb:ListTables` | `dynamodb:List*` | Table inventory; ARNs are built from Region, account and name (`DescribeTable` is not used) |
| `organizations:DescribeOrganization`, `organizations:ListDelegatedAdministrators` | `organizations:Describe*`, `organizations:List*` | Account role resolution |
| `ec2:DescribeRegions` | `ec2:Describe*` | Enabled Regions |
| `kms:DescribeKey`, `logs:DescribeLogGroups`, `iam:GetRole` | explicit or `Describe*` | Optional context: key state, log group exists, `AWSServiceRoleForCloudTrail` present |
| `sns:GetTopicAttributes`, `sns:ListTopics` | explicit, `sns:List*` | Only when the user's required list names an SNS topic |
| `sqs:ListQueues`, `sqs:GetQueueAttributes` | `sqs:List*`, explicit | Only when the user's required list names an SQS queue; if denied, the row is `Unknown` |
| `sts:GetCallerIdentity` | no IAM permission required | Account id |

## Cautions

- `s3:ListBucket` in the managed policy is limited to `AWSLogs/*` prefixes.
  This does not affect the skill, which never lists objects.
- The agent's guardrail classifies `dynamodb:DescribeTable` as a mutative
  operation requiring approval and cancels it, and `lambda:GetFunction` was
  denied under the Agent Space role. Neither is needed: `ListTables` and
  `ListFunctions` give existence and ARN. A cancelled call is classified
  `ToolingFailure` and is never evidence. The skill does not ask for approval
  of any call; nothing it calls changes state.
- The agent's AWS tool refuses any ARN whose account is not an Agent Space
  target account ("ARN account <id> not in target accounts"). From a member
  account this blocks `GetTrailStatus` and `GetEventSelectors` on the
  organization trail's full ARN before the request reaches AWS, so the managed
  policy is not the cause and the result is `ToolingFailure`, not
  `AccessDenied`. The operator runs the same call from the CLI or the
  management account.
- `cloudtrail:LookupEvents` is in the policy but the skill never calls it;
  reading Event history content is log analysis, which is out of scope.

## Forbidden actions (never called)

`cloudtrail:CreateTrail`, `cloudtrail:UpdateTrail`, `cloudtrail:DeleteTrail`,
`cloudtrail:PutEventSelectors`, `cloudtrail:PutInsightSelectors`,
`cloudtrail:StartLogging`, `cloudtrail:StopLogging`,
`cloudtrail:LookupEvents`, any CloudTrail Lake mutation, and any S3, KMS,
Lambda, DynamoDB, SNS, SQS or Organizations write.

## When a call is denied

1. Record the call, the trail or type, and the error under Not Assessed.
2. Set the affected rows to `Unknown` (or `CoveredByOrgTrail-Unverified` when
   the denied or blocked call was `GetEventSelectors` with an organization
   trail's ARN).
3. Cap the rating at `Attention`. Never fill the gap with "no resources" or
   "not covered".
4. In Next Steps, name the action and the policy that normally grants it, so
   the operator can check the Agent Space role for an explicit deny or a
   permission boundary. For the organization trail tool block, give the full
   ARN and `aws cloudtrail get-event-selectors --trail-name <full ARN>` to run
   from the CLI or the management account instead; no IAM change fixes it.
