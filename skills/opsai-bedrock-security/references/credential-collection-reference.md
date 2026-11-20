# Collection Reference

The read-only AWS API calls the audit makes, the parameters it passes, the fields it uses, how each
call pages, and which check each call feeds. Every call is an IAM call made in the audited account
with the AWS DevOps Agent role for that account: select the account through the AWS tool's account
parameter. That parameter, and the ARNs that an IAM call needs as parameters, are the only places a
full account ID may appear. In all text, prompts to sub-agents included, name every account as the
output rule of `SKILL.md` says, the accounts that policies name included. Never call
`sts:AssumeRole`.

**Paging.** Every IAM list call below, and `iam:GetAccountAuthorizationDetails`, pages with
`IsTruncated` and `Marker`. When a response has `IsTruncated` true, call again with `Marker` set to
the returned value until `IsTruncated` is false. IAM can return fewer items than `MaxItems` even
when more exist, so check `IsTruncated` on every page (`credential-api-quirks.md` section 17).

**Previews.** The AWS tool can replace any large result with a preview: a note that the result
exceeds its size threshold, the start of the result, and the options "Distill" and "Narrow search"
(`credential-api-quirks.md` section 20). For every IAM result the audit reads, from any call and made by any
agent:

- Never take the `Distill` option, and never ask any tool or sub-agent to summarise the result. A
  model-written summary can drop or change entries, and nothing in the audit may rest on one.
- Never evaluate a preview and never take any value from one: no user, key, date, policy, field or
  paging value. A preview only says that the result was too large. The one use of a preview is the
  name of its first key under the account key, which `policy-snapshot.md` section 3 step 1 reads
  for a snapshot call.
- The files of this skill are read whole as well. If a file of this skill comes back as a preview,
  never distill it and never work from the part shown: name the file to the requester and stop (a
  sub-agent names it in its reply and returns no results; `credential-audit.md`, guardrail 9).

Ask for a complete result instead:

| Call | Page size | On a preview | Still a preview at the smallest page |
|---|---|---|---|
| `iam:ListUsers`, with the result filter L1 | `MaxItems` 100 | Ask for the same page again (the same `Marker`, or none for the first page) with half the `MaxItems`, rounded down and never below 10, and keep the smaller value for the rest of that listing | The account is failed, with the reason `the AWS tool returned only a preview of iam:ListUsers` |
| Account-wide `iam:ListServiceSpecificCredentials` | `MaxItems` 50 | The same | The account-wide listing failed: its warning (section 2) with `the AWS tool returned only a preview` as the reason, then the per-user listing |
| `iam:GetAccountAuthorizationDetails` | `policy-snapshot.md` section 3 | Halve the names (`policy-snapshot.md` section 3 step 3) | `policy-snapshot.md` section 4 |
| `iam:GetCredentialReport` | - | Not asked for again: a result filter cannot shorten one CSV string | Unreadable (section 1.1) |
| Every other call | - | Not asked for again: its result is small and has no page size to reduce | The call failed, with `the AWS tool returned only a preview` in place of the error code; section 6 says what follows for that call |

The `MaxItems` steps are 100, 50, 25, 12, 10 for `iam:ListUsers`, and 50, 25, 12, 10 for the
account-wide API key listing. A preview at 10 is final. IAM may return fewer items than `MaxItems`
even when more exist, so `IsTruncated` still decides the next page.

**L1, users** (`iam:ListUsers`): the paging fields, then each user's name and ARN. Pass it as the
AWS tool's result filter (a JMESPath expression; `jmespath_filter` in `use_aws`).

```
{IsTruncated: IsTruncated, Marker: Marker, Users: Users[].{UserName: UserName, Arn: Arn}}
```

L1 only keeps the page small. An unfiltered `iam:ListUsers` response holds the same two fields, so
it is read the same way (`Users[].UserName`, `Users[].Arn`). If the AWS tool rejects L1 (an error
that is not an IAM error and names the result filter, `jmespath_filter` or JMESPath, or says that
the input is too long, as in `policy-snapshot.md` section 3 step 3), make the same call without the
filter, read it the same way, and make the rest of that listing without the filter too.
`iam:ListUsers` is the one call that may be repeated without its filter, because its response holds
no policy text; a snapshot call never is (`policy-snapshot.md` section 3).

## 1. Account-level calls

| API | Parameters | Fields used | Feeds |
|---|---|---|---|
| `iam:ListAccountAliases` | none | `AccountAliases[0]`, the name used for the account in every line of the report | Naming only |
| `iam:GetAccountSummary` | none | `SummaryMap.AccountAccessKeysPresent`: 1 when the root user has at least one access key, active or not, 0 when it has none. `SummaryMap.Users`: the number of IAM users, for the work budget | LLM-BPA-001, LLM-BPA-014; work budget |
| `iam:GetCredentialReport` | none. Optional: only when `AccountAccessKeysPresent` is 1 (section 1.1) | `Content`, read only when the AWS tool returns it as CSV text, and `GeneratedTime`. Errors: `ReportNotPresent`, `ReportExpired`, `ReportInProgress` | LLM-BPA-001, LLM-BPA-014; the REPORT GENERATED column |
| `iam:ListServiceSpecificCredentials`, account-wide | `ServiceName` = `bedrock.amazonaws.com`, `AllUsers` = true (do not combine with `UserName`), `MaxItems` 50, and `Marker` on later pages | `ServiceSpecificCredentials[]`: `UserName`, `ServiceSpecificCredentialId`, `Status`, `CreateDate`, `ExpirationDate`, `ServiceName`. Never print `ServiceCredentialAlias` or `ServiceUserName` | Every API key row (LLM-BPA-009 to LLM-BPA-014 apply to API keys specifically); partial status |

The audit reads only a credential report that already exists, and never generates one.

### 1.1 The root account's access keys

Read the root principal like this:

1. `AccountAccessKeysPresent` is 0: the root user has no access key, and there is no root row. Do
   not read the credential report.
2. `AccountAccessKeysPresent` is 1: call `iam:GetCredentialReport`, retrying only on
   `ReportInProgress` as below. Never generate a report.
   * `Content` is readable CSV text: it starts with the header `user,arn,user_creation_time`. Read
     only the row whose `user` is `<root_account>` (normally the first row after the header), with
     these columns: `arn`, `mfa_active`, and for each slot `N` of 1 and 2 `access_key_N_active`,
     `access_key_N_last_rotated`, `access_key_N_last_used_date`, `access_key_N_last_used_region`.
     A slot holds a key when `access_key_N_active` is `TRUE` or `access_key_N_last_rotated` holds a
     date. Make one row per such slot: KEY `root-access-key-N`, active when `access_key_N_active`
     is `TRUE`, age from `access_key_N_last_rotated`, last use from
     `access_key_N_last_used_date` (`N/A` means never used).
   * `Content` is anything else (Base64 text, a byte string, empty): the report is unreadable,
     with the reason `its content was not returned as readable text`. Never decode it by hand.
   * The response is a preview (Previews, above): the report is unreadable, with the reason
     `the AWS tool returned only a preview of it`. Never distill it, never read the root row out of
     the preview, and do not repeat the call.
   * `ReportNotPresent`: unreadable, reason `no credential report exists`. `ReportExpired`:
     unreadable, reason `the latest credential report has expired`. `ReportInProgress`: wait
     briefly and retry, at most five times; then unreadable, reason
     `a credential report is still being generated`. A refusal by the AWS tool: unreadable, reason
     `the AWS tool refused the call`. Any other error, `AccessDenied` included: unreadable, with the
     error code as the reason. The account is not failed.
3. The report is unreadable, or it was read and no slot holds a key (the key may be newer than the
   report): one row, KEY `root-access-key`, AGE `-`, LAST USED `unknown`, MFA `unknown` (or
   `mfa_active` when the report was read), rated under the "does not confirm" case of rule 1 in
   `checks-credentials.md` (Critical, LLM-BPA-001), REPORT GENERATED `could not be read` (or the time,
   when it was read). Add the account warning R1 (`evaluation-outcomes.md` section 3), which tells
   the requester to run `aws iam generate-credential-report` in that account and ask again.
4. When the report was read, record `GeneratedTime` for the account's REPORT GENERATED cell. When
   it is more than one hour before the audit time, add the warning
   `The IAM credential report was generated at <YYYY-MM-DD HH:MM> UTC; a root access key created since then is not visible.`

Never take IAM user data (keys, last use, MFA) from the credential report. It can be up to four hours
old, and it omits users created since and every long-term API key. See `credential-api-quirks.md` section 1.

## 2. User-level calls

| API | Parameters | Fields used | Feeds |
|---|---|---|---|
| `iam:ListUsers` | `MaxItems` 100, and `Marker` on later pages, with the result filter L1 (Previews, above) | `IsTruncated`, `Marker`, `Users[].UserName`, `Users[].Arn` | The inventory |
| `iam:GetUser` | `UserName`. Only for users the requester names | `User.UserName`, `User.Arn` | Confirms a named user exists, and gives the name as IAM writes it |
| `iam:ListAccessKeys` | `UserName` | `AccessKeyMetadata[]`: `AccessKeyId`, `Status` (`Active` or `Inactive`), `CreateDate` | Every access key check |
| `iam:GetAccessKeyLastUsed` | `AccessKeyId` | `AccessKeyLastUsed.LastUsedDate` (absent when never used), `AccessKeyLastUsed.ServiceName` and `Region` (`N/A` when none), `UserName` (the key's owner) | LLM-BPA-006, the LAST USED column and the order; finds the owner of a key the requester names |
| `iam:ListServiceSpecificCredentials`, per user | `UserName`, no `ServiceName`. For each API key user (`BedrockAPIKey-*`, `AeaApiKey-*`), unless the account is partial | As in section 1. `ServiceName` `bedrock.amazonaws.com` is an Amazon Bedrock API key; any other credential on an `AeaApiKey-` user is a Claude Platform API key; anything else is ignored | LLM-BPA-009, LLM-BPA-011, LLM-BPA-013, LLM-BPA-014 |
| `iam:ListMFADevices` | `UserName` | `MFADevices[]`: any entry means MFA `yes` | LLM-BPA-008; the MFA column |
| `iam:GetContextKeysForPrincipalPolicy` | `PolicySourceArn` = the user's ARN. For each evaluated user that is not already `unknown`, after the policy snapshot | `ContextKeyNames[]` | The cross-check in `policy-evaluation.md` section 3 |

**Who is a principal.** An IAM user with at least one access key, at least one API key, or an API key
user name. Console-only users hold no long-lived credential and are skipped. A user deleted during the
scan (`NoSuchEntity`) is skipped with the warning
`User <name> was deleted during the scan and was skipped.`

**Merging API keys.** Combine the account-wide listing and the per-user listings, keeping each
`ServiceSpecificCredentialId` once.

**Partial account.** When the account-wide `iam:ListServiceSpecificCredentials` returns
`AccessDenied` (or `AccessDeniedException` or `UnauthorizedOperation`), the account is partial, not
failed: skip the per-user listing too (it needs the same
permission), audit everything else, and record the reason
`Amazon Bedrock API keys not evaluated: iam:ListServiceSpecificCredentials was denied`. Every API key
user without an active access key then shows as orphaned, because its API keys cannot be seen. If the
account-wide listing fails with any other error, or is still a preview at `MaxItems` 10, add the
warning
`Account-wide Amazon Bedrock API key listing failed (<error code>); only BedrockAPIKey-* users were checked.`
(for a preview, `the AWS tool returned only a preview` in place of `<error code>`) and continue with
the per-user listing.

## 3. The policy snapshot

The audit evaluates each user's identity-based policies itself (`policy-evaluation.md`). It reads
them with `iam:GetAccountAuthorizationDetails`, always with a result filter, and reads customer
managed documents with `iam:GetPolicy` and `iam:GetPolicyVersion`. The calls, their result filters,
the checks on each response, the fallbacks and the rules for sub-agents are in
`policy-snapshot.md`: read it before any of these calls.

## 4. Order and cost per account

1. `iam:ListAccountAliases`, `iam:GetAccountSummary`; the credential report only when a root key is
   present.
2. The account-wide `iam:ListServiceSpecificCredentials`.
3. `iam:ListUsers`; `iam:ListAccessKeys` for each inventoried user; `iam:ListServiceSpecificCredentials`
   for each API key user.
4. For each evaluated user: `iam:GetAccessKeyLastUsed` per access key and `iam:ListMFADevices`.
5. The policy snapshot for the evaluated users (`policy-snapshot.md`): the user snapshot, the group
   snapshot, `iam:GetPolicy` and `iam:GetPolicyVersion` for each customer managed policy, and the
   AWS managed snapshot. Then `iam:GetContextKeysForPrincipalPolicy` for each evaluated user.

As estimates: one `iam:ListUsers` call per 100 users and one account-wide API key call per 50 API
keys, plus one call for each page asked for again after a preview; per evaluated user, one call per
access key plus two; per account, the snapshot pages (users divided by 100, groups divided by 100,
attached AWS managed policies divided by 50, each stopping early), times the number of 20-name
groups when a filter needs more than 20 names, two more calls for each preview that has to be split
and one more for each rejected request that is retried with its first name, and two calls per
distinct customer managed policy. After S1 or S2 is rejected for one name, the short form costs one
request per pending name on each page of that snapshot instead. IAM API calls have no charge.

### 4.1 Work budget

These bounds keep one run tractable. They are a work budget, not AWS thresholds or risk limits, and
the requester can raise or lower them (`credential-audit.md`, Work budget).

| Bound | Default | Notes |
|---|---|---|
| Users inventoried per account (`iam:ListAccessKeys` calls) | 100 | Take users in `iam:ListUsers` order. `SummaryMap.Users` from `iam:GetAccountSummary` tells you the size first. API key users, and users found by the account-wide API key listing, are inventoried even beyond the bound |
| Principals evaluated per account (`credential-audit.md` steps 7 to 9) | 20 | The root account is not evaluated and does not count |

The bounds apply to each account in scope, one after another; the number of accounts has no bound.

When an account has more candidates than the bound, evaluate them in this order, ties by user name:

1. Users the requester named.
2. API key users, and users that hold an Amazon Bedrock or Claude Platform API key.
3. Users with an active access key, oldest `CreateDate` first.
4. Users whose keys are all inactive or expired, oldest first.

This order is a budget heuristic, not a verdict. List every candidate you did not evaluate in the
report's "Not evaluated (work budget)" table, with its masked key IDs, and the count of users not
inventoried.

## 5. Permissions

The calls above need exactly these IAM actions, which the read-only IAM policy in the skill's README grants:
`iam:ListAccountAliases`, `iam:GetAccountSummary`, `iam:GetCredentialReport`,
`iam:ListServiceSpecificCredentials`, `iam:ListUsers`, `iam:GetUser`, `iam:ListAccessKeys`,
`iam:GetAccessKeyLastUsed`, `iam:ListMFADevices`, `iam:GetAccountAuthorizationDetails`,
`iam:GetPolicy`, `iam:GetPolicyVersion` and `iam:GetContextKeysForPrincipalPolicy`.

Calls the skill never makes:

- `sts:AssumeRole`, and any AWS Organizations call;
- any Amazon Bedrock API, including model invocation;
- `iam:SimulatePrincipalPolicy`, `iam:SimulateCustomPolicy` and every IAM `Generate*` call,
  `iam:GenerateCredentialReport` included: AWS DevOps Agent's AWS tool does not run them
  (`credential-api-quirks.md` section 18), and the skill never needs them;
- any IAM call that takes an AWS managed policy's ARN (`credential-api-quirks.md` section 19);
- IAM Access Analyzer;
- any IAM call that creates, updates, attaches, detaches, tags or deletes anything.

## 6. When a call fails

Back off and retry throttled calls first. Then, for an error that persists. "A preview" in this
table means a preview that the Previews paragraph and `policy-snapshot.md` section 3 cannot narrow
any further; no preview is ever distilled.

| Call | Error | What to do |
|---|---|---|
| `iam:ListAccountAliases` | Any, a preview, or no alias | Name the account `account ending NNNN` |
| `iam:GetCredentialReport` | Any error, a refusal, content that is not CSV text, or a preview | Unreadable (section 1.1), never distilled, and not asked for again except for the `ReportInProgress` retries; the account is not failed |
| Account-wide `iam:ListServiceSpecificCredentials` | `AccessDenied`, `AccessDeniedException`, `UnauthorizedOperation` | The account is partial (section 2) |
| Account-wide `iam:ListServiceSpecificCredentials` | Any other, or a preview at `MaxItems` 10 | Warning, then continue with the per-user listing (section 2); for a preview the warning gives `the AWS tool returned only a preview` as the reason |
| `iam:ListUsers` | A preview at `MaxItems` 10 | The account is failed, with the reason `the AWS tool returned only a preview of iam:ListUsers` (Previews) |
| `iam:ListUsers` | The AWS tool rejects the result filter L1 (a rejected filter, as `policy-snapshot.md` section 3 step 3 defines it) | Make the same call without the filter, read it the same way, and make the rest of that listing without the filter (Previews); a preview is then narrowed by halving `MaxItems` as before, and any other error is the last row's |
| `iam:GetAccountAuthorizationDetails`, `iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:GetContextKeysForPrincipalPolicy` | `AccessDenied`, `AccessDeniedException`, `UnauthorizedOperation`, `AuthFailure`, `ExpiredToken`, `ExpiredTokenException` | The account is failed; name the API and the error, and say that adding the read-only IAM policy in the skill's README grants the read |
| The same calls | Refused by the AWS tool (for example `Denied operation`, `blocked by policy`, `not in target accounts`) | Never retry: it is not an IAM permission error. Then, by call, as in the rows below for "any other" |
| `iam:GetAccountAuthorizationDetails` | A preview, the filter not applied, the filter rejected, or a response cut off | `policy-snapshot.md` section 3 (a rejected request with several names is sent again with its first name only; a one-name rejection of S1 or S2 follows the next two rows, and one of S4 the S4 row below), then `policy-snapshot.md` section 4 |
| `iam:GetAccountAuthorizationDetails` with S1 or S2 | The filter rejected for one name | The short form, S1s or S2s, for that name and every name still pending for that template in the account, one name per request (`policy-snapshot.md` section 3 step 3) |
| `iam:GetAccountAuthorizationDetails` with S1s or S2s | The filter rejected, or the response still a preview | That user: U5; that group's evaluated users: U4 (`policy-snapshot.md` section 4), with the reason of `evaluation-outcomes.md` section 3; the other names keep the short form |
| `iam:GetPolicy`, `iam:GetPolicyVersion` | `NoSuchEntity` | Evaluate without the policy, W4 |
| `iam:GetContextKeysForPrincipalPolicy` | `NoSuchEntity` | The user was deleted: skip it with W5 |
| `iam:GetAccountAuthorizationDetails` with `Filter` `["User"]` (S1 or S1s) | Any other, `Throttling` that outlasts the retries included, a refusal, or a response in an unexpected form (`policy-snapshot.md` section 3 steps 1 and 2) | Every evaluated user that the snapshot has not yet returned: U5 (`policy-snapshot.md` section 4). An error from the AWS tool on S1 that is not an IAM error, not a refusal and not throttling is first treated once as a rejected filter (`policy-snapshot.md` section 3 step 3); this row applies when the short form fails with the same error |
| `iam:GetAccountAuthorizationDetails` with `Filter` `["Group"]` (S2 or S2s) | The same | Every evaluated user in a group that the snapshot has not yet returned: U4 naming the group (`policy-snapshot.md` section 4). An error from the AWS tool on S2 that is not an IAM error, not a refusal and not throttling is first treated once as a rejected filter (`policy-snapshot.md` section 3 step 3); this row applies when the short form fails with the same error |
| `iam:GetAccountAuthorizationDetails` with `Filter` `["AWSManagedPolicy"]` (S4) | The same, or the filter rejected for one name (S4 has no short form) | `policy-snapshot.md` section 4: the catalog with W3 for the four catalogued policies, otherwise U3 for the users who hold the policy |
| `iam:GetPolicy`, `iam:GetPolicyVersion` | The same, or a preview | The users who hold the policy: U4 |
| `iam:GetContextKeysForPrincipalPolicy` | The same, or a preview | That user: U7 |
| Every other call in sections 1 and 2 | `NoSuchEntity` for a user | Skip the user with the warning in section 2 (for a user the requester named, say the user was not found) |
| Every other call in sections 1 and 2 | Any other, or a preview | The account is failed; for a preview, the reason `the AWS tool returned only a preview of <API>` |

For a failed account, report the API and the error code in "Accounts that could not be audited", and
when the error is a permission error, say that adding the read-only IAM policy in the skill's
README to the account's AWS DevOps Agent role grants the missing read. A failed account because of a preview is
written without permission advice, for example `<alias>: the AWS tool returned only a preview of iam:ListUsers.`
Any other call of sections 1 and 2 that has no row of its own above and comes back as a preview
fails the account the same way, with its own API name in place of `iam:ListUsers`. Continue with the
next account. Never record a failed call as "cannot invoke".
