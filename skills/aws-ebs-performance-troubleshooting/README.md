# EBS Performance Troubleshooting Skill

This skill helps AWS DevOps Agent find out whether Amazon EBS is the reason disk I/O on an Amazon EC2 instance is slow or stuck, and why.

> **Note:** This skill is sample code. It's not intended for production use without additional review and testing. Validate it in a non-production environment first.

## Purpose

When an application on EC2 gets slow or its disk stops responding, the operator first needs to know whether EBS is the cause and what to do. The signals are spread across volume metrics, instance metrics, status checks and CloudTrail, and some look misleading on their own: a stalled volume can look idle, and a volume that got slower shows fewer IOPS. This skill checks them in a fixed order, names the cause with the evidence, and recommends a safe fix, so the operator doesn't apply the wrong fix or open a support case for a problem caused in their own account.

## Key Capabilities

- Checks each volume against its own limits: provisioned IOPS and throughput, and burst credits for gp2, st1 and sc1
- Checks the instance against its EBS bandwidth and IOPS limits, which affect all its volumes together
- Detects stalled and impaired volumes from `VolumeStalledIOCheck`, the volume status and the attached EBS status check
- Detects I/O disabled after a consistency check, volume modifications and snapshot initialization
- Checks every change to the instance and its volumes in CloudTrail, and running AWS FIS experiments that target them, and only blames a change that can explain the problem
- Hands off to `aws-health-events` for AWS-side events and to `support-cases` for a support case, with a ready-to-use case draft
- Returns a fixed report: the answer, the cause, the evidence, what was ruled out, what to do and the data gaps

## Prerequisites

- The agent's default permissions (`AIDevOpsAgentAccessPolicy`) cover every call this skill makes: `ec2:DescribeInstances`, `ec2:DescribeVolumes`, `ec2:DescribeInstanceTypes`, `ec2:DescribeVolumesModifications`, `ec2:DescribeFastSnapshotRestores`, `ec2:DescribeVolumeStatus`, `ec2:DescribeInstanceStatus`, `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics`, `cloudtrail:LookupEvents`, `fis:ListExperiments`, `fis:ListExperimentResolvedTargets`, `fis:GetExperimentTemplate`, and `health:DescribeEvents` when the `aws-health-events` skill isn't available. No extra IAM policy is needed.
- For the AWS Health check, the account needs a Business Support+, Enterprise Support or Unified Operations plan. Without one, the skill reports the check as a data gap. For support cases, it hands off to the `support-cases` skill.
- For the most complete diagnosis, the instance should be built on the Nitro System, where EBS publishes the stalled I/O check, the exceeded checks and the average latency metrics.

## Limitations

- On Xen and bare metal instances, and for Multi-Attach volumes, some metrics aren't published. The skill falls back to the other metrics and says what is missing.
- The skill can't see inside the instance. It asks the user for `iostat` or Performance Monitor data when the answer depends on it.
- CloudWatch latency is a 1-minute average and can understate what the application waits.
- The skill can't see the internal cause of a problem on the EBS side. Only AWS Support can.
- CloudTrail `LookupEvents` covers the last 90 days of management events in the region.
- The skill only reads data and recommends fixes. It never changes a volume, an instance or an experiment.

## Agent Types

This skill is used by the following agent types:

- **Chat tasks**: "is the disk the cause?" questions about an instance or a volume
- **Incident RCA**: root cause analysis of incidents with slow or stuck disk I/O

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/aws-ebs-performance-troubleshooting` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Instead, connect your personal GitHub account and select any repository from it during the connection setup. Once a GitHub connection is established, you can import skills from any public repository, including this one, even if it wasn't selected during the connection setup.

**Option B: Upload as a zip file**

1. Zip the `aws-ebs-performance-troubleshooting/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r aws-ebs-performance-troubleshooting.zip aws-ebs-performance-troubleshooting/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `aws-ebs-performance-troubleshooting.zip` file (max 6 MB).
5. Select the agent types: **Chat tasks** and **Incident RCA**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage skills, for example in CI/CD pipelines. Assign the skill to the `CHAT` and `INCIDENT_RCA` agent types. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to Use This Skill

### Chat

- "Disk writes on instance i-0123456789abcdef0 became very slow around 15:00 UTC. Is the disk the cause? Why, and what should I do?"
- "Is EBS throttling instance i-0123456789abcdef0?"
- "Volume vol-0123456789abcdef0 has been slow since this morning. What's going on?"
- "The attached EBS status check failed on i-0123456789abcdef0. What should I do?"
- "Writes on my database server hang since 09:30 UTC. Is it the EBS volume?"

### Investigation

- "Investigate the high disk latency alarm on i-0123456789abcdef0"
- "Our application on i-0123456789abcdef0 has had I/O timeouts since 03:00 UTC."
- "StatusCheckFailed_AttachedEBS is in alarm for i-0123456789abcdef0."
