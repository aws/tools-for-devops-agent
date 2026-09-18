# Changelog

## [1.0.0] - 2026-09-18

### Added
- Initial release of the `sagemaker-ops-review` skill for AWS DevOps Agent.
- 20 read-only checks across 8 pillars — Security, Performance, Cost Optimization, Service Quotas, Resiliency, Operational Excellence, Sustainability, and Best Practices — defined authoritatively in `references/pillar-checks.md`.
- Security checks: notebook KMS encryption, Studio domain network posture (`VpcOnly` vs `PublicInternetOnly`), and endpoint/model `VpcConfig` coverage including Inference Component endpoints.
- Performance checks: endpoint inference type classification (Real-Time / Serverless / Asynchronous) and 7-day `ModelLatency` / `OverheadLatency` reporting from the `AWS/SageMaker` CloudWatch namespace.
- Cost Optimization checks: resource tagging coverage, Trainium/Inferentia adoption, endpoint autoscaling, SageMaker Savings Plan coverage, lifecycle configuration inventory, Inference Recommender job inventory, and 90-day stale endpoint detection.
- Service Quotas check across seven SageMaker quota codes, each verified against the live `sagemaker` service, with usage read from CloudWatch `AWS/Usage`/`ResourceCount` over a trailing 24-hour window at `period 3600` and the risk tier derived from utilization (≥ 90% High, ≥ 75% Medium, else Low; Unknown when no usage metrics exist). The 24-hour window is deliberate — SageMaker publishes these metrics about every 20 minutes with ingestion lag, so shorter windows return no datapoints and score every quota `Unknown`.
- Resiliency checks: per-variant endpoint instance counts and AWS Health SageMaker lifecycle events.
- Operational Excellence checks: SageMaker Projects, SageMaker Pipelines, and endpoint data capture configuration.
- Sustainability check: Studio domain region inventory.
- Best Practices pillar: advisory recommendations grounded in the public AWS Well-Architected Machine Learning, Generative AI, and Agentic AI lenses.
- Uniform severity model — High / Medium / Low, plus Informational for inventory checks with no pass/fail signal — with exactly one recommendation per High or Medium finding and a severity-ranked Executive Summary that must reconcile with the per-check sections.
- Findings are keyed per resource (`check`, `region`, `resource`), never aggregated into a single row per check, so severity counts stay comparable between runs.
- Serverless endpoints are scored Informational — never Low/Medium/High — in checks covering features Serverless Inference does not support (VPC configuration, network isolation, data capture, Model Monitor), so the report never emits a recommendation the operator cannot act on.
- AWS Health findings are keyed per affected entity and filtered to the in-scope regions, so a single multi-resource event produces one finding per resource and a region-scoped review never reports out-of-region resources.
- The tagging check excludes SageMaker-generated `model-monitoring-*` processing jobs, which are not operator-taggable and accumulate without limit.
- Explicit prohibition on stating any quota, limit, instance price, monthly cost, or percentage saving that an API did not return — including applied-vs-default quota limits, which must come from `servicequotas:GetServiceQuota` and never from `GetAWSDefaultServiceQuota`.
- Dual-signal, three-state autoscaling detection: managed instance scaling, or an Application Auto Scaling target on `sagemaker:variant:DesiredInstanceCount` **with** at least one scaling policy, counts as autoscaled. A target registered without a policy is reported as its own Medium finding, since bounds alone never trigger a scaling action. This avoids both falsely flagging endpoints scaled through Application Auto Scaling alone and falsely passing endpoints that cannot actually scale.
- Per-check failure isolation: an AccessDenied or API error is recorded as an error row and reported as "not evaluated — permission not granted" rather than a false "none found", and never aborts the review.
- Region discovery via `ce:GetCostAndUsage` with a fallback sweep of `sagemaker:List*` calls, so a payer-scoped Cost Explorer miss does not produce a false "no activity" result.
- Sample add-on IAM policy (`references/iam-policy.json`) for the permissions not covered by the AWS-managed `AIDevOpsAgentAccessPolicy`.
