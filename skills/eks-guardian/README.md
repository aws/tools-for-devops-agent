# EKS Guardian — AWS DevOps Agent Skill

A comprehensive Amazon EKS operational review skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Conducts best-practices assessments aligned with the [EKS Best Practices Guide](https://docs.aws.amazon.com/eks/latest/best-practices/introduction.html) and generates a shareable report artifact per cluster.

> **⚠️ Not for production use.** This is sample code provided for educational and illustrative purposes only. It is not intended for production use and is provided without warranty or support of any kind. You are responsible for reviewing, testing, and hardening the skill before using it, and for evaluating its suitability, security, and compliance for your own use case. Review the instructions in `SKILL.md` and the read-only IAM scope before installing it into an Agent Space.

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to:

1. Discover EKS clusters in the configured account/regions.
2. Collect cluster configuration, K8s resources, node groups, add-ons, networking, security, and workloads. **K8s API is preferred** when reachable; AWS APIs are used as fallback.
3. Collect 7-day historical CloudWatch metrics, control-plane logs, and CloudTrail events.
4. Analyze against 12 EKS best-practices sections (Security, Reliability, Networking, Scalability, Cost Optimization, Karpenter, Cluster Upgrades, etc.).
5. Generate a shareable report artifact per cluster, named `eks-review-<cluster-name>-<YYYY-MM-DD>.md`.

## Agent Types

This skill is intended for the following agent types (selected in the Operator Web App at upload time). These correspond to the `aws-devops-agent-skills.agent-types: Chat tasks, Evaluation` values in the `SKILL.md` frontmatter:

* **Chat tasks (On-demand)** — conversational invocation in Chat ("review my EKS cluster", "EKS health check").
* **Evaluation** — proactive operational improvement recommendations.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. Integrate the DevOps Agent with each EKS cluster

This grants the Agent Space's IAM role read-only Kubernetes API access via an EKS access entry. Repeat **for each cluster** you want to review.

> Reference: [AWS EKS access setup](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-capabilities-for-aws-devops-agent-aws-eks-access-setup.html)

**a. Get the Agent Space IAM role ARN**

In the AWS DevOps Agent console, open your Agent Space → **Capabilities** → **Cloud** → **Primary Source** → **Edit**. Copy the **IAM role ARN**.

**b. Verify cluster authentication mode**

In the [Amazon EKS console](https://console.aws.amazon.com/eks), open the cluster → **Access** tab. The **Authentication mode** must include **EKS API**. If it doesn't, switch to a mode that does (note: this change cannot be reverted).

**c. Create the access entry**

On the cluster's **Access** tab:

1. Click **Create access entry**.
2. **IAM principal**: paste the Agent Space IAM role ARN from step (a).
3. Click **Next**.
4. **Access policy**: select the AWS managed policy **`AmazonAIOpsAssistantPolicy`**.
5. **Access scope**: choose **Cluster** (or specific Kubernetes namespaces if you want to limit visibility).
6. Click **Add Policy** → **Next** → **Create**.

**d. Verify**

In the Operator Web App Chat, ask: *"list all pods in the default namespace on cluster `<name>`"*. If pods are returned, access is configured.

### 3. (Conditional) Private connectivity for clusters with a private API endpoint

If the cluster's API server endpoint access is **private only**, enable **Public and private** API server endpoint access in the EKS console → cluster → **Networking** → **Manage networking**. Restrict with **public access CIDRs** to lock it down.

Alternatively, use the AWS DevOps Agent [private connection](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-capabilities-for-aws-devops-agent-connecting-to-privately-hosted-tools.html) mechanism for fully private access.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

### 1. Package the skill

From the `projects/skills/` directory:

```bash
cd projects/skills
zip -r eks-guardian.zip eks-guardian/ \
  -i '*.md' '*.yaml' '*.yml' \
  -x '*/README.md' '*/CHANGELOG.md' '*/BACKLOG.md' '*/TESTING.md'
```

The resulting zip contains:

```
eks-guardian/
├── SKILL.md                           # main skill instructions (required)
└── references/
    ├── best-practices-checklist.md    # checklist mapped to EKS Best Practices Guide
    ├── metrics-thresholds.md          # CloudWatch metric thresholds & severity rules
    ├── remediation-catalog.md         # Terraform/kubectl commands per finding
    ├── cross-account-scanning.md      # multi-account fleet scanning guide
    ├── compliance-mapping.md          # CIS, SOC2, PCI-DSS, HIPAA, NIST mapping
    ├── upgrade-readiness-playbook.md  # step-by-step upgrade checklist
    └── sample-report-excerpt.md       # example report output
```

Constraints (enforced at upload time):

* Total zip size ≤ **6 MB**.
* `SKILL.md` is required and must include `name` and `description` frontmatter.
* A `scripts/` directory is **not** allowed.

### 2. Upload via the Operator Web App

1. Navigate to the **Skills** page in your Agent Space Operator Web App.
2. Click **Add skill** → **Upload skill**.
3. Drag and drop `eks-guardian.zip` (or browse to it).
4. Select agent types: **Chat tasks (On-demand)** and **Evaluation**.
5. Review the validation results.
6. Click **Upload**.

## Usage

In the DevOps Agent Chat, use natural language:

* *"Run an EKS operational review for all clusters."*
* *"Review my EKS cluster `prod` in `us-east-1` for best practices."*
* *"Audit EKS security and cost optimization."*
* *"Generate an EKS best-practices report for cluster `genai-workshop`."*

## Skill Contents

```
eks-guardian/
├── SKILL.md                           # main skill instructions (with frontmatter)
├── README.md                          # this file
├── CHANGELOG.md                       # version history
├── BACKLOG.md                         # future roadmap
└── references/
    ├── best-practices-checklist.md    # checklist mapped to EKS Best Practices Guide
    ├── metrics-thresholds.md          # CloudWatch metric thresholds & severity rules
    ├── remediation-catalog.md         # Terraform/kubectl commands per finding
    ├── cross-account-scanning.md      # Multi-account fleet scanning guide
    ├── compliance-mapping.md          # CIS, SOC2, PCI-DSS, HIPAA, NIST mapping
    ├── upgrade-readiness-playbook.md  # Step-by-step upgrade checklist
    └── sample-report-excerpt.md       # Example report output
```

## Differentiating Features

Beyond the standard EKS best-practices assessment, EKS Guardian includes:

| Feature | Description |
|---------|-------------|
| **Cluster Scoring (A–F)** | Weighted letter grade per section and overall, with points deducted per severity |
| **Comparison Mode** | Side-by-side comparison across multiple clusters or environments (dev vs prod) |
| **Historical Delta** | Compare against a previous report to show new, resolved, and regressed findings |
| **Custom Severity Overrides** | Mark findings as N/A or accepted risk with justification |
| **Executive Summary** | 1-page leadership-ready summary with key metrics, grades, and top 3 actions |
| **Remediation Catalog** | Terraform/kubectl commands for every finding category with risk levels |
| **Cross-Account Scanning** | Multi-account fleet scanning with IAM setup guide and fleet summary reports |
| **Drift Detection** | Flag dangerous config drift between environments (dev vs staging vs prod) |
| **Compliance Mapping** | Map findings to CIS Benchmark, SOC2, PCI-DSS, HIPAA, NIST 800-53 controls |
| **Auto-Prioritization** | Rank findings by severity × blast radius × ease of fix |
| **Karpenter Cost Modeling** | Analyze Spot %, Graviton, consolidation and estimate savings |
| **Upgrade Readiness Playbook** | Customized step-by-step upgrade checklist based on cluster state |
| **Namespace Security Report** | Per-namespace breakdown of security posture (PSS, NetworkPolicy, quotas) |
| **Incident Correlation** | Correlate CloudWatch events, pod restarts, and CloudTrail to find root causes |
| **Workload Right-Sizing** | Compare requests/limits vs actual usage and recommend optimal values |
| **Network Policy Gap Analysis** | Identify pods with no NetworkPolicy coverage (lateral movement risk) |
| **IRSA/Pod Identity Audit** | Audit all IAM role bindings for over-permission and unused bindings |
| **Add-on Vulnerability Check** | Flag outdated add-ons with known CVEs |
| **Risk Score Trending** | Plot grade trends over time to show improvement or degradation |
| **Blast Radius Analysis** | Estimate impact scope for each CRITICAL/HIGH finding |
| **Toil Reduction Score** | Identify manual operational toil and estimate hours saved by automating |
| **FinOps Integration** | Tag-based cost allocation and namespace spending analysis |
| **Disaster Recovery Assessment** | Evaluate backup, multi-AZ, cross-region, RTO/RPO posture |
| **Golden Config Template** | Generate ideal target-state configuration to achieve A grade |

## Best-Practices Sections Covered

| # | Section | Reference |
|---|---------|-----------|
| 1 | Security (IAM, Pod Security, Network, Encryption, etc.) | [security.html](https://docs.aws.amazon.com/eks/latest/best-practices/security.html) |
| 2 | Reliability (Applications, Control Plane, Data Plane) | [reliability.html](https://docs.aws.amazon.com/eks/latest/best-practices/reliability.html) |
| 3 | Karpenter | [karpenter.html](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html) |
| 4 | Cluster Autoscaler | [cas.html](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html) |
| 5 | EKS Auto Mode | [automode.html](https://docs.aws.amazon.com/eks/latest/best-practices/automode.html) |
| 6 | Networking | [networking.html](https://docs.aws.amazon.com/eks/latest/best-practices/networking.html) |
| 7 | Scalability + Data Plane Scaling | [scalability.html](https://docs.aws.amazon.com/eks/latest/best-practices/scalability.html) |
| 8 | Cluster Upgrades | [cluster-upgrades.html](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html) |
| 9 | Cost Optimization | [cost-opt.html](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt.html) |
| 10–12 | Windows / Hybrid / AI-ML (conditional) | — |

## Performance Considerations

| Cluster Size | Estimated Execution Time | Notes |
|---|---|---|
| Small (≤10 nodes, ≤50 pods) | 2–5 minutes | Full scan with all sections |
| Medium (10–50 nodes, 50–200 pods) | 5–10 minutes | May take longer with 7-day metrics |
| Large (50–100 nodes, 200–500 pods) | 10–20 minutes | Consider scoping to specific sections |
| Very Large (100+ nodes, 500+ pods) | 15–30 minutes | Recommend section-specific review |

### Tips for Faster Execution

- Scope your request: "Review security for cluster X" runs faster than a full review
- For fleet scans (10+ clusters), expect 30+ minutes total
- Historical delta analysis adds ~2–3 minutes per comparison
- Compliance mapping adds ~1–2 minutes per framework

### DevOps Agent Timeout

If a review does not complete, the DevOps Agent will return a partial result. You can resume by asking: "Continue the review from where you left off."

## Cost Estimation

EKS Guardian uses DevOps Agent compute and AWS API calls. Costs depend on scan scope.

| Scan Type | Est. Token Usage | Est. AWS API Calls | Approx. Cost |
|---|---|---|---|
| Single cluster (basic) | 50,000–100,000 tokens | 50–100 calls | $0.15–$0.40 |
| Single cluster (full + compliance) | 100,000–200,000 tokens | 100–200 calls | $0.40–$0.80 |
| Fleet scan (10 clusters, 3 accounts) | 500,000–1,000,000 tokens | 500–1,000 calls | $2.00–$4.00 |
| Fleet scan + comparison + delta | 700,000–1,500,000 tokens | 500–1,000 calls | $3.00–$6.00 |

**Notes:**
- Token costs assume Claude Sonnet pricing via DevOps Agent
- AWS API costs are negligible (~$0.01–$0.04 per scan for EKS/EC2/CloudWatch read calls)
- Weekly fleet scans: ~$8–$24/month
- Costs scale linearly with cluster count and complexity

## Data Handling & Privacy

### What Data Is Collected

EKS Guardian collects cluster configuration data during reviews:
- Cluster settings, node group configurations, add-on versions
- IAM role ARNs, service account names, namespace names
- CloudWatch metrics (aggregated, no PII)
- CloudTrail events (API caller identities, resource ARNs)
- Pod/deployment names and specifications

### Report Storage

- Reports are generated as artifacts within your DevOps Agent session
- Reports are NOT sent to any external service or stored outside your Agent Space
- Access to reports is governed by your Agent Space permissions

### Sensitive Data in Reports

Reports may contain:
- IAM role ARNs (e.g., `arn:aws:iam::123456789012:role/my-role`)
- Kubernetes resource names (namespaces, deployments, service accounts)
- AWS account IDs
- CloudTrail actor identities

**Before sharing reports externally**, consider:
1. Redacting AWS account IDs if sharing outside your organization
2. Reviewing IAM role ARNs for internal naming conventions you don't want exposed
3. Removing CloudTrail actor identities if sharing with third parties

### Data Retention

- DevOps Agent session data follows your Agent Space retention policy
- Report artifacts persist as long as the session/conversation is retained
- No data is stored by the skill itself — it's stateless
- For compliance record-keeping, export report artifacts to your own S3 bucket with appropriate lifecycle policies

## Roadmap

- [ ] **v1.1** — Add remediation tools via MCP server integration (Terraform-based auto-fix)
- [ ] **v1.2** — Add Jira/ticketing integration for finding tracking
- [ ] **v1.3** — Multi-account cross-cluster comparison reports

## License

MIT License. See LICENSE file in the project root.
