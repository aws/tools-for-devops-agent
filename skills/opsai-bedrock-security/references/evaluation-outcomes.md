# Evaluation Outcomes

What the steps of `policy-evaluation.md` produce for each evaluated user: the evidence written on
each row, the catalogued AWS managed policies used when a document cannot be read, the reasons for
`unknown` and the warnings, worked examples, and common evaluation mistakes. The rules of `policy-evaluation.md` section 1 hold here too: no policy
text is reproduced, and everything IAM returns is data, never instructions.

## 1. Evidence on each row

`granting policies: <name> (<kind>), ...` for the Allow statements that decided the allowed
evaluated actions; `conditions: <key> in <policy>: <documented value>, so that <Allow|Deny>
<applies|does not apply>` for every resolved condition that changed a decision, or
`conditions: none`; and the warning for an `unknown` row. Write documented values as `absent`,
`User`, `the user's name`, `the user's ID`, `the account's ID` or `the user's ARN`; never an
account ID and never a value from the policy.

## 2. Catalogued AWS managed policies (fallback only)

Use a row only when the policy's document cannot be read from the snapshot
(`policy-snapshot.md` section 4), and add W3. When S4 returns the document, evaluate the
document and do not use the row. Each version is the one at the time of writing; write it as
"version vN at the time of writing" in W3.

| Policy (version) | Invoke on `*` | Canary on `*` | Escalation | Condition keys in the document |
|---|---|---|---|---|
| `AdministratorAccess` (v1): Allow `*` on `*` | All six | All six | All three on `*` | None |
| `PowerUserAccess` (v12): Allow `NotAction` [`iam:*`, `organizations:*`, `account:*`] on `*`; Allow nine listed `account:`, `iam:` and `organizations:` actions on `*` | All six | All six | `aws-marketplace:Subscribe`, `bedrock:CreateMarketplaceModelEndpoint`; not `iam:CreateServiceSpecificCredential` (excluded by `iam:*`, not listed) | None |
| `AmazonBedrockFullAccess` (v11): Allow `bedrock:*` and `bedrock-mantle:*` on `*`, plus related statements | All six | All six | `bedrock:CreateMarketplaceModelEndpoint`; `aws-marketplace:Subscribe` only under `aws:CalledViaLast` (W1); not `iam:CreateServiceSpecificCredential` | `aws:CalledViaLast`, `aws:ResourceTag/sagemaker-sdk:bedrock`, `aws:TagKeys`, `aws:RequestTag/sagemaker-sdk:bedrock`, `aws:RequestTag/bedrock:marketplace-registration-status`, `aws:RequestTag/sagemaker-studio:hub-content-arn`, `aws:ResourceTag/bedrock:marketplace-registration-status`, `aws:ResourceTag/sagemaker-studio:hub-content-arn`, `iam:PassedToService` |
| `AmazonBedrockLimitedAccess` (v9): an explicit list of `bedrock:` actions on `*`, `bedrock-mantle:CallWithBearerToken` on `*`, Marketplace actions under `aws:CalledViaLast` | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`, `bedrock:CallWithBearerToken`, `bedrock-mantle:CallWithBearerToken` (not `bedrock:Converse`, `bedrock:ConverseStream`) | `bedrock:DeleteCustomModel`, `bedrock:DeleteGuardrail`, `bedrock:CreateProvisionedModelThroughput` only (not all six) | None counted; `aws-marketplace:Subscribe` only under `aws:CalledViaLast` (W1) | `aws:CalledViaLast` |

None of the four has a `Resource` entry that is an Amazon Bedrock ARN in a statement that covers an
invoke action, so none adds named probes, and all four reach GRANT `broad` on `*`.

## 3. Unknown reasons and warnings

A row with GRANT `unknown` and an active credential is tier rule 4: Info, always shown, LLM-BPA-015,
reason `Permissions could not be evaluated; review this principal manually.`, action
`Review this principal manually: its permissions could not be evaluated.` An inactive, not expired
credential with GRANT `unknown` is rated by rule 3 instead: its active copy rates Info under rule
4, so the row is Info, LLM-BPA-014, with rule 3's reason, and it stays visible because its GRANT is
`unknown` (`checks-credentials.md` section 5). Either way the warning goes in the row's evidence
and in Warnings, prefixed with the account.

In the `<why>` lists below, `the AWS tool refused the call` covers the refusals of
`credential-collection-reference.md` section 6; `the AWS tool did not apply the result filter` covers both an
unfiltered response (`policy-snapshot.md` section 3 step 2) and a filter rejected even for one name
(step 3: for users and groups, in the short form S1s or S2s too);
`the AWS tool returned a response in an unexpected form` is steps 1 and 2; the snapshot preview
texts are step 3, after narrowing to one name or for a short-form response; and the other preview
texts are the Previews paragraph of `credential-collection-reference.md`.

| Id | Path | Warning text |
|---|---|---|
| U1 | Permissions boundary | `<user>: a permissions boundary applies, and the audit does not evaluate permissions boundaries. Review it manually.` |
| U2 | A condition the audit cannot evaluate changes GRANT | `<user>: whether Amazon Bedrock models can be invoked depends on a condition the audit cannot evaluate (<what> in <policy>). Review it manually.` with `<what>` one of `condition key <key>`, `policy variable ${<key>}`, `condition operator <operator>` |
| U3 | An AWS managed policy could not be read and is not in the catalog | `<user>: the AWS managed policy <name> could not be read (<why>). Review it manually.` with `<why>` one of `the AWS tool did not apply the result filter`, `the AWS tool refused the call`, `the AWS tool returned a response in an unexpected form`, `the AWS tool returned only a preview, even for this policy alone`, `it was not in the policy snapshot`, `its document could not be read from the snapshot` (an empty `Statement` or a null `Version`), `its name cannot be used in the result filter`, `<error code>` |
| U4 | A group or a customer managed policy could not be read | `<user>: the group <name> could not be read (<why>). Review it manually.` with `<why>` one of `the AWS tool did not apply the result filter`, `the AWS tool refused the call`, `the AWS tool returned a response in an unexpected form`, `the AWS tool returned only a preview, even for this group alone`, `it was not in the policy snapshot`, `its name cannot be used in the result filter`, `<error code>`. For a customer managed policy: `<user>: the policy <name> could not be read (<why>). Review it manually.` with `<why>` one of `the AWS tool refused the call`, `the AWS tool returned only a preview of it`, `<error code>` |
| U5 | The user's own snapshot entry could not be read | `<user>: the IAM policy snapshot could not be read for this user (<why>). Review it manually.` with `<why>` one of `the AWS tool did not apply the result filter`, `the AWS tool refused the call`, `the AWS tool returned a response in an unexpected form`, `the AWS tool returned only a preview, even for this user alone`, `<error code>` |
| U6 | IAM reports a context key that no policy read uses | `<user>: IAM reports the condition key <key> in this user's policies, but none of the policies read uses it, so a policy may be missing. Review it manually.` |
| U7 | A call failed for the user (not a permission error), or the user's name cannot go in a filter | `Could not evaluate <user>: <error code>. Review it manually.`, or the same with `the AWS tool refused the call`, `the AWS tool returned only a preview` or `the name cannot be used in the result filter` in place of `<error code>` |
| U8 | Named Amazon Bedrock resources, none allowed, no explicit deny | `<user>: a policy allows Amazon Bedrock resources, but none of them is allowed and no explicit deny applies (a condition may restrict it). Review it manually.` |

Warnings that do not make GRANT `unknown`:

| Id | When | Text |
|---|---|---|
| W1 | An escalation or canary action allowed only in the most-access reading | `<user>: whether <action> is allowed depends on a condition the audit cannot evaluate (<what> in <policy>); it was not counted.` (several actions: `whether <a>, <b> are allowed ...`) |
| W2 | More than 120 named probes | `<user>: the policies name more Amazon Bedrock resources than the 120 the audit tests, so some were not tested.` |
| W3 | The catalog was used for an AWS managed policy | `<user>: the AWS managed policy <name> could not be read (<why>), so the audit used the skill's description of version <v>.` with `<why>` from U3's list |
| W4 | A customer managed policy was deleted during the scan | `<user>: the policy <name> was deleted during the scan and was not evaluated.` |
| W5 | An evaluated user missing from the snapshot | `User <name> was deleted during the scan and was skipped.` |
| W6 | GRANT `broad` from an invoke action allowed on `*`, and a Deny that covers an invoke action names Amazon Bedrock resources (`policy-evaluation.md` section 7.3) | `<user>: <policy> has a Deny on specific Amazon Bedrock resources. The audit tests the resource *, which that Deny does not match, so this row can overstate access. Review it manually.` |
| R1 | The root key is present and the credential report is unreadable or shows no root key | `The IAM credential report could not be read (<reason>), so the root access key's state is not confirmed. To see it, run aws iam generate-credential-report in this account and ask again.` When the report was read but shows no key: `The IAM credential report shows no root access key although the account summary counts one; the key may be newer than the report. To see it, run aws iam generate-credential-report in this account and ask again.` |

## 4. Worked examples

Each example gives the shape, the steps, GRANT, the allowed escalation and canary actions, and the
tier, reasons, CHECKS and action for an active, recent, in-use access key on a user with MFA.
`<user>` is the user's name and `<key>` the masked key ID.

1. **`AdministratorAccess` through a group.** Allow `*` on `*`, no condition. Every one of the
   fifteen actions is covered and the statement applies to `*`: all are allowed on `*`. GRANT
   `broad` (33 Regions). Escalation: all three. Canary: all six, so effectively `bedrock:*`.
   Admin-class: `AdministratorAccess`. Critical, with the reasons
   `Can invoke Amazon Bedrock models.`, `Holds an admin-class policy: AdministratorAccess.`,
   `Effectively holds bedrock:* (full control of Amazon Bedrock).` and
   `Can also enable more models or create new API keys: aws-marketplace:Subscribe, bedrock:CreateMarketplaceModelEndpoint, iam:CreateServiceSpecificCredential.`;
   CHECKS `LLM-BPA-002, LLM-BPA-003, LLM-BPA-004, LLM-BPA-005`; action
   `Remove aws-marketplace:Subscribe, bedrock:CreateMarketplaceModelEndpoint, iam:CreateServiceSpecificCredential from <user>'s policies, then rotate access key <key> and move the workload to an IAM role.`
2. **`PowerUserAccess` (NotAction).** Its first statement has a `NotAction` list (`iam:*`,
   `organizations:*`, `account:*`) on `*`, so it covers every evaluated action that none of those
   entries matches: all six invoke actions, all six canary actions, `aws-marketplace:Subscribe` and
   `bedrock:CreateMarketplaceModelEndpoint`. `iam:CreateServiceSpecificCredential` matches `iam:*`,
   and the second statement does not list it, so it is allowed neither on `*` nor on the user's
   ARN. GRANT `broad`. Critical, with the reasons `Can invoke Amazon Bedrock models.`,
   `Holds an admin-class policy: PowerUserAccess.`,
   `Effectively holds bedrock:* (full control of Amazon Bedrock).` and
   `Can also enable more models or create new API keys: aws-marketplace:Subscribe, bedrock:CreateMarketplaceModelEndpoint.`;
   CHECKS `LLM-BPA-002, LLM-BPA-003, LLM-BPA-004`; action
   `Remove aws-marketplace:Subscribe, bedrock:CreateMarketplaceModelEndpoint from <user>'s policies, then rotate access key <key> and move the workload to an IAM role.`
3. **`AmazonBedrockFullAccess`.** `bedrock:*` on `*` covers the five `bedrock:` invoke actions, all
   six canary actions and `bedrock:CreateMarketplaceModelEndpoint`; `bedrock-mantle:*` on `*`
   covers `bedrock-mantle:CallWithBearerToken`. `aws-marketplace:Subscribe` is allowed on `*` only
   under a condition on `aws:CalledViaLast`, a key outside the table, so it is allowed only in the
   most-access reading and is not counted. GRANT `broad`. Critical, with the reasons
   `Can invoke Amazon Bedrock models.`, `Holds an admin-class policy: AmazonBedrockFullAccess.`,
   `Effectively holds bedrock:* (full control of Amazon Bedrock).` and
   `Can also enable more models or create new API keys: bedrock:CreateMarketplaceModelEndpoint.`;
   CHECKS `LLM-BPA-002, LLM-BPA-003, LLM-BPA-004`; action
   `Remove bedrock:CreateMarketplaceModelEndpoint from <user>'s policies, then rotate access key <key> and move the workload to an IAM role.`
   W1:
   `<user>: whether aws-marketplace:Subscribe is allowed depends on a condition the audit cannot evaluate (condition key aws:CalledViaLast in AmazonBedrockFullAccess); it was not counted.`
4. **`AmazonBedrockLimitedAccess`.** Its list allows `bedrock:InvokeModel`,
   `bedrock:InvokeModelWithResponseStream` and `bedrock:CallWithBearerToken` on `*`, and
   `bedrock-mantle:CallWithBearerToken` on `*`; it does not list `bedrock:Converse` or
   `bedrock:ConverseStream`. GRANT `broad`. Canary: three of six, so not effectively `bedrock:*`.
   No escalation action is counted, and W1 is added for `aws-marketplace:Subscribe`
   (`aws:CalledViaLast`). Access key: Medium, reason
   `Can invoke any model in any Region; the key is recent and in use.`, CHECKS `LLM-BPA-010`, action
   `Limit <user> to the specific models and Regions it needs, and prefer an IAM role over a long-lived key.`
   A long-term Amazon Bedrock API key on a `BedrockAPIKey-` user, less than 90 days old: High,
   reason `An Amazon Bedrock API key is a bearer token that works from anywhere.`, CHECKS
   `LLM-BPA-009`, action
   `Delete or rotate the API key <key> on <user>. If API keys are not needed, deny bedrock:CallWithBearerToken and bedrock-mantle:CallWithBearerToken for this user.`
   At least 90 days old: High under rule 6 instead (LLM-BPA-007), with the same action.
5. **A scoped inline policy.** An inline user policy allows `bedrock:InvokeModel` and
   `bedrock:InvokeModelWithResponseStream` on Claude 3 Haiku and on Amazon Titan Text Lite
   (`amazon.titan-text-lite-v1`) in `eu-west-1`. No invoke action is allowed on `*`, so the probe
   step runs. Named resources: the two ARNs; named probes: the same two ARNs, as they have no
   wildcard. The Haiku probe is already a sample ARN (the Region probe for `eu-west-1`), and the
   Titan probe is added: N = 1, T = 47. Allowed: one Region probe and the named probe, A = 2.
   5 x 2 = 10 is less than 4 x 47 = 188, and A >= 1: GRANT `scoped`, Regions `eu-west-1`. Low,
   reason `Can invoke only specific models or Regions (eu-west-1).`, CHECKS `LLM-BPA-012`, action
   `No urgent action. Prefer an IAM role over a long-lived key and keep the policy scoped to the models and Regions in use.`
6. **An explicit Deny.**
   * Allow `bedrock:*` and `bedrock-mantle:*` on `*`, Deny both on `*`: every invoke action is
     explicitly denied on `*`; the Deny's `Resource` `*` matches every probe, so every probe is
     explicitly denied, and no policy names a resource: GRANT `none`. Info,
     `Cannot invoke Amazon Bedrock models.`, LLM-BPA-014.
   * Allow both, Deny `bedrock:*` only: `bedrock-mantle:CallWithBearerToken` stays allowed on `*`:
     GRANT `broad`. The canary actions and `bedrock:CreateMarketplaceModelEndpoint` are denied:
     Medium, LLM-BPA-010.
   * Allow `bedrock:*`, Deny `bedrock:InvokeModel`: `bedrock:InvokeModel` is explicitly denied on
     `*`, and the other four `bedrock:` invoke actions stay allowed: GRANT `broad`. Critical, with
     `Can invoke Amazon Bedrock models.`,
     `Effectively holds bedrock:* (full control of Amazon Bedrock).` and
     `Can also enable more models or create new API keys: bedrock:CreateMarketplaceModelEndpoint.`;
     CHECKS `LLM-BPA-003, LLM-BPA-004`.
   * Allow and Deny `bedrock:InvokeModel` on the same model ARN (Amazon Titan Text Lite in
     `us-east-1`): the named probe is explicitly denied; A = 0, T = 47, and a named probe is
     explicitly denied, so GRANT is `none`, not `unknown`. Info, LLM-BPA-014.
   * The trap: Allow `*` on `*`, and Deny `bedrock:*` and `bedrock-mantle:*` on
     `arn:aws:bedrock:*:*:*`. The Deny does not match the resource `*` (`policy-evaluation.md`
     section 4), so every action stays allowed on `*`: GRANT `broad`, Critical with the reasons of
     example 1 except the admin-class one (CHECKS `LLM-BPA-003, LLM-BPA-004, LLM-BPA-005`), and W6 for the
     policy that holds the Deny, because the row can overstate access.
7. **A Deny on `aws:TokenIssueTime`** (the "revoke older sessions" pattern) on a user with
   `AdministratorAccess`: a Deny of `*` on `*` with `DateLessThan` or `DateLessThanEquals` on
   `aws:TokenIssueTime`. The key is in the table and absent for a long-lived credential; a positive
   date operator on an absent key is false, so the Deny does not apply (definite). The result is
   example 1, with the evidence
   `conditions: aws:TokenIssueTime in <policy>: absent, so that Deny does not apply`. An inactive
   access key on this user is Low, LLM-BPA-013, and would be Critical.
8. **A Deny without MFA** on a user with `AdministratorAccess`: a Deny with a `NotAction` list
   (`iam:*`) on `*` and `BoolIfExists` `aws:MultiFactorAuthPresent` `false`. The key is absent for
   a long-lived credential, and with `IfExists` an absent key makes the test true, so the Deny
   applies to every action that `iam:*` does not match: every invoke action is explicitly denied
   on `*` and on every probe, and no policy names a resource. GRANT `none`. Info,
   `Cannot invoke Amazon Bedrock models.`, LLM-BPA-014; the evidence is
   `conditions: aws:MultiFactorAuthPresent in <policy>: absent, so that Deny applies`. With `Bool`
   instead of `BoolIfExists`, the test on the absent key is false and the Deny does not apply, as
   AWS documents: the result is example 1.
9. **A condition the audit cannot evaluate.** Allow `bedrock:*` on `*`, and Deny `bedrock:*` on `*`
   with `NotIpAddress` on `aws:SourceIp`. The key is outside the table, so the Deny is unresolved.
   Least access: the Deny applies, the five `bedrock:` invoke actions are denied on `*` and on every
   probe, and no policy names a resource: `none`. Most access: the Deny does not apply: `broad`.
   The readings differ, so GRANT is `unknown`, with U2:
   `<user>: whether Amazon Bedrock models can be invoked depends on a condition the audit cannot evaluate (condition key aws:SourceIp in <policy>). Review it manually.`
   Active access key: Info, `Permissions could not be evaluated; review this principal manually.`,
   LLM-BPA-015, action `Review this principal manually: its permissions could not be evaluated.`
   Contrast: the Deny that the Amazon Bedrock
   documentation gives for `bedrock:CallWithBearerToken` when `bedrock:bearerTokenType` is
   `LONG_TERM`, on a user with `AmazonBedrockLimitedAccess`. `bedrock:InvokeModel` stays allowed on
   `*` in both readings, so GRANT stays `broad` and no U2 is added.
10. **`IAMSelfManageServiceSpecificCredentials` with `AmazonBedrockLimitedAccess`** (a policy
    variable). The first (version v1 at the time of writing, `Version` `2012-10-17`) allows
    `iam:CreateServiceSpecificCredential` on `arn:aws:iam::*:user/${aws:username}`. The S4 entry
    carries `Version` `2012-10-17`, so substitute the user's name: for a user `alice` with the path
    `/`, the entry becomes `arn:aws:iam::*:user/alice`, which matches the user's own ARN
    (`policy-evaluation.md` section 7.1 step 2). GRANT is `broad` from `AmazonBedrockLimitedAccess`,
    the escalation action counts, and `aws-marketplace:Subscribe` gets W1. Active access key:
    Critical, with the reasons `Can invoke Amazon Bedrock models.` and
    `Can also enable more models or create new API keys: iam:CreateServiceSpecificCredential.`;
    CHECKS `LLM-BPA-005`; action
    `Remove iam:CreateServiceSpecificCredential from <user>'s policies, then rotate access key <key> and move the workload to an IAM role.`
    An inactive key: Low, LLM-BPA-013, would be Critical. A user with another path, such as
    `/division/`, does not match, so nothing is added: Medium, LLM-BPA-010, as in IAM. Read literally,
    without the substitution, the audit would miss LLM-BPA-005 and report Medium.

## 5. Common evaluation mistakes

Each wrong conclusion is in quotes, followed by the right one.

- "One of the canary actions is allowed, so the user has `bedrock:*`." All six must be allowed on
  `*`. `AmazonBedrockLimitedAccess` allows some of them and is not `bedrock:*`.
- "The user's Deny on `aws:TokenIssueTime` blocks the key." A long-lived key's requests carry no
  `aws:TokenIssueTime`, so that Deny does not apply to the key.
- "`AmazonBedrockFullAccess` lets the user subscribe to Marketplace models." That statement applies
  only under `aws:CalledViaLast`, which the audit does not evaluate, so it is not counted and a
  warning says so; `bedrock:CreateMarketplaceModelEndpoint` still counts.
- "The Deny on `arn:aws:bedrock:*:*:*` makes GRANT `none`." Such a Deny does block real requests on
  those resources, but the audit tests the resource `*`, which the Deny does not
  match (`credential-api-quirks.md` section 3). GRANT stays `broad` and the tier is unchanged; add
  W6, because the row can overstate access.
- "`ReadOnlyAccess` cannot invoke." `ReadOnlyAccess` (v191 at the time of writing) allows
  `bedrock:CallWithBearerToken` and `bedrock-mantle:CallWithBearerToken`, which the audit counts as
  invoke actions, so such a user can invoke.
- "`AccountAccessKeysPresent` is 1, so the root key is active." It is 1 for an inactive key too. Read
  the report's `access_key_N_active`, or say the state is not confirmed.
- "The user has no MFA, so the API key is High." MFA does nothing for a bearer token and never counts
  for an API key.
- "The expired API key can be switched back on." Expired keys cannot be re-enabled; they stay Info.

## 6. Sources

For this file and `policy-evaluation.md`:

- [Global condition context keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html) (`policy-evaluation.md` section 5)
- [IAM policy elements: Variables and tags](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_variables.html) (`policy-evaluation.md` sections 4 and 5)
- [IAM JSON policy elements: Condition](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition.html) (`policy-evaluation.md` section 5)
- [IAM JSON policy elements: Condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html) (`policy-evaluation.md` section 5)
- [Multiple context keys or values](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-logic-multiple-context-keys-or-values.html) (`policy-evaluation.md` section 5)
- [Single-valued vs. multivalued context keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-single-vs-multi-valued-context-keys.html) (`policy-evaluation.md` section 5)
- [IAM JSON policy elements: Action](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_action.html) and [NotAction](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notaction.html) (`policy-evaluation.md` section 4)
- [IAM JSON policy elements: Resource](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_resource.html) and [NotResource](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notresource.html) (`policy-evaluation.md` section 4)
- [Policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) (`policy-evaluation.md` sections 5 and 6)
- [Permissions boundaries for IAM entities](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html) (`policy-evaluation.md` section 3)
- [GetAccountAuthorizationDetails](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetAccountAuthorizationDetails.html) and [GetContextKeysForPrincipalPolicy](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetContextKeysForPrincipalPolicy.html) (`policy-evaluation.md` sections 2 and 3)
- [Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html), [How Amazon Bedrock API keys work](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-how.html) and [Permissions for Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-permissions.html) (`policy-evaluation.md` section 5, and section 4 of this file)
- AWS managed policies: [AdministratorAccess](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AdministratorAccess.html), [PowerUserAccess](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/PowerUserAccess.html), [AmazonBedrockFullAccess](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonBedrockFullAccess.html), [AmazonBedrockLimitedAccess](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonBedrockLimitedAccess.html), [IAMSelfManageServiceSpecificCredentials](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/IAMSelfManageServiceSpecificCredentials.html) (sections 2 and 4)
