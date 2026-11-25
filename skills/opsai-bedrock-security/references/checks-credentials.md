# Checks: Credentials (LLM-BPA)

Covers the long-lived credentials that can invoke Amazon Bedrock models: IAM user access keys, root
access keys, and long-term Amazon Bedrock and Claude Platform on AWS API keys. IAM roles are out of
scope because they issue only temporary credentials.

Apply these rules exactly as written. Do not add, merge, soften or reorder rules.

Each catalog row: `check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation`.

Family code **LLM-BPA** (Amazon Bedrock permissions audit). Family prefix: `LLM-BPA-`. Pillar: Security for
every check. Severity is the risk tier: Critical > High > Medium > Low > Info. No check uses a
risk threshold that AWS does not publish: the only one, 90 days, is the default and the value in
AWS Security Hub controls IAM.3 and IAM.8. The other numbers in section 7 are the audit's design
constants (one of them separates a broad grant from a scoped one) or the skill's work budget, and
they are labelled as such.

## 1. Definitions

The inputs come from the read-only calls in `credential-collection-reference.md` and `policy-snapshot.md`, and
from the policy evaluation in `policy-evaluation.md`.

| Term | Exact meaning |
|---|---|
| Invoke actions | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`, `bedrock:CallWithBearerToken`, `bedrock-mantle:CallWithBearerToken`. `bedrock:InvokeModel` also authorizes the Converse operation and `bedrock:InvokeModelWithResponseStream` the ConverseStream operation; `Converse` and `ConverseStream` are not IAM actions, so a policy statement that names either one under the `bedrock` prefix allows or denies nothing ([Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)). Both bearer-token actions count because Amazon Bedrock API keys work through two endpoints |
| Escalation actions | `aws-marketplace:Subscribe`, `bedrock:CreateMarketplaceModelEndpoint` (enable more models), `iam:CreateServiceSpecificCredential` (create new API keys), in this order |
| Canary actions | `bedrock:DeleteCustomModel`, `bedrock:PutModelInvocationLoggingConfiguration`, `bedrock:DeleteGuardrail`, `bedrock:CreateProvisionedModelThroughput`, `bedrock:DeleteAgent`, `bedrock:DeleteKnowledgeBase` |
| Admin-class policies | `arn:aws:iam::aws:policy/AdministratorAccess`, `arn:aws:iam::aws:policy/PowerUserAccess`, `arn:aws:iam::aws:policy/AmazonBedrockFullAccess`. A user holds one when its ARN is in the user's attached policies or in the attached policies of a group the user belongs to. Matched by exact ARN, not by evaluating the policy |
| Allowed actions | Every action allowed in the least-access reading of `policy-evaluation.md` (sections 6 and 7): an invoke action on `*` or on a probe ARN, an escalation or canary action on `*`, and `iam:CreateServiceSpecificCredential` on the user's own ARN. An escalation or canary action allowed only under a condition the audit cannot evaluate is not counted, and a warning names it |
| Can invoke | At least one invoke action is among the allowed actions. The root account always can |
| GRANT | `broad` (any model, any Region), `scoped` (specific models or Regions), `none`, or `unknown` (the audit could not give an answer). Decided by `policy-evaluation.md` section 7. GRANT is `unknown` when a permissions boundary applies (U1); a condition the audit cannot evaluate could change it (U2); an AWS managed policy could not be read and is not in the skill's catalog (U3); a group or a customer managed policy could not be read (U4); the user's own snapshot entry could not be read (U5); IAM reports a context key that no policy read uses (U6); a call failed or was refused, or the user's name cannot be used in a result filter (U7); or the user's policies name Amazon Bedrock resources, none of which is allowed, with no explicit deny (U8). The warning gives the reason (`evaluation-outcomes.md` section 3) |
| Effectively `bedrock:*` | **Every** canary action is allowed on `*`. Any one of them alone proves nothing: narrower managed policies such as `AmazonBedrockLimitedAccess` allow some of them |
| API key user | An IAM user whose name starts with `BedrockAPIKey-` (the user the Amazon Bedrock console creates for a long-term API key) or `AeaApiKey-` (Claude Platform on AWS) |
| API key | An Amazon Bedrock API key: a service-specific credential whose `ServiceName` is `bedrock.amazonaws.com`. Or a Claude Platform API key: any other service-specific credential on an `AeaApiKey-` user. Other service-specific credentials are ignored |
| Active | An access key whose `Status` is `Active`. An API key whose `Status` is `Active` and that has not expired. A root key whose `access_key_N_active` is `TRUE` |
| Expired | An API key whose `ExpirationDate` is present and not later than the audit time. IAM then reports `Status` `Expired`. Only API keys expire |
| Orphaned | An API key user none of whose access keys or API keys is active, including one that has no credential at all |
| Audit time | The UTC date and time at which you started the audit. Use the same value for every computed age |
| Age | Whole days from the key's `CreateDate` to the audit time, rounded down. For a root key, from `access_key_N_last_rotated` in the credential report |
| Unused days | Whole days from `LastUsedDate` to the audit time, rounded down |
| Last use known | True for access keys and for the root key slots the credential report shows. False for API keys, because IAM does not report when an API key was last used, and for the unconfirmed root row (KEY `root-access-key`), which is therefore never dormant |
| Never used | Last use is known and there is no `LastUsedDate`: an absent field, or `N/A`, `no_information` or an empty value in the credential report |
| Threshold `N` | 90 days, unless the requester names another whole number of days (at least 1) |
| Dormant | Last use is known, and the key was never used or its unused days are at least `N` |
| Old | Age of at least `N` days |
| No MFA | `iam:ListMFADevices` returned no device for the user. For the root account the MFA column comes from the credential report's `mfa_active`, and is `unknown` when the report could not be read; it never changes the root tier |

## 2. Tier rules

Make one row per credential: every access key, every API key and every root access key of the
principals you evaluated. An orphaned API key user gets exactly one row, with no credential, and no
separate rows for its inactive keys.

Apply these rules to each row in order. The first rule that matches decides the tier. Write the
reasons in the order given, word for word, with the values filled in.

1. **Root account.**
   * The root key is active: **Critical**, reason `The root account has an active access key.`
     (LLM-BPA-001).
   * `GetAccountSummary` says the root user has an access key, but the credential report could not be
     read or shows no root key: **Critical**, reason
     `The root account has an access key (AccountAccessKeysPresent is 1), but the credential report does not confirm whether it is active.`
     (LLM-BPA-001). The skill reads only an existing report and never
     generates one; see `credential-api-quirks.md` section 1 and `credential-collection-reference.md` section 1.1.
   * The root key is inactive: **Info**, reason `The root access key is inactive.` (LLM-BPA-014).
   * A root key is never re-rated as if it were active.
2. **Orphaned API key user:** **Medium**, reason
   `This API key user has no active credential left but was never cleaned up.` (LLM-BPA-011).
3. **Inactive or expired credential.** If the credential is an access key or an API key and has not
   expired, apply rules 4 to 10 to a copy of the row in which the credential is active. If the copy
   rates Critical or High: **Low** (LLM-BPA-013). Record the copy's tier as the would-be tier, and write
   these reasons:
   1. `The key is inactive but its secret works again if anyone re-enables it with iam:UpdateAccessKey.`
      for an access key, or
      `The key is inactive but works again if anyone re-enables it with iam:UpdateServiceSpecificCredential.`
      for an API key;
   2. `If re-enabled it would rate Critical:` or `If re-enabled it would rate High:`;
   3. every reason of the active copy, in its order, indented under the previous line.

   In every other case (expired, or the active copy rates Medium, Low or Info): **Info**, reason
   `The credential is inactive or expired and cannot be used.` (LLM-BPA-014).
4. **GRANT is `unknown`:** **Info**, reason
   `Permissions could not be evaluated; review this principal manually.` (LLM-BPA-015). Never hidden.
5. **Can invoke, plus admin-class, `bedrock:*` or escalation:** **Critical** when at least one of
   these applies. Reasons:
   `Can invoke Amazon Bedrock models.`, then each that applies, in this order:
   * an admin-class policy is attached: `Holds an admin-class policy: <names>.` with the policy names
     (the part of each ARN after the last `/`) joined by `, ` (LLM-BPA-002). Keep attachment order: first
     the user's own attached policies in the order of its `AttachedManagedPolicies` in the policy
     snapshot, then, for each group in the user's `GroupList` order, that group's
     `AttachedManagedPolicies` in order. Write each name once, at its first position;
   * effectively `bedrock:*`: `Effectively holds bedrock:* (full control of Amazon Bedrock).`
     (LLM-BPA-003);
   * one or more escalation actions allowed:
     `Can also enable more models or create new API keys: <actions>.` with the allowed escalation
     actions in the order of the definition, joined by `, ` (LLM-BPA-004 for `aws-marketplace:Subscribe`
     or `bedrock:CreateMarketplaceModelEndpoint`, LLM-BPA-005 for `iam:CreateServiceSpecificCredential`).
6. **Can invoke, and the key is dormant or old, or the user has no MFA:** **High** when at least one
   of these applies. Reasons: `Can invoke Amazon Bedrock models.`, then each that applies, in this
   order:
   * dormant and never used: `The key has never been used, so nobody would notice misuse.` (LLM-BPA-006);
     dormant otherwise: `The key has not been used for <unused days> days (threshold <N>).` (LLM-BPA-006);
   * old: `The key is <age> days old (threshold <N>).` (LLM-BPA-007);
   * the credential is an access key (not an API key) and the user has no MFA:
     `The user has no MFA device.` (LLM-BPA-008).
7. **API key on an API key user:** the user is an API key user, the credential is an API key, and
   GRANT is not `none`: **High**, reason
   `An Amazon Bedrock API key is a bearer token that works from anywhere.` (LLM-BPA-009).
8. **Can invoke with GRANT `broad`:** **Medium** (LLM-BPA-010), reason
   `Can invoke any model in any Region; the key is recent and in use.` for an access key, or
   `Can invoke any model in any Region; the key is recent (IAM does not report when an API key was last used).`
   for an API key.
9. **Can invoke with GRANT `scoped`:** **Low** (LLM-BPA-012), reason
   `Can invoke only specific models or Regions (<Regions>).` with the allowed Regions sorted and
   joined by `, `, or `none found` when no Region was recorded.
10. **Otherwise:** **Info**, reason `Cannot invoke Amazon Bedrock models.` (LLM-BPA-014).

What follows from the order:

* Rules 5 and 6 need an active credential that can invoke. A user who holds `AdministratorAccess` but
  whom an explicit deny keeps from Amazon Bedrock is Info, not Critical.
* MFA never matters for an API key (a bearer token cannot use it) or a root key. Dormancy never
  applies to an API key, because its last use is unknown.
* Rule 7 needs GRANT `broad` or `scoped`. A console-created API key user whose policy was detached is
  not High.
* An inactive credential whose GRANT is `unknown` is Info under rule 3 but stays visible, because its
  GRANT is `unknown`.
* An escalation action or a canary action allowed without any invoke action does not raise the tier.

**CHECKS cell.** List the LLM-BPA ids of the row's reasons in reason order, without repeats. For an LLM-BPA-013
row write `LLM-BPA-013`, then in parentheses the ids its active copy matched, for example
`LLM-BPA-013 (if re-enabled: LLM-BPA-002, LLM-BPA-004)` or `LLM-BPA-013 (if re-enabled: LLM-BPA-006, LLM-BPA-008)`. The
first matching rule decides the copy too: a copy that rates Critical carries only rule 5 reasons, and
one that rates High carries only rule 6 reasons or only the rule 7 reason.

## 3. Catalog

| check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation |
|---|---|---|---|---|---|
| LLM-BPA-001 | Security | Critical | Rule 1. The root account has an active access key. Presence from `iam:GetAccountSummary` (`SummaryMap.AccountAccessKeysPresent` is 1); active state from the credential report's `<root_account>` row (`access_key_1_active`, `access_key_2_active`). When the report cannot be read or shows no root key, the present key is reported here and the reason says its state was not confirmed | Delete the root access key. Use IAM Identity Center or IAM roles for day-to-day work and keep the root user for account-level tasks only | https://docs.aws.amazon.com/securityhub/latest/userguide/iam-controls.html (control IAM.4); https://docs.aws.amazon.com/IAM/latest/UserGuide/id_root-user_manage_delete-key.html |
| LLM-BPA-002 | Security | Critical | Rule 5. Can invoke, and an admin-class policy (`AdministratorAccess`, `PowerUserAccess`, `AmazonBedrockFullAccess`) is attached to the user directly or through a group | Replace the broad permissions with a policy limited to the Amazon Bedrock actions, models and Regions the workload needs, rotate the key, and move the workload to an IAM role | https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html (apply least-privilege permissions); https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonBedrockFullAccess.html |
| LLM-BPA-003 | Security | Critical | Rule 5. Can invoke, and every one of the six canary actions is allowed on `*` (effectively `bedrock:*`). Fewer than six never matches | As LLM-BPA-002 | https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html (apply least-privilege permissions); https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonBedrockLimitedAccess.html (allows some canary actions without being `bedrock:*`) |
| LLM-BPA-004 | Security | Critical | Rule 5. Can invoke, and `aws-marketplace:Subscribe` or `bedrock:CreateMarketplaceModelEndpoint` is allowed on `*` (can enable more models) | Remove the action from the user's policies, rotate the key, and move the workload to an IAM role | https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html |
| LLM-BPA-005 | Security | Critical | Rule 5. Can invoke, and `iam:CreateServiceSpecificCredential` is allowed on `*` or on the user's own ARN (can create new API keys that outlive a rotated access key) | Remove the action, rotate the key, and move the workload to an IAM role. To block API key creation and keep short-term keys working, see `assets/policy-deny-long-term-bedrock-api-keys.json` | https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html |
| LLM-BPA-006 | Security | High | Rule 6. Can invoke, and the key is dormant: never used, or unused for at least `N` days (default 90) | Decommission in stages: deactivate the key, watch for breakage over an agreed window (last-used data can miss a rare but critical path), then delete it | https://docs.aws.amazon.com/securityhub/latest/userguide/iam-controls.html (control IAM.8, 90 days) |
| LLM-BPA-007 | Security | High | Rule 6. Can invoke, and the key is at least `N` days old (default 90) | Move the workload to an IAM role. If the user must stay, rotate the key | https://docs.aws.amazon.com/securityhub/latest/userguide/iam-controls.html (control IAM.3, 90 days); https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html |
| LLM-BPA-008 | Security | High | Rule 6. Can invoke, the credential is an access key, and the user has no MFA device | Move the workload to an IAM role. If the user must stay, rotate the key and enable MFA | https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html (require MFA); https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa.html |
| LLM-BPA-009 | Security | High | Rule 7. An API key on an API key user (`BedrockAPIKey-*` or `AeaApiKey-*`), and GRANT is `broad` or `scoped` | Delete or rotate the API key. If API keys are not needed, deny `bedrock:CallWithBearerToken` and `bedrock-mantle:CallWithBearerToken` for the user | https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html |
| LLM-BPA-010 | Security | Medium | Rule 8. Can invoke with GRANT `broad`, and no rule above matched: the key is recent and in use (for an API key, recent) | Limit the user to the models and Regions it needs, and prefer an IAM role over a long-lived key | https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html (temporary credentials for workloads; least privilege) |
| LLM-BPA-011 | Security | Medium | Rule 2. An API key user with no active credential left (orphaned) | Delete the IAM user | https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html (regularly review and remove unused users and credentials) |
| LLM-BPA-012 | Security | Low | Rule 9. Can invoke with GRANT `scoped`, and no rule above matched | No urgent action. Prefer an IAM role and keep the policy scoped to the models and Regions in use | https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html (temporary credentials for workloads) |
| LLM-BPA-013 | Security | Low | Rule 3. An inactive, not expired access key or API key that would rate Critical or High if it were re-enabled. Its secret still works after `iam:UpdateAccessKey` or `iam:UpdateServiceSpecificCredential` sets it active again | Delete the inactive key | https://docs.aws.amazon.com/IAM/latest/APIReference/API_UpdateAccessKey.html; https://docs.aws.amazon.com/IAM/latest/APIReference/API_UpdateServiceSpecificCredential.html |
| LLM-BPA-014 | Security | Info | Rules 1, 3 and 10. Cannot invoke Amazon Bedrock; or inactive and would not rate Critical or High if re-enabled; or expired; or an inactive root key. Hidden unless the requester asks for all findings, and counted by cause | None needed for Amazon Bedrock exposure. An inactive key with Amazon Bedrock access can still be deleted (section 4) | https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html |
| LLM-BPA-015 | Security | Info | Rule 4. GRANT `unknown`, for one of these causes: a permissions boundary applies; a condition the audit cannot evaluate could change whether the user can invoke; an AWS managed policy could not be read and is not in the skill's catalog; a group or a customer managed policy could not be read; the user's own snapshot entry could not be read; IAM reports a context key that no policy read uses; a call failed or was refused, or the user's name cannot be used in a result filter; or the user's policies name Amazon Bedrock resources, none of which is allowed, with no explicit deny (a condition may restrict them). The row's warning gives the cause (`evaluation-outcomes.md` section 3). Always shown | Review the principal by hand | https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html |

## 4. Recommended action

Each row gets exactly one action: the first that applies below, word for word. `<key>` is the masked
key ID (`...` plus the last four characters), `<user>` the IAM user name, and `<admin>` is
`, including admin-class permissions` when the user holds an admin-class policy, otherwise empty.

1. Root key active, or not confirmed:
   `Delete the root access key. Use IAM Identity Center or IAM roles for day-to-day work and keep root for account-level tasks only.`
2. Root key inactive: `Delete the inactive root access key; root should have no access keys.`
3. Orphaned API key user:
   `Delete the IAM user <user>. It holds no active credential, and any policy attached to it is a standing risk.`
4. GRANT `unknown`: `Review this principal manually: its permissions could not be evaluated.`
5. Inactive or expired credential:
   * GRANT `none`: `No action needed for Amazon Bedrock exposure.`
   * API key with a would-be tier:
     `Delete inactive API key <key> on <user>. Re-enabling it would restore Amazon Bedrock access<admin>.`
   * any other API key: `Delete the expired API key <key> on <user>; it has no reason to exist.` when
     it expired, otherwise `Delete the inactive API key <key> on <user>; it has no reason to exist.`
   * access key with a would-be tier:
     `Delete inactive access key <key> on <user>. It is unused, and re-enabling it would restore Amazon Bedrock access<admin>.`
   * any other access key: `Delete inactive access key <key>; it has no reason to exist.`
6. Tier Info: `No action needed for Amazon Bedrock exposure.`
7. API key:
   `Delete or rotate the API key <key> on <user>. If API keys are not needed, deny bedrock:CallWithBearerToken and bedrock-mantle:CallWithBearerToken for this user.`
8. Dormant access key: `Delete access key <key> (never used). Recreate it only if a workload breaks.`
   or `Delete access key <key> (unused for <unused days> days). Recreate it only if a workload breaks.`
9. An escalation action is allowed:
   `Remove <actions> from <user>'s policies, then rotate access key <key> and move the workload to an IAM role.`
   with the allowed escalation actions in definition order, joined by `, `.
10. Admin-class policy or effectively `bedrock:*`:
    `Replace the broad permissions on <user> with a policy limited to the Amazon Bedrock actions, models and Regions it needs, and rotate access key <key>.`
11. No MFA, or old:
    `Move the workload behind <user> to an IAM role so no long-lived key exists. If the user must stay, rotate access key <key> and enable MFA.`
12. Tier Low:
    `No urgent action. Prefer an IAM role over a long-lived key and keep the policy scoped to the models and Regions in use.`
13. Otherwise:
    `Limit <user> to the specific models and Regions it needs, and prefer an IAM role over a long-lived key.`

The skill only recommends. It never carries out an action, and never offers to: it hands the steps,
the policy or the command to the customer. Give every action with an AWS documentation link: the
AWS-doc-citation of the row's first check-id (section 3), or, for a suggested policy, the links in
`remediation-guidance.md` section 4. "No action needed" needs no link. Some questions also need the
statements of section 8.

## 5. Order and visibility

Sort the visible rows by tier, Critical first. Within a tier apply these keys in turn:

1. Low only: an inactive key whose would-be tier is Critical, then one whose would-be tier is High,
   then every other row.
2. The root account first.
3. Dormant credentials (including never used) before the rest. A row without a credential is not
   dormant.
4. Older first (larger age; a row with no age counts as 0).
5. More Regions allowed first (a broad grant on `*` and the root account count all Regions in
   `policy-evaluation.md` section 7.2; `none` and `unknown` count 0).
6. Account ID, ascending. Compare the IDs internally and never print them.
7. User name, ascending.

Info rows are hidden unless the requester asks for all findings, with two exceptions: a row with
GRANT `unknown` is always shown, because hiding it would make a gap look clean, and so is a row for a
credential the question asks about (an inventory of API keys asks about every API key). Count every
hidden row by cause:

* `expired or inactive credentials`: its credential is inactive or expired (an inactive root key
  included);
* `cannot invoke Amazon Bedrock`: its credential is active.

Write the summary line as
`<total> Info findings hidden (<a> cannot invoke Amazon Bedrock, <b> expired or inactive credentials); ask for all findings to see them.`
Leave out a cause whose count is 0, and leave out the line when nothing is hidden. Tier counts in the
summary and the per-account table count visible rows only.

## 6. Column values

| Column | Value |
|---|---|
| TIER | `Critical`, `High`, `Medium`, `Low` or `Info` |
| ACCOUNT | The IAM account alias, or `account ending NNNN` with the last four digits of the account ID |
| PRINCIPAL | The IAM user name, or `<root_account>` |
| CREDENTIAL | `access key`, `root access key`, `Amazon Bedrock API key`, `Claude Platform API key`, or `none (orphaned user)` |
| KEY | `...` plus the last four characters of the access key ID or `ServiceSpecificCredentialId`; `root-access-key-1` or `root-access-key-2` for a root key slot (`root-access-key` when the slot is unknown); `-` for an orphaned user |
| AGE | `<age>d`, or `-` when unknown |
| LAST USED | `<unused days>d ago`, `never`, `unknown` (every API key, and a root key whose state the report does not confirm), or `-` for an orphaned user |
| MFA | `yes` or `no`; `unknown` only on a root row when the credential report could not be read |
| GRANT | `broad`, `scoped`, `none` or `unknown` |
| CHECKS | The LLM-BPA ids, as described at the end of section 2 |

## 7. Thresholds and constants

| Value | Source | Used for |
|---|---|---|
| 90 days | Default; AWS Security Hub control IAM.3 (access keys rotated within 90 days) and control IAM.8 (credentials unused for 90 days) | `N` for dormant and old. The requester may choose another whole number of days; state it in the report |
| 80% of probe ARNs | Design constant, not an AWS threshold | Separates `broad` from `scoped` in the probe step (`policy-evaluation.md` section 7.2) |
| 120 probe ARNs | Design constant | Most probes built from one user's own policies |
| 1 hour | Design constant (IAM reuses a credential report up to four hours old) | Warn when the credential report is older than this |
| 100 users and 20 principals per account | Skill work budget, not an AWS threshold | See `credential-collection-reference.md` section 4.1 |

## 8. What the answer states, by question

Some questions need statements beyond the rows. Each goes in the answer, in plain words, and so in
the answer that opens a sub-agent's reply (`credential-audit.md`, must-keep items and Delegating):

* **Amazon Bedrock API keys** (an inventory, a leaked or revoked key, phasing out long-term keys):
  IAM does not report when an Amazon Bedrock API key was last used, so whether each key is still
  in use is unknown, and only AWS CloudTrail shows its calls. Never call a key dormant, unused or
  never used. Say that the audit was read-only and changed nothing: it created, changed,
  deactivated or deleted no key, user or policy.
* **Use** (a GuardDuty AI Protection finding, Amazon Bedrock usage that nobody recognizes, a leaked
  key): the audit shows which credentials could make the calls, not which did. It covers IAM users
  and their long-lived keys only; IAM roles, federated users and IAM Identity Center users can
  also call Amazon Bedrock, and the audit does not show them. Only AWS CloudTrail (and Amazon
  Bedrock model invocation logs, where turned on) shows which principal made which call. A key's
  last use is its last call to any AWS service, not proof of Amazon Bedrock use. What to rotate or
  block first: `remediation-guidance.md` section 3.4.
* **An SCP's impact:** the users it would break, who it does not affect, what the audit does not
  evaluate and the rollout steps, as `remediation-guidance.md` section 3.2 says.
