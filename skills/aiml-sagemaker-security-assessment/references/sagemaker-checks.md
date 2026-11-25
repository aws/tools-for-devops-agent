# Amazon SageMaker AI Security Checks (SM-01..SM-25)

This reference lists the 25 Amazon SageMaker AI security checks. Each check is
regional and read-only (list/describe/get only) and reports `Passed`, `Failed`,
or `N/A`.

Every check carries a **Verifiability** classification the report engine must
honor (see `SKILL.md` → "Verify vs. prescribe"):

- **Verifiable** — a read-only call returns the exact configuration; deterministic.
- **Heuristic** — readable but inferred; apply the stated rule, cite the evidence,
  and emit `N/A` (not `Passed`) when evidence is ambiguous or the read is denied.
- **Prescribe-only** — not provable read-only under the DevOps Agent; emit `N/A`
  with remediation in `Resolution`. **Never `Passed`/`Failed`.**

**Classification summary:** Verifiable — SM-01, 04, 07, 09, 10, 11, 12, 13, 14,
15, 16, 17, 18, 19, 20, 21, 23 (17). Heuristic — SM-02 (see note), 03, 05, 06,
08, 22, 24, 25 (8). `SM-02` additionally carries **Prescribe-only** sub-aspects
(stale access, IAM Identity Center) reported as guidance, never `Passed`.

Where noted, a check maps to an AWS Security Hub control ID (SageMaker.1–25) for
cross-reference only — this skill does **not** call `securityhub:*`.

**Service availability note:** Amazon SageMaker Model Monitor and SageMaker Clarify
are closed to new customers (existing customers are unaffected). Never emit
`Failed` for the mere *absence* of Model Monitor or Clarify, and when recommending
remediation for new accounts point at the documented alternative (open-source
monitoring with Amazon QuickSight and Amazon CloudWatch) rather than a service they
cannot enable.

**Locally-encrypted instance types:** `VolumeKmsKeyId` cannot be requested on
instance types with local (instance-store) storage — for example `ml.g4dn` and
`ml.g5`; that storage is hardware-encrypted. Jobs on such types count as encrypted,
not `Failed`, for the volume-encryption checks (SM-17, SM-18, SM-19).

**Scale guardrails:** Checks that list jobs and then `Describe` each one (SM-03,
SM-06, SM-17..SM-21) MUST paginate `List*` calls, restrict to jobs created in the
last 90 days, and describe at most 50 most-recent jobs per check per region. State
the number of jobs listed vs. described in `Finding_Details`; if the cap truncated
the population, say so and never present the result as exhaustive.

---

### SM-01: Internet Access
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.1
- **Read-only APIs:** `sagemaker:ListNotebookInstances`, `sagemaker:DescribeNotebookInstance`, `sagemaker:ListDomains`, `sagemaker:DescribeDomain`
- **Evaluate:** `Failed` when a notebook instance has `DirectInternetAccess=Enabled` or a domain is not `VpcOnly`; `Passed` when all notebooks/domains use VPC connectivity; `N/A` when no notebook instances or domains exist.
- **Resolution:** Configure notebook instances for VPC connectivity with direct internet access disabled and set domains to `VpcOnly` network access.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/infrastructure-security.html

### SM-02: AWS IAM Permissions
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Heuristic (with Prescribe-only sub-aspects — see below)
- **Read-only APIs:** `sagemaker:ListNotebookInstances`, `sagemaker:DescribeNotebookInstance` (notebook `RoleArn`), `sagemaker:ListDomains`, `sagemaker:DescribeDomain` (`DefaultUserSettings.ExecutionRole`), `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:GetRolePolicy` (for the FullAccess aspect only)
- **Evaluate:**
  - *FullAccess (Heuristic):* `Failed` when a SageMaker execution role or domain default role attaches `AmazonSageMakerFullAccess` (cite role + policy); `Passed` only when every inspected role is free of `AmazonSageMakerFullAccess` **and** no inline policy grants `sagemaker:*` or `iam:PassRole` on `Resource: "*"` (cite the roles inspected); `N/A` when no SageMaker roles/domains exist or reads are denied. Per-user-profile and space execution roles are not enumerated by this check — state that coverage limit in `Finding_Details` and never describe the result as covering every SageMaker role.
  - *Stale access (Prescribe-only):* determining unused SageMaker permissions needs `iam:GenerateServiceLastAccessedDetails` (a `Generate*` verb blocked by the read-only guardrail). **Do not call it; do not mark this aspect Passed.** Recommend an out-of-band Access Advisor review in `Resolution`.
  - *IAM Identity Center (Prescribe-only):* whether a domain uses IAM Identity Center with least-privilege assignments is not reliably exposed on the control plane. **Do not mark Passed;** recommend it in `Resolution`.
- **Resolution:** Replace `AmazonSageMakerFullAccess` with least-privilege custom policies. Out of band, review IAM Access Advisor for stale SageMaker access, and configure IAM Identity Center with scoped assignments for domains.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/security-iam.html

### SM-03: Data Protection
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Heuristic (a customer-managed vs. AWS-managed key is inferred from `kms:DescribeKey`)
- **Security Hub control:** SageMaker.21 (notebook instances encrypted with a customer-managed key)
- **Read-only APIs:** `sagemaker:ListNotebookInstances`, `sagemaker:DescribeNotebookInstance`, `sagemaker:ListDomains`, `sagemaker:DescribeDomain`, `sagemaker:ListTrainingJobs`, `sagemaker:DescribeTrainingJob`, `kms:DescribeKey`
- **Evaluate:** Apply per resource type — notebook instances and domains: `Failed` when `KmsKeyId` is absent or `kms:DescribeKey` reports `KeyManager=AWS`; training jobs (see scale guardrails): `Failed` when `ResourceConfig.VolumeKmsKeyId` is absent on an instance type that supports it, or `EnableInterContainerTrafficEncryption` is false. Inter-container encryption applies to training jobs only, not to notebooks or domains. `Passed` when all inspected resources meet the rule (cite key ARNs and `KeyManager`); `N/A` when no SageMaker resources exist or `kms:DescribeKey` is denied.
- **Resolution:** Configure encryption at rest with customer-managed KMS keys and enable inter-container/VPC traffic encryption.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/key-management.html

### SM-04: Amazon GuardDuty Integration
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `guardduty:ListDetectors`, `guardduty:GetDetector`
- **Evaluate:** `ListDetectors` returns IDs only, so always call `GetDetector` on each ID and test `Status`. `Failed` when no detector exists or none has `Status=ENABLED` (a suspended/disabled detector is `Failed`); `Passed` when a detector has `Status=ENABLED`; `N/A` when either read is denied.
- **Resolution:** Enable Amazon GuardDuty to detect anomalous access patterns and potential data exfiltration in SageMaker workloads.
- **Reference:** https://docs.aws.amazon.com/guardduty/latest/ug/ai-protection.html

### SM-05: MLOps Features
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `sagemaker:ListModelPackageGroups`, `sagemaker:ListModelPackages`, `sagemaker:ListFeatureGroups`, `sagemaker:ListPipelines`, `sagemaker:ListPipelineExecutions`
- **Evaluate:** Advisory check — never emit `Failed` for a feature that is simply not adopted. `Passed` when MLOps features show active use (versioned model packages, `Created` feature groups, pipelines with executions — cite which); `N/A` (state Informational in `Finding_Details`) when features are unused or absent, or when none exist.
- **Resolution:** Adopt Model Registry versioning, Feature Store, and Pipelines to automate and govern ML workflows.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/mlops.html

### SM-06: Clarify Usage
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `sagemaker:ListProcessingJobs`, `sagemaker:DescribeProcessingJob`
- **Evaluate:** Advisory check — never emit `Failed` (a failed job is an operational issue, not a misconfiguration). `Passed` when Clarify-type processing jobs are present and have completed; `N/A` when no Clarify jobs are found or only failed ones exist (cite them). Identify Clarify jobs by the Clarify image/app specification, and say so in `Finding_Details`.
- **Resolution:** Existing customers can use SageMaker Clarify processing jobs for bias detection and explainability. SageMaker Clarify is closed to new customers; for new accounts see the documented alternatives in the AWS documentation.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/clarify-configure-processing-jobs.html

### SM-07: Model Monitor
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListMonitoringSchedules`, `sagemaker:DescribeMonitoringSchedule`
- **Evaluate:** `Failed` when a monitoring schedule status is not `Scheduled`/active; `Passed` when Model Monitor schedules are active; `N/A` when no monitoring schedules exist.
- **Resolution:** Existing customers: fix or recreate the failed Model Monitor schedule. Model Monitor is closed to new customers; for new accounts use open-source monitoring with Amazon QuickSight and Amazon CloudWatch.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor.html

### SM-08: Model Registry
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `sagemaker:ListModelPackageGroups`, `sagemaker:ListModelPackages`
- **Evaluate:** `Failed` when a model package group is empty or has no `Approved` model versions (cite group); `Passed` when the registry has approved, versioned packages; `N/A` when no model package groups exist.
- **Resolution:** Implement Model Registry versioning and approval workflows to manage model lifecycle.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html

### SM-09: Notebook Root Access
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.3
- **Read-only APIs:** `sagemaker:ListNotebookInstances`, `sagemaker:DescribeNotebookInstance`
- **Evaluate:** `Failed` when a notebook instance has `RootAccess=Enabled`; `Passed` when all notebook instances have `RootAccess=Disabled`; `N/A` when no notebook instances exist.
- **Resolution:** Set `RootAccess=Disabled` on notebook instances to prevent privilege escalation.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/nbi-root-access.html

### SM-10: Notebook Amazon VPC Deployment
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.2
- **Read-only APIs:** `sagemaker:ListNotebookInstances`, `sagemaker:DescribeNotebookInstance`
- **Evaluate:** `Failed` when a notebook instance has no `SubnetId` (not in a custom VPC); `Passed` when all notebook instances specify a subnet/security group; `N/A` when no notebook instances exist.
- **Resolution:** Create notebook instances within a custom VPC by specifying `SubnetId` and `SecurityGroupIds`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/appendix-notebook-and-internet-access.html

### SM-11: Model Network Isolation
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.5
- **Read-only APIs:** `sagemaker:ListModels`, `sagemaker:DescribeModel`
- **Evaluate:** `Failed` when a model has `EnableNetworkIsolation=false`; `Passed` when all models have it `true`; `N/A` when no models exist.
- **Resolution:** Set `EnableNetworkIsolation=True` on models to block outbound calls from inference containers.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/mkt-algo-model-internet-free.html

### SM-12: Endpoint Instance Count
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.4
- **Read-only APIs:** `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`
- **Evaluate:** Applies to instance-based variants only. Skip serverless variants (`CurrentServerlessConfig` present, no `CurrentInstanceCount`) and treat async endpoints that scale to zero as out of scope — report them as `N/A` with the reason. `Failed` when an `InService` instance-based variant has `CurrentInstanceCount <= 1`; `Passed` when all instance-based variants have multiple instances; `N/A` when no `InService` instance-based endpoints exist.
- **Resolution:** Configure production endpoints with at least two instances across Availability Zones for high availability.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling.html

### SM-13: Monitoring Network Isolation
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.14 (also .11, .12, .20, .25 for the per-type job definitions)
- **Read-only APIs:** `sagemaker:ListMonitoringSchedules`, `sagemaker:DescribeMonitoringSchedule`, `sagemaker:DescribeDataQualityJobDefinition`, `sagemaker:DescribeModelQualityJobDefinition`, `sagemaker:DescribeModelBiasJobDefinition`, `sagemaker:DescribeModelExplainabilityJobDefinition`
- **Evaluate:** A schedule that references a job definition (`MonitoringJobDefinitionName` + `MonitoringType`) carries no `NetworkConfig` itself — read `MonitoringType` and call the matching `Describe*JobDefinition` to get `NetworkConfig.EnableNetworkIsolation`. For a schedule with an inline `MonitoringJobDefinition`, read `NetworkConfig` from `DescribeMonitoringSchedule`. `Failed` when network isolation is not enabled; `Passed` when enabled on all schedules; `N/A` when no schedules exist or the definition read is denied.
- **Resolution:** Enable network isolation in the monitoring job definition `NetworkConfig`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_MonitoringNetworkConfig.html

### SM-14: Model Container Repository
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListModels`, `sagemaker:DescribeModel`
- **Security Hub control:** SageMaker.16 (primary container), SageMaker.19 (multi-container inference pipelines)
- **Evaluate:** `Failed` when a model uses `RepositoryAccessMode=Platform`; `Passed` when models use `Vpc` repository access; `N/A` when no models exist.
- **Resolution:** Set `RepositoryAccessMode=Vpc` in `ImageConfig` so SageMaker pulls images from a private Docker registry hosted in your VPC.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-container-repositories.html

### SM-15: Feature Store Encryption
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.17 (offline store)
- **Read-only APIs:** `sagemaker:ListFeatureGroups`, `sagemaker:DescribeFeatureGroup`
- **Evaluate:** `Failed` when a feature group offline store lacks `KmsKeyId`; `Passed` when all offline stores use KMS; `N/A` when no feature groups with offline stores exist.
- **Resolution:** Configure `KmsKeyId` in `OfflineStoreConfig.S3StorageConfig` with a customer-managed key.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store-security.html

### SM-16: Data Quality Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.9
- **Read-only APIs:** `sagemaker:ListDataQualityJobDefinitions`, `sagemaker:DescribeDataQualityJobDefinition`
- **Evaluate:** `Failed` when a data quality job definition `NetworkConfig` lacks inter-container traffic encryption; `Passed` when enabled on all; `N/A` when none exist.
- **Resolution:** Enable `EnableInterContainerTrafficEncryption` in the `NetworkConfig`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor-data-quality.html

### SM-17: Processing Job Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListProcessingJobs`, `sagemaker:DescribeProcessingJob`
- **Evaluate:** `Failed` when a processing job `ProcessingResources.ClusterConfig` lacks `VolumeKmsKeyId` **and** its `InstanceType` supports EBS volume encryption (jobs on locally-encrypted types such as `ml.g4dn`/`ml.g5` count as encrypted); `Passed` when configured; `N/A` when none exist.
- **Resolution:** Configure `VolumeKmsKeyId` to encrypt attached EBS volumes.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/processing-job.html

### SM-18: Transform Job Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListTransformJobs`, `sagemaker:DescribeTransformJob`
- **Evaluate:** `Failed` when a transform job `TransformResources` lacks `VolumeKmsKeyId` **and** its `InstanceType` supports EBS volume encryption (locally-encrypted types such as `ml.g4dn`/`ml.g5` count as encrypted); `Passed` when configured; `N/A` when none exist.
- **Resolution:** Configure `VolumeKmsKeyId` in `TransformResources`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html

### SM-19: Hyperparameter Tuning Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListHyperParameterTuningJobs`, `sagemaker:DescribeHyperParameterTuningJob`
- **Evaluate:** `Failed` when a tuning job `TrainingJobDefinition.ResourceConfig` lacks `VolumeKmsKeyId` **and** its `InstanceType` supports EBS volume encryption (locally-encrypted types such as `ml.g4dn`/`ml.g5` count as encrypted); `Passed` when configured; `N/A` when none exist.
- **Resolution:** Configure `VolumeKmsKeyId` in `ResourceConfig`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/automatic-model-tuning.html

### SM-20: Compilation Job Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListCompilationJobs`, `sagemaker:DescribeCompilationJob`
- **Evaluate:** `Failed` when a compilation job `OutputConfig` lacks `KmsKeyId`; `Passed` when configured; `N/A` when none exist.
- **Resolution:** Configure `KmsKeyId` in `OutputConfig`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/neo.html

### SM-21: AutoML Network Isolation
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListAutoMLJobs`, `sagemaker:DescribeAutoMLJob`
- **Evaluate:** `Failed` when an AutoML job `SecurityConfig` lacks inter-container traffic encryption; `Passed` when enabled; `N/A` when none exist.
- **Resolution:** Enable `EnableInterContainerTrafficEncryption` in `AutoMLJobConfig.SecurityConfig`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_AutoMLSecurityConfig.html

### SM-22: Model Approval Workflow
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `sagemaker:ListModelPackageGroups`, `sagemaker:ListModelPackages`
- **Read-only APIs (addition):** `sagemaker:ListActions` (filter `ActionType=Approval`) — SageMaker records an `Approval` lineage action for every model approval status change (named `<group>-<version>-<Status>-…`).
- **Evaluate:** `ListModelPackages` shows the *current* status only, so it cannot show that a version "never" passed through manual approval. Use the `Approval` lineage actions as the history. `Failed` only when a group's versions are all `Approved` **and** the lineage actions show no `PendingManualApproval`/`Rejected` transition for them (auto-approval), or when many versions remain stuck `PendingManualApproval` (cite counts); `Passed` when the history shows versions were gated by manual approval (cite group/version and the transitions); `N/A` when no model package groups exist **or the approval history cannot be read or is ambiguous** — never infer auto-approval from current status alone. State the counts and the lineage evidence in `Finding_Details`.
- **Resolution:** Configure Model Registry approval workflows requiring manual approval or automated validation before production.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html

### SM-23: Model Drift Detection
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListEndpoints`, `sagemaker:ListMonitoringSchedules`, `sagemaker:DescribeMonitoringSchedule`
- **Evaluate:** Model Monitor is closed to new customers, so absence of a schedule alone is not a failure. `Passed` when an `InService` endpoint has an active (`Scheduled`) monitoring schedule; `Failed` only when a monitoring schedule exists for the endpoint but is inactive/failed (cite status); `N/A` when an endpoint has no Model Monitor schedule — report it as Informational and record in `Finding_Details` that other drift tooling (Amazon CloudWatch/QuickSight-based monitoring) cannot be read from the control plane; `N/A` when no `InService` endpoints exist.
- **Resolution:** Existing customers: configure Model Monitor (data quality, model quality, bias, feature attribution) for production endpoints. New customers (Model Monitor unavailable): use open-source monitoring with Amazon QuickSight and Amazon CloudWatch.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor.html

### SM-24: A/B Testing and Shadow Deployment
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`
- **Evaluate:** `Passed` when shadow (`ShadowProductionVariants`) or A/B (multiple `ProductionVariants`) patterns are detected; `N/A` (Informational) when endpoints use a single production variant only; `N/A` when no `InService` endpoints exist. This is an advisory check — do not emit `Failed`.
- **Resolution:** Implement A/B testing or shadow deployments to validate new model versions safely.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-ab-testing.html

### SM-25: ML Lineage Tracking
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `sagemaker:ListExperiments`, `sagemaker:ListTrials`, `sagemaker:ListAssociations`
- **Evaluate:** Advisory check — never emit `Failed` for an unused feature. `ListAssociations` accepts only experiment, trial-component, artifact, action, or context ARNs (not model packages); use it with ARNs obtained from experiments/trial components. `Passed` when Experiments with trials or lineage associations are in use (cite counts); `N/A` (Informational) when experiments exist without trials, or when no experiments exist.
- **Resolution:** Implement SageMaker Experiments, Trials, and lineage associations to track the ML pipeline from data to deployed model.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/experiments.html
