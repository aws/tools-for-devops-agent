# AI/ML Workloads — Inputs, KPIs, and Lens Mapping

Read this file when Step 3 detects the **ML / accelerated** shape, or when Amazon Bedrock
usage appears in CloudWatch for a workload of any shape. It extends Steps 4, 6, 7, and 9 for
AI/ML resources. It does not replace them: CPU-only resources in an ML workload are still
assessed through the standard steps.

Guidance comes from the sustainability pillars of two Well-Architected lenses:

- [Machine Learning Lens](https://docs.aws.amazon.com/wellarchitected/latest/machine-learning-lens/machine-learning-lens.html) — MLSUS01–MLSUS06, 16 best practices
- [Generative AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html) — GENSUS01–GENSUS03, 4 best practices

Both lenses map back to Sustainability Pillar best practices. **Grade every finding under its
SUS best practice and cite the lens ID as evidence.** Do not add lens practices to the
scorecard — it stays at 29.

## What Emissions Data Can and Cannot Say About AI

| Question | Answer |
|----------|--------|
| Can the console or API show emissions for Amazon Bedrock or Amazon SageMaker AI? | No. The service breakdown covers Amazon EC2, Amazon S3, and Amazon CloudFront; every other service is reported under "Other". |
| Can "Other" be split by tokens, invocations, instance-hours, or spend? | No. The split would need each service's emissions per unit of its own weighting factor, which is not published. Do not approximate it. |
| How can a customer isolate AI emissions today? | Run AI workloads in a dedicated AWS account. `GetEstimatedCarbonEmissions` with `GroupBy: USAGE_ACCOUNT_ID` then reports that account as its own line — still under "Other" by service, but separable by account. |
| What can the agent measure for AI directly? | Resources: accelerator-hours, endpoint utilization, training job duration, and token volume. These are the KPIs below. |

You MUST NOT produce a CO2 figure per token, per inference, per training run, or per model.
No such factor is published, and an invented one is indistinguishable from a measured one in
the report.

You MUST NOT quote the lenses' "up to" percentages (energy, carbon, or cost reductions) as an
estimated impact for this workload. They are best-case figures from other workloads. Express
impact in accelerator-hours, instance-hours, or tokens, as Step 9 requires.

## Detection Signals

| Signal | Source |
|--------|--------|
| SageMaker real-time, serverless, or asynchronous endpoints | `sagemaker:ListEndpoints` |
| SageMaker training, processing, tuning, or batch transform jobs in the last 90 days | `sagemaker:ListTrainingJobs`, `ListProcessingJobs`, `ListHyperParameterTuningJobs`, `ListTransformJobs` with `CreationTimeAfter` |
| SageMaker notebook instances or Studio apps in service | `sagemaker:ListNotebookInstances`, `ListApps` |
| SageMaker HyperPod clusters | `sagemaker:ListClusters` |
| GPU, Inferentia, or Trainium EC2 instances or EKS nodes | Instance families `p*`, `g*`, `inf*`, `trn*` from the topology or `ec2:DescribeInstances` |
| Amazon Bedrock usage | Non-zero `Invocations` in the `AWS/Bedrock` CloudWatch namespace, per `ModelId`, in each workload Region |
| Bedrock provisioned throughput | `bedrock:ListProvisionedModelThroughputs` |

Use a **90-day** window for training and tuning jobs. They are bursty, and a 30-day window
routinely misses the run that dominates accelerator use. Keep 30 days for endpoints, notebooks,
and Bedrock usage, matching Step 4.

## Inputs to Collect

### SageMaker inference

| Input | Call / metric | Fields |
|-------|---------------|--------|
| Endpoint capacity | `sagemaker:DescribeEndpoint` | `ProductionVariants[].CurrentInstanceCount` |
| Endpoint configuration | `sagemaker:DescribeEndpointConfig` | `ProductionVariants[].InstanceType`, `InitialInstanceCount`, `ServerlessConfig`; `AsyncInferenceConfig` |
| Multi-model hosting | `sagemaker:DescribeModel` | `PrimaryContainer.Mode` (`MultiModel` vs `SingleModel`), `Containers[]`, `InferenceExecutionConfig.Mode` |
| Autoscaling | `application-autoscaling:DescribeScalableTargets` (`ServiceNamespace: sagemaker`) | `MinCapacity`, `MaxCapacity` for `sagemaker:variant:DesiredInstanceCount` or `sagemaker:inference-component:DesiredCopyCount` |
| Scaling history | `application-autoscaling:DescribeScalingActivities` | Use to time-weight instance count when autoscaling is configured |
| Traffic | CloudWatch `AWS/SageMaker` → `Invocations` (Sum), dimensions `EndpointName`, `VariantName` | Hourly sums over 30 days |
| Utilization | CloudWatch `/aws/sagemaker/Endpoints` → `GPUUtilization`, `GPUMemoryUtilization`, `CPUUtilization`, `MemoryUtilization` | See the normalization rule below |

### SageMaker training, tuning, and development

| Input | Call | Fields |
|-------|------|--------|
| Training jobs | `sagemaker:DescribeTrainingJob` | `ResourceConfig.InstanceType`, `InstanceCount` (or `InstanceGroups`), `TrainingTimeInSeconds`, `BillableTimeInSeconds`, `EnableManagedSpotTraining`, `CheckpointConfig`, `StoppingCondition`, `DebugRuleConfigurations`, `ProfilerConfig`, `TrainingJobStatus` |
| Training utilization | CloudWatch `/aws/sagemaker/TrainingJobs` → `GPUUtilization`, `CPUUtilization`, dimension `Host` | Same normalization rule |
| Tuning jobs | `sagemaker:DescribeHyperParameterTuningJob` | `HyperParameterTuningJobConfig.Strategy` (`Bayesian`, `Hyperband`, `Random`, `Grid`), `TrainingJobEarlyStoppingType` (`Auto`, `Off`), `ResourceLimits.MaxParallelTrainingJobs` |
| Notebook instances | `sagemaker:DescribeNotebookInstance` | `NotebookInstanceStatus`, `InstanceType`, `NotebookInstanceLifecycleConfigName`, `VolumeSizeInGB` |
| Studio apps | `sagemaker:ListApps`, `sagemaker:DescribeDomain` | Apps `InService` and their `ResourceSpec.InstanceType`; idle shutdown under the domain's app lifecycle management `IdleSettings` |
| HyperPod | `sagemaker:DescribeCluster` | `InstanceGroups[].InstanceType`, `CurrentCount` |
| Model optimization | `sagemaker:ListCompilationJobs`, `sagemaker:ListOptimizationJobs` | Existence and recency only |
| Drift monitoring | `sagemaker:ListMonitoringSchedules` | Schedules per endpoint |
| Scheduled retraining | `scheduler:ListSchedules`, `events:ListRules` | Schedules or rules that target SageMaker pipelines or training |

### Amazon Bedrock

| Input | Call / metric | Fields |
|-------|---------------|--------|
| Token volume | CloudWatch `AWS/Bedrock` → `InputTokenCount`, `OutputTokenCount`, `Invocations` (Sum), dimension `ModelId` | Daily sums over 30 days, per Region |
| Provisioned throughput | `bedrock:ListProvisionedModelThroughputs` | `status`, `modelArn`, `modelUnits`, `commitmentDuration` |
| Batch inference | `bedrock:ListModelInvocationJobs` | Existence and recency |
| Model customization | `bedrock:ListModelCustomizationJobs` | `customizationType` (`FINE_TUNING`, `CONTINUED_PRE_TRAINING`, `DISTILLATION`) |
| Cross-Region inference | `bedrock:ListInferenceProfiles` | Profiles in use; their requests can be served from other Regions |

### Data and artifacts

| Input | Call | Use |
|-------|------|-----|
| Model artifact and training data buckets | From `ModelArtifacts.S3ModelArtifacts`, `OutputDataConfig.S3OutputPath`, `InputDataConfig[].DataSource` | Feed into the existing S3 lifecycle and storage-class checks (SUS04-BP02, SUS04-BP03) |
| SageMaker log retention | `logs:DescribeLogGroups` with `logGroupNamePrefix: /aws/sagemaker/` | `retentionInDays` absent means logs never expire |
| Container image cleanup | `ecr:DescribeRepositories`, `ecr:GetLifecyclePolicy` | `LifecyclePolicyNotFoundException` means no cleanup |

## Normalization Rule — Read Before Using Any SageMaker Utilization Metric

SageMaker reports `GPUUtilization`, `GPUMemoryUtilization`, and `CPUUtilization` for endpoints
and jobs as a **sum across devices**: each GPU or core contributes 0–100, so an instance with
four GPUs reports 0–400%. EC2's `CPUUtilization` is 0–100 per instance. The two are not
comparable as reported.

```
utilized_fraction = avg(GPUUtilization) / (100 × gpus_per_instance)
```

Use the same form for `CPUUtilization` with `vcpus_per_instance`. Only inference components
publish `*Normalized` variants (0–100); use those directly when present. A utilized fraction
above 1.0 means the device count is wrong — stop and recheck it rather than reporting the value.

## Accelerator Counts

Derive device counts from `ec2:DescribeInstanceTypes`: `GpuInfo.Gpus[].Count` for GPU
families and `NeuronInfo.NeuronDevices[].Count` for Inferentia and Trainium. For SageMaker
instance types, strip the `ml.` prefix (`ml.g5.2xlarge` → `g5.2xlarge`). If the result is not a
valid EC2 type, record the accelerator count as unknown and omit that resource from accelerator
KPIs rather than guessing.

CPU-only SageMaker instances (`ml.m*`, `ml.c*`, `ml.r*`) are compute, not accelerators: add
their vCPU-hours to Step 4.1.

**Report accelerator-hours per accelerator family** (for example g5, p4d, inf2, trn1). Do not
sum hours across families into one number — an hour of one accelerator is not equivalent to an
hour of another, and a migration between families would otherwise read as no change.

## KPIs

| KPI | Formula | Graded under |
|-----|---------|--------------|
| Inference accelerator intensity | provisioned accelerator-hours ÷ (`Invocations` ÷ 1,000,000), per endpoint and family | SUS05-BP04, SUS02-BP01 |
| Inference accelerator utilization gap | 1 − utilized_fraction, per endpoint | SUS05-BP04 |
| Training accelerator-hours per run | `InstanceCount` × accelerators per instance × `TrainingTimeInSeconds` ÷ 3600, per completed job | SUS03-BP03 |
| Spot share of training | Σ hours of jobs with `EnableManagedSpotTraining` ÷ Σ training hours | SUS03-BP03 |
| Token intensity | (`InputTokenCount` + `OutputTokenCount`) ÷ business output, per `ModelId` | SUS05-BP02, SUS06-BP01 |
| Model mix | share of total tokens per `ModelId` | SUS05-BP02 |
| Idle development capacity | in-service notebook instance-hours and Studio app-hours with no idle shutdown configured | SUS02-BP03, SUS06-BP04 |

Provisioned accelerator-hours for an endpoint = accelerators per instance × instance count ×
hours in the window. With autoscaling, time-weight the instance count from the scaling
activities. Without it, `CurrentInstanceCount` × hours is exact. Serverless endpoints have no
provisioned instances: report their `Invocations` and `ModelSetupTime`, not accelerator-hours.

Tokens are the only resource signal Bedrock exposes. Treat token intensity like the other
intensity KPIs: a change in it is attributable to the customer (prompt length, model choice,
call volume), while emissions for Bedrock stay in "Other" and are not.

## Assessment Mapping

| Lens best practice | NOT MET / PARTIAL when | Graded under | Severity |
|--------------------|------------------------|--------------|----------|
| GENSUS01-BP01, MLSUS03-BP01, MLSUS05-BP01 — scale to zero, serverless, idle shutdown | Real-time endpoint with zero `Invocations` over 30 days | SUS02-BP03 | HIGH |
| | Real-time accelerator endpoint with traffic in fewer than 25% of hourly periods, fixed capacity, and no serverless or asynchronous option | SUS05-BP04 | HIGH |
| | Endpoint with an autoscaling target whose `MinCapacity` never lets it scale in during idle hours | SUS02-BP01 | MEDIUM |
| | Notebook instance in service with no lifecycle configuration, or a Studio domain with idle shutdown disabled | SUS02-BP03 | MEDIUM (HIGH on accelerator instances) |
| | Bedrock provisioned throughput whose model shows near-zero `Invocations` | SUS02-BP03 | HIGH |
| MLSUS05-BP04 — multiple models behind one endpoint | Three or more single-model endpoints using the same container image, each below 20% utilized fraction | SUS05-BP01 | MEDIUM |
| MLSUS05-BP02 — efficient silicon | Previous-generation accelerators (`p3`, `g4dn`, `inf1`) | SUS05-BP02 | MEDIUM |
| | CPU inference on x86 where a Graviton `ml.*g` type exists | SUS05-BP02 | MEDIUM |
| | GPU inference where Inferentia might serve | — | NEEDS HUMAN INPUT — model compatibility with the Neuron SDK cannot be verified from APIs |
| GENSUS01-BP02, MLSUS04-BP01, MLSUS04-BP04 — efficient training and tuning | Tuning jobs using `Grid` or `Random` strategy, or `TrainingJobEarlyStoppingType: Off` | SUS03-BP03 | MEDIUM |
| | Long training jobs (over 4 hours) without managed spot training and without checkpointing | SUS03-BP03 | LOW — spot suits interruptible, non-urgent work only; state the assumption |
| | Long training jobs with no Debugger rules or profiler | SUS03-BP03 | INFO |
| MLSUS03-BP02, MLSUS03-BP03, MLSUS04-BP03, GENSUS02-BP01 — data and artifact lifecycle | Training data or model artifact buckets with no lifecycle configuration | SUS04-BP03 | Per checklist |
| | `/aws/sagemaker/*` log groups with no retention set | SUS04-BP03 | Per checklist |
| | ECR repositories used by training or inference with no lifecycle policy | SUS04-BP05 | Per checklist |
| GENSUS03-BP01, MLSUS05-BP03 — smaller and optimized models | Report token share per model and any distillation, compilation, or optimization jobs | SUS05-BP02 | INFO — whether a smaller model meets the quality bar is the customer's decision; present it as an option, never a finding |
| MLSUS05-BP01 — batch where latency allows | No Bedrock batch inference or SageMaker batch transform for workloads the customer describes as non-interactive | SUS03-BP01 | NEEDS HUMAN INPUT unless the customer has stated latency tolerance |
| MLSUS06-BP02 — retrain only when necessary | Scheduled retraining with no drift monitoring schedule on the served endpoint | SUS03-BP03 | MEDIUM |
| MLSUS06-BP01 — measure material efficiency | No AI KPI from the table above can be computed | SUS06-BP01 | Per checklist |
| MLSUS02-BP02 — sustainable Regions | Region assessment as usual | SUS01-BP01 | Per checklist, with the cross-Region note below |

These need the customer and are always NEEDS HUMAN INPUT: MLSUS01-BP01 (environmental impact
objectives), MLSUS02-BP01 (managed AI services or pre-trained models instead of custom
training), MLSUS04-BP02 (algorithm choice), and the file-format step of MLSUS03-BP03.

## Guards

- **Cross-Region inference.** A Bedrock cross-Region inference profile can serve requests
  outside the calling Region. Do not attribute that usage to the calling Region's grid in a
  SUS01-BP01 assessment, and say so when profiles are in use.
- **GPU visibility on EC2 and EKS.** GPU utilization for EC2 instances and EKS nodes is only
  available if the customer publishes it (CloudWatch agent NVIDIA metrics or a DCGM exporter).
  Without it, mark the utilization gap NEEDS HUMAN INPUT. Never treat a missing metric as idle.
- **Bursty training.** A training fleet idle for most of the window is normal. Assess training
  by accelerator-hours per run and by job configuration, not by window-average utilization.
- **Spot is not universal.** Recommend managed spot training only for work that tolerates
  interruption. Production retraining on a deadline may not.

## Report Additions

In Step 9, add AI/ML rows to Section 2 as their own sub-table, using the KPIs above. Add
endpoints, jobs, notebooks, and Bedrock models to Section 4 as an AI/ML layer. In Section 6,
write the lens ID after the SUS ID, for example `SUS05-BP04 (MLSUS05-BP02)`.

When Bedrock or SageMaker is in scope, Section 3 MUST state: emissions for Amazon Bedrock and
Amazon SageMaker AI are reported under "Other" and cannot be separated from published data; a
dedicated AI account makes them visible by account; the AI KPIs in Section 2 are the measure of
AI efficiency in this review.
