# S3 Resiliency Review Skill

A skill for AWS DevOps Agent that performs a structured, **read-only** resiliency,
security, and data protection review of Amazon S3 buckets and produces a rated
report with prioritized findings and remediation guidance.

## What it does

Given one or more S3 bucket names, the skill collects each bucket's configuration
using read-only control-plane API calls and evaluates it across nine dimensions:

1. **Versioning** — protection against overwrites and deletes
2. **Replication** — cross-region / cross-account redundancy (four-quadrant risk model)
3. **Object Lock** — immutability / WORM protection
4. **Bucket policy** — defensive Deny statements and transport security
5. **Block Public Access** — bucket- and account-level, cross-referenced with ACLs and policy
6. **Default encryption** — SSE-S3 / SSE-KMS / DSSE-KMS and Bucket Key
7. **Ownership controls** — ACL posture and BucketOwnerEnforced migration
8. **Server access logging** — logging or CloudTrail S3 data events for audit trail
9. **Static website hosting** — public-by-design exposure checks

Each bucket receives a **Resiliency Rating** (High / Medium / Low / Indeterminate)
with per-dimension findings. Reviews are routed automatically:

- **1 bucket** → full single-bucket report
- **2–20 buckets** → fleet report (summary matrix + details)
- **21+ buckets** → batched fleet review with a manifest for progress tracking and resume

## Prerequisites

The DevOps Agent role must have **read-only** permissions for the review to
produce complete results. These are IAM action names (which differ from the API
call names for some S3 operations):

```
s3:ListBucket
s3:ListAllMyBuckets
s3:GetBucketVersioning
s3:GetReplicationConfiguration
s3:GetBucketObjectLockConfiguration
s3:GetBucketPolicy
s3:GetBucketPublicAccessBlock
s3:GetAccountPublicAccessBlock
s3:GetEncryptionConfiguration
s3:GetBucketOwnershipControls
s3:GetBucketAcl
s3:GetBucketLogging
s3:GetBucketWebsite
s3:GetBucketCORS
s3:GetBucketLocation
cloudtrail:DescribeTrails
cloudtrail:GetEventSelectors
```

(`sts:GetCallerIdentity` is also used to resolve the account ID; it requires no
IAM permission.)

Most of these are covered by `AIDevOpsAgentAccessPolicy`. If a check lacks
permission, the skill reports it as "Unable to verify — access denied" and caps the
Resiliency Rating at Medium rather than guessing the configuration.

The skill **never** reads object data (`GetObject`) and **never** performs any
write, create, update, or delete operation.

## How to use it with DevOps Agent

Works with the **On-demand** and **Incident RCA** subagents. Describe
the task in natural language — you do not need to name the skill:

- "Run an S3 resiliency review on `my-production-bucket`."
- "Is my bucket `app-data-prod` safe? Audit its security and data protection."
- "Review these buckets for resiliency: `logs-bucket`, `assets-bucket`, `backups-bucket`."
- "What's the disaster recovery posture of `analytics-raw`?"
- "Check versioning, replication, and public access on `customer-uploads`."

The agent gathers configuration via its `use_aws` tool under the assumed role in the
target account, applies the finding logic, and returns a Markdown report artifact.

## Agent Types

This skill is used by the following agent types (selected in the Operator Web App
at upload time):

- **On-demand** — conversational, on-demand reviews ("run an S3 resiliency review
  on `my-bucket`", "is `app-data-prod` safe?").
- **Incident RCA** — automated root cause analysis where an S3 bucket's
  data-protection or public-access posture may be a contributing factor.

Select **Generic** instead if you want the skill available to all agent types.

## Uploading to AWS DevOps Agent

Check that the DevOps Agent role has the [read-only S3 and CloudTrail permissions](#prerequisites) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

The skill runs on-demand bucket reviews, and Incident RCA uses it when a bucket's data-protection or public-access posture may contribute to an incident, so target **On-demand** and **Incident RCA**. **Generic** would load it for every agent type, incident triage included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `storage-s3-resiliency-expertise`, or filter by AWS service **Amazon S3**.
4. Choose **Details** and check that the agent types are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust the finding rules in `references/finding-logic.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/storage-s3-resiliency-expertise/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f storage-s3-resiliency-expertise.zip
   zip -r storage-s3-resiliency-expertise.zip storage-s3-resiliency-expertise/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l storage-s3-resiliency-expertise.zip | tail -1   # expect 6 files
   ```

2. Check that the zip has this structure:

   ```text
   storage-s3-resiliency-expertise.zip
   └── storage-s3-resiliency-expertise/
       ├── SKILL.md                              # required: frontmatter with name and description
       └── references/
           ├── data-collection.md                # read-only configuration calls
           ├── finding-logic.md                  # finding rules per check
           ├── fleet-orchestration.md            # multi-bucket reviews
           ├── report-format.md                  # report structure
           └── s3-resiliency-best-practices.md   # thresholds, gotchas, decision trees
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `storage-s3-resiliency-expertise.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
