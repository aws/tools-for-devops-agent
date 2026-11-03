# Fixed Check Matrix and Severity Scale for CloudTrail Coverage Auditor

Load this file at Step 8 of SKILL.md, before evaluating the checks and rendering
the report. Every run reports all 20 checks in the order below, with the same
IDs. A check that could not be evaluated shows `AccessDenied`, `ToolingFailure`
or `NotApplicable` with the call that failed, never a guessed `PASS`. The two
note rows (N1, N2) always render as `INFO`.

Fields come from `DescribeTrails` and `GetTrail` [S11], `GetEventSelectors`
[S4][S5], `GetTrailStatus` [S7] and `GetInsightSelectors`. "Member / Mgmt"
says from which account type the row is evaluable.

## Check matrix

| ID | Check | Finding condition | Severity | Fields | Member / Mgmt |
|---|---|---|---|---|---|
| T1 | A logging multi Region trail or event data store records management events for this account | None found. If only single Region trails exist, list the Regions with no management trail. An organization trail read with the full ARN counts. When more than one source records management events, the evidence says "recorded by N trails; coverage is not affected" and nothing more | CRITICAL | `IsMultiRegionTrail`, `IsLogging`, `IncludeManagementEvents` or `eventCategory Management` | both |
| T2 | Global service events captured | No logging trail with `IncludeGlobalServiceEvents` true that is multi Region or homed in us-east-1 (global service events deliver only under those conditions [S11]) | HIGH | `IncludeGlobalServiceEvents`, `IsMultiRegionTrail`, `HomeRegion` | both |
| M1 | Management events read and write | No logging trail that records management events has `ReadWriteType All` (or an advanced Management selector without a `readOnly` condition). A second trail set to `WriteOnly` beside one that logs All is not a finding | HIGH | `ReadWriteType`, `readOnly`, `IncludeManagementEvents` | both |
| M2 | Management event sources recorded | A source (`kms.amazonaws.com` or `rdsdata.amazonaws.com`) is excluded on every logging trail that records management events: `ExcludeManagementEventSources` non empty, or `eventSource NotEquals` on a management selector [S12]. An exclusion on one trail while another logging management trail records the source is INFO, naming the trail that records it | MEDIUM / INFO | as named | both |
| M3 | Service initiated events excluded | `eventType NotEquals AwsServiceEvent` or `userIdentity.arn NotStartsWith .../aws-service-role/` present on a management selector; the "Exclude AWS service initiated events" template drops service linked role activity [S3] | MEDIUM | field selectors | both |
| D1 | S3 object data events | Any bucket row `Uncovered` (baseline mode) or any required bucket `Uncovered` (required list mode) | HIGH baseline / CRITICAL required list | coverage-model.md section 3 | both |
| D2 | Lambda invoke data events | Same rule for functions | HIGH / CRITICAL | coverage-model.md section 3 | both |
| D3 | DynamoDB item level data events | Same rule for tables | HIGH / CRITICAL | coverage-model.md section 3 | both |
| D4 | Selector precision | `ReadWriteType` not `All`, `readOnly` set, an `eventName` allowlist missing the multipart names or `DeleteObjects`, a prefix scoped bucket, or a selector ARN that matches no inventoried resource (dangling). The finding states what the narrowing excludes; the operator change is "widen the selector, or record that the audit accepts the exclusion". It never says the narrowing is wrong or what it saves | MEDIUM (dangling: LOW) | coverage-model.md section 3 | both |
| I1 | Insights enabled on a trail that logs write management events (`ApiCallRateInsight` needs write management events [S13]) | No trail with `HasInsightSelectors` true. `GetInsightSelectors` raising `InsightNotEnabledException` means not enabled; it is not an error | LOW | `HasInsightSelectors`, `GetInsightSelectors` | both |
| L1 | A stopped trail has not removed coverage | `IsLogging` false on a trail that was the only source of some coverage: CRITICAL when it was the only trail logging management events for this account; HIGH when it was the only source of management events in a Region, of global service events, or of any in scope resource's data events (those rows are now `Uncovered`). INFO when every event it recorded is recorded by another logging trail, naming that trail; whether to delete the stopped trail is not this skill's question | CRITICAL / HIGH / INFO | `IsLogging`, `StopLoggingTime` | both (organization trail via full ARN) |
| L2 | No delivery error | `LatestDeliveryError` or `LatestDigestDeliveryError` non empty (bucket policy or bucket problem [S7]) | CRITICAL on the only management trail, else HIGH | as named | both |
| L3 | Recent delivery | `LatestDeliveryTime` older than 24 h: HIGH. Older than 1 h: INFO (delivery is about every 5 minutes, not guaranteed [S14]). `StartLoggingTime` within the last 24 h: INFO "no history before <time>" | HIGH / INFO | `LatestDeliveryTime`, `StartLoggingTime` | both |
| L4 | Log file validation | `LogFileValidationEnabled` false (digest files are the tamper evidence [S14]) | MEDIUM | `LogFileValidationEnabled` | both |
| E1 | KMS encryption | `KmsKeyId` empty (SSE-S3 only) | LOW | `KmsKeyId` | both |
| E2 | Destination bucket posture (optional context) | Versioning off, no Object Lock, Block Public Access not all true, or `LatestCloudWatchLogsDeliveryError` non empty | INFO | `s3:GetBucketVersioning`, `s3:GetBucketObjectLockConfiguration`, `s3:GetBucketPublicAccessBlock`, `LatestCloudWatchLogsDeliveryError` | own buckets only; `NotApplicable` for the organization trail bucket from a member [S8] |
| O1 | Organization trail selectors readable | The account is in an organization (`organizations:DescribeOrganization` succeeds), an organization trail is visible, and `GetEventSelectors` with the **full trail ARN** failed | MEDIUM, caps rating at `Attention` | `IsOrganizationTrail`, `HasCustomEventSelectors`, call result | member; `NotApplicable` standalone |
| O2 | Organization trail logs management events for members | Organization trail `IncludeManagementEvents` false (or no Management selector) and no own trail passes T1 | HIGH | `IncludeManagementEvents` | member and management |
| N1 | Event history note (always rendered) | Event history keeps 90 days of management events only, one Region per search, separate from trails [S2]; trails or Lake are the durable record | INFO | none | both |
| N2 | Automated system attribution note (always rendered) | Events by AWS services carry `userIdentity.invokedBy`; service linked role sessions carry a `sessionIssuer` role under `aws-service-role/`; `eventType AwsServiceEvent` marks service originated events [S15]. These are dropped by M3 selectors when present | INFO | none | both |

Fixed rules:

- All 20 rows render every run, in this order, ID alone in the first column.
- A row whose inputs were not readable shows the status (`AccessDenied`,
  `ToolingFailure`) and the call, never `PASS`.
- `NotApplicable` is used for O1 and O2 in a standalone account, for E2 on a
  bucket the account cannot read, and for list mode rows whose type has no
  required resource.
- D1 to D3 are `PASS` only when every in scope row of that type is `Covered`
  (narrowed `Covered` rows still pass D1 to D3 and raise D4 instead).
- A finding names the field and value it rests on and the exact operator change
  (API or console action), never executed by the skill.
- More than one trail recording the same events is a fact, not a finding. T1
  evidence and the Resource Coverage selector note ("also recorded by <trail>")
  state the count; no row says a copy is redundant, paid or wasteful, and no
  row estimates a saving. Duplicate copies, Read event trimming, KMS or RDS
  exclusion as a saving, data event volume and Lake pricing belong to
  `cloudtrail-cost-optimization`; when a finding here touches one of those
  objects, the Operator change column may end with "cost of the extra copy:
  see cloudtrail-cost-optimization" and nothing more.

## Severity scale

| Severity | Meaning | Operator SLA |
|---|---|---|
| CRITICAL | Management activity is not being recorded or not being delivered anywhere for this account, or a resource the audit requires has no data event record | Fix within 24 to 48 hours |
| HIGH | A class of activity (global services, reads, data events for a baseline type, a stopped or erroring trail that was the only source) has no record, or delivery is stale | Fix within 1 week |
| MEDIUM | The record exists but is narrowed, unverifiable from this account, or not tamper evident (a source excluded everywhere, service event exclusions, selector precision, validation off, unreadable organization trail) | Plan within 30 days |
| LOW | Hygiene (Insights off, SSE-S3 only, dangling selector) | Address when convenient |
| INFO | Observations an auditor should know; no action required (a stopped trail or an exclusion whose events another trail records, Event history and attribution notes) | None |

## Rating roll up (first match wins)

1. `Indeterminate`: trail inventory failed (`DescribeTrails` and `ListTrails`
   both unusable) or every baseline type inventory failed.
2. `AtRisk`: any CRITICAL finding (T1; L1 or L2 on the only management trail;
   any required list resource `Uncovered`).
3. `Attention`: any HIGH or MEDIUM finding, any `Uncovered` baseline row, or any
   `Unknown` or `CoveredByOrgTrail-Unverified` row. Blind spots cap here; a
   blind spot is never a gap.
4. `Healthy`: none of the above. LOW and INFO rows may exist.

## Sources

- [S2] Event history: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html
- [S3] Logging data events: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-data-events-with-cloudtrail.html
- [S4] DataResource: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_DataResource.html
- [S5] AdvancedFieldSelector: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_AdvancedFieldSelector.html
- [S7] GetTrailStatus: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_GetTrailStatus.html
- [S8] Organization trails: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/creating-trail-organization.html
- [S11] Trail object: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_Trail.html
- [S12] Logging management events: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-management-events-with-cloudtrail.html
- [S13] Insights events: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-insights-events-with-cloudtrail.html
- [S14] How CloudTrail works (delivery timing) and log file validation: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/how-cloudtrail-works.html and https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-validation-intro.html
- [S15] userIdentity element: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html
