# Amazon Bedrock Permissions Audit

This report is the recommended format when the requester asks for a full audit, an inventory of
credentials or API keys, or everything. For a narrower question, answer it directly instead
(`SKILL.md`, answer rule). Either way, the answer keeps every must-keep item of the answer rule:
the credentials, what each can do (GRANT and tier), the action as steps with its AWS documentation
link, the scope limits that change the conclusion, that the audit changed nothing, and the masking.
When you use this template, keep its sections in this order, fill in every `<placeholder>` and never
deliver one unresolved. Never print any AWS account ID in full, whether an audited account's,
another connected account's or one that a policy names: name an audited account by alias or
`account ending NNNN`, and any other as `account ending NNNN`. Never print a full access key ID or
API key ID, or the text of a policy document.

## Scope

- **Audit time (UTC):** `<YYYY-MM-DD HH:MM>` (every age below is counted to this time)
- **Accounts:** `<alias or "account ending NNNN">`, one per account
- **Scope:** `<all accounts connected to this Agent Space | the accounts named | the users or keys named>`
- **Dormant and old threshold:** `<90>` days `<(default) | (requested)>`
- **Work budget:** `<100>` users inventoried and `<20>` principals evaluated per account
- **Read-only:** no credential, policy or setting was changed

## Findings

`<If no row is visible, write "No findings to report." and skip the table.>`

| # | TIER | ACCOUNT | PRINCIPAL | CREDENTIAL | KEY | AGE | LAST USED | MFA | GRANT | CHECKS |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `<Critical>` | `<alias>` | `<user name or <root_account>>` | `<access key>` | `<...ABCD>` | `<700d>` | `<400d ago>` | `<no>` | `<broad>` | `<LLM-BPA-002, LLM-BPA-003>` |

Rows are in the order of `references/checks-credentials.md` section 5. Info rows are left out unless
the requester asked for all findings, except rows with GRANT `unknown` and rows for the credentials
the question asks about (an inventory of API keys shows every API key).

### Actions and reasons

One block per row, in the same order and with the same number:

**1.** -> `<the one recommended action, word for word from the catalog>`
- docs: `<the AWS documentation link for this action: the AWS-doc-citation of the row's first check-id, references/checks-credentials.md section 3>`
- why: `<first reason, word for word>`
- why: `<next reason>`
- why: `<If re-enabled it would rate Critical:>`
  - `<each reason of the would-be tier, indented under that line>`
- evidence: `<CreateDate 2024-11-30T10:02:11Z; LastUsedDate 2025-09-25T08:12:40Z, last call to service s3 in eu-west-1 (any AWS service, not only Amazon Bedrock)>`
- evidence: `<granting policies: name (kind), ...; conditions: <key> in <policy>: <documented value>, so that <Allow|Deny> <applies|does not apply>, or conditions: none>`

For an API key, give `CreateDate`, `Status` and `ExpirationDate` (or "no expiration date"). For a root
key, give the credential report's `GeneratedTime`, `access_key_N_last_rotated` and
`access_key_N_last_used_date`; or say that the report could not be read, why, and that the requester
can run `aws iam generate-credential-report` in that account and ask again. For a row with GRANT
`unknown`, give the warning that explains it.

The action on each row is the only recommendation for that credential, and the rows are already in
the order in which to fix them. Never add a second recommendation for a credential anywhere in the
answer, for example in a priority, next-steps or further-investigation section. The answer to a
question about a suggested policy, in Suggested policies, is not a second recommendation.

## Summary

- **Scope:** `<N accounts connected to this Agent Space | ...>`
- **Accounts scanned:** `<n>`   **partial:** `<n>`   **failed:** `<n>`   **principals evaluated:** `<n>`   **not evaluated (work budget):** `<n>`
- **Findings:** Critical `<n>`  High `<n>`  Medium `<n>`  Low `<n>`  Info `<n>`
- `<n> Info findings hidden (<a> cannot invoke Amazon Bedrock, <b> expired or inactive credentials); ask for all findings to see them.`

Make every count by counting rows: tier counts from the rows of the Findings table, hidden counts from
the rows you left out, by cause. Leave out a cause with a count of 0, and the hidden line when nothing
is hidden. "Accounts scanned" counts complete and partial accounts; "principals evaluated" counts the
root account (when it has a key) and every user you evaluated.

### Accounts

| ACCOUNT | STATUS | PRINCIPALS | CRITICAL | HIGH | MEDIUM | LOW | INFO | REPORT GENERATED |
|---|---|---|---|---|---|---|---|---|
| `<alias>` | `<ok or partial>` | `<n>` | `<n>` | `<n>` | `<n>` | `<n>` | `<n>` | `<YYYY-MM-DD HH:MM UTC, "-" when no root key needed it, or "could not be read">` |

One row per account audited (`ok` or `partial`), the account with the most Critical findings first,
then the most High, then account ID. Counts are visible rows only.

Accounts audited with incomplete coverage (findings still reported):

- `<alias>`: `Amazon Bedrock API keys not evaluated: iam:ListServiceSpecificCredentials was denied`. Every API key user without an active access key shows as orphaned, because its API keys cannot be seen.

Accounts that could not be audited:

- `<alias>`: `<API and error code, for example iam:GetAccountAuthorizationDetails AccessDenied>`. `<For a permission error: add the read-only IAM policy in the llmops-bedrock-permissions-audit README as an inline policy on the AWS DevOps Agent role in this account.>`

`<Write "None" under a heading with no entry.>`

### Not evaluated (work budget)

| ACCOUNT | PRINCIPAL | CREDENTIALS | OLDEST KEY AGE | WHY |
|---|---|---|---|---|
| `<alias>` | `<user name>` | `<...ABCD (active), ...EFGH (inactive)>` | `<n>d` | `<over the 20-principal bound>` |

- `<n>` users in `<alias>` were not inventoried (over the 100-user bound).

These principals have no tier. `<Write "None" when everything was
evaluated.>`

### Warnings

- `<alias or "account ending NNNN">: <warning, for example "The IAM credential report was generated at 2026-10-30 06:15 UTC; a root access key created since then is not visible.">`
- `<"None" when there is no warning>`

Prefix each warning with the account it belongs to, by alias or `account ending NNNN`, because user
names are unique only within an account. List each warning once per account.

### Suggested policies (review before applying)

- `scp-deny-bedrock-to-iam-users.json`: a service control policy that denies Amazon Bedrock invocation to IAM users and the account root user. It breaks every workload still running on IAM user keys unless those users are listed as exceptions first.
- `policy-deny-bedrock-api-keys.json`: an identity policy that denies using every Amazon Bedrock API key, short-term ones included, and creating long-term ones.
- `policy-deny-long-term-bedrock-api-keys.json`: an identity policy that denies using and creating long-term Amazon Bedrock API keys and leaves short-term keys working.
- `<Only when the requester named Regions or approved models:>` `scp-restrict-bedrock-regions-models.json`: a service control policy that denies Amazon Bedrock outside the named Regions and for models not on the approved list.

`<Only when the requester asked how to fix a finding or what one of these policies would affect: the answer, below the list. For the user-deny SCP, the lists of references/remediation-guidance.md section 3.2 (affected now, affected if re-enabled, not affected, check first), then the filled template as its section 3.1 describes.>`

Nothing was applied. Ask for a template to see it with the placeholders explained. AWS documentation: [Service control policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html), [Control permissions for Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-permissions.html).

### Limitations

In a full report, include every item below.

- **Service control policies and resource control policies are not evaluated.** The audit reads identity-based policies only, so a principal shown as able to invoke Amazon Bedrock may be blocked at the organization level.
- **The audit reads the policies itself instead of using AWS's policy simulator.** AWS DevOps Agent's AWS tool does not run the IAM policy simulator, so AWS DevOps Agent evaluates each user's identity-based policies with the skill's written steps.
- **Access through `sts:AssumeRole` is not followed.** A user whose own policy cannot invoke Amazon Bedrock, but who can assume a role that can, is reported as unable to invoke.
- **Conditions the audit cannot evaluate, and permissions boundaries, give GRANT unknown.** The audit evaluates condition tests only on condition keys whose value AWS documents for a request signed with a long-lived credential, for example the MFA keys, which such requests never carry. When a condition it cannot evaluate could change whether the credential can invoke Amazon Bedrock, or a permissions boundary applies, GRANT is `unknown` and the row is shown for review. An escalation or canary action allowed only under such a condition is not counted, and a warning names it.
- **Only long-lived credentials are audited:** IAM user access keys, root access keys, and long-term Amazon Bedrock and Claude Platform on AWS API keys. IAM roles, federated users and IAM Identity Center users are out of scope, although they can use Amazon Bedrock too.
- **API key last use is unknown.** IAM does not report when an Amazon Bedrock API key was last used, so whether a key is in use is unknown: API keys show `unknown` and are never counted as dormant.
- **"Last used" is not Amazon Bedrock use.** IAM reports the key's last call to any AWS service.
- **Root access key details come from an existing IAM credential report, which can be up to four hours old.** The audit never generates a report, and reads one only when the AWS tool returns it as text. Whether the root user has a key comes from `GetAccountSummary`. Everything about IAM users, including MFA, is read live.
- **Who can re-enable an inactive key is not evaluated.** Inactive keys that would be Critical or High are reported as Low so they stay visible; delete them.
- **The audit reads policy documents to evaluate them.** It reads the identity-based policies of the users it evaluates and of their groups, and never reproduces them.
- **AWS's own exposure signal is not read.** A user with `AWSCompromisedKeyQuarantineV2` or `V3` attached is not specially marked.
- **Commercial AWS partition only.** AWS GovCloud (US) and China Regions are not covered.
- **A point-in-time snapshot of IAM configuration.** It shows what each credential can do, not what it did: only AWS CloudTrail (and Amazon Bedrock model invocation logs, where turned on) shows which calls a key made, and GuardDuty AI Protection reports suspicious use.
- **Work budget.** At most `<100>` users inventoried and `<20>` principals evaluated per account in this run. Every principal not evaluated is listed above, and users not inventoried are counted.
- **The rules were applied by AWS DevOps Agent from the skill's written catalog.** The result can vary between runs, so check the evidence shown for each row.

After the Limitations come, in this order: one sentence for each part of the request that this skill does not cover (`SKILL.md`, When NOT to Use), and one sentence for each Before You Present item that still fails, saying which item and why. The report ends there, with no offer of more work, no follow-up suggestion and no question.
