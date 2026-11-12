# Evidence queries

All reads here are read-only. Replace placeholders in angle brackets. Always bound the time:
the incident window plus a margin, in UTC.

Rows marked **(extra permission)** need a permission that the default
`AIDevOpsAgentAccessPolicy` does not grant (the README lists them). If the call is denied, the
fact it would show is Unknown unless the alternative in the same row answers it.

## 1. CloudTrail management events and trail settings

`AIDevOpsAgentAccessPolicy` allows `cloudtrail:LookupEvents`, `DescribeTrails`,
`GetTrailStatus` and `GetEventSelectors`, but which tool can make the call depends on where you
run (observed November 2026):

| Where you run | Management events (who called which API) | Trail settings (next table) |
|---|---|---|
| An investigation, or a subagent working for one | `lookup_cloudtrail_events` | The "In an investigation" column. `use_aws` refuses CloudTrail operations here ("cloudtrail service operations are not allowed"): don't call them |
| Chat | `lookup_cloudtrail_events` if you have it, otherwise `use_aws` CloudTrail `LookupEvents` with the same attributes | The "In chat" column |

A refusal is a runtime restriction, not a permission gap (SKILL.md, Error handling). When a
fallback answers the same question, the refusal is not a gap in the report.

One lookup attribute per call (`AccessKeyId`, `Username`, `EventName`, `EventSource`,
`ResourceName`, `ResourceType`, `EventId` or `ReadOnly`), one Region per call:

```text
lookup_cloudtrail_events(
    attribute_key="Username",
    attribute_value="<user-name>",
    aws_account_id="<account-id>",
    aws_region="<region>",
    start_time="<start-utc>",
    end_time="<end-utc>",
    jmespath_filter="[].{Time: EventTime, Name: EventName, Event: CloudTrailEvent}"
)
```

The filter applies to a root array of event summaries. Identity, source IP, `errorCode` and
request parameters are inside `CloudTrailEvent`, a serialized JSON string: parse it before you
use any of them. `events: []` is a valid empty result; `events: null` means the filter shape
failed, not zero activity. A returned `continuation_timestamp` means more events remain: do not
treat the result as complete.

Trail settings (is a trail logging, which Regions, does it record data events):

| Question | In chat | In an investigation |
|---|---|---|
| Which trails exist, multi-Region, where they deliver | `aws cloudtrail describe-trails` (per Region; a multi-Region trail appears in every Region): `IsMultiRegionTrail`, `HomeRegion`, `S3BucketName`, `CloudWatchLogsLogGroupArn`, `HasCustomEventSelectors` | AWS Config: `aws configservice list-discovered-resources --resource-type AWS::CloudTrail::Trail`, then `get-resource-config-history` for each **(extra permission)**. The same fields are in `configuration` |
| Is a trail logging, and since when | `aws cloudtrail get-trail-status --name <trail>`: `IsLogging`, `StartLoggingTime`, `StopLoggingTime`, `LatestDeliveryTime`, `LatestCloudWatchLogsDeliveryTime`, `LatestDeliveryError` | `supplementaryConfiguration.isLogging` (the text `"true"` or `"false"`) in the trail's latest Config item, and the `StopLogging` / `StartLogging` events below |
| Does a trail record data events for a bucket | `aws cloudtrail get-event-selectors --trail-name <trail>`: a selector for `AWS::S3::Object` (advanced: `resources.type`, and `resources.ARN` covering the bucket), and whether it records reads: `ReadWriteType` on a basic selector (`WriteOnly` records no `GetObject`), or the `readOnly` and `eventName` field selectors on an advanced one | The last `PutEventSelectors` event for each trail, in its request parameters, with the same fields (the Config history doesn't hold the selectors). No such event in the last 90 days means Unknown, not none |
| Was logging stopped, restarted, or the selectors changed | Management events with `EventName` = `StopLogging`, `StartLogging`, `DeleteTrail`, `UpdateTrail`, `PutEventSelectors` (for a CloudTrail Lake event data store: `StopEventDataStoreIngestion`, `StartEventDataStoreIngestion`): who, when, and the new selectors. A `StopLogging` followed by `StartLogging` leaves a gap between the two, not an open-ended one | Same |

## 2. Check the other sources are recording

| Question | Command | What to read |
|---|---|---|
| Are flow logs on for the ENI, its subnet or its VPC, and what traffic do they record | `aws ec2 describe-flow-logs --filter Name=resource-id,Values=<eni-id>,<subnet-id>,<vpc-id>` | `FlowLogStatus`, `TrafficType`, `LogDestination`, `LogFormat`, `CreationTime`. A flow log with `TrafficType` `REJECT` never holds `ACCEPT` records, so it can't show that an opening was used |
| Is GuardDuty on in this Region | `aws guardduty list-detectors`, then `aws guardduty get-detector --detector-id <id>` | `Status`, enabled features |
| Is AWS Config recording | `aws configservice describe-configuration-recorder-status` | `recording`, `lastStatus` |

If a source was off for part of the window, everything it would have shown for that part is
Unknown. Write the covered window next to the window you were asked about.

## 3. The finding itself

```bash
aws guardduty get-findings --detector-id <detector-id> --finding-ids <finding-id>
```

Read `Type`, `Severity`, `Resource` (access key, instance, bucket), `Service.Action` (API called,
remote IP, port), `Service.ResourceRole` (`TARGET` or `ACTOR`), `Service.EventFirstSeen`,
`Service.EventLastSeen`, `Service.Count`, and `Service.AdditionalInfo` (it contains `"sample": true`
for a GuardDuty sample finding, whose title also starts with `[SAMPLE]`; that is not an event). The same finding in Security Hub is a copy, not a second source.

## 4. Who acted and what changed: management events

With `lookup_cloudtrail_events`, start narrow: the principal (`AccessKeyId` or `Username`) or the
resource (`ResourceName`), then widen to `EventName` for the change events below. From each
parsed `CloudTrailEvent` read `eventTime`, `eventName`, `sourceIPAddress`, `userAgent`,
`errorCode`, `requestParameters`.

Change events to look for in the window:

- Identity: `CreateUser`, `CreateAccessKey`, `UpdateAccessKey`, `CreateLoginProfile`,
  `UpdateLoginProfile`, `CreateRole`, `UpdateAssumeRolePolicy`, `AddUserToGroup`
- Permissions: `AttachUserPolicy`, `AttachRolePolicy`, `AttachGroupPolicy`, `PutUserPolicy`,
  `PutRolePolicy`, `PutGroupPolicy`, `CreatePolicyVersion`, `SetDefaultPolicyVersion`
- Exposure: `AuthorizeSecurityGroupIngress`, `PutBucketPolicy`, `PutBucketAcl`,
  `ModifyImageAttribute` (read `launchPermission`), `ModifyDBInstance` (read `publiclyAccessible`),
  `PutBucketPublicAccessBlock`, `DeleteBucketPublicAccessBlock`, `PutAccountPublicAccessBlock`,
  `DeleteAccountPublicAccessBlock`, `ModifySnapshotAttribute`, `ModifyDBSnapshotAttribute`,
  `ModifyDBClusterSnapshotAttribute`, `PutBucketReplication`
- Logging and detection: `StopLogging`, `StartLogging`, `DeleteTrail`, `UpdateTrail`,
  `PutEventSelectors`, `StopConfigurationRecorder`, `DeleteConfigurationRecorder`,
  `DeleteDetector`, `UpdateDetector`, `DeleteFlowLogs`, `DeleteLogGroup`, `DeleteDeliveryChannel`,
  `DeleteResolverQueryLogConfig`, `DisassociateResolverQueryLogConfig`, `CreateIPSet`, `UpdateIPSet`,
  `CreateFilter`, `UpdateFilter`, `DisassociateFromAdministratorAccount`, `DisableSecurityHub`,
  `BatchUpdateFindings`, `LeaveOrganization`; `PutBucketLifecycle` or `PutBucketPolicy` on the bucket
  that holds the trail's logs
- Keys: `ScheduleKeyDeletion`, `DisableKey`, `PutKeyPolicy`, `CreateGrant`
- Compute and federation: `RunInstances`, `CreateOpenIDConnectProvider`, `CreateSAMLProvider`,
  `PutUserPermissionsBoundary`, `DeleteUserPermissionsBoundary`, `PutRolePermissionsBoundary`,
  `DeleteRolePermissionsBoundary`; `PutBucketLifecycle` for objects set to expire

When the trail also delivers to CloudWatch Logs, Logs Insights is faster for long windows. Run
these against the trail's log group.

All calls by one access key, in order:

```
fields eventTime, eventSource, eventName, sourceIPAddress, userAgent, errorCode, awsRegion
| filter userIdentity.accessKeyId = "<access-key-id>"
| sort eventTime asc
| limit 500
```

Successful and denied calls, counted separately:

```
fields eventName, errorCode
| filter userIdentity.arn = "<principal-arn>"
| stats count(*) as calls by eventName, errorCode
| sort calls desc
```

If a Logs Insights query times out, narrow the window or the filter before retrying.

## 5. Was data read: S3 data events

`GetObject` and other object-level calls are data events. They are never in Event history or
`lookup_cloudtrail_events`. They can be counted here only when the trail that records them also
delivers to a CloudWatch Logs group (`cloudWatchLogsLogGroupArn` in section 1) and its selectors record reads (section 1: a trail that records only `WriteOnly` data events gives 0 `GetObject`, which is Unknown, not zero). Then:

```
fields userIdentity.arn, userIdentity.accountId, errorCode, requestParameters.key
| filter eventSource = "s3.amazonaws.com" and eventName = "GetObject"
    and requestParameters.bucketName = "<bucket>"
| stats count(*) as calls, countDistinct(requestParameters.key) as objects
    by userIdentity.arn, userIdentity.accountId, errorCode
```

`countDistinct` is approximate for many keys: write "about N objects". Anonymous requests have
`userIdentity.accountId` `anonymous` and no ARN, and may not appear in the grouping above: run a
second query for them, `filter eventSource = "s3.amazonaws.com" and eventName = "GetObject" and
userIdentity.accountId = "anonymous" | stats count(*) by errorCode`, and count them separately.

If the data events go only to the trail's S3 files, or no trail records them, object access is
**Unknown** in this investigation. Say which it is, and recommend delivering the trail to
CloudWatch Logs (or querying the files with Athena outside the agent). If
`aws s3api get-bucket-logging --bucket <bucket>` shows S3 server access logs, name the target
bucket as where the evidence is.

## 6. Current state and configuration

| Resource | Command |
|---|---|
| Before and after state of a resource **(extra permission)** | `aws configservice get-resource-config-history --resource-type <type> --resource-id <id> --earlier-time <start-utc> --later-time <end-utc>`. Alternative: the request parameters of the change event |
| Which Config rules flag a resource **(extra permission)** | `aws configservice get-compliance-details-by-resource --resource-type <type> --resource-id <id>`, or `get-compliance-details-by-config-rule --config-rule-name <rule> --compliance-types NON_COMPLIANT` for the resources a rule flags. Alternative: `aws configservice describe-compliance-by-config-rule --config-rule-names <rule>` (counts only) |
| Who uses a security group | `aws ec2 describe-network-interfaces --filters Name=group-id,Values=<sg-id>` |
| Current rules of a security group | `aws ec2 describe-security-group-rules --filters Name=group-id,Values=<sg-id>` |
| Bucket exposure | `aws s3api get-public-access-block --bucket <bucket>`, `aws s3api get-bucket-policy --bucket <bucket>`, `aws s3api get-bucket-acl --bucket <bucket>`; `aws s3api get-bucket-policy-status --bucket <bucket>` **(extra permission)** |
| Account-level Block Public Access **(extra permission)** | `aws s3control get-public-access-block --account-id <account-id>`. `NoSuchPublicAccessBlockConfiguration` means none is set. Alternative: `PutAccountPublicAccessBlock` and `DeleteAccountPublicAccessBlock` events |
| A user's keys and their last use **(extra permission)** | `aws iam list-access-keys --user-name <user>`, `aws iam get-access-key-last-used --access-key-id <access-key-id>`. Alternative: `CreateAccessKey` and `UpdateAccessKey` events, and the lookup tool by `AccessKeyId` for recent use |
| A user's permissions **(extra permission)** | `aws iam list-attached-user-policies --user-name <user>`, `aws iam list-user-policies --user-name <user>`, `aws iam list-groups-for-user --user-name <user>`, then `list-attached-group-policies` and `list-group-policies` for each group. Alternative: the permission events in section 4 |
| A role's permissions | `aws iam list-attached-role-policies --role-name <role>`, `aws iam list-role-policies --role-name <role>` |
| Who can assume a role | `aws iam get-role --role-name <role>` (read `AssumeRolePolicyDocument`) |
| Root access keys present **(extra permission)** | `aws iam get-account-summary` (`AccountAccessKeysPresent` counts keys; it does not show whether they are active). Alternative: `CreateAccessKey` events with `userIdentity.type` `Root`; no such event in the last 90 days means Unknown, not none |
| Instance details | `aws ec2 describe-instances --instance-ids <instance-id>` (role, security groups, `MetadataOptions.HttpTokens`, launch time) |
| KMS key state | `aws kms describe-key --key-id <key-id>` (`KeyState`, `DeletionDate`, `KeyManager`) |

## 7. Was the opening used: VPC Flow Logs

Logs Insights discovers the fields of the default flow log format (`interfaceId`, `srcAddr`,
`dstAddr`, `srcPort`, `dstPort`, `protocol`, `action`, `bytes`). For a custom format, parse
the fields in the exact order of `LogFormat` first.

Accepted inbound connections to the opened port since the change, from outside your ranges:

```
fields @timestamp, interfaceId, srcAddr, dstPort, action, bytes
| filter dstPort = <port> and action = "ACCEPT"
    and interfaceId in ["<eni-id-1>", "<eni-id-2>"]
    and not isIpv4InSubnet(srcAddr, "<internal-cidr>")
| stats count(*) as flows, sum(bytes) as bytes by srcAddr
| sort flows desc
```

`isIpv4InSubnet` takes one IPv4 range and treats every IPv6 address as outside it: repeat the
condition for each internal range, and review IPv6 sources separately.

New outbound destinations from a suspect instance (for mining pools or command and control):

```
fields @timestamp, srcAddr, dstAddr, dstPort, bytes
| filter interfaceId = "<eni-id>" and srcAddr = "<instance-private-ip>" and action = "ACCEPT"
| stats sum(bytes) as bytes, count(*) as flows by dstAddr, dstPort
| sort bytes desc
| limit 50
```

No accepted flows is "exposure without observed use" only if flow logs recorded `ACCEPT` traffic (`TrafficType` `ALL` or `ACCEPT`) for the whole period, at the ENI, its subnet or its VPC.
Flow logs off for part of the period, or records with `logStatus` `SKIPDATA`, make use Unknown
for that part. `NODATA` means the ENI had no traffic in that interval. For deeper flow log
analysis, use the `network-log-analyzer` skill when it is available.
