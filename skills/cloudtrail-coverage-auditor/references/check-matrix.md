# Fixed Check Matrix and Severity Scale for CloudTrail Coverage Auditor

Load this file at Step 8 of SKILL.md, before evaluating the checks and rendering
the report. Every run reports all 20 checks in the order below, with the same
IDs. A check that could not be evaluated shows `AccessDenied`, `ToolingFailure`
or `NotApplicable` with the call that failed, never a guessed `PASS`. The two
note rows (N1, N2) always render as `INFO`.

Fields come from `DescribeTrails` [S11] (never `GetTrail`), `GetEventSelectors`
[S4][S5], `GetTrailStatus` [S7] and `GetInsightSelectors`. "Member / Mgmt"
says from which account type the row is evaluable.

## Check matrix

| ID | Check | Finding condition | Severity | Fields | Member / Mgmt |
|---|---|---|---|---|---|
| T1 | A logging multi Region trail or event data store records management events for this account | None found. If only single Region trails exist, list the Regions with no management trail. An organization trail read with the full ARN counts. When more than one source records management events, the evidence says "recorded by N trails; coverage is not affected" and nothing more | CRITICAL | `IsMultiRegionTrail`, `IsLogging`, `IncludeManagementEvents` or `eventCategory Management` | both |
| T2 | Global service events captured | No logging trail with `IncludeGlobalServiceEvents` true that is multi Region or homed in us-east-1 (global service events deliver only under those conditions [S11]) | HIGH | `IncludeGlobalServiceEvents`, `IsMultiRegionTrail`, `HomeRegion` | both |
| M1 | Management events read and write | No logging trail that records management events has `ReadWriteType All` (or an advanced Management selector without a `readOnly` condition). A second trail set to `WriteOnly` beside one that logs All is not a finding | HIGH | `ReadWriteType`, `readOnly`, `IncludeManagementEvents` | both |
| M2 | Management event sources recorded | A source (`kms.amazonaws.com` or `rdsdata.amazonaws.com`) is excluded on every logging trail that records management events: `ExcludeManagementEventSources` non empty, or `eventSource NotEquals` on a management selector [S12]. An exclusion on one trail while another logging management trail records the source is INFO, naming the trail that records it | MEDIUM / INFO | as named | both |
| M3 | Service initiated events excluded | A **data event selector** on a logging trail or enabled event data store carries `eventType NotEquals AwsServiceEvent`, or a `userIdentity.arn` exclusion (`NotStartsWith` / `NotEquals`) whose value matches a service principal (`.../aws-service-role/` or `assumed-role/AWSServiceRole...`). Per the API reference [S5], trails accept `eventType` and `userIdentity.arn` on Data selectors only (`userIdentity.arn` also on NetworkActivity selectors), so on a trail this check is evaluated on Data selectors and a trail Management selector can never carry them; an event data store additionally accepts both fields on its Management selector, which is evaluated too. Every resource row the selector covers is `Covered (excludes service-initiated events)` (coverage-model.md section 1) and D1 to D3 show `PASS (narrowed)` for it. The finding names the selector, the field and value, and the resources affected, and states that AWS service and service linked role activity on those resources has no record in that source. Evidence lists any NetworkActivity selector exclusion as INFO (it narrows network activity events, not data events) | MEDIUM | `eventCategory`, `eventType`, `userIdentity.arn` field selectors | both |
| D1 | S3 object data events | Any bucket row `Uncovered` (baseline mode) or any required bucket `Uncovered` (required list mode) | HIGH baseline / CRITICAL required list | coverage-model.md section 3 | both |
| D2 | Lambda invoke data events | Same rule for functions | HIGH / CRITICAL | coverage-model.md section 3 | both |
| D3 | DynamoDB item level data events | Same rule for tables | HIGH / CRITICAL | coverage-model.md section 3 | both |
| D4 | Selector precision | `ReadWriteType` not `All`, `readOnly` set, an `eventName` allowlist missing the multipart names or `DeleteObjects`, a prefix scoped bucket, or a selector ARN that matches no inventoried resource (dangling). The finding states what the narrowing excludes; the operator change is "widen the selector, or record that the audit accepts the exclusion". It never says the narrowing is wrong or what it saves | MEDIUM (dangling: LOW) | coverage-model.md section 3 | both |
| I1 | Insights enabled on a trail that logs write management events (`ApiCallRateInsight` needs write management events [S13]) | No trail with `HasInsightSelectors` true. `GetInsightSelectors` raising `InsightNotEnabledException` means not enabled; it is not an error | LOW | `HasInsightSelectors`, `GetInsightSelectors` | both |
| L1 | A stopped trail has not removed coverage | `IsLogging` false on a trail that was the only source of some coverage: CRITICAL when it was the only trail logging management events for this account; HIGH when it was the only source of management events in a Region, of global service events, or of any in scope resource's data events (those rows are now `Uncovered`). INFO when every event it recorded is recorded by another logging trail, naming that trail; whether to delete the stopped trail is not this skill's question | CRITICAL / HIGH / INFO | `IsLogging`, `StopLoggingTime` | both (organization trail only when its status is readable; from a member inside the agent it is `ToolingFailure`, status unknown, never "stopped") |
| L2 | No delivery error | `LatestDeliveryError` or `LatestDigestDeliveryError` non empty (bucket policy or bucket problem [S7]) | CRITICAL on the only management trail, else HIGH | as named | both |
| L3 | Recent delivery | `LatestDeliveryTime` older than 24 h: HIGH. Older than 1 h: INFO (delivery is about every 5 minutes, not guaranteed [S14]). `StartLoggingTime` within the last 24 h: INFO "no history before <time>" | HIGH / INFO | `LatestDeliveryTime`, `StartLoggingTime` | both |
| L4 | Log file validation | `LogFileValidationEnabled` false (digest files are the tamper evidence [S14]) | MEDIUM | `LogFileValidationEnabled` | both |
| E1 | KMS encryption | `KmsKeyId` empty (SSE-S3 only) | LOW | `KmsKeyId` | both |
| E2 | Destination bucket posture (optional context) | Versioning off, no Object Lock, Block Public Access not all true, or `LatestCloudWatchLogsDeliveryError` non empty | INFO | `s3:GetBucketVersioning`, `s3:GetBucketObjectLockConfiguration`, `s3:GetBucketPublicAccessBlock`, `LatestCloudWatchLogsDeliveryError` | own buckets only; `NotApplicable` for the organization trail bucket from a member [S8] |
| O1 | Organization trail selectors readable | The account is in an organization (`organizations:DescribeOrganization` succeeds), an organization trail is visible, and `GetEventSelectors` with the **full trail ARN** failed or was refused by the agent's AWS tool (the normal result from a member account inside the agent; result `ToolingFailure`). The operator change is the exact CLI command with the full ARN, run from the CLI or the management account | MEDIUM, caps rating at `Attention` | `IsOrganizationTrail`, `HasCustomEventSelectors`, call result | member; `NotApplicable` standalone |
| O2 | Organization trail reaches this member | Either (a) the organization trail has `IncludeManagementEvents` false (or no Management selector) and no own trail passes T1, or (b) **opt in home Region**: the organization trail's `HomeRegion` is an opt in Region (`DescribeRegions` with `AllRegions=true` reports it with `OptInStatus` other than `opt-in-not-required` [S16]) and this account reports it `not-opted-in`; a member sends no activity to an organization trail homed in a Region it has not enabled [S8], so the trail contributes nothing here: its rows fall to the next source or `Uncovered`, and its name is removed from T1 and T2 evidence. (b) is HIGH when no own trail passes T1, INFO when own trails cover management events and every in scope resource. If the account's `OptInStatus` for that Region could not be read, rows attributed to the trail stay `CoveredByOrgTrail-Unverified` with the reason "home Region <r> is an opt in Region; this account's Region status could not be read" and the row result is `Unknown`. The operator change for (b) is "enable Region <r> in this account (`aws account enable-region --region-name <r>`), or have the management account add an organization trail homed in a default Region" | HIGH / INFO | `IncludeManagementEvents`, `HomeRegion`, `IsOrganizationTrail`, `OptInStatus` | member and management |
| N1 | Event history note (always rendered) | Event history keeps 90 days of management events only, one Region per search, separate from trails [S2]; trails or Lake are the durable record | INFO | none | both |
| N2 | Automated system attribution note (always rendered) | Events by AWS services carry `userIdentity.invokedBy`; service linked role sessions carry a `sessionIssuer` role under `aws-service-role/`; `eventType AwsServiceEvent` marks service originated events [S15]. A data event selector with an M3 exclusion drops them for the resources it covers | INFO | none | both |

Fixed rules:

- All 20 rows render every run, in this order, ID alone in the first column.
- A row whose inputs were not readable shows the status (`AccessDenied`,
  `ToolingFailure`) and the call, never `PASS`.
- `NotApplicable` is used for O1 and O2 in a standalone account, for E2 on a
  bucket the account cannot read, and for list mode rows whose type has no
  required resource.
- D1 to D3 are plain `PASS` only when every in scope row of that type is
  `Covered` with no narrowing label. When every row is `Covered` but at least
  one carries a narrowing label (`write only`, `read only`, `prefix`,
  `eventName`, `excludes service-initiated events`), the result is `PASS
  (narrowed)` with the affected rows and labels in the evidence; the finding
  itself is carried by D4 (read or write only, prefix, eventName) or M3
  (service initiated events), never by D1 to D3. A bucket whose only covering
  selector excludes service initiated events is therefore never a plain D1 `PASS`.
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
- [S16] Opt in Regions and `OptInStatus`: https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-regions.html and https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_Region.html
