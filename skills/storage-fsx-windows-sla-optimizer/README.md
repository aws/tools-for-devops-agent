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
analysis** over a configurable window (default 30 days): daily aggregates drive the
**weekday/weekend usage profile** and **storage growth** projection, while supported
5-minute `Sum` series provide an approximate interval peak for throughput sizing.
This catches shorter demand peaks that daily averages hide without claiming an
instantaneous maximum.

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
- **Trend needs history.** Usage-pattern analysis and storage growth projection
  need enough complete daily datapoints; with fewer than ~14 days the skill reports
  "insufficient data" and skips those conclusions rather than extrapolating. Empty
  CloudWatch series are treated as missing, never as zero. Peak throughput demand
  is the highest aligned 5-minute read + 2 × write average derived from supported
  `Sum` statistics, so it is approximate and can smooth bursts shorter than five
  minutes.
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

- **On-demand** — conversational, on-demand reviews ("is `fs-0123...` highly
  available?", "why is my FSx file system Misconfigured?", "is it over-provisioned?").
- **Incident RCA** — automated root cause analysis where an FSx for Windows file
  system's availability posture (Single-AZ, Misconfigured AD, throughput
  saturation, full storage) may be a contributing factor.

Select **Generic** instead if you want the skill available to all agent types.

## Uploading to AWS DevOps Agent

This skill needs no IAM policy beyond `AIDevOpsAgentAccessPolicy` (see [Prerequisites](#prerequisites)). You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

The skill runs on-demand SLA and right-sizing reviews, and Incident RCA uses it when a file system's availability posture may contribute to an incident, so target **On-demand** and **Incident RCA**. **Generic** would load it for every agent type, incident triage included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `storage-fsx-windows-sla-optimizer`, or filter by AWS service **Amazon FSx for Windows File Server**.
4. Choose **Details** and check that the agent types are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust the severity rules in `references/finding-logic.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/storage-fsx-windows-sla-optimizer/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f storage-fsx-windows-sla-optimizer.zip
   zip -r storage-fsx-windows-sla-optimizer.zip storage-fsx-windows-sla-optimizer/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l storage-fsx-windows-sla-optimizer.zip | tail -1   # expect 7 files
   ```

2. Check that the zip has this structure:

   ```text
   storage-fsx-windows-sla-optimizer.zip
   └── storage-fsx-windows-sla-optimizer/
       ├── SKILL.md                              # required: frontmatter with name and description
       └── references/
           ├── data-collection.md                # read-only configuration and CloudWatch calls
           ├── finding-logic.md                  # severity rules and finding templates
           ├── trend-analysis.md                 # usage patterns and idle detection
           ├── fleet-orchestration.md            # multi-file-system reviews
           ├── report-format.md                  # report structure and rating criteria
           └── fsx-windows-sla-best-practices.md # reasoning behind the thresholds
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `storage-fsx-windows-sla-optimizer.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to use it with DevOps Agent

Works with the **On-demand** and **Incident RCA**
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

## Try it in a deployable demo

The [FSx for Windows SLA Review demo](https://github.com/aws-samples/sample-aws-genai-ops-demos/tree/main/resilience/fsx-windows-sla-review-devops-agent)
in the GenAI Ops Demo Library deploys everything this skill needs to show its value, in
about an hour, with one script: an Agent Space with this skill registered, a Single-AZ
FSx for Windows file system joined to a self-managed Active Directory, its alarms, and a
Demo Lab that injects reversible mis-configurations and rolls them back:

- **Active Directory credentials rotated** — the file system goes `MISCONFIGURED`, an
  alarm starts an investigation, and the report names invalid service-account
  credentials (not the network) as the cause.
- **Automatic backups disabled** — the review flags the missing recovery point and ties
  it to the Single-AZ recovery model.
- **No CloudWatch alarm on the file system** — the review flags the observability gap
  and names the `FreeStorageCapacity` alarm to create.

Each scenario records what the agent concludes with and without this skill. The demo
references the skill at a stated ref of this repository and never copies it.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
