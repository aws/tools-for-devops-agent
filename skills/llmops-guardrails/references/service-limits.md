# Guardrail Limits and Quotas

What Amazon Bedrock documents about count, size and rate limits on guardrails. Use it when an error or
a question is about a guardrail limit: too many topics or words, a request that is "too long", or
throttling on guarded calls. The numbers are AWS defaults checked on 2026-11-06 against the
[quotas page](https://docs.aws.amazon.com/general/latest/gr/bedrock.html) and the Service Quotas API.
Many differ by Region and tier (the fixed limits below are the same in every Region except where
noted) and AWS changes them, so quote a Region-dependent number only for the Region the evidence names,
say it is the default, and tell the user where to read the value that applies to their account. Never
state a limit that is not in this file or in a page you have read and cite.

## Fixed limits (not adjustable in Service Quotas)

The same default applies in every supported Region unless noted.

| Limit | Default |
|---|---|
| Guardrails per account | 100 |
| Versions per guardrail | 20 (AWS does not say whether the DRAFT counts; it did in one test, see "Versions per guardrail" below) |
| Topics per guardrail (across the topic policies) | 30 |
| Example phrases per topic | 5 |
| Words per word policy (blocked word list) | 10,000 |
| Word length | 100 characters |
| Regex entities in a sensitive information policy | 30 |
| Regex length | 500 characters |
| Automated Reasoning policies per guardrail | 2 |
| Contextual grounding query length | 1 text unit |
| Contextual grounding response length | 5 text units |
| Contextual grounding source length | 100 text units in us-east-1 and us-west-2, 50 in the other Regions |

### Versions per guardrail

AWS defines the limit as "the maximum number of versions that a guardrail can have" and does not say whether the DRAFT counts
([quotas page](https://docs.aws.amazon.com/general/latest/gr/bedrock.html)). The `ListGuardrails` reference says to pass the guardrail ARN in
`guardrailIdentifier` to list all versions of a guardrail and does not say whether the DRAFT is among them
([ListGuardrails](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_ListGuardrails.html)). **Observed, not documented** (one test: a
test account used to evaluate this skill, us-east-1, 2026-11-07, one guardrail): `ListGuardrails` returned 20 entries, versions 1 to 19 and the
DRAFT, and the next `CreateGuardrailVersion` was refused with `ServiceQuotaExceededException`, "You have exceeded the service quota limit for the
number of versions for this guardrail." So treat the DRAFT as one of the 20, which leaves 19 numeric versions, and say the reading is an
observation.

- **Confirm with a count.** When the question names a guardrail in an account you can read, list its versions with `ListGuardrails` and the
  guardrail ARN, paging to the end. For a customer's account, or when no guardrail is named, give the customer
  `aws bedrock list-guardrails --guardrail-identifier <guardrail-arn> --region <Region>`. 20 entries including the DRAFT fits the explanation. A
  smaller count does not: read the full error text and ask whether a version was being created when the list was taken
  (`CreateGuardrailVersion` returns HTTP 202 and a guardrail's `status` can be `VERSIONING`:
  [CreateGuardrailVersion](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_CreateGuardrailVersion.html),
  [GuardrailSummary](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GuardrailSummary.html)). Say what you could not confirm.
- **Do not promise a quota increase.** The row is not adjustable in Service Quotas (item 2 below says what AWS does and does not state about
  increases for fixed limits). Offer a design inside the limit: retire the versions that no path pins.
- **Warn about the delete call.** `DeleteGuardrail` with only the guardrail identifier deletes the guardrail and all its versions; deleting one
  version needs `guardrailVersion` as well
  ([DeleteGuardrail](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_DeleteGuardrail.html)). Tell the customer to check what pins each
  version first (LLM-GRD-006 evidence), and that the delete is their action, never yours.

## Maximum input size per policy (adjustable)

A **text unit** holds up to 1,000 characters; longer text is processed as several text units, so 5,600
characters is 6 text units ([Bedrock pricing](https://aws.amazon.com/bedrock/pricing/), Guardrails).
Each policy has its own maximum input size in text units, and the content filter and denied topic
policies have a value per tier. Defaults in us-east-1:

| Policy | Maximum input size |
|---|---|
| Content filters (Classic and Standard tier) | 1,000 text units |
| Denied topics, Standard tier | 1,000 text units |
| Denied topics, Classic tier | 200 text units |
| Sensitive information filters | 1,000 text units |
| Word filters | 1,000 text units |
| Contextual grounding | 106 text units (the quotas page lists 106 in every Region) |

A text unit holds up to 1,000 characters, so 1,000 text units is at most 1,000,000 characters
(1,000 × 1,000). AWS does not state this figure; it is derived from the two documented facts above and
assumes the quota's text unit is the unit the pricing page defines. If you give it, call it a derived
upper bound. The model's own input limit can be lower. For most policies other Regions have different
defaults and some are much lower, so read the value for the Region in the evidence.

## Rate limits (adjustable)

Quotas exist per second and per burst for `ApplyGuardrail` requests and for the text units each policy
processes (content filters, denied topics, sensitive information filters, word filters, contextual
grounding), with separate values by tier for content filters and denied topics. `InvokeGuardrailChecks`
has its own per-minute and burst quotas. The defaults depend on Region and tier; give no number unless
the evidence names the Region and you have read the value.

## How to answer a limit question

1. **Sort the limit into count, size or rate** from the error text, the API that raised it and any
   policy the error text names, then find that row in the tables above: whether a limit is fixed or
   adjustable depends on its row, not its type. When the evidence does not say which limit was hit,
   list the candidates and the one check that separates them. Do not name a limit the evidence does
   not point at.
2. **A fixed limit cannot be raised in Service Quotas.** The quotas page lists it as not adjustable.
   The Amazon Nova quotas page says a request can be submitted through the limit increase form "to be
   considered" for a quota marked No in the Bedrock quotas table
   ([Nova quotas](https://docs.aws.amazon.com/nova/latest/nova2-userguide/quotas.html)). The pages
   checked do not say whether guardrail limits qualify or what the outcome would be. Say that. Do not
   call a fixed limit an adjustable quota and do not promise an increase. Offer a design that stays
   inside the limit.
3. **For an adjustable quota** the customer checks the Adjustable column in the
   [Service Quotas console](https://console.aws.amazon.com/servicequotas/home) for the Region in the
   evidence and requests an increase
   ([how to request](https://docs.aws.amazon.com/servicequotas/latest/userguide/request-quota-increase.html)).
   They can list applied values with `aws service-quotas list-service-quotas --service-code bedrock
   --region <Region>`, which they run themselves. For some quotas only the default value is available,
   and this command does not return a quota whose applied value is not available, so a missing row does
   not mean there is no quota. `aws service-quotas list-aws-default-service-quotas --service-code
   bedrock --region <Region>` lists the default values, which do not reflect any increases.
4. **"Input too long" on a call with a guardrail attached has at least two common sources**: a guardrail
   size limit and the model's own input limit. Do not pick one without the evidence. Read the full error
   text and which API raised it. The customer can compare by sending the same text to `ApplyGuardrail`
   on its own (their action, billable, never yours):
   `aws bedrock-runtime apply-guardrail --guardrail-identifier <guardrail-id> --guardrail-version <version> --source INPUT --content '[{"text":{"text":"<same text>"}}]' --region <Region>`.
   The same size error there points at the guardrail. Success there makes a guardrail input-size limit
   less likely but does not rule out the output side or the model. Over an adjustable size limit the
   text can be split or the quota raised; over a fixed one it should be split (item 2 covers the limit
   increase form).
5. **Throttling on guarded calls** can come from the model's own quota or from a guardrail rate quota.
   The error text and the API that raised it must say which; if they do not, list both. Guardrail
   text-unit quotas are per policy (and per tier for content filters and denied topics) and request
   quotas are per API, so name the policy or API before you name a quota to raise. Look for throttling
   with `InvocationThrottles` in the `AWS/Bedrock/Guardrails` namespace (throttled requests are not
   counted in `Invocations`). `TextUnitCount` shows the text units the guardrail policies consumed
   (break it down with the `GuardrailPolicyType` dimension), to compare with the text-unit quota of the
   policy the error names. The metrics page defines `Invocations` as requests to the `ApplyGuardrail`
   operation and does not say whether guardrails attached to model calls are included, so an empty
   result does not rule out guardrail throttling on those calls
   ([metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-guardrails-cw-metrics.html)).
6. **Model quotas, token limits and Provisioned Throughput are not guardrail limits.** Route them to
   `llmops-capacity-cost`, and model context windows to the model's documentation.
