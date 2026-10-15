# Discovery, Log Sources, Degraded Path and Advisory DDL

Procedures D-1 to D-7 take the agent from "something is denying traffic" to the Web ACL, its configuration, its log destination and the queryable backend. Every procedure is read-only. The agent never creates, alters or deletes a resource, and it never runs DDL.

**Rules for every procedure**

- Never stop the investigation because a call is denied or returns nothing. Record the gap, apply the stated fallback and move on (D-5 is the shared fallback).
- Record the **exact error code and message** of every failed call. Write "not permitted" or "denied" only for `AccessDenied`, `AccessDeniedException` or `UnauthorizedOperation`. A cancelled, timed-out or throttled call is retried once; if it fails again, report it as "not completed (<code>)", not as a missing permission. A runtime tool refusal such as "cloudtrail service operations are not allowed, Cancelled service operation" is neither: it means "run this call in a subagent" (for CloudTrail, the change subagent in `access-denied-triage.md`, "Change lookups"). Agent-space memory or notes saying a service is blocked describe the main agent's tool; they never replace the subagent call, and they are not an error code to report.
- Always pass the `service_name` parameter on every AWS tool call (in testing, calls without it failed and had to be retried).
- Every default you apply goes under "Assumptions" in the output. For default windows and ACL selection, follow SKILL.md, "Defaults when input is missing".
- CloudFront-scoped Web ACLs, their logs and their metrics live in **us-east-1**, whatever Region the origin runs in. Use `--region us-east-1 --scope CLOUDFRONT` for every WAF, CloudWatch and Logs call that concerns a CloudFront ACL (the ACL, its logging configuration, its log group and its `AWS/WAFV2` metrics). The Glue table and Athena are different: they live in whatever Region the customer set Athena up in, so D-4 searches several Regions, and Athena queries must run in the table's Region.
- Query IDs below point to the sibling references: `athena-queries.md` (QA-nn) and `logs-insights-queries.md` (QI-nn).

| Procedure | Purpose | Default-policy permission needed | If missing |
|---|---|---|---|
| D-1 | Resource to Web ACL | `cloudfront:GetDistribution*`, `wafv2:GetWebACLForResource`, `wafv2:List*` | Use the ACL named in the request, or rank ACLs by metrics (D-5) |
| D-2 | Read the ACL | `wafv2:GetWebACL` | Report rule names from metric dimensions and sampled requests |
| D-2b | Token posture | none beyond D-2 (`wafv2:GetWebACL`) | Classify from logs only (Q-18) and say the ACL was not read |
| D-3 | Logging destination to backend | `wafv2:GetLoggingConfiguration`, `firehose:Describe*` | Treat logging as unknown and go to D-5 |
| D-4 | Find the table or log group | `glue:GetDatabases`, `glue:GetTables`, `glue:GetTable` | Go to D-5 and offer D-6 (table missing), or D-5 (Athena not permitted) |
| D-5 | Degraded path | `s3:ListBucket` (`AWSLogs/` prefixes), `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics`, `wafv2:GetSampledRequests` | Report whatever subset works |
| D-6 | Advisory DDL | none (text only) | n/a |
| D-7 | Shield Advanced status | `shield:Describe*`, `shield:List*` (`DescribeSubscription`, `ListProtections`, `DescribeProtection`, `ListAttacks`, `DescribeAttack`), `cloudwatch:GetMetricData` | Record the denial, continue with the next step, and detect L7AM from logs (Q-14) or the ACL rule name |

---

## D-1 - Resource to Web ACL

Goal: find the Web ACL (name, ID, ARN, scope, Region) that fronts the affected resource.

| Resource | Call | Result field |
|---|---|---|
| CloudFront distribution | `cloudfront:GetDistributionConfig --id <distribution-id>` (or `cloudfront:GetDistribution`) | `DistributionConfig.WebACLId`. For WAFv2 this is an ACL ARN. An empty string means no ACL. A value that is not an ARN is a legacy WAF Classic ID; report it as unsupported by this skill. |
| ALB, API Gateway REST stage, AppSync API, Cognito user pool, App Runner service, Verified Access instance | `wafv2:GetWebACLForResource --resource-arn <arn>` in the resource's Region | `WebACL` (name, ID, ARN). An empty response means no ACL is associated. |
| Amplify app | `amplify:GetApp --app-id <id>` | `app.wafConfiguration.webAclArn`. If this call is not permitted, fall back to "No resource named" below and match by ACL name. |

Notes:

- API Gateway stage ARN format: `arn:aws:apigateway:<region>::/restapis/<api-id>/stages/<stage>`.
- To go the other way for regional ACLs, `wafv2:ListResourcesForWebACL` lists the associated resources. It does not support CloudFront scope.
- Several resources named: repeat per resource and keep each resource-to-ACL mapping for the output.

**No resource named (or the lookup failed).**

1. `wafv2:ListWebACLs --scope CLOUDFRONT --region us-east-1`.
2. `wafv2:ListWebACLs --scope REGIONAL` in each relevant Region. Relevant means the Region of the incident, plus any Region where the user's resources run. If none is known, use the Region of the session and record that as an assumption.
3. Rank the ACLs by denying volume over the default window with WAF metrics: the ACL-level `BlockedRequests`, `ChallengeRequests` and `CaptchaRequests` totals in `AWS/WAFV2` (D-5 step 2). Logs are not located yet at this point (D-3 and D-4 come later), so do not rank with log queries.
4. Take the top 3 and carry them through the investigation. State under Assumptions that the ACLs were chosen by volume, not named by the user.

**If `wafv2:GetWebACLForResource` or `cloudfront:GetDistributionConfig` is denied:** use the "No resource named" path and say the association is unconfirmed.

---

## D-2 - Read the ACL (`wafv2:GetWebACL`)

Call: `wafv2:GetWebACL --name <name> --scope <CLOUDFRONT|REGIONAL> --id <id>` (us-east-1 for CloudFront). `wafv2:DescribeManagedRuleGroup` is not in the default policy; do not depend on it.

Checklist (record what you find; each item feeds the triage verdict):

| Field | Why it matters |
|---|---|
| `DefaultAction` (`Allow` or `Block`, with any `CustomResponse`) | A Block default turns every unmatched request into a denial. |
| `Rules[].Name`, `Priority` | Evaluation order. The first terminating match wins. |
| `Rules[].Action` (Allow, Block, Count, Captcha, Challenge) and `Rules[].OverrideAction` (None or Count, for rule-group references) | Count and an `OverrideAction` of Count do not terminate. |
| `Rules[].Action.Block.CustomResponse` (`ResponseCode`, headers, body key) | Explains a non-403 `responsecodesent`. |
| `Statement.ManagedRuleGroupStatement`: `VendorName`, `Name`, `Version`, `RuleActionOverrides`, `ScopeDownStatement`, `ManagedRuleGroupConfigs` | Identifies the managed group, whether the version is pinned, which inner rules are overridden to Count (or to a different action), and what traffic the group sees. |
| `Statement.RateBasedStatement`: `Limit`, `AggregateKeyType`, `EvaluationWindowSec`, `CustomKeys`, `ScopeDownStatement` | Explains rate-limit denials and which clients share a counter. |
| `CaptchaConfig.ImmunityTimeProperty` and `ChallengeConfig.ImmunityTimeProperty` (also per-rule overrides) | Short immunity means frequent re-challenges; expiry shows as `rejected:expired`. |
| `TokenDomains` | A request host outside these domains is `rejected:domain_mismatch`. |
| `AssociationConfig.RequestBody` (per-resource-type inspection size limit) | Bodies larger than the limit are only partly inspected; compare with `requestbodysizeinspectedbywaf`. |
| `LabelNamespace`, `Rules[].RuleLabels` | Label sources for label-based rules. |
| `VisibilityConfig.MetricName` and each rule's `VisibilityConfig.MetricName` | The dimension values used for metrics and for `GetSampledRequests` (D-5). |
| Rule named `ShieldMitigationRuleGroup_*` | Shield Advanced automatic application layer mitigation (L7AM) is attached. Go to D-7. |

The `ShieldMitigationRuleGroup_*` rule runs at priority 10,000,000, after your own rules.

**If `wafv2:GetWebACL` is denied:** say the configuration was not read, derive rule names from metrics (D-5) and from log fields (`terminatingruleid`, `rulegrouplist`), and cap confidence at "likely".

---

## D-2b - Token posture (from the D-2 response)

Goal: know whether the logs can carry token labels and whether attackers must hold a token to get through. This decides which token analysis to run (Mode B, B0 and B-C) and informs `CLIENT_CANNOT_SOLVE` (Mode A, A3). No extra call: read it from the D-2 `GetWebACL` response.

Record:

| Field | What to note |
|---|---|
| `ManagedRuleGroupConfigs[].AWSManagedRulesBotControlRuleSet` | `InspectionLevel` (`COMMON` or `TARGETED`) and `EnableMachineLearning`. Only `TARGETED` has the `TGT_*` token rules; `TGT_ML_*` needs machine learning enabled. |
| Token-aware rule groups | Bot Control (either inspection level adds token labels; `TGT_*` rules need `TARGETED`), ATP (`AWSManagedRulesATPRuleSet`), ACFP (`AWSManagedRulesACFPRuleSet`), Anti-DDoS. Any of them adds token labels (`awswaf:managed:token:*`, including `token:id:` and `token:fingerprint:`) to the requests it evaluates (its scope-down limits which). |
| Token-enforcing rules | **Strict** (every tokenless request is stopped): a custom rule with a `LabelMatchStatement` on `awswaf:managed:token:absent` (or `token:rejected`) and a non-Count action; `TGT_TokenAbsent` overridden to Challenge, CAPTCHA or Block; Challenge or CAPTCHA actions on the protected paths. **Threshold-only:** `TGT_VolumetricIpTokenAbsent` acts only after 5 or more tokenless requests from one IP in 5 minutes, so a pool sending 3 to 5 requests per IP evades it. A group-level `OverrideAction` of Count disables the group's own rules. |
| `TokenDomains`; `CaptchaConfig` and `ChallengeConfig` `ImmunityTimeProperty` (also per rule) | Cross-domain token acceptance and token lifetime. Absent keys mean the defaults (host domain only; 300-second immunity). |
| `ApplicationIntegrationURL` (top level of the `GetWebACL` response, beside `WebACL`) | The SDK integration endpoint. Populated only when the ACL uses a rule group that integrates with applications (ATP and ACFP per the API reference; also seen with Bot Control targeted); its presence does not prove that any application uses the SDK. |

Classify the posture (per protected path when rules are scoped) and record it under Assumptions:

- **P0, no token-aware rules:** no token labels in the logs. Token analysis can only use the raw `aws-waf-token` cookie or `x-aws-waf-token` header (Q-16, hashed in Athena).
- **P1, labelled but not strictly enforced:** token labels are added, but nothing stops a missing token, or only threshold-only enforcement (`TGT_VolumetricIpTokenAbsent`) does. Attackers do not need tokens: measure the `token:absent` share (Q-18) and look at volume and IP patterns (Q-11, Q-17) before token reuse.
- **P2, strictly enforced:** every request without a valid token is challenged or blocked. Traffic that gets through holds valid tokens, so prioritize reuse and redistribution by token id (Q-16b, then Q-16c).

Confirm the classification with Q-18 (QA-18 / QI-18): the shares of `token:accepted`, `rejected:*` and `absent` per path and action, and whether tokens arrive in a cookie or a header. If `GetWebACL` was denied, classify from Q-18 alone and say so.

---

## D-3 - Logging destination to backend (`wafv2:GetLoggingConfiguration`)

Call: `wafv2:GetLoggingConfiguration --resource-arn <web-acl-arn>` (us-east-1 for CloudFront).

| `LogDestinationConfigs[]` ARN | Backend | Next step |
|---|---|---|
| `arn:aws:logs:<region>:<account>:log-group:aws-waf-logs-*` | CloudWatch Logs Insights | D-4, Logs Insights branch. Use QI-nn queries. |
| `arn:aws:s3:::aws-waf-logs-*` (optionally with a prefix) | Athena over S3 | D-4, Athena branch. Use QA-nn queries. |
| `arn:aws:firehose:<region>:<account>:deliverystream/aws-waf-logs-*` | Firehose, then S3 | `firehose:DescribeDeliveryStream --delivery-stream-name <name>`; read `DeliveryStreamDescription.Destinations[].ExtendedS3DestinationDescription.BucketARN` and `.Prefix` (older streams: `S3DestinationDescription`). The bucket and prefix then follow the Athena branch. Other Firehose destinations (an HTTP endpoint or a third-party log platform, OpenSearch and so on) are not queryable by this skill: see "Third-party destinations" below. |

Also read, and record:

- `LoggingFilter`: `DefaultBehavior` (KEEP or DROP) and `Filters[]`. If records are dropped (for example only BLOCK is kept), the logs cannot show allowed or counted traffic. Allowed-history comparisons (QA-04 / QI-04) and Count-mode analysis (QA-08 / QI-08) are then unavailable; say so.
- `RedactedFields`: redacted headers, query string, URI path or method appear as `REDACTED` in logs. Note any that affect the question.
- `LogType` and `LogScope`, when present.

**Third-party destinations.** When the Firehose destination is not S3 (HTTP endpoint or a third-party log platform), or the customer says the logs go only to a third-party platform:

- Record under Assumptions and in coverage and gaps: "WAF logs are delivered to a non-S3 destination (<type from `DescribeDeliveryStream`>); not queryable by this skill". If the destination has an S3 backup, read its mode and bucket (`<Type>DestinationDescription.S3BackupMode` and `.S3DestinationDescription.BucketARN`, or `S3BackupDescription` where that is the field). Use the bucket on the Athena branch only when the mode keeps all records (`AllData`, `AllEvents` or `AllDocuments`, depending on the destination type). Failed-only modes (`FailedDataOnly`, `FailedEventsOnly`, `FailedDocumentsOnly`) hold only failed deliveries: query them if useful, but record the result as partial coverage.
- Otherwise continue on the degraded path (D-5).
- Advisory fix: enable a full S3 backup on the stream (S3 backup mode for all data) or add direct S3 or CloudWatch Logs delivery, plus the D-6 table.
- If that third-party platform is connected to the agent through another integration, the agent may use it for the log analysis, but this skill provides queries only for Athena and Logs Insights; translate them and say so. Geo-IP or ISP enrichment from such a platform is not in WAF logs (see QA-17 for the in-log alternatives).

**No logging configuration (the call returns a "not found" style error), or the call is denied:** record "logging not enabled or not readable", go to D-5, and include the advisory fix (enable logging to a CloudWatch Logs group or an S3 bucket whose name starts with `aws-waf-logs-`) in the output. Do not enable it yourself.

---

## D-4 - Find the table or log group

### Athena branch

1. `glue:GetDatabases` (paged), then `glue:GetTables --database-name <db>` (paged) for **every** database it lists, including `default` (WAF tables are often created there), in each Region searched, in this order, stopping at the first location match: (a) the ACL's Region (us-east-1 for CLOUDFRONT scope); (b) the agent session's or default Region; (c) the Regions of other resources named in the request. The table's Region is wherever the customer set up Athena, not necessarily the ACL's Region.
2. For each table, compare `StorageDescriptor.Location`, and `Parameters."storage.location.template"` (partition projection), against the expected prefix:

   `s3://<bucket>/AWSLogs/<account-id>/WAFLogs/<region-or-cloudfront>/<webacl-name>/`

   Use `cloudfront` in place of the Region for CloudFront ACLs. If the logging configuration carries an S3 prefix, it comes before `AWSLogs/`.
3. A table with a `storage.location.template` ending in `${log_time}` (or another projection key) is projection-based. Bind the partition filter as described in the "Schema binding" section of `athena-queries.md`, using `glue:GetTable` to read the columns and parameters.
4. **Several matches:** prefer the table whose prefix equals the full expected prefix, then the one with the newest partition range (for projection tables, a range that ends in `NOW`; for others, `glue:GetPartitions` and take the newest). Name the others under Assumptions.
5. **No match:** only after every database in every Region searched was listed (an empty-looking or `default`-only database list is not "no table" until its tables were listed), write "no table found in the Regions searched: <list>; databases listed: <list>" under Assumptions, then go to D-5 and offer D-6. Never fall back to reading raw log objects in S3 (`s3:GetObject`, directly or through a log-reading tool or subagent): that is not an analysis path for this skill.
   Athena queries must run in the table's Region (use that Region for the Athena calls and in the advice you give).
6. **Table found but queries cannot run.** The default policy does not allow `athena:StartQueryExecution`, `athena:GetQueryResults` or `s3:GetObject`. In that case write the Athena queries for the customer (QA-nn, with `<table>` and `<pf>` bound) as advisory text, then continue with D-5. If the session does have Athena rights, run SELECT queries only.
7. **Workgroup and polling (when Athena rights exist).** Use the workgroup named in the request; otherwise one with managed query results enabled (`athena:ListWorkGroups`, then `athena:GetWorkGroup`, `Configuration.ManagedQueryResultsConfiguration.Enabled`); otherwise `primary`. Run in the table's Region. Poll `athena:GetQueryExecution` until the state is `SUCCEEDED`, `FAILED` or `CANCELLED`, and take `Statistics.DataScannedInBytes` from it for the cost report. An output-location, workgroup or permission error is recorded, the intended SQL goes into the output as advisory text, and the investigation continues on D-5 (details: "Schema binding", step 5, in `athena-queries.md`).
8. **Probe first, inside the log subagent.** The main agent stops at `glue:GetTable` and binding; it runs no Athena query. The log subagent's first query is one cheap probe, before it reads any query section: `SELECT count(*) FROM <table> WHERE <pf>` with `<pf>` covering only the last hour of the window. `SUCCEEDED` (any count, including 0): continue with the brief. `AccessDenied`/`AccessDeniedException`, or a workgroup or output-location error: run nothing else and return at once with the exact error and the bound SQL as advisory text; the main agent then records it and continues on D-5. (Running the probe in the main agent serially added about two minutes per run in testing.)

### Logs Insights branch

1. The log group is the one named in the logging configuration (D-3). Confirm with `logs:DescribeLogGroups --log-group-name-prefix aws-waf-logs-` when permitted, and check the retention so the window is not outside it.
2. Run QI-nn queries with `logs:StartQuery` and `logs:GetQueryResults` (both in the default policy). CloudFront ACL log groups are in us-east-1.

**If `glue:GetTables` is denied:** record the denial, say the table search was not possible, and go to D-5 and D-6.

---

## D-5 - Degraded path (logs cannot be queried)

Use when there is no table, no logging, the destination is not queryable, or a permission is missing. The investigation always continues. Confidence is capped at "likely" (except A0 structural clears in `access-denied-triage.md`, which can be high), and the output states what log analysis would add and why it did not happen.

**1. Confirm log freshness (S3 destinations).** `s3:ListBucket` on the `AWSLogs/` prefix is allowed by the default policy for the prefixes `AWSLogs/*` and `*/AWSLogs/*`. List `<prefix>AWSLogs/<account-id>/WAFLogs/<region-or-cloudfront>/<webacl-name>/` using a prefix for today's UTC date path (`.../yyyy/MM/dd/`), then yesterday's if that is empty, because listing returns keys in ascending order and a broad listing would not reach the newest objects. Report the newest object time. This proves logs exist and how fresh they are. It does not read them (`s3:GetObject` is not allowed). If the bucket or prefix is outside the allowed forms, record that and skip.

**2. WAF metrics (always available, logging or not).** `cloudwatch:GetMetricData` in namespace `AWS/WAFV2`. Use `cloudwatch:ListMetrics` first to discover the dimension values. CloudFront-scoped metrics are in us-east-1 with no `Region` dimension. Regional ACLs use the `Region` dimension and the ACL's Region.

| Question | Dimension set | Metrics |
|---|---|---|
| Per ACL totals | `WebACL` (+ `Region` for regional ACLs) | `AllowedRequests`, `BlockedRequests`, `CountedRequests`, `ChallengeRequests`, `CaptchaRequests` |
| Per top-level rule (the ACL name stands for the default action) | `WebACL` + `Rule` | same metrics, plus `BlockRuleMatch`, `CountRuleMatch` |
| Per managed sub-rule | `WebACL` + `ManagedRuleGroup` + `ManagedRuleGroupRule` | same metrics |
| Per label | `WebACL` + `LabelNamespace` + `LabelName` | request counts for that label. For token abuse without logs, compare the Bot Control `token_reuse:*` and `coordinated_activity:*` label counts with `BlockedRequests`: high label counts with flat blocks is detected-not-blocked. Token-id labels have no metrics. |
| Other slices | `Attack`, `Country`, `Device` dimensions | as listed by `ListMetrics` |

Use a Sum statistic with a period that suits the window (60 s for a short window, 300 s for hours). Compare the incident window with a baseline of the same length before it. Metrics can say whether WAF denied requests and which rule did; they cannot say which client or which path. Caveat: Shield L7AM rule-group metrics are not viewable, so L7AM activity does not show per rule.

**3. Sampled requests.** `wafv2:GetSampledRequests --web-acl-arn <arn> --rule-metric-name <RuleMetricName> --scope <scope> --time-window StartTime=<t>,EndTime=<t> --max-items 500`.

- The time window must fall within the last 3 hours. Older incidents cannot be sampled; say so.
- Call once per `RuleMetricName` (take the names from D-2), including the default action's metric name and, for Shield L7AM, the `ShieldMitigationRuleGroup_*` rule.
- Each sample gives example client IP, country, URI, headers, action and labels. Treat them as examples, not counts. Anything the main agent writes from samples (messages, findings, final answer) gives payloads as class and count only, plus field location; application paths without a payload may be named, and no query strings or samples are quoted (SKILL.md, "Output"). The same `awswaf:managed:token:id:` label on samples from several IPs is a qualitative sign of token redistribution (report the id truncated).

Do not bulk-read raw log objects (`s3:GetObject`, directly or through an ad-hoc log-reading subagent) as a substitute for Athena or Logs Insights; on the degraded path, metrics and sampled requests are the sources.

**4. Wrap up.** Finish the rest of the investigation with what these sources give. In "Coverage and gaps" state that WAF logs were not analyzed and why, and give the advisory fix: the DDL from D-6, the logging configuration to enable, or the missing permission (`athena:StartQueryExecution`, `athena:GetQueryResults`, `s3:GetObject`).

---

## D-6 - Advisory table definition (for the customer; the agent never runs DDL)

Offer this when no table matches in D-4. (A table that exists but cannot be queried is a missing-permission case: report the missing Athena permissions per D-4 and D-5 instead.) It is **advisory, for the customer to run; the agent never runs DDL**. Print it with the placeholders filled in from D-3 and D-4 where known, and leave unknown ones as placeholders.

Placeholders:

- `<database>` and `<table>`: names chosen by the customer.
- `<bucket>`: the bucket from the S3 logging destination (name starts with `aws-waf-logs-`).
- `<account-id>`: the account that owns the Web ACL.
- `<region-or-cloudfront>`: the Region of a regional ACL, or the word `cloudfront`.
- `<webacl-name>`: the Web ACL name.
- `<first-day>`: the first day of logs in the form `yyyy/MM/dd/HH/mm`, taken from the oldest object seen in D-5 (or one month before the incident if unknown, recorded under Assumptions).

The column list matches the WAF log format as stored in a table created for these logs. Partition projection on `log_time` (format `yyyy/MM/dd/HH/mm`, 5-minute interval) means no `MSCK REPAIR TABLE` and no partition management are needed.

```sql
CREATE EXTERNAL TABLE `<database>`.`<table>` (
  `timestamp` bigint,
  `formatversion` int,
  `webaclid` string,
  `terminatingruleid` string,
  `terminatingruletype` string,
  `action` string,
  `terminatingrulematchdetails` array<struct<conditiontype:string,sensitivitylevel:string,location:string,matcheddata:array<string>>>,
  `httpsourcename` string,
  `httpsourceid` string,
  `rulegrouplist` array<struct<rulegroupid:string,terminatingrule:struct<ruleid:string,action:string,rulematchdetails:array<struct<conditiontype:string,sensitivitylevel:string,location:string,matcheddata:array<string>>>>,nonterminatingmatchingrules:array<struct<ruleid:string,action:string,overriddenaction:string,rulematchdetails:array<struct<conditiontype:string,sensitivitylevel:string,location:string,matcheddata:array<string>>>,challengeresponse:struct<responsecode:string,solvetimestamp:string>,captcharesponse:struct<responsecode:string,solvetimestamp:string>>>,excludedrules:string>>,
  `ratebasedrulelist` array<struct<ratebasedruleid:string,limitkey:string,maxrateallowed:int>>,
  `nonterminatingmatchingrules` array<struct<ruleid:string,action:string,rulematchdetails:array<struct<conditiontype:string,sensitivitylevel:string,location:string,matcheddata:array<string>>>,challengeresponse:struct<responsecode:string,solvetimestamp:string>,captcharesponse:struct<responsecode:string,solvetimestamp:string>>>,
  `requestheadersinserted` array<struct<name:string,value:string>>,
  `responsecodesent` string,
  `httprequest` struct<clientip:string,country:string,headers:array<struct<name:string,value:string>>,uri:string,args:string,httpversion:string,httpmethod:string,requestid:string,fragment:string,scheme:string,host:string>,
  `labels` array<struct<name:string>>,
  `captcharesponse` struct<responsecode:string,solvetimestamp:string,failurereason:string>,
  `challengeresponse` struct<responsecode:string,solvetimestamp:string,failurereason:string>,
  `ja3fingerprint` string,
  `ja4fingerprint` string,
  `oversizefields` string,
  `requestbodysize` int,
  `requestbodysizeinspectedbywaf` int
)
PARTITIONED BY (
  `log_time` string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES ('serialization.format' = '1')
LOCATION 's3://<bucket>/AWSLogs/<account-id>/WAFLogs/<region-or-cloudfront>/<webacl-name>/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.log_time.type' = 'date',
  'projection.log_time.format' = 'yyyy/MM/dd/HH/mm',
  'projection.log_time.interval' = '5',
  'projection.log_time.interval.unit' = 'minutes',
  'projection.log_time.range' = '<first-day>,NOW',
  'storage.location.template' = 's3://<bucket>/AWSLogs/<account-id>/WAFLogs/<region-or-cloudfront>/<webacl-name>/${log_time}'
)
```

After the customer creates the table, the queries in `athena-queries.md` apply with `<table>` set to `<database>.<table>`, `<req>` = `httprequest.`, label type `array<struct<name>>`, and `<pf>` = `log_time BETWEEN '<start>' AND '<end>'` (see "Schema binding"). Athena needs permission to read the bucket and write query results; mention that the customer must grant it.

---

## D-7 - Shield Advanced status

Run when the ACL has a `ShieldMitigationRuleGroup_*` rule (D-2), when a DDoS event is suspected, or when the WAF rule-out (Q-15, QA-15 / QI-15) needs Shield signals.

1. `shield:DescribeSubscription`. An error such as `ResourceNotFoundException` means there is no Shield Advanced subscription. (`shield:GetSubscriptionState` is not in the default policy.) Optionally `shield:ListProtections` to list protected resources.
2. `shield:DescribeProtection --resource-arn <resource-arn>` (the protected resource: distribution, load balancer and so on). Read `Protection.ApplicationLayerAutomaticResponseConfiguration.Status` (ENABLED or DISABLED) and `.Action` (Block or Count). `ResourceNotFoundException` means the resource is not protected.
3. `shield:ListAttacks --resource-arns <arn> --start-time FromInclusive=<t>,ToExclusive=<t> --end-time FromInclusive=<t>,ToExclusive=<t>`, then `shield:DescribeAttack --attack-id <id>` for each attack overlapping the window. Record attack vectors, start and end times, and peak values.
4. CloudWatch namespace `AWS/DDoSProtection`, dimension `ResourceArn`: `DDoSDetected` (non-zero during an event) and `DDoSAttackRequestsPerSecond` (layer 7 events; only the most significant events are reported). Reported once a minute during events, in us-east-1 for CloudFront and in the resource's Region otherwise.
5. Anti-DDoS managed rule group events report `DDoSAttackRequests` in `AWS/WAFV2`.

Interpretation notes:

- The L7AM rule group always contains the rate-based rule `ShieldKnownOffenderIPRateBasedRule`, plus event-specific mitigation rules that Shield adds and removes. All of them use the configured L7AM action (Count or Block).
- Mitigation rules can stay in place after the event ends. Check for blocks after `DDoSDetected` returns to 0.
- The L7AM rule group's WAF metrics are not viewable. Attribution therefore comes from logs (Q-14, QA-14 / QI-14) or from sampled requests (D-5, step 3) on the `ShieldMitigationRuleGroup_*` rule.

**If any `shield:*` call is denied:** record the denial and continue to the next step and to log-based detection. A `terminatingruleid` or `rulegrouplist` entry starting `ShieldMitigationRuleGroup_` in the logs (Q-14: QA-14 / QA-14b / QI-14 / QI-14b) proves L7AM is attached. Never end D-7 on one denial. If there is no subscription, say "not subscribed" and continue with WAF-side evidence.

---

## Defaults when input is missing (full table)

SKILL.md, "Defaults when input is missing" lists these in short form. Apply them without asking, and record each one under "Assumptions".

| Missing or ambiguous input | Default behavior |
|---|---|
| Time window | Mode A: incident or alarm start minus 30 min, through now, capped at 24 h; if there is no incident time, the last 3 h. Mode B: last 7 days. |
| Which resource or Web ACL | Every Web ACL associated with resources named or implied in the request. If none is identifiable, all Web ACLs in the account (both scopes), ranked by denying-action volume in the window; analyze the top 3. |
| Several Glue tables or log groups for one ACL | Prefer the one whose location matches the ACL's logging destination exactly and that has the newest data. Note the others. |
| Logging enabled to S3, but no Athena table | **Don't stop.** Confirm logs exist and are fresh with `s3:ListBucket` on the `AWSLogs/` prefix. Continue with metrics plus sampled requests ("Degraded path"), and finish the rest of the investigation. Report WAF-log analysis as a coverage gap, with a ready-to-run advisory `CREATE TABLE` (partition projection built from the discovered prefix, D-6). |
| No logging at all | Same degraded path. Report reduced confidence (capped at "likely", except A0 structural clears) and include the advisory logging configuration. |
| Missing IAM permission (for example Athena, or `wafv2:DescribeManagedRuleGroup`) | Fall back to the next source (sampled requests plus metrics; bundled label semantics). Name the missing permission in the output. |

---

## Schema binding and cost guards (detail)

SKILL.md, "Bind schema and guard cost" keeps the short rules. The detail:

- **Athena binding** (`athena-queries.md`, "Schema binding"): bind from `glue:GetTable` (no query cost; not `SHOW CREATE TABLE`).
  - `<table>` = `database.table`.
  - `<req>` = `httprequest.` for a nested request struct, empty for flat fields.
  - Label type `array<struct<name>>` (`x.name`) or `array<string>`.
  - `<pf>` from the partition key and `projection.<key>.format` (for example `log_time BETWEEN '2026/10/06/17/30' AND '2026/10/06/18/30'`).
  - Run SELECT only, and only when `athena:StartQueryExecution` is permitted. Workgroup, Region and polling rules are in the library's "Schema binding".
  - On an output-location, workgroup or permission error, record it, give the bound SQL as advisory text and continue on the degraded path.
- **Probe first, in the log subagent:** the main agent stops at `glue:GetTable` and runs no Athena query. The log subagent's first query is one partition-pruned count over the last hour of the window (D-4 step 8). On `AccessDenied` or a workgroup or output-location error it returns only that error, and the main agent takes the degraded path.
- **Logs Insights** (`logs-insights-queries.md`): flattened, case-sensitive field names (`httpRequest.clientIp`, `labels.0.name`); set the window with the `StartQuery` start and end times.
- **Cost guards:** prune partitions on every Athena query, start with the narrowest window that answers the question, avoid unbounded `SELECT *`, use at most one `UNNEST` per query.
- **Budget:** run at most about 15 log queries per investigation (about 10 on the Mode B fast path) unless a specific finding needs more. Report the number of queries and the bytes scanned for each, and name in coverage and gaps what the budget left out.

---

## Subagent briefs (AWS DevOps Agent)

Read this section in the main agent before you start the log subagent (SKILL.md, Step 1), and in a subagent whose prompt says discovery is done.

**Why subagents.** AWS DevOps Agent can start subagents (in testing: the `subagent` tool with `agent_type` `generic`, a `name`, a `prompt` and `preloaded_skills`). Runs that delegated log querying finished; runs that kept it in the main agent timed out or were refused. The main agent's AWS tool also refuses CloudTrail ("cloudtrail service operations are not allowed"): a tool restriction meaning "use a subagent", not a missing permission.

**Main agent, before delegating.**

- Load this skill once (one load; never again in the same run).
- Read reference sections by search or offset rather than reading or distilling whole files.
- Load no other log-search or log-analysis skill.
- Do D-1 to D-4, D-2b and `glue:GetTable` (or find the log group) yourself.
- Start **one** log-analysis subagent and, when any lookup is needed, the change subagent (Step 3) in the same turn so they run concurrently.
- Give the log subagent `preloaded_skills: ['aws-waf-log-analysis']` where supported.

**Log subagent brief.** The prompt states that discovery is done and must not be repeated, and that the recipient is the querying subagent. It carries everything bound:

- account, Region, scope, Web ACL name and ARN;
- rules with actions, Count overrides, rate rules in Count and token posture;
- logging filter and redacted fields;
- the backend with `<table>` or `<log_group>`, the table's Region, workgroup, `<req>`, label type, partition key and format, and `<pf>`;
- the UTC window;
- the probe as its first query (Athena);
- the mode and the steps to run:
  - Mode A: A0 check 4, the A2 to A4 queries including Q-02 with sub-rules, Q-05 `failureReason` for Challenge or CAPTCHA and Q-19 for blocked attackers, and the A5 label-onset queries. CloudTrail belongs to the change subagent.
  - Mode B: the fast path including Q-13b, or the funnel phases;
- the query budget;
- the return format (below);
- the reminder to pass `service_name` on every AWS tool call.

Keep the brief neutral: no threat adjectives such as "malicious" or "attacker" (the preloaded skill supplies the taxonomy). Give every launch a unique `name` (a finished subagent's name cannot be reused).

**While the subagent runs (main agent).**

- Unless the refusal fallback below applies, do not read `athena-queries.md`, `logs-insights-queries.md` or `label-reference.md`, and do not run Athena or Logs Insights queries yourself (the probe too runs in the log subagent).
- Do metrics (A1, D-5) and Shield (D-7) yourself.
- Start at most one follow-up log pass in total, and only for a new candidate the first pass named but could not characterize. A relaunch after a refusal replaces the failed pass and is not a follow-up. Never a third pass.

**Inside a subagent (prompt says discovery is done).**

- Skip Steps 1 to 3, start no further subagents and do not load this skill again (it is preloaded).
- The log subagent runs the D-4 step 8 probe first, reads only the query-library sections it needs (an offset or search read, not whole files) and returns in the format below.
- The change subagent reads only "Change lookups" in `access-denied-triage.md`, runs at least the skeleton there (Regions, event names, per-source sweep) even if its prompt lists fewer, and returns per that contract.

**Return format (Step 4): compact aggregates only.**

- Per query: its ID, row count, bytes scanned and at most about 20 top rows (counts by rule, client, method and URI, label or time bucket).
- Payloads as **class and count only** (for example "sqli ×75, xss ×60, traversal-lfi ×30"); never samples, match-detail strings, SQL keywords, script tags or metadata IP addresses.
- The exact error code of anything that failed.
- Its Assumptions.
- Mode B also one line per Count or rate-rule client (B-C).
- Never raw result sets or whole log records.

**Refusal, failure or no subagent capability (Step 5).**

- If a log **or change** subagent returns a refusal ("cannot answer") or an empty error, relaunch it once under a new name with the same `preloaded_skills` and the neutral brief.
- A relaunched log subagent also runs without match-detail or payload columns: drop QA-06/QI-06 and the QA-19/QI-19 sample columns; keep counts and class.
- If the change relaunch also fails, write "changes: not checked (change subagent refused twice)".
- Only if a log relaunch also fails, or subagents are unavailable, run count-only aggregate queries yourself:
  - counts by action, rule, client, method and URI, label; about 10 at most;
  - read only the query sections you run;
  - keep results compact as in the return format;
  - never paste a whole reference file or raw result set into your reasoning;
  - record the fallback under "Assumptions".
- A3/A4 detail (Q-05, Q-06, Q-18) is then out of reach: say so under coverage and gaps and cap confidence at "low".

---

## Discovery and degraded-path essentials (full wording)

SKILL.md, "Discover", "Degraded path" and "Rule and label knowledge" list these in short form. Read this section when you need the complete one-line rule; D-1 to D-7 above hold the procedures.

- **Read-only.** Use only Describe, Get and List calls plus the read-only query and lookup calls this skill uses: `logs:StartQuery`/`GetQueryResults`, `athena:StartQueryExecution` (SELECT only, when permitted)/`GetQueryResults`, `cloudtrail:LookupEvents`, `wafv2:GetSampledRequests` and `cloudwatch:GetMetricData`. Never run DDL and never change a Web ACL, rule, IP set, Shield setting, log configuration or any other resource.
- **D-1 Resource to Web ACL:** CloudFront `GetDistributionConfig` `WebACLId`; regional resources `wafv2:GetWebACLForResource`.
- **D-2 Read the ACL:** `wafv2:GetWebACL` for rule order, actions, managed groups and versions, `RuleActionOverrides`, Count overrides, scope-downs, custom responses, token domains, immunity times, and any `ShieldMitigationRuleGroup_*` rule.
- **D-2b Token posture:** from the same response, classify P0 (no token-aware rules), P1 (token labels, no or only threshold-based enforcement) or P2 (strict token enforcement), using Bot Control `InspectionLevel` and ML, ATP/ACFP/Anti-DDoS, token-absent rules, `TokenDomains` and immunity times; confirm with Q-18.
- **D-3 Log destination:** `wafv2:GetLoggingConfiguration`, including logging filters and redacted fields; a log group means Logs Insights, S3 or Firehose means Athena, none, or a non-S3 Firehose destination (HTTP endpoint or third-party platform) without a full S3 backup, means the degraded path.
- **D-4 Find the table or log group:** `glue:GetDatabases`, then `glue:GetTables` for **every** database, including `default`, matching the table `Location` or `storage.location.template` to the bucket/prefix, in the ACL's Region, then the session Region, then the Regions of other resources in the request (the table lives wherever Athena is set up). Write "no table" only after that full listing; then take the degraded path and D-6. Never analyze raw log objects (`s3:GetObject`, directly or through a subagent) as a substitute.
- **D-7 Shield Advanced status:** `shield:DescribeSubscription`, `DescribeProtection` (L7AM status and action), `ListAttacks`/`DescribeAttack`, and `DDoSDetected` in `AWS/DDoSProtection`.

- **WAF metrics:** `AWS/WAFV2` per ACL, per rule and per managed sub-rule say *whether* WAF denied and *which rule*, but not *who* or *which path*; Shield L7AM rule-group metrics are not viewable.
- **Sampled requests:** `wafv2:GetSampledRequests` per rule metric name, last 3 hours only, up to 500 samples per call, as examples rather than counts; Shield L7AM attribution comes from here when logs are unavailable.
- **Confidence:** cap the verdict at "likely" (except A0 structural clears, as defined in `access-denied-triage.md`, which can be high; a metric-based clear is `INCONCLUSIVE` when Shield L7AM is attached, per its "Degraded-path clearing rule"), lower it to "low" when A3 or A4 cannot be assessed, and say exactly what log analysis would add.
- **Wrap-up:** finish the rest of the investigation, then in coverage and gaps state that WAF logs weren't analyzed and why, with the advisory fix (table DDL from D-6, logging configuration, or the missing permission).

- **Rule and label knowledge.** Resolve rule and label facts with L-1 in `label-reference.md` (in AWS DevOps Agent, inside the log-analysis subagent), in this order: `wafv2:DescribeManagedRuleGroup` with the ACL's version when permitted (opt-in; record a denial under "Assumptions"); exact label strings from Q-09 (casing can differ from rule names); then the bundled, dated semantics tables. A connected AWS documentation tool may confirm semantics but is never required. A label found in neither the API output nor the bundled tables is "meaning unverified"; never infer meaning from its name.
