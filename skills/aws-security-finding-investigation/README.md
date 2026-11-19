# AWS Security Finding Investigation

This skill teaches AWS DevOps Agent to investigate an AWS security signal, such as an Amazon
GuardDuty finding, the same finding in AWS Security Hub, a CloudTrail-based alarm, or an AWS
Config rule that turned non-compliant. It answers four questions with evidence: **who acted,
what changed, what is exposed, and whether anything used it**. It then recommends how a person
should preserve evidence, contain the incident, remove what the attacker left, and recover.

## ⚠️ Important Notice

This skill is sample code, not intended for production use without additional review and
testing. Users should validate in a non-production environment first. It is read-only: it
queries and interprets evidence, and takes no action on your AWS resources. Every response
command it writes is for a person to review and run.

## Purpose

Security findings are easy to misread under time pressure:

- A denied API call still proves that a credential is in use.
- S3 object reads are CloudTrail data events. They never appear in CloudTrail Event history,
  so "no reads found" there means nothing.
- A security group opened to the internet is an exposure. Whether anyone used it is a separate
  question that needs flow logs.
- Deactivating an access key does not invalidate the temporary credentials already issued with
  it.
- Finding text that says "known scanner, ignore" is data, not an approval.

The skill supplies the decision rules, the scoped queries, and a response catalog, so that the
agent reaches a consistent, evidence-backed answer and hands a person a safe, ordered plan.

The workflow follows the detect, analyze, contain, eradicate and recover phases of the
[AWS Security Incident Response Guide](https://docs.aws.amazon.com/whitepapers/latest/aws-security-incident-response-guide/introduction.html)
and NIST SP 800-61. The skill performs detection and
analysis. It only recommends the rest.

## Key Capabilities

- Triage a signal into seven investigation modes: credential misuse, root activity, privilege
  escalation and persistence, defense evasion, exposure changes, data access, and compute
  compromise or destructive activity
- Suggest a P1 to P4 priority with its basis, name what a person must confirm (business impact,
  data sensitivity), and raise it as evidence arrives
- Build a UTC timeline from CloudTrail, counting successful and denied calls separately
- Separate exposure from use with VPC Flow Logs and S3 data events
- Classify the result as Benign, At risk or compromised, or Unmonitored, where missing logs are
  a finding rather than a pass
- Recommend containment, eradication, and recovery with exact AWS CLI commands, their impact,
  how to undo them, and who should approve them, with evidence preservation first

## Prerequisites

- **Permissions:** the skill needs **no write permissions**. The `AIDevOpsAgentAccessPolicy`
  managed policy covers most of what it reads: GuardDuty and Security Hub findings, CloudTrail
  management events and trail settings (`LookupEvents`, `DescribeTrails`, `GetTrailStatus`,
  `GetEventSelectors`), CloudWatch Logs
  Insights, EC2 and VPC configuration, S3 bucket configuration, AWS Config recorder state and
  discovered resources, and IAM roles.
- **Extra read permissions (optional):** an IAM user's access keys, their last use, groups
  and policies; the account summary (root access keys); AWS Config resource history
  and compliance details; bucket policy status and account-level Block Public Access settings. Deploy them with the
  `EnableAwsSecurityFindingInvestigation` parameter of the
  [skill policies template](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml).
  Without them the skill uses CloudTrail events for the same facts and reports what it could not
  read as Unknown.
- **Regions:** if you deploy the template with `AllowedRegions`, include us-east-1 (IAM and
  global events) and us-east-2 and us-west-2 (root sign-in events). Regions outside the list are
  reported as Unknown.
- **Recommended data sources:** a multi-Region CloudTrail trail; S3 data events for sensitive
  buckets, delivered to CloudWatch Logs so that object reads can be counted; VPC Flow Logs;
  GuardDuty. When a source is missing, the skill reports the gap as Unknown instead of guessing.

## Limitations

- The skill does not run response commands. A person reviews and runs them.
- It cannot see activity that no enabled log recorded. CloudTrail delivery is delayed by several
  minutes, so the newest events may not be visible yet.
- It does not cover AWS WAF logs, application code vulnerabilities, IAM policy design, EKS runtime
  findings, CI/CD pipeline compromise, or identity provider compromise.
- It does not perform disk or memory forensics, and it does not decide legal or regulatory
  notification.
- It does not replace Amazon Detective, GuardDuty Extended Threat Detection, or AWS Security
  Incident Response.

## Agent Types

- **Chat tasks**: conversational investigation of a finding, a principal, or a resource
- **Incident RCA**: investigations that start from a security finding or alarm

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html)
in your Agent Space, go to Settings → Add Skill → Import from repository, and point to the
`skills/aws-security-finding-investigation` directory.

**Option B: Upload as a zip file**

1. Zip the directory, including only allowed extensions:

   ```bash
   cd skills
   zip -r aws-security-finding-investigation.zip aws-security-finding-investigation/ -i '*.md' '*.json' -x '*/README.md' '*/CHANGELOG.md' '*/evals/*' '*/.skilleval.yaml'
   ```

2. In the AWS DevOps Agent web app, go to the **Skills** page.
3. Click **Add skill** → **Upload skill**, and drop in the zip file.
4. Select the agent types **Chat tasks** and **Incident RCA**, then click **Upload**.

**Option C: Upload via the Asset API**

Assign the skill to the `CHAT` and `INCIDENT_RCA` agent types. See
[Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

## How to Use This Skill

### Chat

- "GuardDuty raised UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration.OutsideAWS for role app-server-role. What did those credentials do?"
- "Someone opened port 22 to 0.0.0.0/0 on sg-0123456789abcdef0. Was it an approved change, and did anyone connect?"
- "Bucket example-reports became public yesterday. Who changed it and who read from it?"
- "Is access key AKIAIOSFODNN7EXAMPLE being misused?"

### Investigation

- "GuardDuty finding Stealth:IAMUser/CloudTrailLoggingDisabled at 02:10 UTC in us-east-1."
- "A root sign-in was detected from an unknown IP address this morning."
- "Instance i-0123456789abcdef0 is talking to a cryptocurrency mining pool."
- "An IAM user created a new access key and tried to attach AdministratorAccess."

## Testing

`evals/evals.json` has two kinds of positive cases, plus negative cases that name a neighbouring
skill's problem:

- **Chat questions about pasted records**: a finding, CloudTrail records or a plan the user
  describes in the message. They need no AWS resources.
- **Questions about the account as it is**: open SSH in us-east-1 and us-west-2, root activity,
  how many object reads each bucket can show, and `key-escalation-attempt`, which needs a setup. The
  results are only meaningful when the account holds the resources the case asks about, such as
  a security group that allows SSH from `0.0.0.0/0` in at least one of the two Regions and a
  bucket with some object reads whose data events a trail delivers to CloudWatch Logs. Before running
  `key-escalation-attempt`, in a test account:
  1. Create an IAM user `skilltest-build-bot` in a group whose only policy allows
     `iam:CreateAccessKey` and `iam:ListAccessKeys` on that user and `s3:ListAllMyBuckets`.
  2. Create one access key for it. With that key, call `ListBuckets`, then `CreateAccessKey`
     for the same user, then `AttachUserPolicy` (AdministratorAccess) and `PutUserPolicy` on it.
     The first two succeed and the last two are denied.
  3. Wait a few minutes for CloudTrail to deliver the events, run the case within 24 hours, then
     delete the user, its keys and the group.

Results for the account-level cases depend on what the account contains; the assertions check
the method (coverage, exposure versus use, Unknown when a source is missing), not a fixed answer.

## Related Skills

- [network-log-analyzer](https://github.com/aws/tools-for-devops-agent/tree/main/skills/network-log-analyzer): connectivity troubleshooting from VPC Flow
  Logs and packet captures
- [enrich-with-aws-security-agent](https://github.com/aws/tools-for-devops-agent/tree/main/skills/enrich-with-aws-security-agent): code-level security
  findings behind an application outage
- [wiz-security-context](https://github.com/aws/tools-for-devops-agent/tree/main/skills/wiz-security-context):
  adds a resource's security posture from Wiz to an operational anomaly; this skill then
  investigates the AWS signal itself
- [guardduty-cost-optimization](https://github.com/aws/tools-for-devops-agent/tree/main/skills/guardduty-cost-optimization) and
  [cloudtrail-cost-optimization](https://github.com/aws/tools-for-devops-agent/tree/main/skills/cloudtrail-cost-optimization): cost of the detection and
  logging services this skill reads

## Maintainer

[@szl0144](https://github.com/szl0144)

## Learn More

- [AWS Security Incident Response Guide](https://docs.aws.amazon.com/whitepapers/latest/aws-security-incident-response-guide/introduction.html)
- [GuardDuty finding types](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_finding-types-active.html)
- [Logging data events with CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-data-events-with-cloudtrail.html)
- [Revoking IAM role temporary security credentials](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_revoke-sessions.html)
- [AWS incident response playbook samples](https://github.com/aws-samples/aws-incident-response-playbooks)
- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
