# Changelog

## 1.0.0
- Evals: `sm-execution-role-s3-kms` replaces the CreateModel-role assertion, which the prompt gave away, with one for the role's other deploy permissions (`s3:GetObject` on `ModelDataUrl`, ECR pull), from `references/known-causes.md` §3.
- Evals: `serverless-cold-start-provisioned-concurrency` and `sm-execution-role-s3-kms` give the endpoint or role setup, since the eval account has no serverless endpoint or failed deploy; `sm-container-port-contract` is removed (scored the same with and without the skill in two runs).
- Evals: the 12-digit account-ID regex ignores the documentation example IDs `123456789012` and `111122223333`.
- Evals: `endpoint-slow-and-erroring` and `sm-autoscaling-not-triggering` are removed; they need a standing real-time endpoint (about $1/hour).
- Evals: `sm-vpc-endpoint-missing` and `sm-endpoint-update-downtime` are removed (general knowledge, answered the same without the skill); check-id assertions are dropped from questions that name no account resource.

- PR #268 review item 3 (evals): `serverless-async-silent-failures` asks for one reply with no status message first (both runs had ended on "I've started the review") and asserts the `EndpointName`-only backlog dimension and `LLM-SM-SERVE-003`/`004`; `idle-endpoint-wasting-money` asserts no-datapoints reporting for an endpoint with no invocation data and `LLM-SM-003`/`008`.
- PR #268 review item 1 (IAM reads and action names):
  - IAM: `sagemaker:ListInferenceRecommendationsJobs` (was a non-existent name); batch output is checked with `s3:ListBucket` only, without `s3:GetObject`.
- Initial release. Merges the earlier SageMaker inference endpoints, serverless and async, and batch transform skills into one skill.
- Real-time endpoints: failures, health check, VPC path, scaling, `ModelError`, right-sizing, lineage (LLM-SM-001..011).
- Serverless and asynchronous endpoints: cold start, concurrency, notifications, backlog scaling, fit decision (LLM-SM-SERVE-001..005).
- Batch transform: job failures, parallelism, partial output, output encryption (LLM-SM-BATCH-001..004).
- SageMaker endpoint cost (instance-hours, idle endpoints) is a step of its own; the real-time idle-cost signal, the serverless/async fit and the batch-or-endpoint choice are one decision.
- Check-ids and severities unchanged; other families' ids removed from the shared references.
- Routes to other skills replaced by an optional Related skills section.
- `ModelSetupTime` now follows the AWS reading (time to launch new compute for a serverless endpoint); async cold start is read from `ApproximateBacklogSizePerInstance` / `ApproximateAgeOfOldestRequest` and the container log.
- The capacity-versus-quota cause, duplicated in the endpoint and batch copies, is kept once (known-causes §9).
- `api-quirks.md` renumbered to traps §1–§4 (InService, scalable targets, no datapoints, transform `Completed`); `DescribeScalableTargets` collection rows merged into one.
- Old evals results (structure, best-practices, functional) not carried over; best-practices and functional must be re-run.
