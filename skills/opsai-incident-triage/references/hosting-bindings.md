# Hosting bindings — resolving the signal triple

## Contents

- [Why a binding exists](#why-a-binding-exists)
- [The signal triple](#the-signal-triple)
- [Binding table](#binding-table)
- [Fault-locus mapping per binding](#fault-locus-mapping-per-binding)
- [Choosing the binding](#choosing-the-binding)
- [When the path leaves AWS](#when-the-path-leaves-aws)

## Why a binding exists

The Step 6 ladder rules on three signals: a client-error count, a server-error count and a
throttle count. The **logic** of the ladder is hosting-independent — a rejected request is a
rejected request wherever the model runs. The **metric names** are not.

An LLM workload runs in many places. "My agent is broken" says nothing about where. Before the
ladder can be walked, the triple has to be bound to real metric names for the hosting that is
actually in the failing path. Binding first, ladder second.

**Never assume a binding from the word the operator used.** "Agent" does not mean Bedrock
AgentCore. An agent loop runs just as happily in a Lambda, a container on ECS or EKS, a process on
EC2, or outside AWS entirely. The binding is established from evidence — what the host
investigation found in the topology — or it is `UNDETERMINED` and said so.

## The signal triple

Three abstract slots. Every binding fills them or records them unfillable.

| Slot | What it counts | Ladder use |
|---|---|---|
| `CLIENT_ERRORS` | requests the model path rejected as malformed, unauthorized, or not found | R1 |
| `SERVER_ERRORS` | requests the model path failed to serve through no fault of the caller | R2 |
| `THROTTLES` | requests refused for rate or capacity | R1 context, R5 |

A fourth signal, provider health, is not part of the triple. It is Step 1 and it is binding-specific:
for a managed provider it is an AWS Health event; for a self-hosted model there is no provider to
have an event, and Step 1 records `not-applicable` rather than `no-datapoints`.

The three-state token rule is unchanged across every binding: a slot's value begins with
`measured <value>`, `no-datapoints` or `not-queried`. A binding that cannot separate a signal adds
no fourth token — it records the slot as `not-separable` **inside** the observed value, after the
token, and names what the signal is folded into.

## Binding table

| Binding | `CLIENT_ERRORS` | `SERVER_ERRORS` | `THROTTLES` | Provider health | Doc |
|---|---|---|---|---|---|
| `bedrock` | `AWS/Bedrock` `InvocationClientErrors` | `AWS/Bedrock` `InvocationServerErrors` | `AWS/Bedrock` `InvocationThrottles` | `health:DescribeEvents`, service `bedrock` | [Bedrock runtime metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html) |
| `sagemaker` | `AWS/SageMaker` `Invocation4XXErrors` | `AWS/SageMaker` `Invocation5XXErrors` | `not-separable` — 429 folds into `Invocation4XXErrors` | `health:DescribeEvents`, service `sagemaker` | [SageMaker CloudWatch metrics](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html) |
| `agentcore` | the model stage binds to `bedrock`; the runtime stage is workload-emitted | same | same | `health:DescribeEvents`, service `bedrock` | [Agentic AI Lens — observability](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel08-bp02.html) |
| `self-hosted-alb` | `AWS/ApplicationELB` `HTTPCode_Target_4XX_Count` | `AWS/ApplicationELB` `HTTPCode_Target_5XX_Count` | `RejectedConnectionCount`, plus app-emitted queue depth | `not-applicable` — the customer is the provider | [ALB CloudWatch metrics](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-cloudwatch-metrics.html) |
| `self-hosted-lambda` | `AWS/Lambda` `Errors` split by the function's own error taxonomy | same metric, same caveat | `AWS/Lambda` `Throttles` | `not-applicable` | [Lambda metrics](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics.html) |
| `third-party` | no AWS signal | no AWS signal | no AWS signal | `not-visible` | — |

**`agentcore` is a composite, not a third namespace.** An AgentCore runtime still calls a model, and
that call is a Bedrock invocation, so the model stage binds to `bedrock` exactly. What AgentCore adds
is a runtime stage above it. Do **not** invent a metric namespace for that stage: its signals are
whatever the workload emits over OTLP or to CloudWatch, which is a customer choice. If the runtime
stage has no emitted signal, that is `LLM-TEL-001` firing — triage is blind to the stage — and it is
reported as the finding rather than papered over.

**`self-hosted-lambda` cannot split the triple from the platform metric.** `AWS/Lambda` `Errors`
counts a failed invocation without saying whose fault it was. Splitting client from server requires
the function to emit its own taxonomy. Where it does not, both slots carry the same measured value
with the ambiguity named, and R1 may not fire on it — an undifferentiated error count is not client-
error dominance.

## Fault-locus mapping per binding

The locus token set is closed at four members and does not vary. What varies is which members a
binding can reach.

| Binding | `PROVIDER` reachable? | `INFRASTRUCTURE` reachable? | `APPLICATION` reachable? |
|---|---|---|---|
| `bedrock` | yes — AWS runs the model | yes — VPC endpoints, networking, IAM plumbing | yes |
| `sagemaker` | yes — AWS runs the hosting layer | yes — instance sizing, scaling, container | yes |
| `agentcore` | yes, for the model stage | yes — runtime, gateway, VPC | yes |
| `self-hosted-alb` | **no** — collapses into `INFRASTRUCTURE` | yes | yes |
| `self-hosted-lambda` | **no** — collapses into `INFRASTRUCTURE` | yes | yes |
| `third-party` | yes, but **never confirmable** from AWS signal | yes | yes |

**For a self-hosted model the customer is the provider.** `PROVIDER` has no referent, so a fault in
the serving layer is `INFRASTRUCTURE`. Reporting `PROVIDER` on a self-hosted binding is a category
error and sends the operator looking for an AWS Health event that cannot exist.

**For `third-party`, `PROVIDER` is a hypothesis, never a measurement.** No AWS read can confirm an
OpenAI or Anthropic API incident. If the evidence points past the boundary, the locus is `PROVIDER`
with transience `UNKNOWN` and an explicit statement that it rests on the absence of a customer-side
signal rather than on a provider-side one, plus the provider's own status page as the next step.

## Choosing the binding

Work this in order. Stop at the first row that matches the **failing** path, not the first row that
matches anything in the account.

1. Does the failing call go to `bedrock-runtime` (`InvokeModel`, `Converse`, `InvokeModelWithResponseStream`)? → `bedrock`.
2. Is there an AgentCore runtime or a Bedrock Agent in the failing path **above** that call? → `agentcore`, with the model stage still bound per row 1.
3. Does the failing call go to a SageMaker endpoint (`InvokeEndpoint`, `InvokeEndpointAsync`)? → `sagemaker`.
4. Is the model served by the customer's own process on AWS compute? → `self-hosted-alb` or `self-hosted-lambda` by what fronts it.
5. Is the model served outside AWS? → `third-party`.
6. None of the above established from evidence → **do not pick one**. Record the binding as
   `UNDETERMINED`, report the locus as `UNDETERMINED`, and name the one fact that would resolve it.

Row 6 is the row that matters. A guessed binding produces a confident ruling on metrics that
describe a different system, which is worse than no ruling at all.

## When the path leaves AWS

State the boundary explicitly, in the findings, as its own row. The operator needs to know the shape
of what you could not see, not merely that something was missing:

- which stage of the request path is beyond AWS visibility
- which of the three slots therefore carry no AWS signal
- what evidence would be needed, and who holds it (provider status page, provider support, the
  customer's own application telemetry)

A boundary disclosed this way is a finding. A boundary left implicit reads as a healthy signal, and
that is the failure this section exists to prevent.
