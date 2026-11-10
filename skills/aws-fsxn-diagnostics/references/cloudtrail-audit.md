# CloudTrail Audit — Who Changed What

**Sources:** public AWS FSx for NetApp ONTAP documentation (`docs.aws.amazon.com`). Public doc wins any conflict. Read-only, control-plane.

**When to use.** Any finding where the open question is *who or what changed
this, and when*: a stuck or FAILED administrative action (`REFERENCE.md` §8), a performance
change with no matching load change (`REFERENCE.md` §2/§3), a missing backup (`REFERENCE.md` §7), or a
tiering-policy or AD-configuration change. `REFERENCE.md` §8 establishes that a change
happened; this section establishes who made it.

**Permission required:** `cloudtrail:LookupEvents`. CloudTrail Event History
covers the **last 90 days** with no trail configured. Older events require a
trail. Event source for FSx is `fsx.amazonaws.com`, API version `2018-03-01`.

## What CloudTrail does and does not cover

| Logged | NOT logged |
|---|---|
| All FSx management API calls (`Create*`, `Update*`, `Delete*`, `Describe*`) | ONTAP CLI commands (SSH to the management endpoint) |
| Console actions (identical to the API calls they issue) | NFS / SMB / iSCSI file access (data plane) |
| SDK and CLI calls | ONTAP REST API calls to the SVM management endpoint |
| This skill's own read calls, under `fsx.amazonaws.com` and `monitoring.amazonaws.com` | ONTAP EMS events |

This boundary is a finding in itself. CloudTrail can prove a control-plane
change occurred, but it is silent on data-plane activity. When the question
requires ONTAP CLI or REST to answer — export-policy edits, CIFS share ACL
changes, volume-level ONTAP commands — say so explicitly rather than reporting
"no change found", which would be misleading.

## Management operations worth querying

| Resource | Operations | Diagnostic use |
|---|---|---|
| File system | `CreateFileSystem`, `UpdateFileSystem`, `DeleteFileSystem` (ONTAP restores are volume-level: `CreateVolumeFromBackup`) | Correlate a performance change with a throughput / IOPS / storage change; identify who changed it; audit deletions |
| SVM | `CreateStorageVirtualMachine`, `UpdateStorageVirtualMachine`, `DeleteStorageVirtualMachine` | Track AD join and unjoin events and who changed AD configuration (`REFERENCE.md` §6) |
| Volume | `CreateVolume`, `UpdateVolume`, `DeleteVolume`, `CreateVolumeFromBackup`, `RestoreVolumeFromSnapshot` | Find who changed a tiering policy or volume size; correlate with capacity findings (`REFERENCE.md` §1, §4) |
| Backup | `CreateBackup`, `CopyBackup`, `DeleteBackup` | Verify schedule compliance; investigate backup deletion as a data-loss risk |
| Snapshot | `CreateSnapshot`, `UpdateSnapshot`, `DeleteSnapshot` | Audit snapshot lifecycle when a snapshot policy appears not to fire |
| Tagging | `TagResource`, `UntagResource` | Cost-allocation and tagging-compliance changes |

All `Describe*` and `ListTagsForResource` calls are logged too, which is how you
audit who has been querying the file system.

## Queries — CloudTrail Event History (no trail required)

```bash
# All FSx control-plane calls in the last 24 hours
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventSource,AttributeValue=fsx.amazonaws.com \
  --start-time "$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --query 'Events[*].{Time:EventTime,Action:EventName,User:Username}'

# Everything that touched one file system.
# FSx events carry an EMPTY Resources[] array, so
# --lookup-attributes AttributeKey=ResourceName,AttributeValue=<fs-id> returns
# NOTHING (verified). Look up by EventName and filter the event JSON instead.
# Omit --max-results so the CLI paginates the full window.
for n in CreateStorageVirtualMachine CreateVolume \
         UpdateFileSystem UpdateVolume UpdateStorageVirtualMachine \
         DeleteVolume DeleteStorageVirtualMachine DeleteFileSystem DeleteBackup; do
  aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=EventName,AttributeValue=$n \
    --start-time "<incident-start minus 7 days>" \
    --query "Events[?contains(CloudTrailEvent, '<fs-id>') || contains(CloudTrailEvent, '<svm-id>')].{Time:EventTime,Action:EventName,User:Username}"
done
# Successful calls match on the fs-id because responseElements carries
# fileSystemId (verified for UpdateVolume, whose request has only volumeId).
# FAILED calls have no responseElements — add the svm-id / fsvol-ids from
# Step 2 to the contains() filter so attempted-but-failed changes are not missed.

# Who changed throughput capacity, and to what
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=UpdateFileSystem \
  --query 'Events[*].{Time:EventTime,User:Username,Detail:CloudTrailEvent}'

# Backup deletions — data-loss investigation
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteBackup \
  --query 'Events[*].{Time:EventTime,User:Username,Detail:CloudTrailEvent}'

# Failed FSx calls only
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventSource,AttributeValue=fsx.amazonaws.com \
  --query 'Events[?contains(CloudTrailEvent, `errorCode`)].{Time:EventTime,Action:EventName,Detail:CloudTrailEvent}'
```

`Username` is often absent or unhelpful for assumed roles; read
`userIdentity.arn` and `sourceIPAddress` out of the `CloudTrailEvent` JSON for
the real caller.

## Queries — CloudWatch Logs Insights (only if a trail ships to CloudWatch Logs)

```
# All FSx management events
fields eventTime, userIdentity.arn, eventName, requestParameters, errorCode, errorMessage
| filter eventSource = "fsx.amazonaws.com"
| sort eventTime desc
| limit 100

# Failed FSx calls only
fields eventTime, userIdentity.arn, eventName, errorCode, errorMessage
| filter eventSource = "fsx.amazonaws.com"
| filter ispresent(errorCode)
| sort eventTime desc
| limit 50

# Who changed what on a specific file system
fields eventTime, userIdentity.arn, eventName, requestParameters
| filter eventSource = "fsx.amazonaws.com"
| filter requestParameters like "<fs-id>"
| sort eventTime desc
```

## Scenario to query

Field paths below were **verified against captured events** (FSx test account,
Oct 2026) unless marked †. † means the event type did not occur in the test
account; the path follows the API request shape in lowerCamelCase. If a †
path is absent, search the `requestParameters` object for the key name rather
than concluding the parameter was not changed. Throughput, storage, and IOPS
keys were observed on `CreateFileSystem`; `UpdateFileSystem` uses the same key
names (backup/maintenance-window keys were observed on `UpdateFileSystem`
directly).

**Do not use `EventSource=fsx.amazonaws.com` for change history (verified in a
live run):** it returns every `Describe*`/`List*` call, including the agent's
own, 50 per page. A real `UpdateVolume` fell off the results and was missed.
Look up each mutating `EventName` instead, and paginate.

**Lookups that do NOT work (verified):** FSx management events carry an empty
`Resources[]` array, so `--lookup-attributes AttributeKey=ResourceName,...`
returns nothing for an fs-id, SVM id, volume id, or file-system ARN. Use
`EventName` lookups filtered with `contains(CloudTrailEvent, '<id>')` (the
response elements carry the `fileSystemId`). `ResourceName` **does** work for
EC2 resources such as security-group ids.

| Question | Query | Read from the event |
|---|---|---|
| Who changed throughput capacity? | `UpdateFileSystem` (filter on fs-id) | `requestParameters.ontapConfiguration.throughputCapacity` (gen1 and `MULTI_AZ_2`); `requestParameters.ontapConfiguration.throughputCapacityPerHAPair` (`SINGLE_AZ_2`). Both verified on `CreateFileSystem` |
| Who changed SSD storage or IOPS? | `UpdateFileSystem` | `requestParameters.storageCapacity`, `requestParameters.ontapConfiguration.diskIopsConfiguration.{mode,iops}` |
| What type / HA pairs / routing was a file system created with? | `CreateFileSystem` | `requestParameters.ontapConfiguration.{deploymentType, preferredSubnetId, routeTableIds}`; HA pairs are **`hAPairs`** (note the casing, verified on `SINGLE_AZ_2`) |
| Who moved the backup or maintenance window? | `UpdateFileSystem` | `requestParameters.ontapConfiguration.dailyAutomaticBackupStartTime`, `.weeklyMaintenanceStartTime`, `.automaticBackupRetentionDays` |
| Why did performance degrade at a given time? | `UpdateFileSystem` + `UpdateVolume` around that window | any config change that explains it |
| Who deleted the backup? | `DeleteBackup` † | `userIdentity.arn`, `sourceIPAddress` |
| Was the tiering policy changed? | `UpdateVolume` / `CreateVolume` | `requestParameters.ontapConfiguration.tieringPolicy.{name,coolingPeriod}` |
| Was a volume resized or its snapshot policy changed? | `UpdateVolume` | `requestParameters.ontapConfiguration.sizeInMegabytes`, `.snapshotPolicy` |
| Was the AD configuration changed? | `UpdateStorageVirtualMachine` / `CreateStorageVirtualMachine` | `requestParameters.activeDirectoryConfiguration.selfManagedActiveDirectoryConfiguration.{domainName,organizationalUnitDistinguishedName,userName,dnsIps,fileSystemAdministratorsGroup}` — the password is omitted from the event |
| Why did the AD join fail? (SVM MISCONFIGURED) | `UpdateStorageVirtualMachine` (latest for the SVM) | `responseElements.storageVirtualMachine.ontapErrorMessage` — ONTAP's own join trace (DC and port reached, failing step). Quote the failing step. Not populated on `CreateStorageVirtualMachine` (lifecycle still `PENDING`); fall back to the ONTAP CLI pack only when no event carries it |
| Why did a backup job fail? | `CreateBackup` with `errorCode` present | `errorCode`, `errorMessage` |
| Who deleted the file system / why is it stuck in DELETING? | `DeleteFileSystem` | event time — billing stops at the API call (`REFERENCE.md` §8) |

## Cross-service change events (dependency faults)

Most FSx ONTAP configuration incidents are caused by a change to a
**dependency**, not to FSx — a revoked security-group rule, a replaced NACL
entry, a disabled KMS key. These calls are logged under their own service's
event source, so an FSx-only query (`EventSource=fsx.amazonaws.com`) will miss
them. Rows mirror the Service Dependency Map in `dependencies-and-errors.md`.

| Symptom | Event source | Event names to look up | Read from the event |
|---|---|---|---|
| NFS/SMB mount refused or timing out; port newly closed | `ec2.amazonaws.com` | `RevokeSecurityGroupIngress`, `RevokeSecurityGroupEgress`, `ModifySecurityGroupRules` †, `ModifyNetworkInterfaceAttribute` † (SG swapped on an FSx ENI) | `requestParameters.groupId`; `requestParameters.ipPermissions.items[].{ipProtocol,fromPort,toPort}`; source in `.groups.items[].groupId` (SG reference) or `.ipRanges.items[].cidrIp` (CIDR); `userIdentity.arn` |
| Traffic blocked although the SG is correct | `ec2.amazonaws.com` | `CreateNetworkAclEntry`, `ReplaceNetworkAclEntry`, `DeleteNetworkAclEntry`, `ReplaceNetworkAclAssociation` | `requestParameters.networkAclId` †, `ruleAction` †, `portRange` † |
| No route to the FSx subnet / endpoint unreachable | `ec2.amazonaws.com` | `DeleteRoute`, `ReplaceRoute`, `ReplaceRouteTableAssociation` | `requestParameters.routeTableId` †, `destinationCidrBlock` † |
| Name resolution or AD discovery broke | `ec2.amazonaws.com`, `route53resolver.amazonaws.com` | `AssociateDhcpOptions`, `DisassociateResolverRule`, `UpdateResolverRule` | `requestParameters.dhcpOptionsId` †, `vpcId` † |
| SMB auth failing / SVM MISCONFIGURED (AWS Managed AD) | `ds.amazonaws.com` | `ResetUserPassword` † (FSx service-account password rotated), `DeleteDirectory` †; `CreateMicrosoftAD` for the directory's subnets/VPC | `requestParameters.directoryId` †, `userName` †; `CreateMicrosoftAD`: `requestParameters.vpcSettings.{vpcId,subnetIds}` (password shows as `HIDDEN_DUE_TO_SECURITY_REASONS`) |
| Encryption errors / FSx operations failing on key access | `kms.amazonaws.com` | `DisableKey`, `ScheduleKeyDeletion`, `PutKeyPolicy`, `RevokeGrant` | `requestParameters.keyId` †; match against the file system's `KmsKeyId` |
| Backups stopped or missing | `backup.amazonaws.com` | `UpdateBackupPlan`, `DeleteBackupPlan`, `DeleteBackupSelection`, `PutBackupVaultAccessPolicy`, `DeleteRecoveryPoint` | `requestParameters.backupPlanId` †, `backupVaultName` † |

```bash
# Who touched a specific security group (works for any resource id: sg-, acl-, rtb-, key id)
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=<sg-id> \
  --start-time "<incident-start minus 7 days>" \
  --query 'Events[*].{Time:EventTime,Action:EventName,Detail:CloudTrailEvent}'

# Every ingress revoke in the region over the window
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=RevokeSecurityGroupIngress \
  --start-time "<incident-start minus 7 days>" \
  --query 'Events[*].{Time:EventTime,User:Username,Detail:CloudTrailEvent}'
```

`lookup-events` accepts **one** lookup attribute per call and is **regional** —
query the region the file system lives in. Prefer `ResourceName=<id>` when you
already know the dependency's resource id (from Step 2), and fall back to
`EventName` when you do not.

## Reading a captured event (sanitized sample)

A real `RevokeSecurityGroupIngress` that closed SMB (port 445) on an FSx
security group, trimmed to the fields the analysis uses. Account, IPs, and
ids are placeholders.

```json
{
  "eventTime": "2026-10-12T02:38:15Z",
  "eventSource": "ec2.amazonaws.com",
  "eventName": "RevokeSecurityGroupIngress",
  "awsRegion": "us-east-1",
  "userIdentity": {
    "type": "AssumedRole",
    "arn": "arn:aws:sts::111122223333:assumed-role/<role-name>/<session-name>"
  },
  "sourceIPAddress": "203.0.113.10",
  "userAgent": "aws-cli/2.x ... md/command#ec2.revoke-security-group-ingress",
  "requestParameters": {
    "groupId": "sg-0fsx0example",
    "ipPermissions": { "items": [ {
      "ipProtocol": "tcp", "fromPort": 445, "toPort": 445,
      "groups": { "items": [ { "groupId": "sg-0client0example" } ] },
      "ipRanges": {}, "ipv6Ranges": {}, "prefixListIds": {}
    } ] }
  },
  "errorCode": null
}
```

Read it as: *at 02:38:15Z, `<role-name>/<session-name>` removed TCP 445 from
`sg-0fsx0example` for sources in `sg-0client0example`, via the AWS CLI.* That
is the evidence for "port 445 was **removed**," with caller and time.

## Attributing the caller

| What the event shows | Who actually made the change | How to report it |
|---|---|---|
| `userIdentity.arn` = `assumed-role/<role>/<session>`, CLI/SDK `userAgent` | The principal behind `<session>` | Name the role and session; the session name often identifies the person or automation |
| `userIdentity.invokedBy` = `cloudformation.amazonaws.com`, `Username` = `AWSCloudFormation` | A CloudFormation stack, running as its service role | Attribute to the **stack**: read `aws:cloudformation:stack-name` / `logical-id` from `tagSpecificationSet` (create events), or look up the stack's change set — not to the service role |
| `Username` = `FSx`, `invokedBy` an AWS service (e.g. `CreateNetworkInterface`) | FSx acting on its own resources | Expected service activity (ENI creation at file-system create) — not a customer change |
| `errorCode` present (e.g. `Client.UnauthorizedOperation`) | An **attempted** change that was denied | Not a change. Do not count it as having modified the resource; mention it only if the attempt itself is relevant (e.g. unexpected principal) |
| Session name matches this skill's own read role | This skill or another diagnostic | A denied write attempt from a read-only diagnostic role is a red flag about the diagnostic, not a root cause |

**Self-managed Active Directory is not in CloudTrail.** Password resets,
OU-permission changes, and domain-controller changes on a customer-managed AD
happen outside AWS. For self-managed AD, report the change history as a data
gap and point the customer at their AD audit logs.

**"Removed" vs "never present."** The reference distinction this audit enables:

- A matching `Revoke*` / `Delete*` / `Replace*` event in the window → the rule
  or setting was **removed**; name the caller and time.
- No matching event in the 90-day Event History and no trail → the setting is
  **absent, origin unknown**. Do **not** claim it was "never present" or that it
  was "removed by a recent change" — either is an unsupported inference.
- `cloudtrail:LookupEvents` denied → record a data gap; describe only the
  current state ("port 445 is not allowed"), not its history.

**If no trail exists** and the 90-day Event History window is not enough, that
is a **recommendation to the customer** — create a multi-region trail, and
optionally ship it to CloudWatch Logs for the Insights queries above. This
skill is read-only and never creates or modifies a trail.
