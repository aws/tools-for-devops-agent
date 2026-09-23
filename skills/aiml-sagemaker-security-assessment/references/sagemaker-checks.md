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

**Classification summary:** Verifiable — SM-01, 03, 04, 07, 09, 10, 11, 12, 13,
14, 15, 16, 17, 18, 19, 20, 21, 23 (18). Heuristic — SM-02 (see note), 05, 06,
08, 22, 24, 25 (7). `SM-02` additionally carries **Prescribe-only** sub-aspects
(stale access, IAM Identity Center) reported as guidance, never `Passed`.

Where noted, a check maps to an AWS Security Hub control ID for cross-reference
only — this skill does **not** call `securityhub:*`.

---

### SM-01: Internet Access
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.2
- **Read-only APIs:** `sagemaker:ListNotebookInstances`, `sagemaker:DescribeNotebookInstance`, `sagemaker:ListDomains`, `sagemaker:DescribeDomain`
- **Evaluate:** `Failed` when a notebook instance has `DirectInternetAccess=Enabled` or a domain is not `VpcOnly`; `Passed` when all notebooks/domains use VPC connectivity; `N/A` when no notebook instances or domains exist.
- **Resolution:** Configure notebook instances for VPC connectivity with direct internet access disabled and set domains to `VpcOnly` network access.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/infrastructure-security.html

### SM-02: AWS IAM Permissions
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Heuristic (with Prescribe-only sub-aspects — see below)
- **Read-only APIs:** `sagemaker:ListDomains`, `sagemaker:DescribeDomain`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:GetRolePolicy` (for the FullAccess aspect only)
- **Evaluate:**
  - *FullAccess (Heuristic):* `Failed` when a SageMaker execution role or domain default role attaches `AmazonSageMakerFullAccess` (cite role + policy); `Passed` when inspected roles use scoped policies; `N/A` when no SageMaker roles/domains exist or reads are denied.
  - *Stale access (Prescribe-only):* determining unused SageMaker permissions needs `iam:GenerateServiceLastAccessedDetails` (a `Generate*` verb blocked by the read-only guardrail). **Do not call it; do not mark this aspect Passed.** Recommend an out-of-band Access Advisor review in `Resolution`.
  - *IAM Identity Center (Prescribe-only):* whether a domain uses IAM Identity Center with least-privilege assignments is not reliably exposed on the control plane. **Do not mark Passed;** recommend it in `Resolution`.
- **Resolution:** Replace `AmazonSageMakerFullAccess` with least-privilege custom policies. Out of band, review IAM Access Advisor for stale SageMaker access, and configure IAM Identity Center with scoped assignments for domains.
- **Reference:** https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/security-iam.html

### SM-03: Data Protection
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.1
- **Read-only APIs:** `sagemaker:ListNotebookInstances`, `sagemaker:DescribeNotebookInstance`, `sagemaker:ListDomains`, `sagemaker:DescribeDomain`, `sagemaker:ListTrainingJobs`, `sagemaker:DescribeTrainingJob`
- **Evaluate:** `Failed` when resources lack a `KmsKeyId`, use an AWS-managed key, or lack inter-container/VPC traffic encryption; `Passed` when all inspected resources use customer-managed KMS and in-transit encryption; `N/A` when no SageMaker resources exist.
- **Resolution:** Configure encryption at rest with customer-managed KMS keys and enable inter-container/VPC traffic encryption.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/key-management.html

### SM-04: Amazon GuardDuty Integration
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `guardduty:ListDetectors`
- **Evaluate:** `Failed` when no GuardDuty detector is enabled in the region; `Passed` when a detector is enabled; `N/A` when the read is denied.
- **Resolution:** Enable Amazon GuardDuty to detect anomalous access patterns and potential data exfiltration in SageMaker workloads.
- **Reference:** https://docs.aws.amazon.com/guardduty/latest/ug/ai-protection.html

### SM-05: MLOps Features
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `sagemaker:ListModelPackageGroups`, `sagemaker:ListModelPackages`, `sagemaker:ListFeatureGroups`, `sagemaker:ListPipelines`, `sagemaker:ListPipelineExecutions`
- **Evaluate:** `Failed` when model groups have no versioned packages, feature groups are not in `Created` state, or pipelines have no execution history (cite which); `Passed` when MLOps features show active use; `N/A` when no model groups, feature groups, or pipelines exist.
- **Resolution:** Adopt Model Registry versioning, Feature Store, and Pipelines to automate and govern ML workflows.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/mlops.html

### SM-06: Clarify Usage
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `sagemaker:ListProcessingJobs`, `sagemaker:DescribeProcessingJob`
- **Evaluate:** `Failed` when a Clarify-type processing job is in a `Failed` state (cite job); `Passed` when Clarify jobs are present and succeeding; `N/A` when no Clarify jobs are found. Identify Clarify jobs by the Clarify image/app specification, and say so in `Finding_Details`.
- **Resolution:** Implement SageMaker Clarify processing jobs for bias detection and model explainability.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/clarify-configure-processing-jobs.html

### SM-07: Model Monitor
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListMonitoringSchedules`, `sagemaker:DescribeMonitoringSchedule`
- **Evaluate:** `Failed` when a monitoring schedule status is not `Scheduled`/active; `Passed` when Model Monitor schedules are active; `N/A` when no monitoring schedules exist.
- **Resolution:** Configure Model Monitor schedules for drift detection on production endpoints.
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
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.4
- **Read-only APIs:** `sagemaker:ListModels`, `sagemaker:DescribeModel`
- **Evaluate:** `Failed` when a model has `EnableNetworkIsolation=false`; `Passed` when all models have it `true`; `N/A` when no models exist.
- **Resolution:** Set `EnableNetworkIsolation=True` on models to block outbound calls from inference containers.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/mkt-algo-model-internet-free.html

### SM-12: Endpoint Instance Count
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Security Hub control:** SageMaker.5
- **Read-only APIs:** `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`
- **Evaluate:** `Failed` when an `InService` endpoint variant has `CurrentInstanceCount <= 1`; `Passed` when all variants have multiple instances; `N/A` when no `InService` endpoints exist.
- **Resolution:** Configure production endpoints with at least two instances across Availability Zones for high availability.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling.html

### SM-13: Monitoring Network Isolation
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListMonitoringSchedules`, `sagemaker:DescribeMonitoringSchedule`
- **Evaluate:** `Failed` when a monitoring job definition `NetworkConfig.EnableNetworkIsolation` is not enabled; `Passed` when enabled on all schedules; `N/A` when no monitoring schedules exist.
- **Resolution:** Enable network isolation in the monitoring job definition `NetworkConfig`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_MonitoringNetworkConfig.html

### SM-14: Model Container Repository
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListModels`, `sagemaker:DescribeModel`
- **Evaluate:** `Failed` when a model uses `RepositoryAccessMode=Platform`; `Passed` when models use `Vpc` repository access; `N/A` when no models exist.
- **Resolution:** Set `RepositoryAccessMode=Vpc` in `ImageConfig` to pull images from private ECR through the VPC.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-container-repositories.html

### SM-15: Feature Store Encryption
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListFeatureGroups`, `sagemaker:DescribeFeatureGroup`
- **Evaluate:** `Failed` when a feature group offline store lacks `KmsKeyId`; `Passed` when all offline stores use KMS; `N/A` when no feature groups with offline stores exist.
- **Resolution:** Configure `KmsKeyId` in `OfflineStoreConfig.S3StorageConfig` with a customer-managed key.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store-security.html

### SM-16: Data Quality Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListDataQualityJobDefinitions`, `sagemaker:DescribeDataQualityJobDefinition`
- **Evaluate:** `Failed` when a data quality job definition `NetworkConfig` lacks inter-container traffic encryption; `Passed` when enabled on all; `N/A` when none exist.
- **Resolution:** Enable `EnableInterContainerTrafficEncryption` in the `NetworkConfig`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor-data-quality.html

### SM-17: Processing Job Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListProcessingJobs`, `sagemaker:DescribeProcessingJob`
- **Evaluate:** `Failed` when a processing job `ProcessingResources.ClusterConfig` lacks `VolumeKmsKeyId`; `Passed` when configured; `N/A` when none exist.
- **Resolution:** Configure `VolumeKmsKeyId` to encrypt attached EBS volumes.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/processing-job.html

### SM-18: Transform Job Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListTransformJobs`, `sagemaker:DescribeTransformJob`
- **Evaluate:** `Failed` when a transform job `TransformResources` lacks `VolumeKmsKeyId`; `Passed` when configured; `N/A` when none exist.
- **Resolution:** Configure `VolumeKmsKeyId` in `TransformResources`.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html

### SM-19: Hyperparameter Tuning Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListHyperParameterTuningJobs`, `sagemaker:DescribeHyperParameterTuningJob`
- **Evaluate:** `Failed` when a tuning job `TrainingJobDefinition.ResourceConfig` lacks `VolumeKmsKeyId`; `Passed` when configured; `N/A` when none exist.
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
- **Evaluate:** `Failed` when all model versions in a group are `Approved` with none ever `PendingManualApproval`/`Rejected` (auto-approval signal) or when many remain stuck `PendingManualApproval` (cite counts); `Passed` when an approval workflow shows a healthy mix; `N/A` when no model package groups exist. State the counts observed in `Finding_Details`.
- **Resolution:** Configure Model Registry approval workflows requiring manual approval or automated validation before production.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html

### SM-23: Model Drift Detection
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `sagemaker:ListEndpoints`, `sagemaker:ListMonitoringSchedules`, `sagemaker:DescribeMonitoringSchedule`
- **Evaluate:** `Failed` when an `InService` endpoint has no monitoring schedule, or is missing data/model-quality monitoring, or its schedules are inactive; `Passed` when endpoints have active drift detection; `N/A` when no `InService` endpoints exist.
- **Resolution:** Configure Model Monitor (data quality, model quality, bias, feature attribution) for production endpoints.
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
- **Read-only APIs:** `sagemaker:ListExperiments`, `sagemaker:ListTrials`, `sagemaker:ListModelPackageGroups`, `sagemaker:ListModelPackages`, `sagemaker:ListAssociations`
- **Evaluate:** `Failed` when experiments exist but have no trials, or model packages have no lineage associations (cite which); `Passed` when Experiments/Trials/associations are used; `N/A` when no experiments exist.
- **Resolution:** Implement SageMaker Experiments, Trials, and lineage associations to track the ML pipeline from data to deployed model.
- **Reference:** https://docs.aws.amazon.com/sagemaker/latest/dg/experiments.html
