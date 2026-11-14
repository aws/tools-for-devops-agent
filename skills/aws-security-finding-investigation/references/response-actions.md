# Response actions: preserve, contain, eradicate, recover

Every command in this file changes state. **The agent never runs them.** Copy the ones that
apply into the report, fill the placeholders, and label each one "for a person to run; not run
by the agent".

For each action, the report states: purpose, command, impact, how to undo it, and who should
approve it. Production changes need the account owner's approval. Changes that can disrupt a
service need the incident lead's approval as well.

Order: preserve evidence, then contain, then eradicate, then recover and verify. Prefer the
smallest action that is reversible. Isolate; don't destroy.

## 1. Preserve evidence (before any containment)

| Purpose | Command | Undo |
|---|---|---|
| Snapshot every volume of an instance | `aws ec2 create-snapshots --instance-specification InstanceId=<instance-id> --description "IR <case-id>" --copy-tags-from-source volume` | Not needed; delete the snapshots only after the case closes |
| Stop the instance from being terminated | `aws ec2 modify-instance-attribute --instance-id <instance-id> --disable-api-termination`, and `aws ec2 modify-instance-attribute --instance-id <instance-id> --instance-initiated-shutdown-behavior stop` | `--no-disable-api-termination`; the previous shutdown behavior, which you record first with `aws ec2 describe-instance-attribute --instance-id <instance-id> --attribute instanceInitiatedShutdownBehavior` |
| Mark resources as under investigation | `aws ec2 create-tags --resources <resource-id> --tags Key=ir-case,Value=<case-id>` | `aws ec2 delete-tags` with the same key |
| Keep a copy of the current configuration | Save the output of the read-only commands in the evidence queries file (security group rules, bucket policy, role trust policy, user policies) to the case record | Not needed |

Notes:
- Termination protection does not stop Auto Scaling scale-in or health replacement, Spot
  interruption, or a shutdown from inside the instance when its shutdown behavior is
  `terminate`. For an Auto Scaling instance, detach it first: `aws autoscaling detach-instances
  --instance-ids <instance-id> --auto-scaling-group-name <asg> --no-should-decrement-desired-capacity`.
- Containment can destroy volatile evidence (memory, running processes) and can alert an
  attacker. Say so when recommending it. Memory capture needs tooling on the instance and is
  outside this skill.
- Keep the trail's log files: copy them to a separate evidence bucket if the trail bucket's
  retention is short.

## 2. Contain: identities

| Purpose | Command | Impact | Undo |
|---|---|---|---|
| Stop an IAM user's access key | `aws iam update-access-key --user-name <user> --access-key-id <access-key-id> --status Inactive` | Applications using the key fail | `--status Active` |
| Invalidate temporary credentials an IAM user already obtained (for example with `GetSessionToken`) | `aws iam put-user-policy --user-name <user> --policy-name DenyOlderSessions --policy-document file://deny-older-sessions.json` | All of the user's sessions issued before the time in the policy are denied. Write it after the key is deactivated or the user is blocked, or the key can still create newer sessions | `aws iam delete-user-policy --user-name <user> --policy-name DenyOlderSessions`, but not for at least 36 hours: the credentials from `GetSessionToken` and `GetFederationToken` can last 129,600 seconds, and deleting the policy earlier makes stolen sessions valid again |
| Revoke a role's active sessions (not for `AWSReservedSSO_*` roles: see the next row) | IAM console: Roles, the role, **Revoke active sessions**. CLI equivalent: `aws iam put-role-policy --role-name <role> --policy-name AWSRevokeOlderSessions --policy-document file://deny-older-sessions.json` | Every session of the role issued before that time is denied, including legitimate workloads, until they obtain new credentials. Write it after the key or user that can assume the role is cut off | `aws iam delete-role-policy --role-name <role> --policy-name AWSRevokeOlderSessions`, but not before the role's `MaxSessionDuration` has passed (read it with `aws iam get-role --role-name <role>`; up to 12 hours), because deleting it earlier makes stolen sessions valid again |
| Revoke an IAM Identity Center user's permission set sessions (role named `AWSReservedSSO_*`, which IAM won't let you edit) | 1. Find the instance and user ID: `aws sso-admin list-instances`, then `aws identitystore get-user-id --identity-store-id <identity-store-id> --alternate-identifier '{"UniqueAttribute":{"AttributePath":"userName","AttributeValue":"<user-name>"}}'`. 2. Add `deny-identity-center-user.json` to a service control policy attached to the account (from the management account), or merge it into the inline policy of each permission set the user holds: read the current one first with `aws sso-admin get-inline-policy-for-permission-set`, because putting a new inline policy replaces it, write the merged policy with `aws sso-admin put-inline-policy-to-permission-set --instance-arn <instance-arn> --permission-set-arn <permission-set-arn> --inline-policy file://merged.json`, then `aws sso-admin provision-permission-set --instance-arn <instance-arn> --permission-set-arn <permission-set-arn> --target-type AWS_ACCOUNT --target-id <account-id>`. An SCP does not apply to the management account: if the user holds permission sets there, the permission set inline policy is the only option. 3. List the user's assignments (`aws sso-admin list-account-assignments-for-principal --instance-arn <instance-arn> --principal-id <user-id> --principal-type USER`) and remove each with `aws sso-admin delete-account-assignment`, and remove the user from groups that grant access. 4. If the identity source is an external identity provider or Active Directory, disable the user there first, so the user cannot start a new access portal session, then delete the user's active sessions in the IAM Identity Center console. If the identity source is the Identity Center directory, delete the active sessions first, then disable the user. Keep the deny for at least 12 hours | The user loses every permission set in the accounts the deny covers; other users of the same permission sets are not affected | Remove the user ID from the deny policy, recreate the recorded assignments, and enable the user |
| Block a user completely while you investigate | `aws iam put-user-policy --user-name <user> --policy-name DenyAll --policy-document file://deny-all.json` | The user can do nothing, console included. Role sessions the user already assumed keep the role's permissions: revoke those roles' sessions too | `aws iam delete-user-policy --user-name <user> --policy-name DenyAll` |
| Stop instance credentials from being used | Find the association with `aws ec2 describe-iam-instance-profile-associations --filters Name=instance-id,Values=<instance-id>`, then `aws ec2 disassociate-iam-instance-profile --association-id <association-id>` | The instance's applications lose AWS access. Credentials already issued to the instance, and any copy taken from it, stay valid until they expire: also revoke the role's active sessions (row above) | `aws ec2 associate-iam-instance-profile --instance-id <instance-id> --iam-instance-profile Name=<profile>` |

`deny-older-sessions.json`, with a time about 30 seconds after the current UTC time, so that it also covers sessions created while the policy takes effect:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Action": "*",
    "Resource": "*",
    "Condition": {"DateLessThan": {"aws:TokenIssueTime": "<current-utc-time-plus-30-seconds>"}}
  }]
}
```

`deny-all.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{"Effect": "Deny", "Action": "*", "Resource": "*"}]
}
```

`deny-identity-center-user.json`, with the user ID from the identity store:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Action": "*",
    "Resource": "*",
    "Condition": {"StringEquals": {"identitystore:userId": "<identity-store-user-id>"}}
  }]
}
```

What these do not do:
- Deactivating a key does not invalidate temporary credentials already issued with it. Cut off the
  source credential first (deactivate the key, or use the DenyAll row), then write the
  `aws:TokenIssueTime` deny with a time about 30 seconds after now, never earlier. If you write
  the deny first, the key can still create sessions with a later issue time. Do not use the
  attacker's last visible `GetSessionToken` or `AssumeRole` call as the time: CloudTrail delivery
  is delayed, Regional STS calls are logged in the Region that was called, and the key may still
  be active.
- Revoke the sessions of every role the key assumed, including the roles those sessions assumed
  in turn (role chaining) and roles in other accounts. Revoke a role in the account that owns it.
- Keep the user deny for at least 36 hours, and each role deny for at least the role's
  `MaxSessionDuration` (up to 12 hours). Deleting it earlier makes the stolen sessions valid again.
- Never detach an `AWSCompromisedKeyQuarantine*` policy (V2, V3, V4 or later): AWS attached it to
  contain an exposed key. Leave it until the exposure is resolved.
- Revoking sessions does not stop anyone who can assume the role again. Fix the trust policy or
  the credential that allowed it.
- `put-role-policy` fails on roles that IAM Identity Center created for permission sets
  (`AWSReservedSSO_*`). Disabling an Identity Center user alone does not end an active AWS
  access portal session: the user can keep assuming roles until their assignments are removed
  and the session is deleted, so follow the order in the Identity Center row.
- Root credentials: contain from the console. Change the root password, remove root access keys,
  and check the MFA devices. Contact AWS Support if you cannot sign in. In AWS Organizations
  with centralized root access, the management account can remove a member account's root
  credentials. Temporary credentials that root created with `GetSessionToken` or
  `GetFederationToken` are not limited by IAM policies and stay valid until they expire (up to
  1 hour). In a member account, only an SCP that denies the root user applies to them.

## 3. Contain: network

| Purpose | Command | Impact | Undo |
|---|---|---|---|
| Remove one rule that opened a port | `aws ec2 revoke-security-group-ingress --group-id <sg-id> --security-group-rule-ids <rule-id>` | Every resource using the group loses that access | `aws ec2 authorize-security-group-ingress` with the rule you recorded |
| Isolate an instance | Create a security group with no inbound rules and remove its default outbound rules (`aws ec2 revoke-security-group-egress --group-id <isolation-sg-id> --ip-permissions 'IpProtocol=-1,IpRanges=[{CidrIp=0.0.0.0/0}]'`, and the `::/0` rule in a VPC with IPv6), check with `describe-security-group-rules` that none remain, then `aws ec2 modify-instance-attribute --instance-id <instance-id> --groups <isolation-sg-id>` | New connections stop. Tracked connections, including an attacker's open session, continue until they time out | `modify-instance-attribute` with the original group ids you recorded |
| Take an instance out of a load balancer | `aws elbv2 deregister-targets --target-group-arn <target-group-arn> --targets Id=<instance-id>` | Less capacity behind the load balancer | `aws elbv2 register-targets` with the same target |

Notes:
- Security group changes do not cut connections that are already tracked. A TCP or UDP flow is
  untracked, and drops at once, only when an all-traffic rule (`0.0.0.0/0` or `::/0`) allows it
  and a rule in the other direction allows all response traffic on all ports, and it doesn't pass
  through a NAT gateway, Network Load Balancer, Global Accelerator or interface VPC endpoint,
  which always track. Confirm with flow logs that the traffic stopped. A network ACL deny for the instance's address on the subnet cuts it
  at once but is evaluated for the whole subnet; recommend it when an attacker's session is
  still open.
- An instance in an Auto Scaling group can be replaced while isolated. Detach it from the group
  first (section 1), or protect it with `aws autoscaling set-instance-protection
  --protected-from-scale-in` and suspend the `ReplaceUnhealthy` process, and record which one
  you chose. Spot instances cannot get termination protection: snapshot them first.
- For an instance with several network interfaces, change each one with
  `aws ec2 modify-network-interface-attribute --network-interface-id <eni-id> --groups <isolation-sg-id>`.

## 4. Contain: data

| Purpose | Command | Impact | Undo |
|---|---|---|---|
| Stop public access to a bucket | `aws s3api put-public-access-block --bucket <bucket> --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true` | Public and anonymous access stops, and so does cross-account access granted by a public policy and any intended public use such as a static website | `put-public-access-block` with the recorded settings, or `delete-public-access-block` if none were set |
| Remove a policy statement that grants access | Save the policy (`get-bucket-policy`), then `aws s3api put-bucket-policy --bucket <bucket> --policy file://policy-fixed.json` | Principals in the removed statement lose access | `put-bucket-policy` with the saved policy |
| Stop a replication rule that copies data out | Save the configuration (`get-bucket-replication`), then `aws s3api delete-bucket-replication --bucket <bucket>` | Replication stops for all rules of the bucket | `put-bucket-replication` with the saved configuration |
| Keep earlier versions of overwritten or deleted objects | `aws s3api put-bucket-versioning --bucket <bucket> --versioning-configuration Status=Enabled` | Overwritten or deleted objects keep their earlier versions from now on. Anyone with `s3:DeleteObjectVersion`, and any lifecycle rule that expires noncurrent versions, can still remove them | Versioning can be suspended, not removed |

What these do not do:
- Block Public Access does not stop reads by IAM principals that are already allowed. It does not
  contain an incident that uses a valid identity; contain the identity instead.
- None of them recover data already read or copied.

## 5. Eradicate

Run the read-only check first, then remove only what the evidence ties to the attacker.

| What to remove | Read-only check | Command | Undo |
|---|---|---|---|
| Access keys the attacker created | `aws iam list-access-keys --user-name <user>` and the `CreateAccessKey` events | Deactivate first (`update-access-key --status Inactive`), then `aws iam delete-access-key --user-name <user> --access-key-id <access-key-id>` after confirmation | **Irreversible** once deleted |
| Policies the attacker attached | `aws iam list-attached-user-policies --user-name <user>`, `list-user-policies` | `aws iam detach-user-policy --user-name <user> --policy-arn <policy-arn>`, `aws iam delete-user-policy --user-name <user> --policy-name <name>` (never the AWS quarantine policy) | Re-attach from the recorded state |
| A policy version the attacker made default | `aws iam get-policy --policy-arn <policy-arn>` (`DefaultVersionId`), `aws iam get-policy-version`, and the `CreatePolicyVersion` and `SetDefaultPolicyVersion` events | `aws iam set-default-policy-version --policy-arn <policy-arn> --version-id <previous-version>` | Set the attacker's version as default again |
| A console password the attacker set | `aws iam get-login-profile --user-name <user>` and the `CreateLoginProfile` or `UpdateLoginProfile` events | `aws iam delete-login-profile --user-name <user>` | `create-login-profile` with a new password |
| An OpenID Connect provider the attacker added | `aws iam list-open-id-connect-providers` and the `CreateOpenIDConnectProvider` events | Record it first (`aws iam get-open-id-connect-provider --open-id-connect-provider-arn <provider-arn>`) and the roles whose trust policy names it, then `aws iam delete-open-id-connect-provider --open-id-connect-provider-arn <provider-arn>` after confirmation. Find trusting roles with `aws iam list-roles` and look for the provider ARN in `AssumeRolePolicyDocument`; they stay in the account and cannot be assumed until it is recreated | `aws iam create-open-id-connect-provider --url https://<recorded-url>` with the recorded client IDs and thumbprints |
| A permissions boundary the attacker removed or changed | `aws iam get-user --user-name <user>` or `get-role --role-name <role>` (`PermissionsBoundary`) and the `PutUserPermissionsBoundary`, `DeleteUserPermissionsBoundary`, `PutRolePermissionsBoundary`, `DeleteRolePermissionsBoundary` events | `aws iam put-user-permissions-boundary --user-name <user> --permissions-boundary <policy-arn>` (or the role form) with the previous boundary ARN from the AWS Config history of the user or role (or the earlier Put event) | `aws iam delete-user-permissions-boundary --user-name <user>` (or the role form) |
| Roles the attacker created | `aws iam get-role --role-name <role>` and the `CreateRole` events | Revoke the role's sessions, detach its managed policies, delete its inline policies (`aws iam delete-role-policy`), remove it from instance profiles (`aws iam remove-role-from-instance-profile`), then `aws iam delete-role --role-name <role>` after confirmation | **Irreversible** |
| A changed role trust policy | `aws iam get-role --role-name <role>` and the AWS Config history of the role | `aws iam update-assume-role-policy --role-name <role> --policy-document file://trust-before.json` | Apply the changed policy again |
| Users the attacker created | `aws iam list-users` and the `CreateUser` events | Remove their keys, login profile, signing certificates, SSH public keys, service-specific credentials, MFA devices, policies and group memberships (find them with `aws iam list-signing-certificates`, `list-ssh-public-keys`, `list-service-specific-credentials`), then `aws iam delete-user --user-name <user>` after confirmation | **Irreversible** |
| Group memberships the attacker added | `aws iam list-groups-for-user --user-name <user>` and the `AddUserToGroup` events | `aws iam remove-user-from-group --user-name <user> --group-name <group>` | `aws iam add-user-to-group --user-name <user> --group-name <group>` |
| Policies the attacker attached or wrote on existing roles and groups | `aws iam list-attached-role-policies --role-name <role>`, `list-role-policies`, `aws iam list-attached-group-policies --group-name <group>`, `list-group-policies`, and the `AttachRolePolicy`, `PutRolePolicy`, `AttachGroupPolicy` and `PutGroupPolicy` events | Save an inline policy first (`aws iam get-role-policy`, `get-group-policy`), then `aws iam detach-role-policy --role-name <role> --policy-arn <policy-arn>`, `aws iam delete-role-policy --role-name <role> --policy-name <name>`, `aws iam detach-group-policy --group-name <group> --policy-arn <policy-arn>` or `aws iam delete-group-policy --group-name <group> --policy-name <name>`. Remove only what the events tie to the attacker: other users and workloads rely on these roles and groups | Attach or put the policy again from the saved copy |
| A SAML provider the attacker added | The `CreateSAMLProvider` events (the provider ARN is in the response elements), then `aws iam get-saml-provider --saml-provider-arn <provider-arn>` | Record it first (`get-saml-provider`) and the roles whose trust policy names it (`aws iam list-roles`, look for the provider ARN in `AssumeRolePolicyDocument`), then `aws iam delete-saml-provider --saml-provider-arn <provider-arn>` after confirmation. Those roles stay in the account and cannot be assumed until it is recreated | `aws iam create-saml-provider --name <name> --saml-metadata-document file://metadata.xml` with the recorded metadata |
| MFA devices the attacker registered | The `CreateVirtualMFADevice` and `EnableMFADevice` events (they show the serial number), and `aws iam list-virtual-mfa-devices --assignment-status Assigned` | `aws iam deactivate-mfa-device --user-name <user> --serial-number <serial-number>`, then for a virtual device `aws iam delete-virtual-mfa-device --serial-number <serial-number>`. Keep the user's own legitimate device | The user registers a device again |
| Snapshots and images the attacker shared | `aws ec2 describe-snapshot-attribute --snapshot-id <snapshot-id> --attribute createVolumePermission`, `aws ec2 describe-image-attribute --image-id <image-id> --attribute launchPermission`, `aws rds describe-db-snapshot-attributes --db-snapshot-identifier <snapshot-id>`, and the `ModifySnapshotAttribute`, `ModifyImageAttribute`, `ModifyDBSnapshotAttribute` and `ModifyDBClusterSnapshotAttribute` events | `aws ec2 modify-snapshot-attribute --snapshot-id <snapshot-id> --attribute createVolumePermission --operation-type remove --group-names all` (or `--user-ids <account-id>` for one account), `aws ec2 modify-image-attribute --image-id <image-id> --launch-permission '{"Remove":[{"Group":"all"}]}'`, `aws rds modify-db-snapshot-attribute --db-snapshot-identifier <snapshot-id> --attribute-name restore --values-to-remove all` (for a cluster snapshot, `modify-db-cluster-snapshot-attribute --db-cluster-snapshot-identifier <snapshot-id>`). Whoever already copied a snapshot keeps the copy | Add the permission again with the same command and `--operation-type add`, `Add` or `--values-to-add` |
| Instances the attacker launched, in any Region | `aws ec2 describe-instances --region <region>` per Region, and the `RunInstances` events | After the snapshots in section 1: `aws ec2 terminate-instances --instance-ids <instance-id>` after confirmation | **Irreversible**; only for instances the attacker created |

Do not clean a compromised instance in place. Recommend replacing it from a known-good image.

## 6. Recover and verify

| Purpose | Command |
|---|---|
| Restart a stopped trail | `aws cloudtrail start-logging --name <trail>` (for an organization trail, from the management account or the CloudTrail delegated administrator) |
| Restart AWS Config recording | `aws configservice start-configuration-recorder --configuration-recorder-name <name>` |
| Re-enable a GuardDuty detector | `aws guardduty update-detector --detector-id <detector-id> --enable`. If the detector was deleted: `aws guardduty create-detector --enable` (or re-enable from the delegated administrator); earlier findings are lost, so record the gap |
| Cancel a scheduled KMS key deletion | `aws kms cancel-key-deletion --key-id <key-id>`, then `aws kms enable-key --key-id <key-id>` (the key is disabled after cancellation). It does not recover data rewritten with a key you do not control |
| Require IMDSv2 on an instance | `aws ec2 modify-instance-metadata-options --instance-id <instance-id> --http-tokens required` (applications that still use IMDSv1 stop getting credentials until they are updated; undo with `--http-tokens optional`) |
| Rotate a legitimate user's key | Create the new key, update the applications, confirm the old key is no longer used (`get-access-key-last-used`), then delete the old key |

Verify with read-only checks and say which ones passed:
- The contained key shows no use after containment (`aws iam get-access-key-last-used`; it covers the long-term key only).
- Session revocation worked: in CloudTrail, find the `ASIA…` access keys issued before the revocation time and confirm that their later calls now fail with an explicit-deny `AccessDenied`.
- `aws s3api get-bucket-policy-status --bucket <bucket>` reports `IsPublic` false.
- The security group no longer has the opened rule (`describe-security-group-rules`), and flow
  logs show no new accepted connections on that port.
- The trail is logging again (`aws cloudtrail get-trail-status`: `IsLogging` true and a recent
  `LatestDeliveryTime`; or the trail's `isLogging` in AWS Config), and the gap in logging is
  recorded in the report.
- No new GuardDuty findings for the same resources since containment.
- The normal business flow still works: name the check the service owner should run.

Recommend the logging that was missing during this incident, for example S3 data events for the
affected bucket, flow logs for the VPC, or a multi-Region trail.
