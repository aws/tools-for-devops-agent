# Service Specifics — Amazon Lex V2

Load only when the failing call is a Lex V2 runtime or builder operation.

Lex is the service where the **permission direction reversal** is most confusing. A caller
needs Lex runtime permissions to talk to the bot, and Lex needs Lambda invoke permissions
to call the code hook — but those are two entirely separate authorization paths that produce
the same symptom: the conversation stops working. The error surfaces at the caller in both
cases, with no indication of which direction failed.

## Applicable hops

| Call | Hop 1 | Hop 2 | Hop 3 | Hop 4 | Hop 5 | Hop 6 |
|---|---|---|---|---|---|---|
| `RecognizeText`, `RecognizeUtterance`, `StartConversation` | ✓ | n/a | n/a | n/a | ✓ | ✓ |
| `CreateBot`, `UpdateBot`, `BuildBotLocale` | ✓ | n/a | n/a | n/a | n/a | ✓ |

The Bot→Lambda code-hook invocation (the Lambda function's resource-based policy granting
`lexv2.amazonaws.com`) is a **second authorization chain**, not a sixth-hop row. `report-format.md`
mandates exactly one six-hop table per diagnosis, so do not add it as a table row — render it
as a `### Service-specific:` finding (Mode 3 below), where its Lambda resource-policy evidence
and the verified `DependencyFailedException` message carry the diagnosis.

Runtime calls (`RecognizeText`, `RecognizeUtterance`, `StartConversation`) do not pass a
role. There is no execution role in a Lex conversation — the bot itself is the actor when
calling Lambda. This means hops 2–4 are `NOT_APPLICABLE`, not skipped.

**Hop 5 is where Lex departs from every other service in this skill.** In SageMaker or
Bedrock Agents, hop 5 is a resource policy on the *target* resource the execution role
accesses. In Lex, hop 5 is the Lambda function's resource-based policy granting
`lexv2.amazonaws.com` permission to invoke it. The Lex service principal is the caller, not
the customer's role.

## Actions and resource ARNs

| Operation | IAM action | Resource ARN shape |
|---|---|---|
| Send text to bot | `lex:RecognizeText` | `arn:aws:lex:<region>:<account>:bot-alias/<botId>/<aliasId>` |
| Send audio to bot | `lex:RecognizeUtterance` | same |
| Streaming conversation | `lex:StartConversation` | same |
| Create/update bot | `lex:CreateBot`, `lex:UpdateBot` | `arn:aws:lex:<region>:<account>:bot/<botId>` |
| Build bot locale | `lex:BuildBotLocale` | `arn:aws:lex:<region>:<account>:bot/<botId>` |

**The runtime ARN targets the bot-alias, not the bot.** A policy granting access to
`arn:aws:lex:<region>:<account>:bot/<botId>` does NOT grant `RecognizeText` — the
runtime actions require the `bot-alias/` ARN path. This is the single most common
authoring error for Lex callers.

Confirmed by policy simulation: a statement allowing `lex:RecognizeText` on
`arn:aws:lex:<region>:<account>:bot/<botId>`, evaluated against the resource
`arn:aws:lex:<region>:<account>:bot-alias/<botId>/<aliasId>`, returns `implicitDeny`. The
same statement written against the `bot-alias/` ARN returns `allowed`. The two ARNs differ
at the resource-type segment, so no amount of wildcarding inside `bot/<botId>` will reach a
bot alias.

The mechanism matters for the finding. This is not Lex rejecting a malformed ARN — it is
IAM resource matching failing to find any statement that covers the resource, which is an
**implicit** deny. Report it with the hop 1 implicit-deny body from `finding-logic.md`, and
propose a scoped allow on the `bot-alias/` ARN. Treating it as an explicit deny would send
the customer looking for a denying statement that does not exist.

## The three failure modes that look identical

All three produce a conversation failure. The first two return `AccessDeniedException`
at the caller. The third returns a `DependencyFailedException` or a silent fulfillment
failure (the bot responds with the "Failure" path message, not an access error).

| # | Direction | What is missing | Observed behavior | Who needs the fix |
|---|---|---|---|---|
| 1 | Caller → Bot | Caller lacks `lex:RecognizeText` on the bot-alias ARN | `AccessDeniedException` to caller | Caller's identity policy |
| 2 | Caller → Bot | A same-account bot/alias resource policy carries an explicit `Deny`, or scopes the runtime actions away from this principal | `AccessDeniedException` to caller | Bot's resource-based policy (same account only) |
| 3 | Bot → Lambda | Lambda function lacks a resource-based policy granting `lexv2.amazonaws.com` invoke | `DependencyFailedException` at caller, OR silent failure (bot takes the "Failure" branch) | Lambda function's resource-based policy |

**Mode 3 is real, and it is verified.** Built end to end: a bot alias with a code hook
wired and no Lambda resource policy. `RecognizeText` failed; adding a single
`lambda:InvokeFunction` statement for `lexv2.amazonaws.com` was the only change made, and
the same call then succeeded. So the Lambda resource policy is genuinely required, and
nothing adds it on your behalf — `lambda:GetPolicy` returned `ResourceNotFoundException`
both before the code hook was attached and after, meaning attaching a code hook via
`UpdateBotAlias` does **not** create the permission.

**The caller does see an explicit error, and it names the cause.** With a fulfillment code
hook and no failure response configured, the observed result is:

```
DependencyFailedException: Invalid Bot Configuration: Access denied while invoking
lambda function arn:aws:lambda:<region>:<account>:function:<functionName> from
arn:aws:lex:<region>:<account>:bot-alias/<botId>/<aliasId>. Please check the policy on
this function.
```

That message carries the whole diagnosis: both ARNs and the instruction to check the
function's policy. **When it is present, report Mode 3 directly from it** rather than
traversing the chain. Do not describe this mode as undiagnosable from the caller's side.

The "silent failure" variant is the case where a failure response *is* configured, so Lex
catches the error and follows the failure branch instead of surfacing it. That path was not
reproduced here, so treat it as the harder variant rather than the default one.

**Do not send the diagnosis to the Lambda's CloudWatch Logs for this.** Lambda rejects the
invoke at the resource-policy layer before any execution, so the failing attempt produces
no log stream, no log events and no `Invocations` datapoint. Measured: the failing call
logged zero invocations, and the function's log group was only created by the first
*successful* invocation after the permission was added. An empty log group is therefore
consistent with Mode 3 rather than evidence against it, and the absence of a `Task timed
out` or `AccessDenied` line there means nothing either way.

CloudTrail would record the `lambda:InvokeFunction` denial by principal
`lexv2.amazonaws.com`, in the Lambda function's account rather than the bot's where they
differ — but v1 established `cloudtrail:LookupEvents` as `RuntimeUnavailable`, so treat
that as corroboration if it happens to be available, never as the evidence path.

**Mode 2 is a same-account resource-policy denial.** A bot or bot-alias policy can exist
in the same account and carry a `Deny`, or scope the runtime actions to specific
principals — so it can deny a caller whose identity policy is otherwise correct. It is
**not** a cross-account mechanism: Lex V2 rejects cross-account resource policies outright
(see "Bot resource-based policy (Mode 2)" below). Because a same-account bot/alias policy
can be the operative denial at hop 5, it must **always** be read with
`lex:DescribeResourcePolicy` — never assumed absent.

## Non-denial causes and the closed vocabulary

Lex is the first service in this skill with causes that **resemble an access error but are
not a denial**. Bedrock's four non-IAM causes all still produce a real
`AccessDeniedException`, so they carry `DENIED_BY` (service-specific). Neither Lex cause
below does: one returns a non-access error, the other returns HTTP 200 and fails inside the
conversation. Assigning `DENIED_BY` to either would assert a denial that never happened,
which is the error class this skill exists to prevent.

The six-token vocabulary in `finding-logic.md` is closed over **hop verdicts and finding
headings**, and neither cause is a hop verdict. No token is added. Instead:

- Every hop row keeps its own evidence-based verdict. A chain where nothing denied is
  reported as such, not bent to match the symptom.
- The finding renders under `### Service-specific: <cause name>`, which
  `report-format.md` already defines.
- The root-cause line takes a third form, alongside the hop form and `❓ Undetermined`:

      **Root cause:** 🚫 Not an access denial — <one-line statement>

  This extends the root-cause line, which is already polymorphic. It does not extend the
  verdict vocabulary. See `finding-logic.md` "Root cause selection", case 3b.

A non-denial root cause is only ever emitted from evidence that was actually read. Where
the establishing read was unavailable, the cause is `CANNOT_DETERMINE` naming the missing
operation. "The bot does not work and no hop denied" is not grounds for either.

## Non-IAM cause 1 — Bot alias not built or not deployed

A bot alias pointing to a draft version that has not been built returns a runtime error
that is NOT an access error, but customers conflate the two because the bot "doesn't
work."

**The error is `ResourceNotFoundException`, not `BadRequestException`.** `RecognizeText`
documents eight errors and `BadRequestException` is not among them, so any guidance naming
it is wrong. Measured against a locale in `NotBuilt` state:

```
ResourceNotFoundException: The provided BotId/BotLocale combination is not valid.
Please update the BotId/BotLocale combination and retry your request.
```

Two things follow, and both matter for the finding.

**The alias-level and locale-level failures are distinguishable by message.** A bad or
missing alias gives `<botId>/<aliasId> is not a valid BotId/BotAliasId combination`; an
unusable locale gives the `BotId/BotLocale` message above. Use the wording to tell which
layer failed.

**The error cannot tell you *why* the locale is unusable.** A locale that exists but was
never built and a locale that was never created at all return the byte-identical
`BotId/BotLocale` message. So the exception establishes only that the combination is not
serviceable, never that something is unbuilt. The `botAliasStatus` and `botLocaleStatus`
reads are the evidence; the error is the prompt to go and read them. This is why the
finding below is gated on the status read rather than the error.

**How to check**
- `lex:DescribeBotAlias` — inspect `botAliasStatus`. Valid values are `Creating`,
  `Available`, `Deleting`, `Failed`. Only `Available` serves runtime traffic.
- `lex:DescribeBotVersion` for the version the alias points to

**Finding body**
- verdict: none — this is not a hop verdict. See "Non-denial causes and the closed
  vocabulary" above. Leave all six hop rows at their evidence-based verdicts.
- root-cause line: "**Root cause:** 🚫 Not an access denial — bot alias `[aliasId]` is `[status]`, not `Available`"
- gate: emit only when `botAliasStatus` was read for this diagnosis. If
  `lex:DescribeBotAlias` returned `AgentAccessDenied` or `RuntimeUnavailable`, this cause
  is `CANNOT_DETERMINE` naming that operation. Never infer it from the absence of a denial
  elsewhere in the chain.
- body: "Bot alias `[aliasId]` status is `[status]`, not `Available`. This is not a permissions issue, and no identity policy, resource policy or SCP change will resolve it. The bot version the alias points to must build successfully before the alias can serve runtime traffic. A `[status]` alias additionally means `[Creating: the build is still in progress, so retry once it reaches Available | Deleting: the alias is being removed and will not serve traffic again | Failed: the last build did not complete, and that build failure is the thing to investigate]`."

## Non-IAM cause 2 — Lambda code hook timeout

**This is never a root cause.** When the code hook exceeds its timeout, Lex returns the
"Timeout" response path and the `RecognizeText` call itself returns HTTP 200. There is no
API-layer failure to diagnose, and Lex runtime calls do not appear in CloudTrail, so the
skill cannot establish that a timeout occurred on the failing turn. Reporting it as the
cause would be a guess presented as a finding.

What the skill *can* do is compare two readable numbers and state which layer gives up
first. That is a static configuration check, and it needs no permission beyond what the
shared chain reads already grant.

**The two budgets**

| Budget | Where it is set | Readable? |
|---|---|---|
| Lambda function timeout | `lambda:GetFunctionConfiguration` → `Timeout`, in seconds | Yes |
| Lex code hook timeout | 30s by default; raised with the `x-amz-lex:codehook-timeout-ms` session attribute, set in milliseconds, maximum 120s | No — the client supplies it per request; it is not stored on the bot |

Because the Lex budget is a client-side value, assume the 30s default and say that it was
assumed. Never present an assumed budget as an observed one.

**How to check**
- `lex:DescribeBotAlias` → `botAliasLocaleSettings[].codeHookSpecification.lambdaCodeHook.lambdaARN`
  for the function wired to the alias
- `lambda:GetFunctionConfiguration` on that ARN for `Timeout`
- `logs:FilterLogEvents` on the function's log group for `Task timed out`, which is what
  distinguishes a timeout from an `AccessDenied`

**Where it renders** — in `What This Diagnosis Cannot Tell You`, as a named alternative
explanation. Emit when the chain shows no denial and a code hook is configured on the
alias. Do not emit a Service-specific finding, and do not touch the root-cause line.

**Body**
- "A code hook is configured on this alias (`[functionName]`), and a code hook timeout produces the same user-visible symptom as a permission failure: the bot replies on its Timeout path rather than returning an access error. The function is configured with a `[N]`s timeout against an assumed Lex budget of 30s — the default. The `x-amz-lex:codehook-timeout-ms` session attribute can raise that to 120s, but the client supplies it per request, so its actual value for this call was not observed. `[Lex gives up first, so the function may be completing after Lex has stopped waiting | The function gives up first, so Lex receives an error rather than reaching its own timeout]`. Whether a timeout occurred on the failing turn was not established, because Lex runtime calls do not appear in CloudTrail. Confirm in the function's log group `[log group]`, where a timeout appears as `Task timed out` and a permission failure appears as `AccessDenied`."

## Non-IAM cause 3 — Code hook disabled (hook never runs, bot behaves as if it succeeded)

Likely more common than Mode 3, and the opposite failure: the hook is wired but switched
off, so Lex skips it and proceeds as though it returned successfully. Two settings cause this:

- `enableCodeHookInvocation: false` on the dialog/fulfillment code-hook setting — Lex acts
  as if the code hook returned successfully without ever invoking the Lambda.
- fulfillment `enabled: false` — the fulfillment hook is not run at all.

The call returns HTTP 200 and the conversation "works," but the custom logic never executed,
so the customer reports wrong/empty results that look like a broken integration or a silent
permission failure. No IAM hop denied; no Lambda was invoked.

**How to check**
- `lex:DescribeIntent` / the alias's `botAliasLocaleSettings[].codeHookSpecification` —
  inspect `enableCodeHookInvocation` and the fulfillment `enabled` flag.

**Finding body**
- verdict: none — not a hop verdict. See "Non-denial causes and the closed vocabulary".
- root-cause line: "**Root cause:** 🚫 Not an access denial — code hook is configured but
  `[enableCodeHookInvocation=false | fulfillment enabled=false]`, so Lex never invoked the Lambda"
- body: "The code hook on `[intent/alias]` is configured but disabled
  (`[enableCodeHookInvocation=false | fulfillment enabled=false]`). Lex treats the hook as
  if it returned successfully and never invokes the function, so the custom logic does not
  run. This is a configuration setting, not a permissions issue — the Lambda resource policy
  and the caller's IAM are irrelevant to it. Enable the setting to make the hook run."

## Lambda resource-based policy for Lex (Mode 3 fix)

The Lambda function must grant `lexv2.amazonaws.com` permission to invoke it. The
recommended pattern includes confused-deputy protection:

```json
{
  "Effect": "Allow",
  "Principal": {
    "Service": "lexv2.amazonaws.com"
  },
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:<region>:<account>:function:<functionName>",
  "Condition": {
    "StringEquals": {
      "aws:SourceAccount": "<botOwnerAccountId>"
    },
    "ArnLike": {
      "aws:SourceArn": "arn:aws:lex:<region>:<botOwnerAccountId>:bot-alias/<botId>/<aliasId>"
    }
  }
}
```

Without this statement every code hook invocation fails, and the failure is **not** silent
in the default configuration — see the verified `DependencyFailedException` above. Treat a
silent failure as the variant that needs a configured failure response, not the norm.

Verified for the API path: attaching a code hook with `UpdateBotAlias` does not create this
permission. `lambda:GetPolicy` returned `ResourceNotFoundException` both before and after
the attach, and the invocation failed until the statement was added by hand. So for bots
built via CloudFormation, CDK or the API, assume the permission is absent unless read.

The console is widely reported to add the permission for you when you select a function in
the bot configuration, which is why this is mostly an API-and-IaC problem. **That console
behaviour is untested here** — only the API path was exercised. Do not state it as fact in
a report; read `lambda:GetPolicy` and find out.

**Match the condition keys case-insensitively when reading this policy.** IAM condition
keys match case-insensitively, and the authored form and the stored form differ in
practice: `lambda add-permission` writes `AWS:SourceAccount` and `AWS:SourceArn`, while the
block above and most documentation use `aws:`. A diagnosis that string-matches on `aws:`
will miss a policy AWS itself created and wrongly report the statement as absent. Lower-case
both sides before comparing.

**Cross-account Lambda**: If the Lambda function is in a different account than the
bot, the function's resource-based policy must name the bot's account in `SourceAccount`.
The Lambda function's own account's IAM policies are irrelevant here — only the
function's resource-based policy matters for service principal invocations.

## Bot resource-based policy (Mode 2) — cross-account is NOT supported

A bot or bot-alias resource-based policy (a *bot policy* / *bot alias policy*) is a
**same-account** control only. Amazon Lex V2 does not support cross-account or cross-region
resource policies: per the docs, "You can't use cross-account or cross-region policies with
Amazon Lex V2. If you create a policy for a resource with a cross-account or cross-region
ARN, Amazon Lex V2 returns an error," and `CreateResourcePolicyStatement` "can't create a
resource policy statement that allows cross-account access." So there is **no** valid
`Principal: { "AWS": "arn:aws:iam::<otherAccount>:role/..." }` bot policy — do not propose
one as a cross-account fix; Lex rejects it at create time.

What a same-account bot/alias policy legitimately does is add `Deny` or scope access to
principals within the same account — AWS's own "allow a user to have a conversation"
example denies `UpdateBot`/`DeleteBot` while allowing the runtime actions. It can therefore
be the cause of a same-account denial, which is why hop 5 must always read it (see below).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::<sameAccountId>:role/<callerRole>" },
      "Action": [
        "lex:RecognizeText",
        "lex:RecognizeUtterance",
        "lex:StartConversation"
      ],
      "Resource": "arn:aws:lex:<region>:<sameAccountId>:bot-alias/<botId>/<aliasId>"
    }
  ]
}
```

For an AWS **service** that calls Lex (Connect, a Lambda calling back into Lex), the
resource policy uses `"Principal": {"Service": "connect.amazonaws.com"}` with
`aws:SourceAccount` / `aws:SourceArn` conditions — a service principal, not a
cross-account IAM principal. A genuinely cross-account caller cannot be authorized through
a Lex resource policy at all; that access has to be brokered another way (e.g. the caller
assumes a role in the bot's account).

## Diagnostic sequence

1. **Check the ARN in the caller's policy.** Is it `bot-alias/` or `bot/`? If `bot/`,
   that is the cause — fix the ARN shape.
2. **Read the bot/alias resource policy** with `lex:DescribeResourcePolicy` — always, not
   only cross-account. A same-account policy can carry a `Deny` that is the operative cause
   at hop 5. (A cross-account resource policy cannot exist — Lex rejects it — so cross-account
   access is never fixed here.)
3. **Does the bot use code hooks?** If the caller's error is
   `DependencyFailedException: Invalid Bot Configuration: Access denied while invoking
   lambda function ...`, stop — that message is the diagnosis and names both ARNs. If not,
   read the Lambda's resource-based policy for `lexv2.amazonaws.com` via
   `lambda:GetPolicy`. A function wired via API, CloudFormation or CDK should be assumed to
   lack the permission until read. Do not look for evidence in the function's CloudWatch
   Logs; a denied invoke never reaches the function and leaves no trace there.
4. **Is the bot alias `Available`?** If not, that is the root cause, reported in the
   non-denial form — not an access issue. See non-IAM cause 1.
5. **Is a code hook configured, and which timeout budget is smaller?** This is never the
   root cause. It renders as a limitation, not a finding. See non-IAM cause 2.

## Runtime permission reality and condition-key matching

Coverage is bounded by what the DevOps Agent role can read. This diagnosis would use `lex:DescribeBotAlias`/`DescribeBot` and `lex:DescribeResourcePolicy` (Mode 1/2 reads) plus the shared `lambda:GetPolicy` (the Mode-3 bot-alias to Lambda invoke-policy read), `iam:GetRole`/`GetRolePolicy`, and `organizations:*`. Confirmed by reading `AIDevOpsAgentAccessPolicy` (v12, 2026-11-02): it grants **no** `lex:*` actions - like Textract and Transcribe, Lex is unreadable without the opt-in read policy, so the caller-to-bot (Mode 1) and bot/alias resource-policy (Mode 2) reads come back refused. The Lambda side IS readable: `lambda:GetPolicy` is granted, so the Mode-3 code-hook invoke-policy check works. Until the Lex read delta is deployed, state the gap plainly and mark the affected `lex:*` reads `CANNOT_DETERMINE` naming the operation rather than inferring a pass.

Match condition keys case-insensitively - `lambda add-permission` writes `AWS:SourceArn`/`AWS:SourceAccount` (capitalized), IAM evaluates them case-insensitively, and a case-sensitive match can wrongly report a present statement as missing.

## References

Covers the two non-denial causes only. Extend as the remaining sections are confirmed.

- Lex V2 `DescribeBotAlias` (`botAliasStatus` values, `codeHookSpecification`): https://docs.aws.amazon.com/lexv2/latest/APIReference/API_DescribeBotAlias.html
- Code hook timeout and the `x-amz-lex:codehook-timeout-ms` session attribute: https://docs.aws.amazon.com/lexv2/latest/dg/context-mgmt-session-attribs.html
- Code hook Success / Failure / Timeout response paths: https://docs.aws.amazon.com/lexv2/latest/dg/paths-code-hook.html
- Lambda `GetFunctionConfiguration` (`Timeout`): https://docs.aws.amazon.com/lambda/latest/api/API_GetFunctionConfiguration.html
- Attaching a Lambda code hook to a bot alias: https://docs.aws.amazon.com/lexv2/latest/dg/lambda-attach-api.html
- Lex V2 resource-based policies (bot policy, bot alias policy): https://docs.aws.amazon.com/lexv2/latest/dg/security_iam_service-with-iam.html
- Cross-account resource policies NOT supported ("returns an error"): https://docs.aws.amazon.com/lexv2/latest/dg/security_iam_service-with-iam.html
- CreateResourcePolicyStatement — no cross-account access: https://docs.aws.amazon.com/lexv2/latest/APIReference/API_CreateResourcePolicyStatement.html
- Resource-based policy examples (DescribeResourcePolicy, same-account Deny example): https://docs.aws.amazon.com/lexv2/latest/dg/security_iam_resource-based-policy-examples.html
