# Diagnosis Playbook — LLM-INV

Per-step methods for the review procedure in `SKILL.md`: which read-only call to make, which field to
read, what each result means, and the fallback when a call is denied or does not apply. Where this
file is more specific than a catalog row in `checks-model-invocation.md`, follow this file; the
catalog stays the source of check-ids, severities, and citations.

## Runtime limits seen in AWS DevOps Agent (2026-10-22)

Plan around these instead of discovering them mid-review. In the DevOps Agent runtime with the
standard `AIDevOpsAgentAccessPolicy` role:

| Call | Result | Use instead |
|---|---|---|
| any `cloudtrail` operation (`LookupEvents`) | blocked by the tool ("cloudtrail service operations are not allowed") | invocation logs (`identity.arn`, `modelId`), `AWS/Bedrock` metrics, or ask the user for the CloudTrail event / full error message |
| `iam:SimulatePrincipalPolicy` | denied by the tool | read the principal's policies (Step 4 calls) |
| `iam:GetAccountAuthorizationDetails` | denied | per-role `list-attached-role-policies` / `list-role-policies` / `get-role-policy` |
| `iam:GetPolicyVersion` on an AWS-managed policy (`arn:aws:iam::aws:policy/...`) | blocked | judge AWS-managed policies by name (Step 4) |
| `bedrock:GetFoundationModelAvailability` | AccessDenied | `GetFoundationModel` lifecycle plus successful invocations in logs/metrics |

Record each one you hit as unavailable, with the fallback you used. Other runtimes may allow these
calls; try once, never retry a denied call.

---

## Step 2 — Invocation logging (LLM-INV-001, 005, 010)

**Read** `bedrock get-model-invocation-logging-configuration`.

| Observed | Verdict |
|---|---|
| No `loggingConfig`, or neither `cloudWatchConfig` nor `s3Config` | Logging DISABLED → LLM-INV-001 CRITICAL |
| `cloudWatchConfig` and/or `s3Config` present | Logging ENABLED → LLM-INV-001 passes. Say which destination(s) exist and name them |

**Delivery flags gate payload parts, not whether a call is logged.** `textDataDeliveryEnabled`,
`imageDataDeliveryEnabled`, `embeddingDataDeliveryEnabled`, `videoDataDeliveryEnabled` (and
`audioDataDeliveryEnabled` where returned) control whether that modality's request/response *data* is
included. With `embeddingDataDeliveryEnabled: false` an embedding call is still recorded (operation,
`modelId`, `identity.arn`, token counts, and any text input when text delivery is on); only the
embedding output body is left out. Never report "embedding calls are not logged" from a flag alone.
Report each flag with its boolean. A flag that is off for a modality the account invokes is a
coverage note under LLM-INV-001 (INFO), never a separate finding or cause: for embeddings it only means
the vectors are not stored, which audits rarely need. A flag that is on for a modality nobody uses is
not worth mentioning beyond the flag list.

**Is it landing? (LLM-INV-005).** Logging configured is not logging delivered. Evidence, in order:

1. `AWS/Bedrock` metrics `ModelInvocationLogsCloudWatchDeliveryFailure` /
   `ModelInvocationLogsS3DeliveryFailure` / `ModelInvocationLargeDataS3DeliveryFailure` (and the
   matching `...Success` metrics) over the review window. Failures > 0 → LLM-INV-005.
2. CloudWatch destination: `logs describe-log-groups --log-group-name-prefix <logGroupName>`
   (`storedBytes`) and the newest stream's `lastEventTimestamp` from
   `logs describe-log-streams --order-by LastEventTime --descending --max-items 1`.
3. S3 destination: `s3api list-objects-v2 --prefix <keyPrefix>/AWSLogs/ --max-items 1` for a recent
   object.

Recent events while `Invocations` > 0 → delivery working, LLM-INV-005 passes. `Invocations` > 0 with
no recent events or delivery failures > 0 → LLM-INV-005. No `Invocations` datapoints → say there was
no traffic to deliver; do not pass or fail 005 on it.

**Destination protection (LLM-INV-010).** The catalog row describes the S3 case; apply the same test
to every destination present.

| Destination | Read | Weak when |
|---|---|---|
| CloudWatch Logs | `logs describe-log-groups` → `kmsKeyId`, `retentionInDays` | `kmsKeyId` absent (no customer-managed key). Report `retentionInDays` absent as "never expires" in the same finding's evidence |
| S3 | `s3api get-bucket-encryption`, `get-bucket-policy-status`, `get-public-access-block` | not SSE-KMS with a customer-managed key, or bucket not access-restricted |
| `largeDataDeliveryS3Config` | same as S3 | same as S3 |

If the user asks whether the logging role is scoped tightly (`cloudWatchConfig.roleArn`), read its
trust policy (`iam get-role`: principal `bedrock.amazonaws.com` with `aws:SourceAccount` /
`aws:SourceArn` conditions) and its permissions (`logs:CreateLogStream` and `logs:PutLogEvents` on
that log group only). Report what you read as evidence under LLM-INV-010 (destination access
restriction); there is no separate check-id for it.

Raise LLM-INV-010 when text (or image) data delivery is on and a destination is weak. Remediation for
a log group: `aws logs associate-kms-key --log-group-name <name> --kms-key-arn <cmk-arn>` (the key
policy must allow the CloudWatch Logs service principal) and
`aws logs put-retention-policy --log-group-name <name> --retention-in-days <n>`.

---

## Step 3 — Models in use, profiles, lifecycle (LLM-INV-002, 003)

**What is in use, not what exists.** `ListFoundationModels` lists what the Region offers. Take the
models actually invoked from:

1. `cloudwatch list-metrics --namespace AWS/Bedrock --metric-name Invocations` → every distinct
   `ModelId` dimension value.
2. Invocation logs, when enabled: `stats count() by modelId` over the window.

Name the source you used. A value is a **profile id** if it starts with a geographic prefix (`us.`,
`eu.`, `apac.`, and others) or with `global.`, or is an inference-profile ARN. A bare model id or a
`foundation-model/` ARN is a bare-model invocation. One model can appear under several forms (short
id, foundation-model ARN, profile id, profile ARN); group them by model before reporting.

**LLM-INV-002 fires only when a better option exists.** For each bare model id:

1. `bedrock list-inference-profiles --type-equals SYSTEM_DEFINED`, paging until `nextToken` is
   absent.
2. Look for a profile whose `models[]` contains that model in the Region.
3. Profile exists → raise LLM-INV-002 and cite the profile id. No profile → do **not** raise; say
   "no system-defined inference profile found for <model>" and move on.

A quick cross-check: `GetFoundationModel` → `inferenceTypesSupported`. `["ON_DEMAND"]` only is
consistent with no profile (observed for `amazon.titan-embed-text-v2:0`); `["INFERENCE_PROFILE"]` only
means the model cannot be called by bare id at all. The profile lookup above is still the evidence.

Do not assume an embedding model has or lacks a profile; look it up.

**LLM-INV-003.** For each model in use, read `modelLifecycle.status` from `ListFoundationModels` or
`GetFoundationModel` (resolve a profile to its member model first). `LEGACY` → LLM-INV-003. An EOL
model is gone from `ListFoundationModels`, and `GetFoundationModel` returns `ResourceNotFoundException`
with "This model version has reached the end of its life" → LLM-INV-003 (migrate). That error is
evidence, not a collection gap. For
`ACTIVE`, only the Bedrock dates count: the model card's "EOL no sooner than" date or the Model
lifecycle (Legacy) page. Provider-published dates differ and do not apply. If neither source states a
date, say "no EOL date published" — never estimate one. Legacy models can stop being available to
accounts that have not called them for 15 days or more, so a LEGACY model that suddenly returns
AccessDenied belongs in Step 5 as well.

---

## Step 4 — Invoke scope (LLM-INV-004)

1. Pick principals: start with the callers seen in invocation logs (`identity.arn`) or CloudTrail;
   then `iam list-roles` (page fully). If there are more than about 50 roles, review the callers plus
   roles whose name or trust policy mentions Bedrock, SageMaker, Lambda, or ECS, and disclose the
   bound.
2. For each: `iam list-attached-role-policies` and `iam list-role-policies`.
3. AWS-managed policies are known by name: `AmazonBedrockFullAccess`, `AdministratorAccess`,
   `PowerUserAccess` grant Bedrock invoke on `Resource: "*"` → LLM-INV-004. Report the policy name
   only.
4. Customer-managed and inline: `iam get-policy` + `get-policy-version` / `get-role-policy`; look
   for `bedrock:InvokeModel*`, `bedrock:*`, or `*` actions on `Resource: "*"`.

Remediation names the exact foundation-model and inference-profile ARNs the principal invokes, with
the account segment masked. Remember a cross-Region profile needs both the profile ARN and the
foundation-model ARNs in each member Region.

---

## Step 5 — Access diagnosis (LLM-INV-013, 014, 015)

Classify **before** prescribing. When the user asks for a policy up front, establish the deny class
first, then give the policy only if the class is an IAM implicit deny.

### 5a. Is the model still alive?

Before classifying a deny on a specific model, run `GetFoundationModel` on it. `ResourceNotFoundException`
with "has reached the end of its life" → the model is EOL: LLM-INV-003, migrate to an ACTIVE model
(cite the replacement profile ids from `ListInferenceProfiles`), and stop — no IAM policy fixes an EOL
model. `GetFoundationModelAvailability` reported `AVAILABLE` for an EOL model in testing, so it does
not rule EOL out.

### 5b. Find the failing calls

- A pasted error message is evidence; quote it with the account segment masked.
- CloudTrail (where your tooling allows it — see Runtime limits): `InvokeModel`,
  `InvokeModelWithResponseStream`, `Converse`, `ConverseStream` are **management events**, so
  `cloudtrail lookup-events --lookup-attributes AttributeKey=EventSource,AttributeValue=bedrock.amazonaws.com`
  (filter `errorCode` AccessDenied) finds them without a trail configured, for the last 90 days.
- `AWS/Bedrock` `InvocationClientErrors` shows that client errors happened. It also counts requests
  rejected for exceeding a quota, so it is not proof of an access problem on its own. Query it with
  and without the `ModelId` dimension: requests that fail before Bedrock resolves the model appear
  only in the series without it. That subset is **not** an authorization signature: an invalid or
  misspelled model identifier fails the same way (observed live: a `Converse` `ValidationException`
  "The provided model identifier is invalid"). It stays unclassified.
- **Never diagnose by elimination.** Ruling out SCP, EOL, and model access does not make the cause
  IAM. Without a failing call's message or event, LLM-INV-013 is not raised; the answer is "13 client
  errors, cause not determinable read-only — send the exact error message". Do not attribute failures
  to a role because its policy is narrow; show that role made the failing call or say you cannot.
- **Invocation logs are not an error source.** The documented log entry has no `errorCode` field
  (0 of 2,745 records carried one in testing), and failed calls are not shown to be logged. "No
  `errorCode` in logs" proves nothing about success or denial.

### 5c. Read the message

IAM access-denied messages end with a context clause that names the policy type: `with an explicit
deny in a <type> policy` or `because no <type> policy allows the <action> action`.

| Message contains | Points to |
|---|---|
| `with an explicit deny in a service control policy` or `because no service control policy allows` | SCP → LLM-INV-015 |
| `... in an identity-based policy` / `because no identity-based policy allows` | IAM → LLM-INV-013 |
| a permissions boundary, session policy, or VPC endpoint policy clause | IAM-side control in the account → LLM-INV-013, naming that policy type |
| `model is not available for this account` | account-level restriction, not IAM → LLM-INV-014 path |
| an agreement, subscription, or model-access message | model access → LLM-INV-014 |
| `is not authorized to perform: bedrock:InvokeModel on resource: <arn>` with **no** context clause | not classified by the message. Go to 5d–5f |

"Other models work from the same role" narrows it to something specific to this model: a Resource
list in the role's policy that omits this ARN (013), a deny scoped to this model (013/015), the
model's access agreement (014), or a LEGACY/EOL model (003, see 5a). Check those before
answering. When several policy types deny, the message names only one, so confirm with 5d–5f where
you can.

### 5d. Simulate (LLM-INV-013)

`iam simulate-principal-policy --policy-source-arn <role-arn> --action-names bedrock:InvokeModel
--resource-arns <model-or-profile-arn>`. Read `EvalDecision` (`allowed` / `implicitDeny` /
`explicitDeny`) and `OrganizationsDecisionDetail.AllowedByOrganizations`.
`AllowedByOrganizations: false` attributes the deny to an SCP even when you cannot read
Organizations. The simulator does not return SCP statements.

**If SimulatePrincipalPolicy is denied** (the DevOps Agent role is): record it as unavailable, then
read the principal's policies directly (Step 4 calls) and compare their `bedrock:InvokeModel*`
Resource list with the failing ARN. State which conclusion that leaves unconfirmed. Do not guess.

### 5e. Organizations (LLM-INV-015)

1. `organizations describe-organization`.
   - `AWSOrganizationsNotInUseException` → the account is not in an Organization; no SCP can apply.
     LLM-INV-015 is **not applicable**. Say so and point remaining denies at IAM or model access.
   - Succeeds → the account is in an Organization; continue.
2. `organizations list-policies-for-target --filter SERVICE_CONTROL_POLICY --target-id <account>`
   works only from the management account or a delegated administrator. From a member account expect
   AccessDenied: record it and rely on the message wording (5c) or `AllowedByOrganizations` (5d).
3. If an SCP deny is established but its name and statement cannot be read, escalate to the
   Organizations administrator with the denied action, resource, and the evidence you have. Do not
   prescribe an IAM change.

### 5f. Model access (LLM-INV-014)

In commercial Regions there is no access request to submit: most serverless models are enabled for
the account on first invocation. The Model access page applies to AWS GovCloud (US).

- Read `bedrock get-foundation-model-availability --model-id <id>` (needs AWS CLI 2.27.42 or later;
  if the command or permission is unavailable, record it). `agreementAvailability.status`:
  `AVAILABLE` (access exists), `PENDING` (still being set up; InvokeModel returns AccessDenied
  until AVAILABLE), `NOT_AVAILABLE`, `ERROR` (read `errorMessage`). Also report
  `authorizationStatus`, `entitlementAvailability`, `regionAvailability`.
- Prerequisites for the first invocation of a Marketplace-sold model: the invoking principal has
  `aws-marketplace:Subscribe`, `aws-marketplace:Unsubscribe`, `aws-marketplace:ViewSubscriptions`;
  the account has a valid payment method. Anthropic models also need the first-time-use form
  (`PutUseCaseForModelAccess`, or the console), once per account or at the Organization's
  management account.
- Remediation: make the first invocation from a principal that has the Marketplace permissions and
  satisfies any condition keys on `bedrock:InvokeModel`; for Anthropic, submit the use-case form
  first. If prerequisites are met, the model is supported in the Region, and AccessDenied persists,
  the account needs additional access: contact AWS.

---

## Step 6 — Invocation patterns (LLM-INV-006, 007, 008, 009, 011, 012)

**Window.** Use the user's window if given; otherwise the last 14 days ending now (UTC). State the
window in the output.

**Verify fields first.** For each field below, compare `filter ispresent(<field>) | stats count()`
with the total `stats count()` over the window before relying on it, and report what you found.

| Check | Signal | Field / metric |
|---|---|---|
| 008 Converse adoption | share of `InvokeModel*` vs `Converse*` | `operation` |
| 006 streaming | buffered `InvokeModel`/`Converse` on interactive callers; `TimeToFirstToken` exists only for streaming calls | `operation`, `identity.arn`; metric `TimeToFirstToken` |
| 011 maxTokens | requests with no cap; truncation rate | `input.inputBodyJson.inferenceConfig.maxTokens` (Converse) or `input.inputBodyJson.max_tokens` (native Anthropic); `output.outputBodyJson.stopReason` = `max_tokens` |
| 007 throttling | throttles in the window | metric `InvocationThrottles` (Sum) |
| 009 batch | high-volume, latency-tolerant traffic on on-demand | volume by `identity.arn` and hour; `bedrock list-model-invocation-jobs` |
| 012 Prompt Management | prompts managed and versioned | `bedrock-agent list-prompts` |

**Counts from different sources will not match.** `Invocations`, logged records, and
`ModelInvocationLogsCloudWatchDeliverySuccess` count different things over different spans (the log
group may be younger than the window; `Invocations` includes calls that later failed). Report the
numbers side by side and say the cause of a difference is unconfirmed. Do not explain it with a
mechanism you have not checked.

**Raise only what a signal confirms.**

- A user claim the data cannot confirm (for example "we run a nightly bulk job") → INFO
  (unconfirmed), naming the signal that is missing. Do not raise LLM-INV-009 from the claim alone.
- `InvocationThrottles` with no datapoints means nothing was throttled or nothing ran. It says nothing
  about whether retry/backoff is implemented → LLM-INV-007 "not evaluable" unless throttles > 0.
- Client code (backoff, streaming in the UI, prompts hard-coded) is not visible to read-only APIs.
  When the verdict depends on it, mark the check INFO (not evaluable from read-only signals).
