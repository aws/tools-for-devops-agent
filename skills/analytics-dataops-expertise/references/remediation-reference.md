# Remediation Reference (verbatim dictionary — 26 entries)

Loaded by SKILL.md via `read_skill_resource` before the Prioritized Recommendations
section is written. For every question scored ≤ 3, copy the "Why it matters" line and
"Resolve" steps verbatim (observed values may be instantiated) and include the
"Dive deeper" links EXACTLY as written. Never emit a documentation link not in this file.

#### Q3 Data Architecture Patterns
**Why it matters:** Ad-hoc storage without a governed catalog or open table formats makes data hard to discover, evolve, and maintain, and blocks self-serve analytics.
**Resolve:** 1) Catalog data with AWS Glue Data Catalog and run crawlers to keep schemas current 2) Adopt an open table format (Apache Iceberg) for transactional tables needing upserts/time-travel 3) Apply Lake Formation governance (LF-Tags, per-domain permissions) and schedule table maintenance (compaction, vacuum)
**Dive deeper:** [AWS Glue Data Catalog](https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html) · [Using Apache Iceberg on AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/apache-iceberg-on-aws/introduction.html)

#### Q4 Real-time Data Processing
**Why it matters:** Batch-only pipelines add hours/days of latency; time-sensitive decisions (fraud, risk, personalization) need streaming ingestion and processing.
**Resolve:** 1) Introduce streaming ingestion with Amazon Kinesis Data Streams or Amazon MSK 2) Add stream processing with Managed Service for Apache Flink for real-time transforms/aggregations 3) Use Firehose for streaming delivery to S3/Redshift/OpenSearch with buffering
**Dive deeper:** [Amazon Kinesis Data Streams](https://docs.aws.amazon.com/streams/latest/dev/introduction.html) · [Managed Service for Apache Flink](https://docs.aws.amazon.com/managed-flink/latest/java/what-is.html)

#### Q5 Change Data Capture (CDC)
**Why it matters:** Full refreshes are slow, costly, and risk data loss; CDC captures incremental changes for timely, consistent downstream data.
**Resolve:** 1) Use AWS DMS with `full-load-and-cdc` tasks for relational sources 2) Enable DMS event subscriptions to monitor task health and failures 3) For DynamoDB sources, enable DynamoDB Streams (or Kinesis Data Streams for DynamoDB) to propagate item-level changes
**Dive deeper:** [AWS DMS change data capture](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Task.CDC.html) · [DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)

#### Q6 Capacity Planning
**Why it matters:** Manual capacity management leads to reactive scaling after incidents and over-provisioning; automated scaling matches capacity to demand.
**Resolve:** 1) Enable Application Auto Scaling target tracking on DynamoDB, ECS, and other data services 2) Add scheduled scaling for predictable peaks 3) Review utilization trends periodically and set forecasts for growth
**Dive deeper:** [Application Auto Scaling](https://docs.aws.amazon.com/autoscaling/application/userguide/what-is-application-auto-scaling.html) · [DynamoDB auto scaling](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/AutoScaling.html)

#### Q7 Fault Tolerance & High Availability
**Why it matters:** Single-AZ, no-replica deployments risk full data-service unavailability during an AZ failure.
**Resolve:** 1) Enable Multi-AZ on RDS/Aurora and add read replicas for critical databases 2) Enable zone awareness (3-AZ) on OpenSearch and multi-broker/multi-AZ on MSK 3) Test automated failover and document RPO/RTO for each stateful service
**Dive deeper:** [Amazon RDS Multi-AZ](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html) · [Reliability Pillar — AWS Well-Architected](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)

#### Q8 Disaster Recovery
**Why it matters:** Without backups and cross-region copies, a regional failure or accidental deletion can cause permanent data loss with no defined recovery target.
**Resolve:** 1) Centralize backups with AWS Backup plans covering all data services; verify recent successful runs 2) Enable point-in-time recovery (PITR) on RDS and DynamoDB 3) Configure cross-region backup copy and define + test RPO/RTO targets
**Dive deeper:** [AWS Backup](https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html) · [Disaster recovery of workloads on AWS](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-workloads-on-aws.html)

#### Q11 Workload Analytics
**Why it matters:** Without dashboards and custom metrics for data services, teams lack visibility into workload behavior and cannot spot degradation early.
**Resolve:** 1) Build CloudWatch dashboards covering each data-service namespace 2) Publish custom/business metrics for pipeline throughput and freshness 3) Review dashboards in operational cadences, not just during incidents
**Dive deeper:** [Using CloudWatch dashboards](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html) · [Publishing custom metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/publishingMetrics.html)

#### Q12 Monitoring & Optimization
**Why it matters:** Missing alarms on data services means pipeline failures and resource saturation go undetected until they cause customer impact.
**Resolve:** 1) Create CloudWatch alarms across all active data-service namespaces; add composite alarms to reduce noise 2) Wire alarms to SNS with confirmed subscriptions 3) Add EventBridge rules that trigger Lambda/SSM automation for auto-remediation of common failures
**Dive deeper:** [Using CloudWatch alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html) · [What is Amazon EventBridge?](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html)

#### Q13 Application Monitoring
**Why it matters:** Without distributed tracing, root-causing latency and errors across data services and pipelines is slow and guesswork-driven.
**Resolve:** 1) Enable AWS X-Ray tracing with custom sampling rules and X-Ray groups 2) Add CloudWatch RUM for user-facing data apps 3) Correlate traces with logs using CloudWatch ServiceLens
**Dive deeper:** [AWS X-Ray](https://docs.aws.amazon.com/xray/latest/devguide/aws-xray.html) · [Using ServiceLens](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ServiceLens.html)

#### Q14 Drift Detection
**Why it matters:** Without a schema registry or data quality rules, schema and data drift silently break downstream consumers.
**Resolve:** 1) Adopt AWS Glue Schema Registry and enforce compatibility on producers 2) Define AWS Glue Data Quality rulesets on critical datasets 3) Alert on schema-compatibility and DQ-rule failures
**Dive deeper:** [AWS Glue Schema Registry](https://docs.aws.amazon.com/glue/latest/dg/schema-registry.html) · [AWS Glue Data Quality](https://docs.aws.amazon.com/glue/latest/dg/glue-data-quality.html)

#### Q19 SLA Management
**Why it matters:** Without SLI/SLO-style alarms, there is no objective signal when a data service breaches its reliability or latency targets.
**Resolve:** 1) Define SLIs (availability, latency, freshness) per critical data service 2) Create CloudWatch alarms with appropriate `treatMissingData` settings as SLO monitors 3) Track error budgets and review breaches in operational reviews
**Dive deeper:** [Using CloudWatch alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html) · [Operational Excellence Pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html)

#### Q20 User Experience
**Why it matters:** Report staleness and dashboard latency degrade the data consumer experience but go unnoticed without UX monitoring.
**Resolve:** 1) Add CloudWatch RUM to user-facing analytics apps 2) Monitor QuickSight dataset refresh success and dashboard load times 3) Alert on refresh failures and staleness thresholds
**Dive deeper:** [CloudWatch RUM](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-RUM.html) · [Refreshing QuickSight datasets](https://docs.aws.amazon.com/quicksight/latest/user/refreshing-imported-data.html)

#### Q23 Infrastructure Pipeline
**Why it matters:** Manual provisioning is error-prone and unrepeatable; IaC and CI/CD make data infrastructure consistent, reviewable, and recoverable.
**Resolve:** 1) Define data infrastructure as code (CloudFormation/CDK) 2) Deploy through a CI/CD pipeline (CodePipeline) with review gates 3) Add drift detection and policy checks to the pipeline
**Dive deeper:** [What is AWS CloudFormation?](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html) · [What is AWS CodePipeline?](https://docs.aws.amazon.com/codepipeline/latest/userguide/welcome.html)

#### Q24 Orchestration
**Why it matters:** Cron/manual triggers can't express cross-pipeline dependencies, retries, or SLAs, leading to fragile, hard-to-recover data pipelines.
**Resolve:** 1) Orchestrate with Amazon MWAA (Airflow), AWS Step Functions, or Glue Workflows 2) Model cross-pipeline dependencies and configure retry/backoff policies 3) Add event-driven triggers and SLA-based scheduling
**Dive deeper:** [Amazon MWAA](https://docs.aws.amazon.com/mwaa/latest/userguide/what-is-mwaa.html) · [AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)

#### Q25 Version Management
**Why it matters:** Outdated engine versions and deprecated Lambda runtimes miss security patches and can stop functioning when runtimes reach end of support.
**Resolve:** 1) Upgrade RDS/OpenSearch/EKS engines to within one minor version of the latest supported 2) Migrate deprecated Lambda runtimes to current supported versions 3) Configure SSM Patch Manager baselines and scheduled maintenance windows
**Dive deeper:** [Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) · [AWS Systems Manager Patch Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/patch-manager.html)

#### Q26 Data Quality Testing
**Why it matters:** Without executed data quality rules, bad data flows to consumers undetected, eroding trust and causing downstream errors.
**Resolve:** 1) Define AWS Glue Data Quality rulesets on critical tables 2) Schedule rule evaluation in pipelines and capture results 3) Alert on rule failures and track quality scores over time
**Dive deeper:** [AWS Glue Data Quality](https://docs.aws.amazon.com/glue/latest/dg/glue-data-quality.html) · [Getting started with Glue Data Quality](https://docs.aws.amazon.com/glue/latest/dg/data-quality-getting-started.html)

#### Q29 Metadata Management & Catalog
**Why it matters:** Without a centralized catalog, data assets are discovered manually with inconsistent metadata, blocking governance and self-serve analytics.
**Resolve:** 1) Centralize metadata in AWS Glue Data Catalog; run crawlers to keep it current 2) Add table/column descriptions and business context 3) Consider Amazon DataZone for organization-wide discovery and governance
**Dive deeper:** [AWS Glue Data Catalog](https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html) · [What is Amazon DataZone?](https://docs.aws.amazon.com/datazone/latest/userguide/what-is-datazone.html)

#### Q30 Lineage
**Why it matters:** Without lineage, impact analysis and root-cause investigation across pipelines are manual and slow, and schema changes cause surprise breakages.
**Resolve:** 1) Capture pipeline dependencies with Glue Workflows or Step Functions 2) Adopt a lineage capability (e.g., Amazon DataZone / OpenLineage integration) for upstream/downstream mapping 3) Track schema evolution and alert on drift
**Dive deeper:** [Amazon DataZone data lineage](https://docs.aws.amazon.com/datazone/latest/userguide/data-lineage.html) · [AWS Glue Workflows](https://docs.aws.amazon.com/glue/latest/dg/workflows_overview.html)

#### Q31 Data Classification
**Why it matters:** Without automated classification, sensitive data (PII) can be stored or shared without appropriate controls, creating compliance risk.
**Resolve:** 1) Enable Amazon Macie and schedule classification jobs on S3 data 2) Apply Lake Formation LF-Tags and cell-level filters based on sensitivity 3) Document a classification policy and enforce it via tag-based access
**Dive deeper:** [Amazon Macie](https://docs.aws.amazon.com/macie/latest/user/what-is-macie.html) · [Lake Formation tag-based access control](https://docs.aws.amazon.com/lake-formation/latest/dg/tag-based-access-control.html)

#### Q32 Data Protection
**Why it matters:** Unencrypted data at rest and missing point-in-time recovery expose data to compromise and make recovery from corruption/deletion impossible.
**Resolve:** 1) Enable encryption at rest with AWS KMS (prefer customer-managed keys) across S3, RDS, DynamoDB, and analytics services 2) Enable PITR on RDS and DynamoDB 3) Enable key rotation and review key policies
**Dive deeper:** [AWS KMS concepts](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html) · [Data Protection — Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/data-protection.html)

#### Q33 Access Control
**Why it matters:** Broad IAM and no fine-grained data permissions violate least privilege and make it hard to prove who can access which data.
**Resolve:** 1) Use Lake Formation permissions for fine-grained (database/table/column) data access 2) Tighten IAM policies toward least privilege 3) Add AWS Config rules to detect and track access-control compliance
**Dive deeper:** [Lake Formation permissions](https://docs.aws.amazon.com/lake-formation/latest/dg/lake-formation-permissions.html) · [IAM security best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

#### Q36 Resource Tagging
**Why it matters:** Low tag coverage prevents cost allocation, ownership tracking, and automated governance across the data estate.
**Resolve:** 1) Define a tagging standard (Environment, Owner, CostCenter) and activate cost-allocation tags 2) Backfill tags on untagged data resources 3) Enforce tagging with AWS Config rules or tag policies
**Dive deeper:** [Tagging AWS resources](https://docs.aws.amazon.com/tag-editor/latest/userguide/tagging.html) · [Activating cost allocation tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/activating-tags.html)

#### Q37 Chargeback / Showback
**Why it matters:** Without cost allocation by tag/team, data-platform spend cannot be attributed, so there is no accountability or incentive to optimize.
**Resolve:** 1) Activate cost-allocation tags and ensure data resources carry them 2) Build Cost Explorer / CUR reports grouped by tag and service 3) Establish a regular showback (or chargeback) reporting cadence to owners
**Dive deeper:** [Activating cost allocation tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/activating-tags.html) · [Analyzing cost with Cost Explorer](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html)

#### Q38 Storage Management
**Why it matters:** S3 data without lifecycle rules accumulates in expensive tiers indefinitely, inflating storage cost.
**Resolve:** 1) Add S3 Lifecycle rules to transition aging data to cheaper tiers and expire obsolete objects 2) Enable S3 Intelligent-Tiering for unpredictable access patterns 3) Review storage-class distribution with S3 Storage Lens
**Dive deeper:** [Managing S3 lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) · [Amazon S3 Storage Lens](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens.html)

#### Q39 Data Processing Cost
**Why it matters:** On-demand-only processing with oversized clusters wastes spend; right-sizing and Spot materially reduce data-processing cost.
**Resolve:** 1) Right-size EMR clusters and adopt EMR managed scaling and Spot for task nodes 2) Tune Glue worker type/count and enable auto scaling 3) Track processing cost by service/tag in Cost Explorer and act on trends
**Dive deeper:** [EMR cluster scaling](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-scale-on-demand.html) · [Cost Optimization Pillar](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html)

#### Q40 Unused Resources
**Why it matters:** Idle and unused data resources accrue cost with no value; leaving Cost Optimization Hub recommendations unaddressed wastes spend.
**Resolve:** 1) Enable AWS Cost Optimization Hub and review its recommendations 2) Remediate idle/unused resources (delete, stop, or right-size) on a cadence 3) Automate detection with Trusted Advisor and scheduled reviews
**Dive deeper:** [Cost Optimization Hub](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html) · [AWS Trusted Advisor](https://docs.aws.amazon.com/awssupport/latest/user/trusted-advisor.html)
