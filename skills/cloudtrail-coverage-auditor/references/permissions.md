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
| `s3:GetBucketVersioning`, `s3:GetBucketObjectLockConfiguration`, `s3:GetBucketPublicAccessBlock`, `s3:GetBucketPolicy` | explicit | E2 optional destination bucket context |
| `lambda:ListFunctions` | `lambda:List*` | Function inventory |
| `dynamodb:ListTables`, `dynamodb:DescribeTable` | `dynamodb:List*`, `dynamodb:Describe*` | Table inventory, stream note |
| `organizations:DescribeOrganization`, `organizations:ListDelegatedAdministrators` | `organizations:Describe*`, `organizations:List*` | Account role resolution |
| `ec2:DescribeRegions` | `ec2:Describe*` | Enabled Regions |
| `kms:DescribeKey`, `logs:DescribeLogGroups`, `iam:GetRole` | explicit or `Describe*` | Optional context: key state, log group exists, `AWSServiceRoleForCloudTrail` present |
| `sns:GetTopicAttributes`, `sns:ListTopics` | explicit, `sns:List*` | Only when the user's required list names an SNS topic |
| `sqs:ListQueues`, `sqs:GetQueueAttributes` | to be confirmed in v12 before relying on it | Only when the user's required list names an SQS queue; if denied, the row is `Unknown` |
| `sts:GetCallerIdentity` | no IAM permission required | Account id |

## Cautions

- `s3:ListBucket` in the managed policy is limited to `AWSLogs/*` prefixes.
  This does not affect the skill, which never lists objects.
- The agent's tool policy has cancelled some read calls as "mutative" in other
  skills. A cancelled call is classified `ToolingFailure` and is never evidence.
  The skill does not ask for approval of any call; nothing it calls changes
  state.
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
   the denied call was `GetEventSelectors` with an organization trail's ARN).
3. Cap the rating at `Attention`. Never fill the gap with "no resources" or
   "not covered".
4. In Next Steps, name the action and the policy that normally grants it, so
   the operator can check the Agent Space role for an explicit deny or a
   permission boundary.
