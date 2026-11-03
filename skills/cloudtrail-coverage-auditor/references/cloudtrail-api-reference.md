# API Reference for CloudTrail Coverage Auditor

Load this file at Step 1 of SKILL.md, before issuing any API call. It lists the
read only calls the skill is allowed to make, the fields to keep from each,
pagination, the full ARN rule for organization trails, error classification,
and known quirks. Every call runs through the agent's native AWS tooling under
the Agent Space role. No credentials or profile are ever requested from the
user.

## 1. Allowed calls

| Call | Scope | Fields to keep | Pagination | Purpose |
|---|---|---|---|---|
| `sts:GetCallerIdentity` | once | `Account` | none | Account under review |
| `ec2:DescribeRegions` (`AllRegions=false`) | once | `RegionName` | none | Enabled Regions; never ask the user |
| `organizations:DescribeOrganization` | once | `Organization.MasterAccountId`, `Organization.Id` | none | Standalone, member or management account |
| `organizations:ListDelegatedAdministrators` (`ServicePrincipal=cloudtrail.amazonaws.com`) | once | `DelegatedAdministrators[].Id` | `NextToken` | Delegated administrator detection; `AccessDeniedException` from a member is expected |
| `cloudtrail:ListTrails` | once per Region or once (it lists every trail with `HomeRegion`) | `TrailARN`, `Name`, `HomeRegion` | `NextToken` | Trail inventory [S10] |
| `cloudtrail:DescribeTrails` (`includeShadowTrails` default true) | once per Region, de duplicate by `TrailARN` | `Name`, `TrailARN`, `HomeRegion`, `IsMultiRegionTrail`, `IsOrganizationTrail`, `IncludeGlobalServiceEvents`, `HasCustomEventSelectors`, `HasInsightSelectors`, `LogFileValidationEnabled`, `S3BucketName`, `S3KeyPrefix`, `KmsKeyId`, `CloudWatchLogsLogGroupArn`, `SnsTopicARN` | none | Trail fields [S9][S11] |
| `cloudtrail:GetTrail` | per trail, `Name` = **full TrailARN** | same as above | none | Fills fields for a shadow or organization trail |
| `cloudtrail:GetTrailStatus` | per trail, `Name` = **full TrailARN** | `IsLogging`, `LatestDeliveryTime`, `LatestDeliveryError`, `LatestDigestDeliveryTime`, `LatestDigestDeliveryError`, `LatestCloudWatchLogsDeliveryError`, `StartLoggingTime`, `StopLoggingTime` | none | L1, L2, L3, E2 [S7] |
| `cloudtrail:GetEventSelectors` | per trail, `TrailName` = **full TrailARN** | `EventSelectors[]` (`ReadWriteType`, `IncludeManagementEvents`, `DataResources[]`, `ExcludeManagementEventSources`), `AdvancedEventSelectors[]` (`Name`, `FieldSelectors[]`) | none | Coverage mapping, T1, M1, M2, M3, D1 to D4 [S4][S5] |
| `cloudtrail:GetInsightSelectors` | per trail, `TrailName` = full TrailARN | `InsightSelectors[].InsightType` | none | I1; `InsightNotEnabledException` means not enabled |
| `cloudtrail:ListEventDataStores` | once (stores are listed account wide) | `EventDataStoreArn`, `Name`, `Status`, `MultiRegionEnabled`, `OrganizationEnabled` | `NextToken` | Lake stores as coverage sources |
| `cloudtrail:GetEventDataStore` | per store | `Status`, `AdvancedEventSelectors`, `MultiRegionEnabled`, `OrganizationEnabled`, `RetentionPeriod` | none | Selector evaluation for stores |
| `s3:ListAllMyBuckets` (`ListBuckets`) | once | `Buckets[].Name` | `ContinuationToken` where supported | Bucket inventory |
| `s3:GetBucketLocation` | per bucket | `LocationConstraint` (empty or null means `us-east-1`; `EU` means `eu-west-1`) | none | Bucket Region for single Region trail matching |
| `s3:GetBucketVersioning`, `s3:GetBucketObjectLockConfiguration`, `s3:GetBucketPublicAccessBlock` | per trail destination bucket the account owns | `Status`, `ObjectLockEnabled`, `PublicAccessBlockConfiguration` | none | E2 optional context |
| `lambda:ListFunctions` | per Region | `FunctionArn`, `FunctionName` | `Marker` / `NextMarker` | Function inventory |
| `dynamodb:ListTables` | per Region | `TableNames[]` | `LastEvaluatedTableName` | Table inventory |
| `dynamodb:DescribeTable` | per table | `TableArn`, `LatestStreamArn` | none | Table ARN for matching; stream note |
| `kms:DescribeKey` | per `KmsKeyId`, optional | `KeyState` | none | E1 context: key enabled |
| `logs:DescribeLogGroups` | optional, by prefix of `CloudWatchLogsLogGroupArn` | `logGroupName` | `nextToken` | E2 context: log group exists |
| `iam:GetRole` (`AWSServiceRoleForCloudTrail`) | optional, member account | `Role.Arn` | none | Organization trail service linked role present [S8] |
| `sns:GetTopicAttributes`, `sns:ListTopics`, `sqs:ListQueues`, `sqs:GetQueueAttributes` | only when the user's required list names a topic or queue | ARN | provider tokens | Request only types |

Every action above is in `AIDevOpsAgentAccessPolicy` v12, including
`sqs:GetQueueAttributes` (explicit) and `sqs:ListQueues` (`sqs:List*`); see
[permissions.md](permissions.md). The skill never lists objects in any bucket.

## 2. Hard denials (never called)

`cloudtrail:CreateTrail`, `cloudtrail:UpdateTrail`, `cloudtrail:DeleteTrail`,
`cloudtrail:PutEventSelectors`, `cloudtrail:PutInsightSelectors`,
`cloudtrail:StartLogging`, `cloudtrail:StopLogging`, `cloudtrail:LookupEvents`
(log content analysis is out of scope), any CloudTrail Lake mutation
(`CreateEventDataStore`, `UpdateEventDataStore`, `DeleteEventDataStore`,
`StartQuery`), and any S3, KMS, Lambda, DynamoDB, SNS, SQS or Organizations
write. If the user asks the skill to apply a change, decline in one sentence
and restate the operator action already in the report.

## 3. The full ARN rule for organization trails

An organization trail is created in the management (or delegated
administrator) account and appears in each member account's `DescribeTrails`
as a shadow trail with `IsOrganizationTrail` true [S8][S9]. From a member
account:

- `GetTrailStatus`, `GetTrail`, `GetEventSelectors` and `GetInsightSelectors`
  **must be called with the full `TrailARN`**
  (`arn:aws:cloudtrail:<home-region>:<management-account>:trail/<name>`). The
  documentation states this for `GetTrailStatus` [S7] and that members can run
  it on organization trails [S8].
- Calling them with the bare trail name returns `TrailNotFoundException`,
  because the name resolves only in the owning account. That error after a name
  call is **not** evidence of a permission boundary. Retry with the ARN.
- Only after the **ARN** call fails (`AccessDeniedException`, a guardrail
  cancellation, or `TrailNotFoundException` with the ARN) may the trail's
  selectors be treated as unreadable, which produces
  `CoveredByOrgTrail-Unverified` rows and check O1.
- The ARN call works from any Region; the trail's `HomeRegion` is in the ARN.

Whether the Agent Space role (as opposed to an administrator role) can read the
selectors this way is an open question for SME review (README); the skill
always tries and classifies the result.

## 4. Error classification

| Result | Classification | Effect |
|---|---|---|
| Success | evidence | Use the fields |
| `AccessDeniedException`, `UnauthorizedOperation`, `AccessDenied` (S3) | `AccessDenied` | Row or source becomes `Unknown`; Not Assessed lists the call; rating caps at `Attention`. Never "no trails", "no buckets" or "not covered" |
| Guardrail message such as "Cancelled mutative operation" or any tool cancellation | `ToolingFailure` | Same as `AccessDenied`; note that the call is a read and was cancelled by the agent's tool policy |
| `ThrottlingException`, `TooManyRequestsException`, 5xx | retry up to 3 times with backoff; then `ToolingFailure` | Same as above |
| `TrailNotFoundException` after a **name** call on an organization trail | not evidence | Retry with the full ARN (section 3) |
| `TrailNotFoundException` after an **ARN** call | `Unreadable` | `CoveredByOrgTrail-Unverified` for the resources it could cover; O1 |
| `InsightNotEnabledException` | `NotConfigured` | I1 finding at LOW; not an error |
| `AWSOrganizationsNotInUseException` | standalone account | O1, O2 `NotApplicable` |
| `organizations:ListDelegatedAdministrators` denied | member, delegate unknown | Role type "member account" |
| `NoSuchBucket`, `NoSuchPublicAccessBlockConfiguration`, `ObjectLockConfigurationNotFoundError` | `NotConfigured` or bucket gone | E2 context row; not an error |
| Empty `EventSelectors` and `AdvancedEventSelectors` with `HasCustomEventSelectors` false | default selector | Management events read and write, no data events [S4] |
| Empty list from an inventory call that succeeded | evidence of zero resources | The type has no rows; D row `NotApplicable` with "no resources of this type" |

A denied or cancelled read is never reported as an empty result.

## 5. Pagination and de duplication

- `DescribeTrails` is called per enabled Region; a multi Region or organization
  trail appears in every Region's response as a shadow trail. Keep one entry
  per `TrailARN` and record `HomeRegion` from the object [S9].
- `ListTrails`, `ListEventDataStores`, `ListFunctions`, `ListTables`,
  `DescribeLogGroups` and `ListDelegatedAdministrators` paginate; follow the
  token until it is absent.
- `ListAllMyBuckets` returns every bucket in the account regardless of Region;
  the Region comes from `GetBucketLocation`.
- State the counts once: trails (unique), stores, buckets, functions, tables.

## 6. Inline data (no account access)

When the prompt pastes `DescribeTrails`, `GetEventSelectors`, `GetTrailStatus`
or an inventory list and says there is no account or console access, evaluate
from the supplied values alone. Make no API call. Label the report `SUPPLIED
DATA`. Fields the prompt does not supply are `NotApplicable` with "not
supplied", never guessed. Resources the prompt does not list are not invented;
say "no functions or tables supplied" rather than asserting coverage for them.

## 7. Known quirks

| Quirk | Consequence |
|---|---|
| Event history is 90 days, management events only, one Region per search, and independent of trails [S2] | N1 always renders; Event history never satisfies a data event or retention question |
| `IncludeGlobalServiceEvents` delivers global service events only from a multi Region trail or a single Region trail in us-east-1 [S11] | T2 passes only when such a trail is logging |
| Multi Region and organization trails are shadow trails in every Region [S9] | De duplicate by `TrailARN`; do not report the same trail per Region |
| Advanced and basic selectors are mutually exclusive; applying one clears the other [S3] | Read whichever array is non empty; never merge them |
| Organization trail APIs need the full ARN from a member [S7] | Section 3; a name call failure is a mistake, not a boundary |
| A member cannot modify an organization trail and by default cannot read its bucket [S8] | O1 and O2 direct the operator to the management account; E2 is `NotApplicable` for that bucket |
| S3 multipart uploads emit `CreateMultipartUpload`, `UploadPart`, `CompleteMultipartUpload`, not `PutObject`; bulk deletes emit `DeleteObjects` [S6] | An `eventName` allowlist without them misses writes and deletes (D4) |
| `GetBucketLocation` returns null for us-east-1 and `EU` for eu-west-1 | Normalise before Region matching |
| Delivery is about every 5 minutes but not guaranteed [S14] | L3 uses 1 h INFO and 24 h HIGH thresholds; quiet Regions can be older |
| `InsightNotEnabledException` from `GetInsightSelectors` | Normal for a trail without Insights; not an error |
| Selecting `AWS::DynamoDB::Table` also logs stream events by default [S3] | No separate stream row; one line note |
| A `ReadWriteType` of `ReadOnly` or `WriteOnly` on a basic selector applies to both management and data events in that selector [S4] | Narrow both the management checks (M1) and the data rows (D4) |

## Sources

- [S2] Event history: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html
- [S3] Logging data events: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-data-events-with-cloudtrail.html
- [S4] DataResource: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_DataResource.html
- [S5] AdvancedFieldSelector: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_AdvancedFieldSelector.html
- [S6] Amazon S3 CloudTrail event names: https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudtrail-logging-s3-info.html
- [S7] GetTrailStatus: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_GetTrailStatus.html
- [S8] Organization trails: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/creating-trail-organization.html
- [S9] DescribeTrails: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_DescribeTrails.html
- [S10] ListTrails: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_ListTrails.html
- [S11] Trail object: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_Trail.html
- [S14] How CloudTrail works: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/how-cloudtrail-works.html
