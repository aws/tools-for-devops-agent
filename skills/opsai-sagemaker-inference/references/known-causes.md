# Known Causes — SageMaker inference break-fix

Documented causes for the real-time, serverless, asynchronous and batch transform errors operators report most, for
answering a stated error directly (SKILL.md, *Break-fix first*). Each bullet names the AWS page it rests on; verify
against that page before you answer. A cause tied to a catalog id (LLM-SM-*, LLM-SM-SERVE-*, LLM-SM-BATCH-*) is
reported as that finding with the catalog severity; a cause with no id is **guidance**, cited by URL, never given an
invented id. Where AWS says nothing (for example on input "mount" errors), say so rather than filling the gap.

## 1. Real-time: Endpoint creation or update failed

- **Read `FailureReason` from `DescribeEndpoint`.** `Failed` means the endpoint could not be created, updated or re-scaled, and `DeleteEndpoint` is the only operation allowed on a failed endpoint ([DescribeEndpoint](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeEndpoint.html)).
- **Then read the container log group `/aws/sagemaker/Endpoints/[EndpointName]`**, one stream per `[variant]/[instance-id]` ([log groups](https://docs.aws.amazon.com/sagemaker/latest/dg/logging-cloudwatch.html)).

## 2. Real-time: Custom container works locally but never passes the health check

- **The hosting contract differs from `docker run` defaults**: SageMaker starts the container as `docker run <image> serve`, overriding `CMD`; the web server must listen on port 8080 and accept `POST /invocations` and `/ping`; socket connections must be accepted within 250 ms; `/ping` attempts time out after 2 seconds; responses must arrive within 60 seconds ([inference container contract](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-inference-code.html)).

## 3. Real-time: Deploy fails reading the model artifact

- **The `CreateModel` execution role needs `s3:GetObject` on the `ModelDataUrl` object and ECR pull permissions for the image** ([CreateModel execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).
- **A KMS-encrypted artifact also needs the key policy to allow that role** — an IAM policy alone has no effect on a KMS key unless the key policy allows it ([key policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html)).

## 4. Real-time: App in a private subnet cannot reach the endpoint

- **With no NAT or internet path, invoke through an interface VPC endpoint for the SageMaker Runtime service**; with private DNS enabled the default `runtime.sagemaker.<region>.amazonaws.com` hostname resolves to it (LLM-SM-006 covers the endpoint's own `VpcConfig`, not the caller's path) ([SageMaker interface endpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/interface-vpc-endpoint.html)).
- **DNS resolves but calls still fail** — the security group on the endpoint network interfaces must allow inbound HTTPS from the callers, and any network ACL must allow the traffic ([create an interface endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html)).
- **Fails from only some tasks or subnets** — an interface endpoint gets a network interface only in the subnets you select (one per Availability Zone), and AWS notes the Runtime endpoint must be enabled in the client's Availability Zone for private DNS to work. Add the missing subnets ([create an interface endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html), [SageMaker interface endpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/interface-vpc-endpoint.html)).

## 5. Real-time: Invocation errors

- **`ModelError` (HTTP 424) is the customer's model container returning a 4xx or 5xx**; the error carries the original status, message and log stream ARN, so the real error is in the container log, not in SageMaker. A retry that succeeds points at the container's handling of some inputs or load (LLM-SM-009 when there is no alarm) ([InvokeEndpoint errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html)).
- **`ModelNotReadyException` (HTTP 429)** means a multi-model endpoint is still downloading or loading the target model; wait and retry ([InvokeEndpoint errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html)).

## 6. Real-time: Multi-model endpoint slow on the first call for some models

- **Models load on demand**: a model not yet on an instance is downloaded from S3 and loaded into memory; under memory pressure unused models are unloaded and reloaded later, so infrequently used models pay cold-start latency ([multi-model endpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/multi-model-endpoints.html)).

## 7. Real-time: Autoscaling never scales out

- **Scaling needs a registered scalable target for the endpoint and variant plus a scaling policy** (LLM-SM-001 if no target exists) ([auto scaling prerequisites](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling-prerequisites.html)).
- **Check the policy's metric, target value and cooldowns** — e.g. `SageMakerVariantInvocationsPerInstance` with a `TargetValue`, `ScaleOutCooldown` and `ScaleInCooldown`; a target set above the real per-instance load never fires ([define a scaling policy](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling-add-code-define.html)).

## 8. Real-time: Shipping a new model version without dropping traffic

- **`UpdateEndpoint` deploys the new endpoint config to a new fleet, shifts traffic, then deletes the old instances, with no availability loss** ([UpdateEndpoint](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_UpdateEndpoint.html)).
- **Add deployment guardrails** for a regressive model: blue/green with canary or linear traffic shifting and auto-rollback on CloudWatch alarms (the execution role needs `cloudwatch:DescribeAlarms` on those alarms) ([deployment guardrails](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails.html), [CreateModel execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).

## 9. Capacity versus quota (endpoints and transform jobs)

- **`ResourceLimitExceeded` is an account resource limit** — raise it through Service Quotas ([CreateEndpoint errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateEndpoint.html), [CreateTransformJob errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTransformJob.html), [quotas](https://docs.aws.amazon.com/sagemaker/latest/dg/regions-quotas.html)).
- **A capacity shortfall means AWS lacks capacity for that request right now**: read the wording of the endpoint's or transform job's `FailureReason` rather than assuming an error name (EC2's own launch error is `InsufficientInstanceCapacity`; SageMaker training reports `InsufficientCapacityError`). EC2 documents retrying after a few minutes, requesting fewer instances, or using a different instance type. A quota increase does not add capacity — this skill's reading ([EC2 insufficient capacity](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/troubleshooting-launch.html)).

## 10. Serverless: cold start, concurrency limits and feature exclusions

- **Slow first response after idle is a cold start**: on-demand serverless scales to zero and must start compute, download the model and start the container; it also happens when concurrent requests exceed current usage. `OverheadLatency` tracks it. Provisioned Concurrency keeps that many slots warm; AWS positions on-demand serverless for workloads that can tolerate cold starts, so without it they are expected (LLM-SM-SERVE-001) ([serverless inference](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html)).
- **Throttling is the per-endpoint `MaxConcurrency` or the shared Regional pool**: invocations beyond an endpoint's maximum are throttled, and all serverless endpoints in an account share a per-Region total concurrency (1000 or 500 depending on Region) (LLM-SM-SERVE-002) ([serverless inference](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html)).
- **A `MaxConcurrency` value is rejected** when it is outside 1–200, or when `ProvisionedConcurrency` exceeds it; `MemorySizeInMB` must be 1024–6144 in 1 GB steps ([ProductionVariantServerlessConfig](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ProductionVariantServerlessConfig.html)).
- **A config that works for real-time fails validation on serverless** when it uses an excluded feature: GPUs, AWS Marketplace model packages, private Docker registries, multi-model endpoints, VPC configuration, network isolation, data capture, multiple production variants, Model Monitor or inference pipelines. Remove the option or use a real-time or async endpoint; a real-time endpoint cannot be updated to serverless ([serverless feature exclusions](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html)).
- **Serverless or real-time for low, bursty traffic** — AWS positions on-demand serverless for workloads with idle periods between bursts that tolerate cold starts, and Provisioned Concurrency for predictable bursts (LLM-SM-SERVE-005) ([serverless inference](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html)).

## 11. Async: large inputs, completion signal, notifications and scale to zero

- **Large inputs go by S3 reference**: async is built for payloads up to 1 GB and processing up to one hour; the request passes `InputLocation` (an S3 URI) to `InvokeEndpointAsync` instead of an inline body ([asynchronous inference](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html), [InvokeEndpointAsync](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpointAsync.html)).
- **The completion signal is the output object or the SNS notification, not the invoke response**: `InvokeEndpointAsync` returns `202` with `OutputLocation` and `FailureLocation`; AWS's own example polls the output location until the object exists. A client that treats the 202 as completion shows stale status — this skill's reading ([InvokeEndpointAsync](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpointAsync.html), [check prediction results](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-check-predictions.html)).
- **No notification arrives** when `NotificationConfig` has no `SuccessTopic`/`ErrorTopic` (none is sent without a topic), or when the execution role lacks `sns:Publish` on the topic (LLM-SM-SERVE-003) ([AsyncInferenceNotificationConfig](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_AsyncInferenceNotificationConfig.html), [async prerequisites](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-create-endpoint-prerequisites.html)).
- **Async can scale to zero**: register the variant with `MinCapacity` 0 and scale on the backlog; without the optional `HasBacklogWithoutCapacity` step policy, scale-up from zero waits until the backlog exceeds the target-tracking value (LLM-SM-SERVE-004) ([autoscale an async endpoint](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html)).
- **A cloned endpoint config that lost async behaviour** is missing `AsyncInferenceConfig`, which lives in the endpoint configuration and is required for the endpoint to be invoked with `InvokeEndpointAsync`; set it (output path, optional notification topics) on the new config explicitly ([CreateEndpointConfig](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateEndpointConfig.html)).

## 12. Batch: Parsing errors on records that "look like valid JSON"

- **`SplitType` = `Line` splits records on newline boundaries**, so a pretty-printed JSON document or a wrapping JSON array is cut into fragments that do not parse; each record must be one complete object per line (JSON Lines). The default `SplitType` `None` sends the whole object as one request (LLM-SM-BATCH-001) ([TransformInput](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_TransformInput.html), [batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).
- **Set `ContentType` to the MIME type the container expects** — SageMaker sends it with each HTTP call. For JSON Lines input use `application/jsonlines` with `SplitType` and `AssembleWith` `Line`, and AWS recommends `Accept` `application/jsonlines` for batch transform responses ([TransformInput](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_TransformInput.html), [associate predictions with inputs](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform-data-processing.html), [common inference formats](https://docs.aws.amazon.com/sagemaker/latest/dg/cdf-inference.html)).
- **CSV with embedded newlines is not supported** by batch transform ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).

## 13. Batch: Timeouts on large records

- **The per-invocation timeout is `ModelClientConfig.InvocationsTimeoutInSeconds`** (default 600, range 1–3600), separate from how long the whole job runs; `InvocationsMaxRetries` (0–3, default 3) sets the retries ([ModelClientConfig](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ModelClientConfig.html)).
- **`MaxPayloadInMB` must be at least the size of one record and at most 100 MB**, and `MaxConcurrentTransforms × MaxPayloadInMB` must not exceed 100 MB ([CreateTransformJob](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTransformJob.html), [batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).

## 14. Batch: Slow job with idle instances on one large file

- **Batch transform maps S3 objects to instances, so one input file is processed by one instance and the rest sit idle**; split the input into several files, and use `SplitType` `Line` with `BatchStrategy` `MultiRecord` to build mini-batches up to `MaxPayloadInMB`. AWS says the ideal `MaxConcurrentTransforms` equals the number of compute workers (LLM-SM-BATCH-002) ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html), [CreateTransformJob](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTransformJob.html)).

## 15. Batch: Output access or KMS errors

- **Batch transform runs as the role in the `CreateModel` request**, and for `TransformOutput.KmsKeyId` AWS states the key policy must grant that role; an IAM policy alone has no effect on a KMS key unless the key policy allows it (LLM-SM-BATCH-001, LLM-SM-BATCH-004 for the missing CMK) ([TransformOutput](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_TransformOutput.html), [key policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html)).

## 16. Batch: Success status but records missing, or intermittent internal errors

- **An output file is written only when every record in its input file succeeded**, named `<input>.out`, so a missing `.out` names the input file to inspect (LLM-SM-BATCH-003) ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).
- **Read the container log group `/aws/sagemaker/TransformJobs`** (streams `[job]/[instance-id]-[timestamp]`, plus `/data-log`) to tell a container error from a service error before retrying ([log groups](https://docs.aws.amazon.com/sagemaker/latest/dg/logging-cloudwatch.html)).

## 17. Batch: Predictions cannot be matched to input rows

- **Use `DataProcessing`**: `InputFilter` selects what the model sees, `JoinSource` = `Input` joins each prediction to its input record, and `OutputFilter` keeps the ID and prediction columns; for JSON or JSON Lines input the prediction lands in the reserved `SageMakerOutput` key, and predictions are listed in the same order as the input records ([associate predictions with inputs](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform-data-processing.html), [batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).

## 18. Batch: Batch transform or a real-time endpoint?

- **AWS positions batch transform for inference on large datasets when you do not need a persistent endpoint**; a periodic bulk scoring run with no live caller fits it, while an endpoint keeps incurring charges until it is deleted. Problems with the endpoint itself are covered in sections 1–9 ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html), [UpdateEndpoint](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_UpdateEndpoint.html)).
