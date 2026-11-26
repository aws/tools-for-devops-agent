# Graviton Migration — Eligibility, Effort, and What May Be Claimed

Read this file before assessing **SUS05-BP02** whenever the workload runs x86 compute (EC2,
Auto Scaling groups, ECS, EKS, Lambda `x86_64`) or x86 instance classes on a managed database,
cache, search, or streaming service. It replaces a blanket "x86 where Graviton is supported"
test with a per-service eligibility check, an effort band per resource, a migration order, and
rules on what the report may say about carbon.

## What a Graviton Recommendation May Claim

| Claim | Rule |
|-------|------|
| Energy efficiency | Quote AWS's statement, attributed to AWS: "AWS Graviton-based Amazon EC2 instances use up to 60% less energy than comparable EC2 instances for the same performance" ([AWS Graviton sustainability](https://aws.amazon.com/ec2/graviton/graviton-sustainability/)). The Sustainability Pillar's wording is also usable: Graviton "offer[s] the best performance per watt of energy use in Amazon EC2" ([SUS05-BP02](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sus_sus_hardware_a3.html)). |
| Carbon saving for this workload | **Never.** No MTCO2e figure and no percentage reduction in emissions. No published factor converts a Graviton migration into a customer's CO2e. |
| The "up to 60%" figure | A best-case statement about energy at equal performance. Never apply it to the customer's fleet, vCPU-hours, or emissions, and never multiply anything by it. |
| Effect on reported emissions | Do not predict one. See below. |
| Cost | Compute Optimizer's `savingsOpportunity` may be quoted, labelled as **cost**. Never convert it into carbon. |

**Why the reported figure cannot be predicted.** In the [AWS Customer Carbon Footprint
Methodology](https://sustainability.aboutamazon.com/aws-customer-carbon-footprint-tool-methodology.pdf)
(model 3.0, sections 4.2–4.3), the emissions of every EC2 server-rack type in a cluster are
combined into one EC2 service total (Eq 38). That total is split across customer accounts by
each account's share of normalized instance-hours (Eq 40–41). The methodology does not define
the normalization and publishes no per-rack-type intensity. So:

- A like-for-like swap from x86 to Graviton is **not** expected to show a predictable change in
  the customer's reported figure. Say so if asked.
- The reported allocation falls when the migration lets the customer provision **less** —
  fewer or smaller instances. That is a provisioning change, which the KPIs measure directly.
- Services without dedicated racks are allocated by equivalent revenue (section 4.3.2). A lower
  Graviton list price may lower that allocation (an inference from the allocation method, not
  an AWS statement); it would reflect price, not energy. Do not present
  it as an efficiency gain.

Express the impact of a Graviton finding as **vCPU-hours per month moved to Graviton**, plus
any reduction in provisioned vCPU-hours when the target type is smaller (see Compute
Optimizer below). The effect is tracked through compute intensity in Step 6, not through the
Step 5 emissions data.

## Eligibility by Service

Record each resource's current architecture, then test whether a Graviton option exists for
its engine, runtime, or image. A resource with no Graviton option is **NOT APPLICABLE** for this
practice, never NOT MET.

| Service | Current architecture | Eligible when | No Graviton option | Change type |
|---------|----------------------|---------------|--------------------|-------------|
| RDS, Aurora | `rds:DescribeDBInstances` → `DBInstanceClass` (`g` after the family digit = Graviton, e.g. `db.r7g`) | `rds:DescribeOrderableDBInstanceOptions` with `Engine`, `EngineVersion`, and the Graviton `DBInstanceClass` of the same family returns a result | SQL Server, Oracle, Db2 | Instance class change |
| DocumentDB, Neptune | Same, `Engine: docdb` / `neptune` | Same API returns a result | — | Instance class change |
| ElastiCache | `elasticache:DescribeCacheClusters` / `DescribeReplicationGroups` → `CacheNodeType`, `EngineVersion` | Valkey 7.2+ (all node types); Redis OSS 5.0.6+ for m6g/r6g, 6.2+ for m7g/r7g; Memcached 1.5.16+ for m6g/r6g/m7g/r7g/t4g, 1.6.6+ for m8g/r8g/c7gn ([supported node types](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/CacheNodes.SupportedTypes.html)) | Engine version below the minimum | Node type change |
| OpenSearch Service | `es:DescribeDomain` → `ClusterConfig.InstanceType`, `EngineVersion` | `es:ListInstanceTypeDetails` with the domain's `EngineVersion` returns Graviton types. Elasticsearch 7.9+ or any OpenSearch version | Elasticsearch below 7.9 | Instance type change. Graviton3 types need gp3 storage |
| MemoryDB | `memorydb:DescribeClusters` → `NodeType` | All current node types are Graviton | — | Already Graviton — counts toward MET |
| MSK | `kafka:DescribeClusterV2` → broker instance type, Kafka version | `kafka.m7g` / `express.m7g` with Kafka 2.8.2 or 3.3.2+ | Kafka version below the minimum | Broker type change |
| EMR | `elasticmapreduce:ListInstanceGroups` / `ListInstanceFleets` → instance types | `elasticmapreduce:ListSupportedInstanceTypes` for the cluster's `ReleaseLabel` lists an `arm64` type | — | Instance type change; custom code and native libraries are NEEDS HUMAN INPUT |
| Lambda | `lambda:GetFunctionConfiguration` → `Architectures`, `Runtime`, `PackageType`, `Layers[].Arn` | Every supported runtime runs on `arm64`. For `.zip` functions, every layer's `lambda:GetLayerVersion` → `CompatibleArchitectures` includes `arm64` | — | `.zip` on a language runtime: configuration change. `.zip` on an OS-only runtime (`provided.*`) or `Image`: arm64 rebuild. Native modules inside a package are not visible — state that assumption |
| ECS (Fargate, EC2) | `ecs:DescribeTaskDefinition` → `runtimePlatform` (`cpuArchitecture` absent or `X86_64` means x86) | Linux task and an image confirmed to include `arm64` (ECR check below) | `operatingSystemFamily` is a Windows value | Task definition change once the image is multi-architecture |
| EKS managed node groups | `eks:DescribeNodegroup` → `amiType` (`*_ARM_64*` values are Graviton). For `CUSTOM`, read the launch template's AMI via `ec2:DescribeImages` → `Architecture` | Images confirmed to include `arm64` | Windows AMI types | New or mixed-architecture node group |
| EC2, Auto Scaling groups | `ec2:DescribeInstances` → `Architecture`, `PlatformDetails`; `ec2:DescribeInstanceTypes` → `ProcessorInfo.SupportedArchitectures` | Linux; effort from Compute Optimizer when available | `PlatformDetails` contains Windows | Depends on the software stack |

Engine-version minimums change as services add families. The values above are as published at
the time of writing; when a resource is close to a boundary, the orderable-options or
instance-type API is authoritative.

### Container images — confirming arm64

1. `ecr:DescribeImages` → `imageManifestMediaType`. An image index
   (`application/vnd.oci.image.index.v1+json` or
   `application/vnd.docker.distribution.manifest.list.v2+json`) means a multi-platform image
   **may** include arm64. A single manifest type means one architecture — treat it as needing an
   arm64 build.
2. An index alone does not prove arm64. Build tools also emit an index for a single-architecture
   image with attestation manifests. When `ecr:BatchGetImage` is permitted, read the index in
   `imageManifest` and confirm a `manifests[].platform.architecture` of `arm64`.
3. Without `ecr:BatchGetImage`, record "index present, arm64 unconfirmed" and place the
   resource in the build-change band.
4. Images outside ECR (public or third-party registries) are NEEDS HUMAN INPUT for architecture.

## Compute Optimizer — Optional Effort Ratings

AWS Compute Optimizer rates the migration effort of Graviton alternatives for EC2, Auto
Scaling groups, and RDS. Use it only for architecture effort and target type, not for sizing
tables — per-instance rightsizing stays out of scope (see When to Use).

1. Call `compute-optimizer:GetEnrollmentStatus` once. Proceed only if `status` is `Active`.
2. In each workload Region:
   - `compute-optimizer:GetEC2InstanceRecommendations` with the workload's `instanceArns` and
     `recommendationPreferences.cpuVendorArchitectures: ["AWS_ARM64"]`, which restricts the
     options to Graviton types.
   - `compute-optimizer:GetAutoScalingGroupRecommendations` with the same preference.
   - `compute-optimizer:GetRDSDatabaseRecommendations` with the same preference. It covers RDS
     for MySQL, RDS for PostgreSQL, and Aurora only.
3. From the rank-1 option, read the target `instanceType` (or `dbInstanceClass` for RDS),
   `migrationEffort` (EC2 and Auto Scaling groups only), and `platformDifferences` (EC2 only).
   Read `inferredWorkloadTypes` from the recommendation itself.
4. Look up the target type's vCPU count with `ec2:DescribeInstanceTypes`. Current minus target
   vCPU-hours is the provisioning reduction to report alongside the vCPU-hours moved.

`migrationEffort` meanings: `VeryLow` — same CPU architecture; `Low` — Amazon EMR inferred and
Graviton recommended; `Medium` — no workload type inferred, Graviton recommended; `High` —
different architecture with no known compatible version of the inferred workload.

Compute Optimizer does **not** recommend an architecture change for Lambda or ECS; use the
eligibility table for those.

| Outcome | Action |
|---------|--------|
| `status` is not `Active`, or `OptInRequiredException` | Use the eligibility table alone. Add an INFO note that opting in to Compute Optimizer would add migration-effort ratings. |
| `AccessDeniedException` | Use the eligibility table alone and name the denied `compute-optimizer:` action. |
| Any other error | Record it verbatim, use the eligibility table, and recommend no IAM change. |
| Resource not in the results | Compute Optimizer needs about 30 hours of metrics in the last 14 days. Treat the resource as unrated. |

## Effort Bands and Severity

Place every eligible x86 resource in one band. The SUS05-BP02 finding takes the severity of the
highest band present.

| Band | Includes | Severity |
|------|----------|----------|
| **Quick win** | Managed database, cache, search, or streaming resources whose engine version qualifies; Lambda `.zip` functions whose layers all support arm64; ECS or EKS workloads whose images are confirmed to include arm64; EC2 or Auto Scaling groups rated `VeryLow` or `Low` | MEDIUM |
| **Build change** | Images that are single-architecture or arm64-unconfirmed; Lambda container images and OS-only runtimes; EC2 or Auto Scaling groups rated `Medium` | LOW |
| **Assessment needed** | EC2 or Auto Scaling groups rated `High` or unrated; EMR with custom code; anything whose dependencies the agent cannot see | LOW, with the compatibility question stated as NEEDS HUMAN INPUT |
| **Engine upgrade first** | Engine version below the Graviton minimum | LOW — the upgrade is the prerequisite; cross-reference SUS06-BP03 if the version is also end of life |
| **No Graviton option** | Windows, SQL Server, Oracle, Db2 | NOT APPLICABLE — excluded from the eligible share |

Practice status:

- **MET** — no resource in the quick-win or build-change bands, and no previous-generation
  families.
- **PARTIAL** — some compute already runs on Graviton, but eligible x86 resources remain.
- **NOT MET** — eligible x86 resources exist and none of the workload runs on Graviton. This is
  the Pillar's anti-pattern "You are only using x86 instances."

Previous-generation families are a separate SUS05-BP02 finding at MEDIUM, as before. A
previous-generation x86 instance that is also Graviton-eligible is reported once, in its
Graviton band, with the generation noted.

## KPIs

Add these to the Step 6 table, computed from the Step 4.1 vCPU-hours with each resource's
architecture recorded:

| KPI | Formula |
|-----|---------|
| Graviton share | Graviton vCPU-hours ÷ total vCPU-hours, overall and per service |
| Graviton-eligible x86 share | x86 vCPU-hours in the quick-win and build-change bands ÷ total vCPU-hours |
| Current-generation share | current-generation vCPU-hours (either architecture) ÷ total vCPU-hours |

Report Graviton share and current-generation share separately: a fleet of current-generation
x86 is not the same finding as a fleet of previous-generation Graviton.

## Migration Order for Prioritised Actions

Recommend this order in Step 9 Section 8, skipping steps with no eligible resources:

1. **Managed services** — RDS, Aurora, ElastiCache, OpenSearch, MSK, DocumentDB, Neptune. An
   instance class change with no application build change. Plan it for a maintenance window.
2. **Lambda `.zip` functions** — a configuration change once layers support arm64. Test before
   switching production aliases.
3. **Containers** — add arm64 to the image build so images become multi-architecture, then
   switch the task definition `cpuArchitecture` or add a Graviton node group.
4. **Self-managed EC2** — follow the
   [AWS Graviton Getting Started transition guide](https://github.com/aws/aws-graviton-getting-started/blob/main/transition-guide.md).
   Interpreted and JIT-compiled languages generally run as-is; compiled code needs an arm64
   build. The customer can scan source code with
   [Porting Advisor for Graviton](https://github.com/aws/porting-advisor-for-graviton) — the agent
   cannot run it.

Combine each step with rightsizing: size the Graviton target from measured utilization, not by
matching the current instance size. Performance-test before cutover and roll out with canary
or blue/green deployment. [AWS Graviton Fast Start](https://aws.amazon.com/ec2/graviton/fast-start/)
offers migration guidance.

## Report Wording

Write the SUS05-BP02 finding in this form:

> N x86 resources (X vCPU-hours/month, Y% of compute) run on services with a Graviton option
> for their engine, runtime, or image: A quick wins, B build changes, C needing assessment.
> AWS states that Graviton-based EC2 instances use up to 60% less energy than comparable EC2
> instances for the same performance. This review does not estimate the effect on this
> workload's reported emissions; track it through compute intensity and Graviton share in
> Section 2.

In Section 9, cite the AWS Graviton page and the transition guide whenever this finding appears.
