# FSx for Windows SLA Optimizer Skill

A skill for AWS DevOps Agent that performs a structured, **read-only** SLA-readiness
and availability review of Amazon FSx for Windows File Server file systems, and
surfaces cost-optimization opportunities where capacity is over-provisioned. It
produces a rated report with prioritized findings and remediation guidance.

## What it does

Given one or more FSx for Windows file-system IDs (or a region to discover them in),
the skill collects each file system's configuration and CloudWatch metrics using
read-only control-plane API calls and evaluates it across seven availability
dimensions:

1. **Deployment type** — Single-AZ vs Multi-AZ (the primary availability lever;
   Multi-AZ provides automatic cross-AZ failover)
2. **Active Directory health** — Misconfigured-state detection and AD reachability,
   the most common cause of FSx for Windows unavailability
3. **Throughput capacity** — provisioned throughput vs measured **peak** demand
   (read + 2 × write), for under-provisioning (SLA risk)
4. **Storage capacity headroom** — free-space against the 20% guidance, with a
   growth projection ("projected to reach the 20% floor in ~N weeks")
5. **Backups** — automatic backup enablement and retention
6. **Maintenance window** — configured, and (on Single-AZ) placed off peak hours
7. **Alarms / observability** — CloudWatch alarm coverage, especially on
   `FreeStorageCapacity`

Each file system receives an **SLA Readiness rating** (High / Medium / Low /
Indeterminate) with per-dimension findings.

The throughput and storage checks are enriched with **usage-pattern (trend)
analysis** built on daily-aggregate CloudWatch metrics over a configurable window
(default 30 days): it evaluates throughput against **peak** demand (not just the
average, catching e.g. weekday-morning throttling that averages hide), classifies the
**weekday/weekend usage profile**, and projects **storage growth** to the 20%-full
floor.

While measuring utilization for the SLA checks, the skill also flags cost
opportunities as 💰 advisory notes that never lower the SLA rating: **heavily
over-provisioned throughput and storage**, and — the strongest signal — an
**idle file system** (near-zero activity across the window) as a decommission
candidate. Reviews are routed automatically:

- **1 file system** → full single-file-system report
- **2–20 file systems** → fleet report (summary matrix + details)
- **21+ file systems** → batched fleet review with a manifest for progress tracking
  and resume

## Prerequisites

The DevOps Agent role must have **read-only** permissions for the review to produce
complete results:

```
fsx:DescribeFileSystems
fsx:DescribeBackups
ds:DescribeDirectories
cloudwatch:GetMetricData
cloudwatch:DescribeAlarms
```

(`sts:GetCallerIdentity` is also used to resolve the account ID; it requires no IAM
permission.)

**All of these are already covered by the AWS managed policy
[`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html)**
(via `fsx:Describe*`, `ds:Describe*`, `cloudwatch:GetMetricData`, and
`cloudwatch:Describe*`), so this skill needs **no additional IAM policy**. The skill
reads the `Name` and cost-allocation tags from the `Tags` array returned inline by
`fsx describe-file-systems`, so it does not require `fsx:ListTagsForResource` (which
the managed policy does not grant). If a check ever lacks permission, the skill
reports it as "Unable to verify" and caps the SLA Readiness rating at Medium rather
than guessing the configuration.

The skill **never** reads file or share data over SMB and **never** performs any
write, create, update, or delete operation.

> **Optional — running the AD validation runbook.** For a Misconfigured file system,
> the skill recommends the `AWSSupport-ValidateFSxWindowsADConfig` Systems Manager
> Automation runbook — a **read-only diagnostic** that checks Active Directory
> reachability, credentials, and OU permissions. The skill only *names* it; it never
> executes it. If your AgentSpace has **Agent Actions** enabled and the agent's role
> is permitted to run it (`ssm:StartAutomationExecution` plus the runbook's own
> permissions), the DevOps Agent can execute this runbook on your behalf as a
> follow-up action. That execution is governed by your AgentSpace configuration and
> IAM, independent of this skill's read-only control-plane allowlist.

## Limitations

- **Region-scoped.** FSx file-system IDs are region-scoped; the skill reviews one
  region per run and will ask for the region if IDs are provided without one.
- **Self-managed AD health is inferred.** For self-managed Active Directory there is
  no Directory Service object to read, so AD health is inferred from the
  file-system lifecycle (`MISCONFIGURED`) rather than a directory `Stage`. The skill
  never connects to customer domain controllers directly.
- **Deployment type is immutable.** The skill recommends creating a new Multi-AZ
  file system and migrating; it cannot and does not change deployment type in place.
- **Cost notes are directional.** Over-provisioning notes are based on measured
  utilization vs provisioned capacity, not on billing data; they are advisory
  right-sizing signals, not exact savings figures.
- **Throughput metrics floor.** Some throughput metrics are only published for file
  systems provisioned at ≥ 32 MBps; below that the report notes limited metrics.
- **Trend needs history.** Usage-pattern analysis, peak detection, and the storage
  growth projection need enough daily datapoints; for a file system younger than
  ~14 days the skill reports "insufficient data" and skips the projections rather
  than extrapolating. Peak figures are derived from daily `Maximum` statistics and
  are therefore **approximate** (the busiest sub-interval of each day), not exact
  instantaneous peaks.
- **Throughput cost recommendations stop at 32 MBps.** Because FSx emits
  throughput-utilization metrics only at ≥ 32 MBps, the skill can recommend stepping
  *toward* the 32 MBps tier but cannot validate the 8/16 MBps tiers from CloudWatch;
  those require customer-side observation after the change.

## Scope boundaries (what this skill does not cover)

This skill reviews **availability posture and capacity right-sizing** from the FSx
control plane and CloudWatch. It deliberately does not diagnose data-plane, SMB, or
Windows-feature behavior. The following are common FSx for Windows support themes
that are **out of scope** — the skill will not flag or remediate them:

- **Shadow copies (VSS).** FSx can auto-delete shadow copies under IOPS/latency
  pressure or during data-deduplication optimization; shadow-copy tuning is not
  assessed here.
- **SMB over WAN / on-premises latency** is not a supported/measured access pattern.
- **No built-in file-search indexing** — slow enterprise file search is a Windows
  Search Service concern, not an FSx SLA dimension.
- **NTFS permissions and the SYSTEM account.** The `SYSTEM` account requires Full
  Control at the share root; removing it breaks automatic backups. The skill does not
  read or audit NTFS ACLs (it never touches the data plane).
- **GPOs do not apply to FSx file-server nodes** — you cannot harden or reconfigure
  the managed nodes via Group Policy; the skill does not evaluate GPO posture.
- **Anti-malware / AV** on file content is a customer shared-responsibility task and
  is out of scope.
- **Deployment type, storage-type direction, and AZ placement are immutable** — the
  skill recommends migration paths but performs no changes.

## Agent Types

This skill is used by the following agent types (selected in the Operator Web App at
upload time):

- **Chat tasks** — conversational, on-demand reviews ("is `fs-0123...` highly
  available?", "why is my FSx file system Misconfigured?", "is it over-provisioned?").
- **Evaluation** — proactive, best-practices SLA reviews of a file system or fleet
  against the seven dimensions.
- **Incident RCA** — automated root cause analysis where an FSx for Windows file
  system's availability posture (Single-AZ, Misconfigured AD, throughput
  saturation, full storage) may be a contributing factor.

Select **Generic** instead if you want the skill available to all agent types.

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/storage-fsx-windows-sla-optimizer` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Instead, connect your personal GitHub account and select any repository from it during the connection setup. Once a GitHub connection is established, you can import skills from any public repository, including this one, even if it wasn't selected during the connection setup.

**Option B: Upload as a zip file**

1. Zip the `storage-fsx-windows-sla-optimizer/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r storage-fsx-windows-sla-optimizer.zip storage-fsx-windows-sla-optimizer/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `storage-fsx-windows-sla-optimizer.zip` file (max 6 MB).
5. Select the agent types: **Chat tasks**, **Evaluation**, and **Incident RCA**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage skills — useful for CI/CD pipelines or automation workflows. Assign the skill to the `CHAT`, `EVALUATION`, and `INCIDENT_RCA` agent types. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to use it with DevOps Agent

Works with the **Chat**, **Evaluation**, and **Investigations / Incident RCA**
subagents. Describe the task in natural language — you do not need to name the skill:

- "Run an FSx for Windows SLA review on `fs-0123456789abcdef0` in us-east-1."
- "Is my FSx file system `fs-0123...` highly available?"
- "Why is my FSx for Windows file system in a Misconfigured state?"
- "Is `fs-0123...` over-provisioned on throughput or storage?"
- "Review these FSx Windows file systems for availability: `fs-aaa...`, `fs-bbb...`."
- "Audit all my FSx for Windows file systems in eu-west-1 for SLA readiness."

The agent gathers configuration and CloudWatch metrics via its `use_aws` tool under
the assumed role in the target account, applies the finding logic, and returns a
Markdown report artifact.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
