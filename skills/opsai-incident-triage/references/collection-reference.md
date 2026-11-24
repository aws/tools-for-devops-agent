# Collection Reference

The exact **read-only** API calls this skill uses to collect incident state, and the fields each contributes. All calls are describe/list/get/lookup — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

The API column names **IAM actions**. Bedrock has two control-plane clients, `bedrock` (model and logging config) and `bedrock-agent` (agents, knowledge bases); both authorize under the `bedrock:` IAM prefix (`bedrock-agent` is a CLI and SDK client name, not an IAM prefix). Every read below is in the AWS managed policy `AIDevOpsAgentAccessPolicy`, so this skill needs no extra template parameter. The data-plane clients `bedrock-runtime` and `bedrock-agent-runtime` are **not** used for collection — they invoke models, which costs money and proves nothing about the incident.

This is the triage subset. The companion catalogue `references/metrics-and-logs.md` says how to *read* each metric and log pattern; this file says *which call to make*. Load both with any router row.

---

## Service-health and change correlation (the two that decide transient vs config)

| API (service) | Fields contributed | Feeds |
|---|---|---|
| `health:DescribeEvents` | active and recent service events in the region, `eventTypeCode`, `statusCode`, affected services | classifier Steps 1–2, 5; `transient-vs-config-classifier.md` |
| `health:DescribeAffectedEntities` | whether the caller's own account/resources are named in an event | classifier Step 4 (blast radius) |
| `cloudtrail:LookupEvents` | control-plane changes in the window — `UpdateGuardrail`, `PutModelInvocationLoggingConfiguration`, alias and provisioned-throughput changes, IAM/SCP edits | classifier Step 6 ("nothing changed on our side" is a claim to verify, not accept) |
| `cloudtrail:LookupEvents` with `AttributeKey=EventSource`, `AttributeValue=bedrock.amazonaws.com` | the **error codes and calling principals** of requests the invocation log never sees — `eventName` (`Converse`, `InvokeModel`), `errorCode`, `userIdentity.arn`, `requestParameters.modelId` | classifier **Step 5b**, to resolve the remainder when the per-code counts do not sum to the metric total |

A `locus=PROVIDER` asserted without a `health:DescribeEvents` result is unsupported — except on a self-hosted binding, where that call is `not-applicable` and the locus is `INFRASTRUCTURE` instead. A `locus=APPLICATION` asserted without a `cloudtrail:LookupEvents` window is equally unsupported. Every metric and log source named below is the `bedrock` binding's; bind at Step 0 (`hosting-bindings.md`) and substitute.

**Use `EventSource`, not `EventName`, for the Step 5b lookup.** `InvokeModel`, `InvokeModelWithResponseStream`, `Converse` and `ConverseStream` are CloudTrail **management** events, logged by default ([Bedrock and CloudTrail](https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html)). In a measured run on 2026-10-26 the `AttributeKey=EventName, AttributeValue=InvokeModel` form returned 0 events while the `EventSource` form returned 49 `Converse` events over the same 35-minute window, carrying `ValidationException` and `AccessDenied` against two distinct roles. The callers used `Converse`, so an `EventName=InvokeModel` lookup could not match them; query by `EventSource` and read `eventName` off the results. Count only `eventType` `AwsApiCall`: a streaming call also writes an `AwsServiceEvent` stream-completion event with the same `eventName`.
## Error and latency signal (CloudWatch)

| API (service) | Fields contributed | Feeds |
|---|---|---|
| `cloudwatch:GetMetricData` | `Invocations`, `InvocationClientErrors`, `InvocationServerErrors`, `InvocationThrottles`, `InvocationLatency`, `TimeToFirstToken` over the window, per `ModelId` | classifier Steps 1–4; LLM-TEL-001 |
| `cloudwatch:ListMetrics` | which of `AWS/Bedrock`, `AWS/Bedrock/Guardrails`, `AWS/Bedrock/Agents` have data at all | telemetry readiness; absence is itself a finding |
| `cloudwatch:DescribeAlarms` | whether an alarm existed that should have caught this | gap reporting |

Read `references/metrics-and-logs.md` before interpreting any of these — the namespace, the required dimensions, and the error-class split are all there, and `InvocationServerErrors` in particular is the metric most often claimed without being read.

## Invocation logs

| API (service) | Fields contributed | Feeds |
|---|---|---|
| `logs:DescribeLogGroups` | existence of the Bedrock invocation log group; retention | LLM-INV-001, 005 |
| `bedrock:GetModelInvocationLoggingConfiguration` | whether invocation logging is on, and where it delivers | LLM-INV-001, 005, 010 |
| `logs:StartQuery` / `logs:GetQueryResults` | per-request error patterns, finish reasons, throttle bursts (Logs Insights) | invocation error patterns in `metrics-and-logs.md` |

If logging was off during the incident window, say so plainly and stop claiming per-request causes — that absence is usually *why* the incident is hard to diagnose, and it is the most actionable finding available.

## Configuration reads, only where a hypothesis needs them

| API (service) | Fields contributed | Feeds |
|---|---|---|
| `bedrock:ListFoundationModels` | `modelLifecycle.status`, modality and streaming support — is the model even valid here | LLM-INV-003, `ValidationException` triage |
| `bedrock:ListInferenceProfiles` / `GetInferenceProfile` | profile type and member regions — cross-region routing surprises | LLM-INV-002 |
| `bedrock:ListProvisionedModelThroughputs` | `status`, `modelUnits` — throttling with PT present reads differently | LLM-PT-001/002, `InvocationThrottles` |
| `bedrock:GetAgentAlias` / `bedrock:ListAgentAliases` | alias → version pinning, the usual cause of "the agent changed by itself" | LLM-AGT-007, `api-quirks.md` §6 |
| `bedrock:ListIngestionJobs` | per-source job history and per-job `statistics`; empty means never synced | LLM-KB-001, `api-quirks.md` §8 |

## Access and policy, for 4xx that look like outages

| API (service) | Fields contributed | Feeds |
|---|---|---|
| `iam:ListAttachedRolePolicies` / `iam:GetRolePolicy` / `iam:GetPolicyVersion` | whether the caller's identity policies allow `bedrock:InvokeModel*`, read action by action and labelled "read from policy documents, not simulated" (`iam:SimulatePrincipalPolicy` is refused in the DevOps Agent runtime) | `AccessDeniedException` triage, LLM-INV-013 |
| `organizations:ListPoliciesForTarget` / `DescribePolicy` | SCP denies that mask as service failures | LLM-INV-015 |
| The `AccessDeniedException` message and `cloudtrail:LookupEvents` `errorMessage` | model access / subscription state (for example "model is not available for this account"); `bedrock:GetFoundationModelAvailability` is not in the managed policy, so triage does not call it | LLM-INV-014 |

An `AccessDeniedException` and a `ResourceNotFoundException` on a non-entitled model are both **customer config**, not service transient, however much the symptom looks like an outage. `ValidationException` is config too. Only the 5xx family and `ServiceUnavailableException` point at the service, and `AWS/Bedrock InvocationServerErrors` is frequently flat zero even during a real incident — see `metrics-and-logs.md`.

## Never called during triage

`bedrock:ApplyGuardrail` is **not** a collection call. It invokes a guardrail, it is billable, and it tells you nothing about an incident. Do not call it. Guardrail configuration is read with `bedrock:GetGuardrail`; guardrail *behaviour* during the incident is read from `AWS/Bedrock/Guardrails` metrics and the invocation logs.

Likewise, no `Create*`, `Update*`, `Delete*`, `Put*` or `Invoke*` call belongs in a triage run.
