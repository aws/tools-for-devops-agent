# Investigation modes and triage priority

Pick every mode the signal matches. One incident often spans several modes, for example a
leaked key (mode 1) used to create another key (mode 3) and read a bucket (mode 6). Run each
mode's checks and merge the results into one timeline.

The modes follow the scenarios in the AWS incident response playbooks and the GuardDuty threat
purposes. For a GuardDuty attack sequence finding (`AttackSequence:*`), start from the signals it
lists and open every mode they match. A finding that matches no mode still gets the four questions from the skill: who
acted, what changed, what is exposed, was it used. Say in the report that no specific mode
applied.

## Triage priority

This is a **suggested** priority. Start from the first row that matches, then adjust. Report the
row you used. Business impact and data sensitivity are not in the account data: list them as
inputs the incident lead confirms before the priority is final. Persistence and root rows are
this skill's own judgement; movement into one other account is P2 and into several is P1.

| Priority | Use when |
|---|---|
| P1 Critical | Root credentials used by anyone other than the expected owner; data confirmed leaving the account; production down because of the incident; several accounts involved |
| P2 High | A compromise confirmed and still needing containment; misuse of a privileged credential; persistence created (for example a second access key, a new user or role, a changed trust policy) even if the escalation was denied; movement into another account; a credential exposed publicly |
| P3 Medium | Suspicious activity that is not yet confirmed; an exposure with no evidence of use yet; a policy violation with security impact |
| P4 Low | Informational findings, reconnaissance with no confirmed impact, or activity confirmed benign |

Adjust:
- Raise one level when the attacker is still active, or when you cannot tell. Treat unknown as
  active.
- When it is unknown whether data was accessed, start at P2 and raise to P1 if access to
  customer or personal data is confirmed.
- Lower one level only when the scope is limited to non-production, non-sensitive resources and
  the access has ended with no persistence.

## 1. Credential and identity misuse

Signals: `UnauthorizedAccess:IAMUser/*` (including `InstanceCredentialExfiltration.OutsideAWS`
and `.InsideAWS`, `MaliciousIPCaller`, `TorIPCaller`, `ConsoleLoginSuccess.B`),
`CredentialAccess:IAMUser/*`, `InitialAccess:IAMUser/AnomalousBehavior`,
`Discovery:IAMUser/AnomalousBehavior`, a CloudTrail alarm on an access key used from a new
network, an AWS Health notification about an exposed key.

Collect:
- All calls by the access key or session in the window, in order, with source IP, user agent,
  and `errorCode`. Mark the first call from the suspicious source.
- For a role session: the `AssumeRole` (or `AssumeRoleWithWebIdentity`, `AssumeRoleWithSAML`)
  event that issued it, and whether the role was assumed again or chained into another role or
  account. A role named `AWSReservedSSO_<permission-set>_<suffix>` belongs to an IAM Identity
  Center permission set: record the session name and the permission set, because containment
  for it happens in IAM Identity Center, not on the role (response actions, section 2).
- For instance credentials used outside AWS: the instance, its role, and the instance metadata
  settings (IMDSv1 allowed or not). Open mode 7 for the instance.
- Console sign-ins (`ConsoleLogin`) for the user, with MFA used or not. The Region of these
  events varies; check every Region listed in the SKILL.md gotchas, or a multi-Region trail.

Read carefully:
- Denied calls are evidence of use. A burst of denied `List*` and `Get*` calls is typical of
  discovery after a leak.
- A CI system or a developer laptop on a new network is a common benign cause. Confirm it
  against an approval source or the owner; do not assume it.

## 2. Root account activity

Signals: `Policy:IAMUser/RootCredentialUsage`, `Policy:IAMUser/ShortTermRootCredentialUsage`,
a root `ConsoleLogin`, any event where `userIdentity.type` is `Root`.

Collect: every root event in the window, source IP, MFA status, and what was changed. Root
`ConsoleLogin` events can be in us-east-1, us-east-2 or us-west-2: look in all three, or in a multi-Region trail. Check
whether root access keys exist (`aws iam get-account-summary`, field `AccountAccessKeysPresent`: the count shows that a key exists, not that it is active;
extra permission; otherwise look for `CreateAccessKey` events by `Root`; none in the last 90 days means Unknown, not none).

Read carefully: some tasks need root, and with centralized root access in AWS Organizations a
short-term root session can be expected. Use of root by anyone other than the documented owner
is P1.

## 3. Privilege escalation and persistence

Signals: `PrivilegeEscalation:IAMUser/AnomalousBehavior`, `Persistence:IAMUser/AnomalousBehavior`,
and CloudTrail events such as `CreateUser`, `CreateAccessKey`, `CreateLoginProfile`,
`UpdateLoginProfile`, `AttachUserPolicy`, `AttachRolePolicy`, `PutUserPolicy`, `PutRolePolicy`,
`CreatePolicyVersion` with `setAsDefault`, `UpdateAssumeRolePolicy`, `AddUserToGroup`,
`CreateRole`.

Collect: who made each change, from where, and whether it succeeded. For each new or changed
identity, list its permissions and every call it made afterwards. For a changed trust policy,
list who can now assume the role, including other accounts.

Read carefully: an attempt denied by policy (for example
`AttachUserPolicy` with `AccessDenied`) means escalation was tried and failed. Report it as contained for that path,
but keep looking for paths that succeeded.

## 4. Defense evasion and logging changes

Signals: `Stealth:IAMUser/CloudTrailLoggingDisabled`, `Stealth:IAMUser/PasswordPolicyChange`,
`DefenseEvasion:IAMUser/AnomalousBehavior`, and events such as `StopLogging`, `DeleteTrail`,
`UpdateTrail`, `PutEventSelectors`, `StopConfigurationRecorder`, `DeleteConfigurationRecorder`,
`DeleteDetector`, `UpdateDetector`, `DeleteFlowLogs`, `DeleteLogGroup`.

Collect: what was turned off, when, by whom, whether it was turned back on (`StartLogging`,
`StartConfigurationRecorder`, a new detector), and the gap it leaves. Everything in that gap is
Unknown for the sources that were off; say so in every later step. `StopLogging` stops delivery
for that trail only: Event history (and GuardDuty) still record management events, so query
them for the gap.

Read carefully: an administrator tuning cost settings can trigger these. Confirm against a
change record. A logging change made by a principal that is also in mode 1 or 3 is a strong
signal of compromise.

## 5. Exposure changes (network and resource policies)

Signals: a security group rule opened to `0.0.0.0/0` or `::/0` (`AuthorizeSecurityGroupIngress`),
network ACL changes, `PutBucketPolicy`, `PutBucketAcl`, `DeleteBucketPublicAccessBlock` or
`PutBucketPublicAccessBlock` with settings off (account level: `DeleteAccountPublicAccessBlock`,
`PutAccountPublicAccessBlock`), `Policy:S3/BucketBlockPublicAccessDisabled`,
`Policy:S3/BucketAnonymousAccessGranted`, `Policy:S3/BucketPublicAccessGranted`, an RDS instance
made publicly accessible, a snapshot or AMI shared with another account or made public, an AWS
Config rule for SSH exposure or S3 public access turning NON_COMPLIANT.

Collect:
- Who changed it, when, and the before and after state (the change event's request
  parameters, or AWS Config history).
- What the change exposes: the ENIs, instances, and load balancers that use the security
  group; the bucket and prefixes the policy opens; whether the resource is tagged as production.
- Whether it was used: accepted inbound flows on the opened port from outside your ranges since
  the change; object reads by anonymous or external principals since the change.

Read carefully: report exposure and use as separate findings. "Exposed with no observed use"
needs the logs to have been on for the whole period; otherwise use is Unknown.

## 6. Data access and exfiltration

Signals: `Exfiltration:S3/*`, `Exfiltration:IAMUser/AnomalousBehavior`, `Impact:IAMUser/AnomalousBehavior`, `Discovery:S3/*`, `UnauthorizedAccess:S3/*`, `Impact:S3/*`, a burst
of `GetObject` or `ListObjects`, a new replication rule (`PutBucketReplication`), a bucket
policy granting another account, unusual `GetSecretValue` calls.

Collect: object reads by principal and prefix (S3 data events), successful and denied counts,
distinct objects, bytes if available, and the destination of any replication rule. Check first
whether data events are recorded for the bucket and can be queried (evidence queries, section
5); if not, object-level access is Unknown.

Read carefully: a successful read outside the approved prefix proves that identity read those
objects. It does not by itself prove the credentials were stolen or that data left the
environment.

## 7. Compute compromise and destructive activity

Signals: `Backdoor:EC2/*`, `CryptoCurrency:EC2/*`, `Trojan:EC2/*`,
`UnauthorizedAccess:EC2/SSHBruteForce`, `UnauthorizedAccess:EC2/RDPBruteForce`, `Recon:EC2/*`,
`Impact:EC2/*`, GuardDuty Malware Protection findings, unexpected `RunInstances` in unused
Regions, and destructive events such as bulk `DeleteObject`, `PutBucketLifecycle` that expires
objects, `ScheduleKeyDeletion`, `DisableKey`, `PutKeyPolicy`, `DeleteSnapshot`, or objects
rewritten with an encryption key you do not control.

Collect:
- For an instance: who launched it, its role and recent role activity, security groups, and
  flow log destinations and ports.
- For SSH or RDP brute force, read `Service.ResourceRole`. `TARGET`: the instance was attacked;
  it is an attempt until an accepted connection followed by new outbound traffic shows a
  login. `ACTOR`: the instance is attacking others; treat it as compromised (P2 at least).
- For new instances in unusual Regions: who launched them and with which credentials (open
  mode 1).
- For destructive activity: what was deleted or re-encrypted, whether S3 Versioning, Object
  Lock, AWS Backup, or snapshots allow recovery, and the KMS key deletion date. If objects were
  rewritten with a key you do not control, cancelling a key deletion does not recover them:
  only earlier versions, Object Lock or backups do.

Read carefully: a KMS key scheduled for deletion can be cancelled until its waiting period
ends. Say the date in the report.
