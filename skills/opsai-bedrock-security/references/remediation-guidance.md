# Remediation Guidance

The audit only advises. It never changes a credential or a policy, and it never claims a change was
made. Every action in the report is one the customer takes, after review.

## 1. Preferred outcome

For every finding, the preferred outcome is to replace the long-lived credential with a short-lived
one:

* IAM Identity Center for people;
* IAM roles for workloads that run on AWS;
* OIDC federation or IAM Roles Anywhere for systems outside AWS.

## 2. Controls while a long-lived key has to stay

Where a key cannot be replaced yet, these controls reduce what it can do and make its use visible:

* Scope its permissions to the Amazon Bedrock actions and models it needs. The policies in
  `assets/` are a starting point.
* Add IAM condition keys that limit where it can be used from, such as source IP or VPC endpoint.
* Set AWS Budgets and Cost Anomaly Detection alerts on Amazon Bedrock spend.
* Keep AWS CloudTrail on, and turn on Amazon Bedrock model invocation logging where you need request
  detail.
* Enable GuardDuty AI Protection.

Run the audit again after a change to confirm the tier has dropped.

## 3. Suggested policies

Four templates ship with the skill. Each is a policy document with placeholders, and every statement
ID starts with `ReviewBeforeApplying`, so the intent stays visible after someone copies it. Never
apply, attach or create any of them yourself, and never offer to: hand the template, or the command
that would apply it, to the customer to review and apply. Give each one with its AWS documentation
link from section 4.

| Template | Type | What it does | When to present it |
|---|---|---|---|
| `assets/scp-deny-bedrock-to-iam-users.json` | Service control policy | Denies the four invoke actions to IAM users and to the account root user (`aws:PrincipalType` `User` or `Account`). IAM roles and IAM Identity Center users are unaffected | Name it in every full report. Show its content when the requester asks how to keep long-lived keys away from Amazon Bedrock, or asks what such an SCP would break |
| `assets/policy-deny-bedrock-api-keys.json` | Identity policy for users, groups or roles that should never use Amazon Bedrock API keys | Blocks **every** Amazon Bedrock API key, short-term ones included: denies using any API key through both endpoints (`bedrock:CallWithBearerToken`, `bedrock-mantle:CallWithBearerToken`) and creating a new long-term key (`iam:CreateServiceSpecificCredential` where `iam:ServiceSpecificCredentialServiceName` is `bedrock.amazonaws.com`). Never present it as keeping short-term keys working | Name it in every full report. Show its content when a finding involves API keys (LLM-BPA-005, LLM-BPA-009, LLM-BPA-010 or LLM-BPA-013 on an API key), the requester asks how to fix it, and no API key should work at all |
| `assets/policy-deny-long-term-bedrock-api-keys.json` | Identity policy for the IAM users that hold long-term keys and the identities that could create them | Blocks **long-term** Amazon Bedrock API keys only: denies `bedrock:CallWithBearerToken` when `bedrock:BearerTokenType` is `LONG_TERM`, and `bedrock-mantle:CallWithBearerToken` when `bedrock-mantle:BearerTokenType` is `LONG_TERM`, and creating a new long-term key (the same `iam:CreateServiceSpecificCredential` deny). Short-term keys keep working | Name it in every full report. Show its content when the requester wants to phase out or forbid long-term keys, or to block them without breaking short-term ones (section 3.3) |
| `assets/scp-restrict-bedrock-regions-models.json` | Service control policy | One statement denies the invoke actions outside the approved Regions (`aws:RequestedRegion`). The other denies the model-invocation actions for models not on the approved list | Only when the requester names the Regions they use or the model IDs they approve. Otherwise do not mention it beyond one line saying it needs those lists |

### 3.1 Filling the placeholders

* **User-deny SCP.** The `ArnNotLike` block lists the IAM users whose workloads still need their keys
  and must keep working. Write one entry per user as `arn:aws:iam::<account-id>:user/<user name>`,
  leaving `<account-id>` for the customer to fill in: never write a real account ID. If there are no
  exceptions, say to delete the whole `ArnNotLike` block. Without it, the SCP **breaks every workload
  still running on IAM user keys**, so list those first.
* **Region and model SCP.** Keep only the statement for what the requester named. Put each Region in
  the `aws:RequestedRegion` list. For each approved model ID, write two `NotResource` entries: the
  `foundation-model` ARN and the `inference-profile` ARN that ends in `.<model ID>`. The model
  statement leaves out the two bearer-token actions, which have no model resource. Application
  inference profiles are not matched by model ID; say they need a separate review.
* **API key policies.** No placeholders.

Show a filled template as a JSON code block, below the sentence
`Review before applying. Test every service control policy on a sandbox organizational unit first.`

### 3.2 What a user-deny SCP would affect

When the requester asks what an SCP that denies Amazon Bedrock to IAM users would break, answer from
the audit rows:

* Affected now: every row with an **active** credential that can invoke (Critical, High, Medium and
  Low rows other than LLM-BPA-013). API key users are IAM users, so their API keys are denied too. The
  root account (`Account`) is denied as well.
* Affected if re-enabled: LLM-BPA-013 rows. An inactive key does not work today.
* Not affected: IAM roles and IAM Identity Center users, which the audit does not cover, and every
  principal in the organization's management account, because service control policies do not
  affect the management account.
* Check first: rows with GRANT `unknown` (LLM-BPA-015) and users in "Not evaluated (work budget)".

List the affected users as candidates for the exception list, for the customer to confirm with the
workload owners. Last use (`LAST USED`) shows whether a key is in use, not whether it calls Amazon
Bedrock, so it cannot tell which workloads use Amazon Bedrock today.

For this question the action is the rollout, given as steps for the customer in this order; the
credentials' own catalog actions may follow it:

1. Review the list of affected users with the workload owners, and decide for each one: an
   exception in the template's `ArnNotLike` block, or a move of its workload to an IAM role first.
   Without that, the SCP breaks every workload still running on IAM user keys.
2. Test the SCP on a sandbox organizational unit first.
3. Then attach it to the organizational units or accounts it is meant for.

The answer also says that IAM roles and IAM Identity Center users are not affected by this SCP and
that the audit does not cover them, and that the audit does not evaluate SCPs or RCPs, so the
policies already in the organization are not taken into account. Give the link to
[Service control policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html).

### 3.3 Phasing out long-term API keys

When the requester wants to stop using long-term Amazon Bedrock API keys but keep short-term ones,
answer from the audit:

* **Who holds a long-term key:** every Amazon Bedrock API key in the inventory (the account-wide
  `iam:ListServiceSpecificCredentials`), with its IAM user, status and expiry, and what it can do in
  Amazon Bedrock.
* **Who could create one today:** every evaluated user whose allowed actions include
  `iam:CreateServiceSpecificCredential` (on `*` or its own ARN), whatever its tier. The audit does
  not cover the other identities that can hold the same permission: IAM users with no access key
  or API key (console-only users, for example) are not inventoried, and IAM roles and IAM Identity
  Center users are out of scope. Say so.
* **How to block long-term keys and keep short-term ones:**
  `assets/policy-deny-long-term-bedrock-api-keys.json`. Its two bearer-token statements
  deny only requests made with a long-term key (`LONG_TERM`), on both endpoints, and its third
  statement denies creating new long-term keys. The customer attaches it to the IAM users that hold
  long-term keys and to the identities that could create them, or puts the same statements in a
  service control policy for a whole account, tested on a sandbox organizational unit first.
* **What to do with the keys that exist:** for the customer, after the workloads have moved:
  deactivate each key (`iam:UpdateServiceSpecificCredential`, status `Inactive`; it can be turned
  back on), then delete it (`iam:DeleteServiceSpecificCredential`, permanent). Deleting a key does
  not delete its IAM user.

Never give `policy-deny-bedrock-api-keys.json` for this: it has no `LONG_TERM` condition, so it
blocks short-term keys too. If the requester wants that template anyway, say plainly that it stops
every Amazon Bedrock API key.

Short-term keys are not IAM credentials. Each is a pre-signed URL that inherits the credentials and
the expiry of the session that made it: at most 12 hours, or less when the session ends sooner. No
audit can list them, and IAM cannot deactivate, reset or delete one. To stop them before they
expire, deny `bedrock:CallWithBearerToken` and `bedrock-mantle:CallWithBearerToken` with
`SHORT_TERM` to the identities that make them, or end those sessions.

The Service Authorization Reference lists the condition keys as `bedrock:BearerTokenType` and
`bedrock-mantle:BearerTokenType`; the Amazon Bedrock user guide writes them
`bedrock:bearerTokenType` and `bedrock-mantle:bearerTokenType`. Condition key names are not
case-sensitive, so both spellings match.

### 3.4 Usage that nobody recognizes

When the requester asks which credentials could have made Amazon Bedrock calls they do not
recognize, and what to rotate or block first:

* Rotate or restrict first the credentials that can invoke, in the fix-first order of the rows
  (`checks-credentials.md` section 5), each with its own catalog action.
* Blocking IAM users (the user-deny SCP) or API keys (the API key policies) stops only long-lived
  credentials. Calls made through IAM roles, federated users and IAM Identity Center users go on,
  and the audit does not cover them.
* Only AWS CloudTrail (and Amazon Bedrock model invocation logs, where turned on) shows which
  principal made the calls, so it is where to look for their source. The audit shows who could
  make them, not who did (`checks-credentials.md` section 8).

## 4. AWS documentation

* [IAM best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
* [Service control policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
* [Service control policy examples](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps_examples.html)
* [SCP syntax](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps_syntax.html): a Condition element in a deny statement, as section 3.3 uses it
* [Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html): short-term and long-term keys, and how long each lasts
* [Control permissions for generating and using Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-permissions.html): `iam:CreateServiceSpecificCredential` with `iam:ServiceSpecificCredentialServiceName`, both `CallWithBearerToken` actions, and the bearer token type values `SHORT_TERM` and `LONG_TERM` (section 3.3 and both API key templates)
* [Handle compromised long-term and short-term Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-revoke.html): deactivate, reset or delete a long-term key; short-term keys cannot be revoked one by one
* [Actions, resources, and condition keys for Amazon Bedrock](https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock.html): `bedrock:CallWithBearerToken` and `bedrock:BearerTokenType`
* [Actions, resources, and condition keys for Amazon Bedrock Powered by AWS Mantle](https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock-mantle.html): `bedrock-mantle:CallWithBearerToken` and `bedrock-mantle:BearerTokenType`
* [Actions, resources, and condition keys for AWS Identity and Access Management](https://docs.aws.amazon.com/service-authorization/latest/reference/list_iam.html): `iam:CreateServiceSpecificCredential` and `iam:ServiceSpecificCredentialServiceName`
* [IAM JSON policy elements: Condition](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition.html): condition key names are not case-sensitive
* [AWS global condition context keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html)
* [GuardDuty AI Protection](https://docs.aws.amazon.com/guardduty/latest/ug/ai-protection.html)
