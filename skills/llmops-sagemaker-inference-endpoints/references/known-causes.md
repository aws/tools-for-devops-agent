# Known Causes — SageMaker real-time endpoint break-fix

Documented causes for the real-time endpoint errors operators report most, for answering a stated
error directly (SKILL.md, *Break-fix first*). Each bullet names the AWS page it rests on; verify
against that page before you answer. A cause tied to a catalog id (`LLM-SM-001`..`LLM-SM-011`) is reported as that finding
with the catalog severity; a cause with no id is **guidance**, cited by URL, never given an invented
id. Serverless and asynchronous endpoints are `llmops-sagemaker-serverless-async`; the
batch-or-endpoint choice is `llmops-sagemaker-batch`.

## 1. Endpoint creation or update failed

- **Read `FailureReason` from `DescribeEndpoint`.** `Failed` means the endpoint could not be created, updated or re-scaled, and `DeleteEndpoint` is the only operation allowed on a failed endpoint ([DescribeEndpoint](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeEndpoint.html)).
- **Then read the container log group `/aws/sagemaker/Endpoints/[EndpointName]`**, one stream per `[variant]/[instance-id]` ([log groups](https://docs.aws.amazon.com/sagemaker/latest/dg/logging-cloudwatch.html)).
- **`ResourceLimitExceeded` is an account resource limit** — raise it through Service Quotas ([CreateEndpoint errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateEndpoint.html), [quotas](https://docs.aws.amazon.com/sagemaker/latest/dg/regions-quotas.html)). **`InsufficientInstanceCapacity`** means AWS lacks capacity for that request right now; EC2 documents retrying after a few minutes, requesting fewer instances, or using a different instance type. A quota increase does not add capacity — this skill's reading ([EC2 insufficient capacity](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/troubleshooting-launch.html)).

## 2. Custom container works locally but never passes the health check

- **The hosting contract differs from `docker run` defaults**: SageMaker starts the container as `docker run <image> serve`, overriding `CMD`; the web server must listen on port 8080 and accept `POST /invocations` and `/ping`; socket connections must be accepted within 250 ms; `/ping` attempts time out after 2 seconds; responses must arrive within 60 seconds ([inference container contract](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-inference-code.html)).

## 3. Deploy fails reading the model artifact

- **The `CreateModel` execution role needs `s3:GetObject` on the `ModelDataUrl` object and ECR pull permissions for the image** ([CreateModel execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).
- **A KMS-encrypted artifact also needs the key policy to allow that role** — an IAM policy alone has no effect on a KMS key unless the key policy allows it ([key policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html)).

## 4. App in a private subnet cannot reach the endpoint

- **With no NAT or internet path, invoke through an interface VPC endpoint for the SageMaker Runtime service**; with private DNS enabled the default `runtime.sagemaker.<region>.amazonaws.com` hostname resolves to it (LLM-SM-006 covers the endpoint's own `VpcConfig`, not the caller's path) ([SageMaker interface endpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/interface-vpc-endpoint.html)).
- **DNS resolves but calls still fail** — the security group on the endpoint network interfaces must allow inbound HTTPS from the callers, and any network ACL must allow the traffic ([create an interface endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html)).
- **Fails from only some tasks or subnets** — an interface endpoint gets a network interface only in the subnets you select (one per Availability Zone), and AWS notes the Runtime endpoint must be enabled in the client's Availability Zone for private DNS to work. Add the missing subnets ([create an interface endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html), [SageMaker interface endpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/interface-vpc-endpoint.html)).

## 5. Invocation errors

- **`ModelError` (HTTP 424) is the customer's model container returning a 4xx or 5xx**; the error carries the original status, message and log stream ARN, so the real error is in the container log, not in SageMaker. A retry that succeeds points at the container's handling of some inputs or load (LLM-SM-009 when there is no alarm) ([InvokeEndpoint errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html)).
- **`ModelNotReadyException` (HTTP 429)** means a multi-model endpoint is still downloading or loading the target model; wait and retry ([InvokeEndpoint errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html)).

## 6. Multi-model endpoint slow on the first call for some models

- **Models load on demand**: a model not yet on an instance is downloaded from S3 and loaded into memory; under memory pressure unused models are unloaded and reloaded later, so infrequently used models pay cold-start latency ([multi-model endpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/multi-model-endpoints.html)).

## 7. Autoscaling never scales out

- **Scaling needs a registered scalable target for the endpoint and variant plus a scaling policy** (LLM-SM-001 if no target exists) ([auto scaling prerequisites](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling-prerequisites.html)).
- **Check the policy's metric, target value and cooldowns** — e.g. `SageMakerVariantInvocationsPerInstance` with a `TargetValue`, `ScaleOutCooldown` and `ScaleInCooldown`; a target set above the real per-instance load never fires ([define a scaling policy](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling-add-code-define.html)).

## 8. Shipping a new model version without dropping traffic

- **`UpdateEndpoint` deploys the new endpoint config to a new fleet, shifts traffic, then deletes the old instances, with no availability loss** ([UpdateEndpoint](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_UpdateEndpoint.html)).
- **Add deployment guardrails** for a regressive model: blue/green with canary or linear traffic shifting and auto-rollback on CloudWatch alarms (the execution role needs `cloudwatch:DescribeAlarms` on those alarms) ([deployment guardrails](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails.html), [CreateModel execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).
