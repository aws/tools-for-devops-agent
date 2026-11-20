# Amazon FSx for NetApp ONTAP Operational Review — AWS DevOps Agent Skill

Performs a strictly **read-only, fully automated** operational review of Amazon FSx for NetApp ONTAP
(FSxN) file systems, SVMs, and volumes — across **5 pillars and 46 checks** — producing a
severity-ranked **Amazon FSx for NetApp ONTAP Operational Review** report with one recommendation per
Critical, High, or Medium finding.

Every check runs against **public AWS APIs** (`fsx`, `cloudwatch`, `backup`, `ec2`) via the `use_aws`
tool. There are **no manual steps, no customer questionnaire, and no ONTAP CLI commands** anywhere in
the review. ONTAP-CLI-level diagnosis is out of scope for this skill.

## Purpose

Teams running FSxN at scale accumulate posture drift that no single console page surfaces: volumes left
without a snapshot policy, file systems with no automatic backups, SSD tiers quietly climbing past 90%
(where tiering promotion stops), security groups open to the world, alarms sitting in ALARM state. This
skill gives the agent the check definitions, severity model, and report format to assess all of it in
one pass from native AWS control-plane and CloudWatch APIs, and to return findings ordered by how much
they matter.

## Operational Posture Review (Production or Pre-production)

This is an **operational posture review** that can be run against any FSxN file system — whether in
**production or pre-production**. Because every finding is severity-ranked and carries exactly one
concrete remediation, the report is a prioritized action list: clear the Critical, High, and Medium
findings to improve posture.

| When | Why |
|------|-----|
| Recurring (weekly / monthly) | Catch posture drift on a running file system; successive runs are directly comparable |
| Ad hoc | Audit a production or pre-production FSxN file system and get a prioritized remediation list |
| Health check | Full best-practices sweep when something feels off |

## Key Capabilities

- **46 checks across 5 pillars** — Backup, Observability, Operations, Performance, and Security.
  `references/overview.md` (severity model, status values, Evidence Guardrails, APIs/metrics) plus the
  per-pillar `references/<pillar>-checks.md` files are the authoritative definition of each check's
  public APIs, logic, thresholds, severity, and output fields.
- **Fully automated, public-API only** — every check is answerable from `fsx` / `cloudwatch` / `backup`
  / `ec2` `Describe*` / `List*` / `Get*` calls. No ONTAP CLI, no questionnaire, no customer interview.
- **Uniform severity ranking** — every finding is Critical, High, Medium, Low, or Informational, and the
  Executive Summary ranks them most-severe first with per-pillar pass/warning/fail counts.
- **One recommendation per Critical/High/Medium finding** — concrete and FSxN-specific, never generic.
- **Per-check failure isolation** — a denied or failing API becomes an error row on that check and the
  review continues; an `AccessDenied` is reported as "not evaluated — permission not granted" rather than
  a false "none found".

## Pillars

| Pillar | Checks | Focus |
|--------|--------|-------|
| Backup | 7 | AWS Backup coverage, recovery points, SnapMirror (DP) volumes, FS automatic backups, backup growth, staleness, daily cadence |
| Observability | 3 | CloudWatch alarm coverage and state |
| Operations | 11 | Tagging (FS + volume/SVM), unused volumes, maintenance windows, storage efficiency, snapshot policies, deployment type, AD, per-volume capacity, aged snapshots |
| Performance | 17 | CPU, IOPS, throughput, SSD capacity, tiering, FlexGroup/FlexClone, capacity-pool reads, HA pairs, generation, cache hit ratio, latency |
| Security | 8 | Security-group ingress/egress and exposure, volume security style, AD integration, encryption/KMS, Multi-AZ routing |

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

An existing Agent Space with each account you want to review configured as a cloud source, and the
`use_aws` tool available to the agent.

### 2. IAM permissions

The skill needs read-only access to `fsx`, `cloudwatch`, `backup`, and `ec2`. These permissions are
delivered repo-wide through [`cloudformation/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml),
which attaches the inline policy `DevOpsAgentSkill-AwsFsxnOperationsReview` to your DevOps Agent role. The
skill is enabled by default (`EnableAwsFsxnOperationsReview=true`). Deploy or update the stack against your
agent role:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies \
  --parameter-overrides ExistingRoleName=<YOUR-DEVOPS-AGENT-ROLE-NAME> \
  --capabilities CAPABILITY_NAMED_IAM
```

The skill operates strictly read-only: no `Create*`, `Update*`, or `Delete*` calls, no mounting, and no
data-plane access of any kind.

### 3. FSxN file systems with activity (recommended)

Performance and capacity checks read `AWS/FSx` CloudWatch metrics, which publish while a file system is
in use. Reviewing an idle file system produces "No data" rows rather than false findings.

## Limitations

- **Control-plane and CloudWatch metrics only.** The review reports configuration and CloudWatch signals
  exposed by public AWS APIs. ONTAP-internal state — SnapMirror lag/health, WAFL/aggregate internals,
  per-volume ONTAP latency counters, FlexCache hit ratios, audit-log and snapshot auto-delete policy — is
  **not** assessed by the review.
- **No ONTAP CLI in the review.** CLI-level diagnosis is out of scope for this skill.
- **Point-in-time.** Findings reflect state at run time; per-check metric windows are fixed.
- **Large estates may need scoping.** Many file systems across many regions can exhaust the run budget;
  scope to fewer file systems or pillars if a run times out.

## Design Notes

This skill is a general-purpose FSxN operational review:

- **Fully automated — no manual steps.** No customer questionnaire and no ONTAP CLI "manual
  verification" items. Every check is answerable from a public AWS API.
- **Workload-agnostic.** It assesses general FSxN best practices and does not embed assumptions about
  any specific workload type.
- **Public AWS APIs only.** Every check calls a public AWS API via `use_aws` — `fsx`, `cloudwatch`,
  `backup`, `ec2` — with no dependency on any non-public control plane. The per-pillar
  `references/<pillar>-checks.md` files list the exact public operation and `AWS/FSx` CloudWatch metric
  for each check.

## Skill Contents

```
skills/aws-fsxn-operations-review/
├── SKILL.md                              # skill instructions — scope, check execution, report format
├── README.md
├── references/
│   ├── overview.md                       # severity model, status values, Evidence Guardrails, APIs/metrics
│   ├── backup-checks.md                  # Backup pillar (7 checks)
│   ├── observability-checks.md           # Observability pillar (3 checks)
│   ├── operations-checks.md              # Operations pillar (11 checks)
│   ├── performance-checks.md             # Performance pillar (17 checks)
│   └── security-checks.md                # Security pillar (8 checks)
├── assets/
│   └── report-template.md                # full tabular report format (on request)
└── evals/
    ├── evals.json                        # functional eval definitions (skill-eval tool input)
    ├── additional-permissions.json       # read-only perms for the functional eval's agent spaces
    └── README.md                         # how evaluation results are generated and stored
```

The least-privilege IAM for this skill is delivered repo-wide through the shared template
[`cloudformation/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml),
which adds the `DevOpsAgentSkill-AwsFsxnOperationsReview` inline policy when
`EnableAwsFsxnOperationsReview` is `true` (the default).

## How to Use This Skill

Recurring posture review of a running workload (the primary use case):

> Run an operational review of our production FSx for NetApp ONTAP file systems and give me the
> prioritized findings.

Full review of specific file systems:

> Run an FSx for NetApp ONTAP operational review for account 123456789012 in us-east-1, file systems
> fs-0123456789abcdef0 and fs-0abcdef1234567890.

Single pillar:

> Review just the Performance pillar of my FSxN file systems — CPU, IOPS, SSD capacity, and tiering.

Targeted question that still routes through the check definitions:

> Which of my FSxN volumes have no snapshot policy or use ALL tiering on active data?

## Uploading to AWS DevOps Agent

Deploy the [IAM permissions](#2-iam-permissions) stack against your DevOps Agent role first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs an on-demand operational review that you ask for in chat and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add review context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `aws-fsxn-operations-review`, or filter by AWS service **Amazon FSx for NetApp ONTAP**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust check thresholds in `references/performance-checks.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/aws-fsxn-operations-review/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f aws-fsxn-operations-review.zip
   zip -r aws-fsxn-operations-review.zip aws-fsxn-operations-review/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l aws-fsxn-operations-review.zip | tail -1   # expect 8 files
   ```

2. Check that the zip has this structure:

   ```text
   aws-fsxn-operations-review.zip
   └── aws-fsxn-operations-review/
       ├── SKILL.md                          # required: frontmatter with name and description
       ├── assets/
       │   └── report-template.md
       └── references/
           ├── overview.md
           ├── backup-checks.md
           ├── observability-checks.md
           ├── operations-checks.md
           ├── performance-checks.md
           └── security-checks.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `aws-fsxn-operations-review.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing.
> It performs read-only operational analysis and makes no changes to your AWS resources, but you are
> responsible for reviewing the IAM permissions you grant and for validating the findings and
> recommendations it produces before acting on them.
