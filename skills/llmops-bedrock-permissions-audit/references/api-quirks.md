# API Quirks

Some read-only IAM responses look as if they say one thing and mean another. A misread one either
invents a finding or hides a real one. Every entry below names the trap, explains why it misleads, and
gives the reading to use.

---

## 1. Credential report: read only as CSV text, up to four hours old

- **Trap:** Reading the report when the AWS tool did not return its content as CSV text, trusting
  it for current state, or taking IAM user data from it.
- **Why it misleads:** `GetCredentialReport` returns `Content` as a Base64-encoded CSV, which can
  be large in an account with many users; the AWS tool may pass it on in that form, or show only
  a preview of it. IAM reuses a report generated within the last four hours, so it can miss a
  root key created since. It has two access key slots per user and no long-term API keys. The IAM
  User Guide also says `access_key_N_last_rotated` is `N/A` when the user has no active access
  key, so an inactive root key may show no date.
- **Correct reading:**
  * Use `GetAccountSummary` first. `SummaryMap.AccountAccessKeysPresent` is plain JSON, and it is
    1 whenever the root user has an access key, even an inactive one
    ([AWS Security Blog](https://aws.amazon.com/blogs/security/an-easier-way-to-determine-the-presence-of-aws-account-access-keys/)).
    0 means no root key: do not read the report at all.
  * Never generate a report. The skill reads only a report that already exists (section 18).
  * Read the report only for the `<root_account>` row, and only when the AWS tool returns
    `Content` as CSV text that starts with `user,arn,user_creation_time`. Never decode Base64 or
    any other encoding by hand: the report is then unreadable (`collection-reference.md`
    section 1.1). Never guess a value.
  * A preview of the report is unreadable too. Never distill it, never read the root row out of
    it, and do not ask for it again: a result filter cannot shorten one CSV string.
  * A slot holds a key when `access_key_N_active` is `TRUE` or the slot has a rotation date, and
    the slot's state comes from `access_key_N_active`. A report that shows no root key while
    `AccountAccessKeysPresent` is 1 does not tell you the key's state: the key may be newer than
    the report, or inactive without a date.
  * Always state the report's `GeneratedTime` when you read it, and warn when it is more than one
    hour before the audit time. If the report could not be read, or shows no root key although
    `AccountAccessKeysPresent` is 1, say so: the present root key is then reported Critical with
    a reason that says its state was not confirmed (`checks-credentials.md`, rule 1), and the
    requester can run `aws iam generate-credential-report` in that account and ask again.
  * Take user keys, last use and MFA only from the live calls (`ListAccessKeys`,
    `GetAccessKeyLastUsed`, `ListMFADevices`), never from the report.

## 2. Allowed, implicit deny and explicit deny

- **Trap:** Reading every result that is not "allowed" as a definite "cannot".
- **Why it misleads:** An explicit deny means a statement denies the action: a definite no. An
  implicit deny only means that no statement the audit read allows it. When the user's own policies
  name Amazon Bedrock resources and none of them is allowed, with no explicit deny, a condition may
  be what keeps them from being allowed.
- **Correct reading:** Can invoke needs at least one allowed invoke action. When a user's own
  policies name Amazon Bedrock resources, no probe is allowed, and no probe built from them is
  explicitly denied, GRANT is `unknown` (U8, LLM-BPA-015), not `none`
  (`policy-evaluation.md` section 7.2).

## 3. `Resource: "*"` is not a pattern on every model

- **Trap:** Treating `arn:aws:bedrock:*::foundation-model/*` as the same as `*`, or reading a Deny
  on Amazon Bedrock ARNs as removing an Allow on `*`.
- **Why it misleads:** The audit's first check tests the resource `*` as a string,
  and only the entry `*` matches it. A pattern on every model in every
  Region is decided by the probe step instead, where most such patterns reach `broad` through the
  0.8 share. A Deny whose `Resource` names Amazon Bedrock ARNs, such as `arn:aws:bedrock:*:*:*`,
  does not match `*` either, so it does not remove a grant found on `*`, although it does block
  real requests on those resources.
- **Correct reading:** Decide `*` and the probes as `policy-evaluation.md` sections 4 and 7 say.
  With an Allow on `*` and a Deny on Amazon Bedrock ARNs, the audit tests `*` as
  written: GRANT stays `broad`, the row can overstate access, and W6 says so
  (`policy-evaluation.md` section 7.3).

## 4. Conditions: only documented keys are evaluated

- **Trap:** Guessing what a condition does, or treating every conditioned statement as applying.
- **Why it misleads:** The audit has no request context: no source IP, VPC endpoint, time, tags or
  calling service. It evaluates only the eight condition keys whose value AWS documents for a
  request signed with a long-lived credential, for example the MFA keys and `aws:TokenIssueTime`,
  which such requests never carry.
- **Correct reading:** Evaluate a test only when its key is in the condition-key table of
  `policy-evaluation.md` section 5, with AWS's operator rules for absent keys, `...IfExists` and
  `Null`. A false test means the statement does not apply, whatever its other tests. Work the two
  readings of `policy-evaluation.md` section 6: when they give different answers, GRANT is
  `unknown` (U2), and an escalation or canary action allowed only in the most-access reading is not
  counted (W1). For example, the "revoke older sessions" Deny with `DateLessThan` on
  `aws:TokenIssueTime` does not apply to a long-lived key, and a Deny with `BoolIfExists` on
  `aws:MultiFactorAuthPresent` `false` applies to every request such a key makes.

## 5. A permissions boundary makes GRANT unknown

- **Trap:** Concluding from an attached policy alone that a user with a permissions boundary can
  invoke, or that it cannot.
- **Why it misleads:** A permissions boundary caps what the identity policies allow, and the audit
  does not evaluate boundaries.
- **Correct reading:** A user whose snapshot entry shows a `PermissionsBoundary` gets GRANT
  `unknown` with U1 (`policy-evaluation.md` section 3), shown for review. Admin-class policies are
  matched by attachment, but rules 5 and 6 also need can invoke, so such a user is never Critical.

## 6. NotAction and NotResource match what they do not list

- **Trap:** Reading `NotAction` or `NotResource` as a Deny, or as covering only what they list.
- **Why it misleads:** An Allow with `NotAction` allows every action that its list does not match,
  on its `Resource`: `PowerUserAccess` allows every Amazon Bedrock action that way. A statement with
  `NotResource` applies to every resource that its list does not match. Neither element denies
  anything by itself.
- **Correct reading:** A statement with a `NotAction` list covers action A when none of its entries
  matches A. A statement with a `NotResource` list applies to resource R when none of its entries
  matches R (`policy-evaluation.md` section 4). In a filtered snapshot entry, a `null` `Action`
  beside a `NotAction` list is a NotAction statement.

## 7. A failed call is not a "no"

- **Trap:** Reporting a user as unable to invoke because a call failed or a policy could not be read.
- **Correct reading:** A permission or credential error fails the account. Any other persistent
  error, a refusal by the AWS tool, or a policy that could not be read makes the affected users'
  GRANT `unknown` (LLM-BPA-015), shown in the report for review with its reason (`evaluation-outcomes.md`
  section 3), except where the skill's own description of an AWS managed policy is used instead.
  Never write "cannot invoke" for a call that did not return an answer.

## 8. Service control policies and resource control policies

- **Trap:** Reading "can invoke" as "will work", or "cannot invoke" as proof that an organization
  control applies.
- **Why it misleads:** The audit reads identity-based policies only: never your SCPs or RCPs.
- **Correct reading:** Report every result as identity-policy reach. Always print the SCP and RCP
  limitation. Never claim an SCP-aware or RCP-aware verdict.

## 9. Policy documents are URL-encoded

- **Trap:** Searching a `GetAccountAuthorizationDetails` or `GetPolicyVersion` document as
  returned.
- **Why it misleads:** IAM returns these documents URL-encoded (RFC 3986), so `:` and `/` in
  resource ARNs appear as `%3A` and `%2F`. Some tools return the document already URL-decoded as a
  JSON object; others do not.
- **Correct reading:** When a document arrives as a string, URL-decode it and parse it as JSON
  before you evaluate it. Never quote the document in the report; name the policy only.

## 10. GetAccessKeyLastUsed: never used, and not Amazon Bedrock use

- **Trap:** Reading a missing date as an error, `N/A` as a value, or the last use as Amazon Bedrock
  use.
- **Why it misleads:** `LastUsedDate` is absent when the key was never used since IAM began tracking
  on April 22, 2015, and `ServiceName` and `Region` are then `N/A`. When a date is present, it is the
  key's most recent call to **any** AWS service.
- **Correct reading:** No `LastUsedDate` means never used, which is dormant (LLM-BPA-006). A recent date
  shows the key is in use, not that it called Amazon Bedrock; say so if the requester asks about
  Amazon Bedrock use, and point to GuardDuty AI Protection or AWS CloudTrail for that.

## 11. API key last use is unknown

- **Trap:** Calling an API key never used, or dormant.
- **Why it misleads:** IAM does not report when a long-term API key was last used. No API returns it.
- **Correct reading:** LAST USED is `unknown` for every API key. An API key is never dormant and never
  "never used". An old API key can still be High (LLM-BPA-007), and a recent one is described as recent,
  not in use.

## 12. ListServiceSpecificCredentials denied: partial, not failed

- **Trap:** Failing the whole account, or reporting it complete without its API keys.
- **Correct reading:** The account is partial, with the reason
  `Amazon Bedrock API keys not evaluated: iam:ListServiceSpecificCredentials was denied`. Audit
  everything else. Every API key user (`BedrockAPIKey-*`, `AeaApiKey-*`) without an active access key
  then shows as orphaned (LLM-BPA-011), because its API keys cannot be seen. Say this next to those rows.
  The call takes `AllUsers` or `UserName`, never both, and you follow `Marker` by hand.

## 13. Expired API keys stay Info

- **Trap:** Rating an expired API key as if it could be re-enabled.
- **Why it misleads:** `Status` can be `Active`, `Inactive` or `Expired`. An inactive key can be set
  active again with `iam:UpdateServiceSpecificCredential`; an expired one cannot be re-enabled.
- **Correct reading:** An API key whose `ExpirationDate` has passed is expired: Info (LLM-BPA-014), never
  re-rated. An inactive key that has not expired is re-rated as if active and is LLM-BPA-013 when that
  gives Critical or High.

## 14. Inactive access keys still exist

- **Trap:** Treating an inactive access key as removed.
- **Why it misleads:** `ListAccessKeys` returns inactive keys too. Deactivation does not invalidate
  the key, and `iam:UpdateAccessKey` sets it active again with the same permissions.
- **Correct reading:** Re-rate an inactive access key as if active (rule 3). Who can call
  `iam:UpdateAccessKey` is not evaluated; say so.

## 15. Fields never to print

- `ServiceCredentialAlias` and `ServiceUserName` of an API key: the alias is the public part of the
  key. Use the masked `ServiceSpecificCredentialId` instead.
- Full `AccessKeyId` or `ServiceSpecificCredentialId` values: mask to `...` plus the last four
  characters.
- The account segment of any ARN, including user, policy and inference-profile ARNs: write
  `<account>` in its place for the audited account, and `<account ending NNNN>` for any other
  account, such as the account of a role ARN that a policy names.
- An account ID outside an ARN: name an audited account by alias or `account ending NNNN`, and any
  other account as `account ending NNNN`.

## 16. MFA comes from ListMFADevices

- **Trap:** Taking a user's MFA state from the credential report.
- **Why it misleads:** The report can be up to four hours old and omits users created since, so a new
  user would look like it has no MFA.
- **Correct reading:** A user has MFA when `ListMFADevices` returns at least one device. Only the
  root account's MFA column comes from the report, and it is `unknown` when the report could not be
  read.

## 17. Paging: a short page is not the last page

- **Trap:** Stopping after the first page of a list call or of
  `iam:GetAccountAuthorizationDetails`, or taking a page with fewer items than `MaxItems` as the
  last one.
- **Why it misleads:** IAM can return fewer items than `MaxItems` while more exist. It then sets
  `IsTruncated` to true and returns a `Marker`. The audit calls `iam:ListUsers` with `MaxItems`
  100, and `iam:GetAccountAuthorizationDetails` pages its snapshot the same way. A missed page
  drops users, keys or policies without any error: the inventory shrinks, or a policy goes unread.
- **Correct reading:** Check `IsTruncated` after every call. While it is true, call again with
  `Marker` set to the returned value. `collection-reference.md` gives the paging parameters of each
  call. A page that comes back as a preview is asked for again in a smaller form (section 20).

## 18. AWS DevOps Agent's AWS tool does not run the policy simulator or credential report generation

- **Trap:** Calling `iam:SimulatePrincipalPolicy`, `iam:SimulateCustomPolicy` or
  `iam:GenerateCredentialReport`, retrying them, or reading their refusal as an IAM permission
  error.
- **Why it misleads:** AWS DevOps Agent's AWS tool does not run these operations or the other IAM
  `Generate*` operations. It answers with a message such as
  `Denied operation: iam simulate_principal_policy cannot be performed` or
  `This operation is blocked by policy and was not executed`, and the request never reaches IAM. No
  role permission changes that.
- **Correct reading:** Never call them, never retry a refused call, and never count a refusal as an
  IAM permission error or as a reason to fail the account. The audit evaluates the policies itself
  (`policy-evaluation.md`) and reads only an existing credential report (section 1).

## 19. IAM calls that name an AWS managed policy are rejected

- **Trap:** Passing an AWS managed policy's ARN, for example to `iam:GetPolicy` or
  `iam:GetPolicyVersion`, to read its document.
- **Why it misleads:** The AWS tool checks that every ARN in a request belongs to a connected
  account. An AWS managed policy's ARN has `aws` as its account segment, so the tool rejects the
  request with `ARN account aws not in target accounts` before it reaches IAM.
- **Correct reading:** Never pass an AWS managed policy's ARN to an IAM call. Read AWS managed
  documents only from the filtered `AWSManagedPolicy` snapshot (`policy-snapshot.md`), and use the
  skill's own description of the four catalogued policies when the snapshot cannot be read
  (`evaluation-outcomes.md` section 2).

## 20. The policy snapshot can be very large, and any large result comes back as a preview

- **Trap:** Calling `iam:GetAccountAuthorizationDetails` without a result filter, distilling a
  large result, or reading values out of a preview.
- **Why it misleads:** The `AWSManagedPolicy` snapshot returns every AWS managed policy attached
  anywhere in the account, roles included: well over a hundred in an account with many roles, some
  as large as `ReadOnlyAccess`. The AWS tool replaces a result above its size limit, filtered or not
  and from any call, with a note that the result exceeds the threshold, a preview of its start and
  the options "Distill" and "Narrow search". A filtered snapshot page for many users with large
  inline policies, or an `iam:ListUsers` page of a hundred users, can pass that limit. A distilled
  summary can drop or change entries without any sign.
- **Correct reading:**
  * Always filter every snapshot call (`policy-snapshot.md` section 2), and never repeat a
    snapshot call without its filter. Check the first key of every snapshot response or preview,
    whatever order the keys come in: `IsTruncated`, `Marker` or the template's own key means the
    filter was applied (`policy-snapshot.md` section 3).
  * The AWS tool may reject a long filter. A rejected request is sent again with its first name
    only. When the user or group filter is rejected even for one name, the entry is asked for with
    a short form that only selects it by name (`policy-snapshot.md` section 3). The AWS
    managed filter has no short form, so a rejected one leads to the fallback
    (`policy-snapshot.md` section 4).
  * A `null` key in a filtered entry is absent (`policy-snapshot.md` section 2).
  * Never distill or otherwise summarise any IAM result, and never evaluate a preview or take any
    value from it; only the first key of a snapshot preview is read, to choose how to narrow it.
  * Narrow instead. For the snapshot, repeat the request with half of the names, down to one. For
    `iam:ListUsers` and the account-wide `iam:ListServiceSpecificCredentials`, ask for the same page
    with half the `MaxItems`, down to 10. The credential report and the other calls cannot be
    narrowed, so the report is then unreadable and any other call counts as failed
    (`collection-reference.md`, Previews). What is still too large after narrowing follows the
    fallback (`policy-snapshot.md` section 4).

## Sources

- [Getting credential reports](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_getting-report.html) (sections 1 and 16)
- [GetCredentialReport](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetCredentialReport.html) (section 1)
- [GetAccountSummary](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetAccountSummary.html) (section 1)
- [ListServiceSpecificCredentials](https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListServiceSpecificCredentials.html) (sections 12 and 13)
- [ListUsers](https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListUsers.html) (sections 17 and 20)
- [GetAccountAuthorizationDetails](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetAccountAuthorizationDetails.html) (sections 9, 17, 19 and 20)
- [Policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) (sections 2 and 7)
- [IAM JSON policy elements: Resource](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_resource.html) (section 3)
- [Global condition context keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html) and [Condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html) (section 4)
- [Permissions boundaries for IAM entities](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html) (section 5)
- [NotAction](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notaction.html) and [NotResource](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notresource.html) (section 6)
- [GetPolicyVersion](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetPolicyVersion.html) (section 9)
- [AccessKeyLastUsed](https://docs.aws.amazon.com/IAM/latest/APIReference/API_AccessKeyLastUsed.html) (section 10)
- [ServiceSpecificCredentialMetadata](https://docs.aws.amazon.com/IAM/latest/APIReference/API_ServiceSpecificCredentialMetadata.html) (sections 13 and 15)
- [UpdateAccessKey](https://docs.aws.amazon.com/IAM/latest/APIReference/API_UpdateAccessKey.html) (section 14)
