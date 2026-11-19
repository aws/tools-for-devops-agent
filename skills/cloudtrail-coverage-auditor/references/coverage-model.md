# Coverage Model for CloudTrail Coverage Auditor

Load this file at Step 6 of SKILL.md, before mapping selectors to resources.
It defines the five coverage states, the resource types in the baseline, the
selector matching rules for basic and advanced event selectors, Region scope,
and how CloudTrail Lake event data stores count as coverage sources. Sources
are numbered [S#] and listed at the end; every behaviour claim carries one.

## 1. Coverage states (one per resource row, first match wins)

| Order | State | Rule | Effect on rating |
|---|---|---|---|
| 1 | `NotApplicable` | The resource is outside the user's requested scope (Region or type), or its type is not auditable by this skill. | Never counted |
| 2 | `Unknown` | The inventory call for the type, or the selector read for a trail that could cover it, returned `AccessDenied`, was cancelled by the agent guardrail, or failed. Also used for a required list name that does not resolve in inventory (note "not found in account"). | Caps rating at `Attention` |
| 3 | `Covered` | At least one logging trail (`IsLogging` true) or `ENABLED` event data store whose selectors match the resource (section 3) and whose Region scope includes the resource (section 4). The row names the covering trail or store. An organization trail whose selectors were read (possible from the management account, or from the CLI; inside the agent a member's read is blocked by the AWS tool) gives `Covered` with the trail marked `(organization trail)`; a Lake store is marked `(event data store)`. Narrowing conditions stay in the state cell: `Covered (write only)`, `Covered (read only)`, `Covered (prefix <p> only)`, `Covered (eventName <list>)`, and `Covered (excludes service-initiated events)` when the covering **data event selector** has `eventType NotEquals AwsServiceEvent`, or a `userIdentity.arn` exclusion (`NotStartsWith` or `NotEquals`) whose value matches a service principal (`.../aws-service-role/`, `assumed-role/AWSServiceRole...`): AWS service and service linked role activity on that resource has no record in that source [S5][S3]. A narrowed row is counted as covered in N but makes D1 to D3 `PASS (narrowed)`, never plain `PASS`. | None by itself; narrowing raises D4 (read or write only, prefix, eventName) or M3 (service initiated events) |
| 4 | `CoveredByOrgTrail-Unverified` | An organization trail is visible (`IsOrganizationTrail` true) with `HasCustomEventSelectors` true and `GetEventSelectors` with the **full trail ARN** failed or was blocked by the agent's AWS tool (the normal result from a member account inside the agent; `ToolingFailure`), so its selectors cannot be read. Also used when the trail's `HomeRegion` is an opt in Region and this account's `OptInStatus` for it could not be read (section 4). The resource may be covered. | Caps rating at `Attention`; O1 fires (O2 for the opt in Region case); Next Steps gives the full ARN and the `get-event-selectors` command to run from the CLI or the management account |
| 5 | `Uncovered` | Every readable trail and event data store was evaluated and none matches. | D1 to D3 finding (HIGH baseline, CRITICAL in required list mode) |

Rules that follow from the order:

- `Unknown` and `CoveredByOrgTrail-Unverified` are blind spots, never gaps. They
  cap the rating at `Attention` and are never described as "not logged".
- `Uncovered` is only reachable after every readable source was evaluated. A
  denied or cancelled call anywhere in the path makes the row `Unknown`.
- A trail with `IsLogging` false covers nothing; its selectors are still read
  and reported so the operator can see what starting it would capture.
- When more than one logging source matches a resource, the row names the
  first and the selector note adds "also recorded by <trail or store>". That
  is a fact about coverage, not a finding; whether the second copy is worth
  paying for is `cloudtrail-cost-optimization`'s question, and this skill
  never answers it.

## 2. Resource types

| Type | In baseline | Inventory | Why |
|---|---|---|---|
| `AWS::S3::Object` (general purpose buckets) | Yes | `s3:ListAllMyBuckets`, then `s3:GetBucketLocation` per bucket for the Region | Basic and advanced selectors both support it [S4] |
| `AWS::Lambda::Function` | Yes | `lambda:ListFunctions` per Region | Basic and advanced [S4] |
| `AWS::DynamoDB::Table` | Yes | `dynamodb:ListTables` per Region; ARN built as `arn:aws:dynamodb:<region>:<account>:table/<name>`. Never `DescribeTable` (the agent guardrail cancels it as mutative) | Basic and advanced [S4] |
| `AWS::DynamoDB::Stream` | No, note only | none (stream presence is not read) | Selecting `AWS::DynamoDB::Table` logs stream events too by default [S3], so the table row answers the stream question. Add the one line note "DynamoDB stream events are logged with the table's data events" when any table is in scope. |
| `AWS::S3Outposts::Object`, `AWS::S3Express::Object`, `AWS::S3::AccessPoint` | No | none | Advanced selectors only [S3]; rare in audit scopes; need extra inventory APIs. Listed in the report as not assessed. |
| `AWS::SNS::Topic`, `AWS::SQS::Queue`, `AWS::Cognito::IdentityPool`, `AWS::EKS::Cluster`, other advanced only types in [S3] | By request only | The type's List call, only when the user's required list names one | Advanced selectors only. Evaluate the selector match the same way; never enumerate them unasked. |

The baseline type set is the three types that basic event selectors support
[S4]; advanced only types are evaluated on request so the sweep never enumerates
services the user did not ask about (README, Design decisions).

## 3. Selector interpretation (per trail, per resource)

Advanced and basic selectors are mutually exclusive on a trail; applying
advanced selectors overwrites basic ones [S3]. Read whichever array in the
`GetEventSelectors` response is non empty. Both arrays empty with
`HasCustomEventSelectors` false means the trail logs management events only
with the default selector (read and write, no data events) [S4].

### 3.1 Basic event selectors (`EventSelectors[].DataResources[]`), semantics from [S4]

| Field or value | Meaning |
|---|---|
| `Type` | One of `AWS::S3::Object`, `AWS::Lambda::Function`, `AWS::DynamoDB::Table` only |
| `Values` entry `arn:aws:s3` | Every general purpose bucket in the account, plus cross account buckets the account's principals touch |
| `arn:aws:s3:::bucket/` | All objects in that bucket |
| `arn:aws:s3:::bucket/prefix` | Objects under the prefix only. Row is `Covered (prefix <prefix> only)` because objects outside the prefix are not logged; raise D4 |
| `arn:aws:lambda` | Every function in the account |
| A function ARN | Exact match only. `helloworld` does not match `helloworld2` |
| `arn:aws:dynamodb` | Every table in the account |
| A table ARN | Exact match only |
| `ReadWriteType` `ReadOnly` or `WriteOnly` | Narrows the row to `Covered (read only)` or `Covered (write only)`; raise D4 |
| `IncludeManagementEvents` | Whether this selector logs management events (feeds T1, M1) |
| `ExcludeManagementEventSources` | `kms.amazonaws.com` or `rdsdata.amazonaws.com` excluded (feeds M2) [S12] |

Limits: up to 5 event selectors and 250 data resources per trail [S4].
Evaluate all of them; a resource is covered if any selector matches it.

### 3.2 Advanced event selectors (`AdvancedEventSelectors[].FieldSelectors[]`), semantics from [S5] and [S3]

A selector covers data events only if it has `eventCategory Equals Data` and
`resources.type Equals <type>`; both are required fields for data events [S5].
Without `eventCategory Data` it covers no data events in this model. A selector
with `eventCategory Equals Management` is a management selector (feeds T1, M1,
M2, M3).

| Condition | Meaning |
|---|---|
| No `resources.ARN` field selector | All resources of that type in the trail's Region scope |
| `resources.ARN Equals` | Exact ARN match |
| `resources.ARN StartsWith` | Prefix match. For S3, match against the bucket ARN with a trailing slash (`arn:aws:s3:::bucket/`), because object ARNs differ from the bucket ARN [S3] |
| `resources.ARN EndsWith` | Suffix match on the resource ARN |
| `resources.ARN NotEquals`, `NotStartsWith`, `NotEndsWith` | Exclusion. `NotStartsWith` on a bucket excludes that bucket (its row is `Uncovered` for this trail; all other buckets `Covered`) |
| Wildcards | Not supported in `resources.ARN` values [S5]; treat a literal `*` as a character |
| `readOnly Equals true` or `false` | Narrows the row to read only or write only; raise D4 |
| `eventName Equals [...]` | Allowlist. Row is `Covered (eventName <list>)`; raise D4 when the list is incomplete for an audit (section 3.3) |
| `eventType NotEquals AwsServiceEvent` on a **Data** selector | Excludes service initiated events for the resources the selector covers; row is `Covered (excludes service-initiated events)`; raise M3 [S3][S5]. On a trail this field is valid only on Data selectors [S5]; an event data store also accepts it on a Management selector (then M3 fires for management events, no row label) |
| `userIdentity.arn NotStartsWith .../aws-service-role/` (or `NotEquals` a service role ARN) on a **Data** selector | Excludes service linked role sessions for the covered resources; row is `Covered (excludes service-initiated events)`; raise M3. On a trail `userIdentity.arn` is valid on Data and NetworkActivity selectors only [S5]; a NetworkActivity exclusion narrows network activity events, not data events, and is INFO. An event data store also accepts it on a Management selector. A `userIdentity.arn` exclusion naming a non service principal (a scanner role, a user) narrows the row to `Covered (excludes <principal>)` and raises D4, not M3 |
| `sessionCredentialFromConsole` | Narrows to console or non console sessions; record on the row, raise D4 |
| `eventSource NotEquals kms.amazonaws.com` or `rdsdata.amazonaws.com` | Management source exclusion; raise M2 [S12] |

### 3.3 S3 event name allowlists and the multipart gap

S3 object level data event names include `GetObject`, `HeadObject`,
`PutObject`, `CopyObject`, `DeleteObject`, `DeleteObjects`,
`CreateMultipartUpload`, `UploadPart`, `UploadPartCopy`,
`CompleteMultipartUpload`, `AbortMultipartUpload`, `RestoreObject`,
`GetObjectAcl`, `PutObjectAcl` and others [S6]. A large upload through the SDK
or console is a multipart upload: `CreateMultipartUpload`, `UploadPart`,
`CompleteMultipartUpload`, never `PutObject`. A bulk delete is `DeleteObjects`,
not `DeleteObject`.

An `eventName` allowlist that names `PutObject` without the three multipart
names, or `DeleteObject` without `DeleteObjects`, therefore misses writes and
deletes an auditor would expect to see. Record it on the row and raise D4
(MEDIUM) with the missing names. The gap is derived from the event name list in
[S6]; no AWS page states it as a caveat, so the report presents it as a
consequence of the list, not as an AWS warning.

## 4. Region scope of a trail or store

| Source | Scope rule |
|---|---|
| Multi Region trail (`IsMultiRegionTrail` true) | Matches resources in every enabled Region [S3] |
| Single Region trail | Matches only resources in `HomeRegion`. Lambda functions and DynamoDB tables are Regional; S3 bucket names are global but a single Region trail logs only buckets located in its Region [S3]. Use `GetBucketLocation` for the bucket Region (an empty or null `LocationConstraint` means `us-east-1`). |
| Organization trail | Scope of the trail (multi or single Region) across every account in the organization [S8]; from a member account it covers that member's resources when its selectors match. **Opt in home Region:** when `HomeRegion` is an opt in Region (`OptInStatus` not `opt-in-not-required` [S16]), a member sends activity to the trail only if it has enabled that Region [S8]. Member `OptInStatus` `not-opted-in`: the trail covers nothing in this account; evaluate the next source or `Uncovered`; O2 fires. `OptInStatus` unreadable: rows the trail could cover are `CoveredByOrgTrail-Unverified` with the reason "home Region <r> is an opt in Region; this account's Region status could not be read". Default Region home (`opt-in-not-required`): no effect |
| Event data store | `MultiRegionEnabled` true matches every enabled Region; false matches only the store's Region. `OrganizationEnabled` sets organization scope. |

Multi Region trails and organization trails appear in `DescribeTrails` of every
Region as shadow trails (`includeShadowTrails` defaults to true) [S9].
De duplicate by `TrailARN` before counting or reporting trails.

## 5. CloudTrail Lake event data stores as coverage sources

`ListEventDataStores` then `GetEventDataStore` per store. A store counts as a
coverage source when `Status` is `ENABLED`. Its `AdvancedEventSelectors` are
evaluated with section 3.2. Rows covered by a store say `(event data store)` so
an auditor can tell a trail from Lake; a store cannot satisfy L4 (log file
validation is a trail feature) and has no delivery status fields, so L2 and L3
are evaluated on trails only. Stores count as coverage sources because an
auditor asks whether a record exists, not where; the row label keeps the two
distinguishable (README, Design decisions).

## 6. Worked examples

1. Basic selector `Type AWS::S3::Object, Values ["arn:aws:s3"]` on a logging
   multi Region trail: every bucket in every Region is `Covered` by that trail.
   No `AWS::Lambda::Function` data resource: every function is `Uncovered`
   unless another source covers it.
2. Advanced selector `eventCategory Equals Data; resources.type Equals
   AWS::S3::Object; resources.ARN StartsWith ["arn:aws:s3:::audit-logs/"]` on a
   single Region trail in us-east-1: bucket `audit-logs` in us-east-1 is
   `Covered`; `audit-logs` in eu-west-1 would be `Uncovered` (Region scope);
   every other bucket is `Uncovered`.
3. Advanced selector with `eventName Equals ["PutObject","DeleteObject"]` and
   `resources.ARN NotStartsWith ["arn:aws:s3:::scratch/"]`: all buckets except
   `scratch` are `Covered (eventName PutObject, DeleteObject)`; `scratch` is
   `Uncovered`; D4 MEDIUM for the missing `CreateMultipartUpload`,
   `UploadPart`, `CompleteMultipartUpload`, `DeleteObjects` and all reads.
4. Organization trail visible with `HasCustomEventSelectors` true, and
   `GetEventSelectors` with the full ARN is refused by the agent's AWS tool
   ("ARN account ... not in target accounts", the normal result from a member
   account inside the agent) or returns `AccessDenied`: every bucket, function
   and table the trail's Region scope could cover is
   `CoveredByOrgTrail-Unverified`, O1 fires, rating caps at `Attention`, Not
   Assessed lists the call as `ToolingFailure` with the ARN, and Next Steps
   gives `aws cloudtrail get-event-selectors --trail-name <full ARN>` for the
   operator to run from the CLI or the management account.
5. Organization trail read with the full ARN (from the management account, or
   supplied by the user from a CLI run), `IncludeManagementEvents` false and a
   single Lambda data resource in another account: it contributes no coverage
   to this account; rows stay `Uncovered` unless another source matches; O2
   fires only if no own trail passes T1.
6. Advanced Data selector on a logging trail: `eventCategory Equals Data;
   resources.type Equals AWS::S3::Object; resources.ARN StartsWith
   ["arn:aws:s3:::finance-reports/"]; eventType NotEquals [AwsServiceEvent];
   userIdentity.arn NotStartsWith [".../assumed-role/aws-service-role/"]`:
   bucket `finance-reports` is `Covered (excludes service-initiated events)` by
   that trail, M3 fires MEDIUM naming the selector and the bucket, D1 shows
   `PASS (narrowed)` (not plain `PASS`) if every other bucket is covered, and
   What Auditors Should Know states that replication, lifecycle, Backup and
   other AWS service activity on `finance-reports` has no record in that trail.
   Every other bucket is `Uncovered` unless another source matches.
7. Organization trail `HomeRegion` `eu-south-2` (an opt in Region [S16]),
   multi Region, `HasCustomEventSelectors` true, selector read blocked by the
   agent's tool; this account's `DescribeRegions AllRegions=true` reports
   `eu-south-2` `not-opted-in`: the trail receives nothing from this account
   [S8], so no row is attributed to it; rows fall to the account's own trails
   or `Uncovered`; O2 fires (HIGH if no own trail passes T1, else INFO) and
   Next Steps gives `aws account enable-region --region-name eu-south-2` or an
   organization trail homed in a default Region as the operator change. If
   `DescribeRegions` had failed, the rows would instead be
   `CoveredByOrgTrail-Unverified` with the Region status reason.

## Sources

- [S3] Logging data events: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-data-events-with-cloudtrail.html
- [S4] DataResource API reference: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_DataResource.html
- [S5] AdvancedFieldSelector API reference: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_AdvancedFieldSelector.html
- [S6] Amazon S3 CloudTrail event names: https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudtrail-logging-s3-info.html
- [S8] Organization trails: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/creating-trail-organization.html
- [S9] DescribeTrails (`includeShadowTrails`): https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_DescribeTrails.html
- [S12] Logging management events (KMS and RDS Data API exclusion, readOnly): https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-management-events-with-cloudtrail.html
- [S16] Opt in Regions list and `OptInStatus` values: https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-regions.html and https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_Region.html
