# CloudTrail Coverage Auditor Skill

A skill for AWS DevOps Agent that answers, for one AWS account, which API
activity CloudTrail is capturing today and which S3 buckets, Lambda functions
and DynamoDB tables have no data event record anywhere, so an audit team can
state what is and is not covered. It is **read only**: it reports the exact
operator change for each gap and never applies it.

## Purpose

CloudTrail configuration questions from auditors ("what exactly is being
logged?") have a precise answer that depends on trail scope, event selectors,
Region, logging state, delivery health and, in an organization, a trail owned by
another account. Without a fixed procedure the answer varies from run to run and
stops at "no data events configured" instead of naming the resources that have
no record. This skill runs the same 20 check matrix every time, resolves every
in scope resource to one of five coverage states, models an organization trail
the agent cannot read as an explicit unverified state with the ARN and command
the operator needs, always states the Event history limit and how automated
activity is attributed, and returns a rating an auditor can quote.

By default the skill checks against a built in baseline: multi Region
management logging with global service events, data events for the baseline
resource types present in the account, log file validation, healthy delivery,
and Insights noted. When the user supplies a required resource list it checks
that list and rates against it.

### Gap measured against the base agent

Measured on 2026-10-21 against a test account holding a single Region trail
(no global service events, no data events, no Insights, no log file
validation), an account wide management trail and an organization trail owned
by the management account. Three customer prompts, two runs each, base DevOps
Agent without a skill:

1. Facts were correct in every run; the agent knows the APIs.
2. The same prompt ("audit our CloudTrail for our auditors") produced a 3.9 KB
   answer with 5 checks per trail in one run and an 18.6 KB answer with 15 or
   more checks per trail in the next. The check set changed 3x and the length
   5x between identical runs.
3. 0 of 6 runs listed which S3 buckets, Lambda functions or DynamoDB tables
   therefore have no data event record. Every run stopped at "no data events
   configured".
4. 0 of 6 runs mentioned the 90 day Event history limit or how service and
   service linked role activity is attributed, both named in the request that
   motivated the skill.
5. The organization trail was called "opaque from this account" in every run,
   with no ARN and no command the operator could use to confirm it. Inside
   DevOps Agent neither the base agent nor the skill can read the organization
   trail's selectors from a member account: the agent's AWS tool blocks cross
   account ARNs before the request reaches AWS, even though the CloudTrail API
   permits the call with the full trail ARN (verified from the CLI). The
   skill's value is that it records the exact ARN and the `GetEventSelectors`
   command for the operator and models the result as an explicit
   `CoveredByOrgTrail-Unverified` state instead of saying "I can't inspect it".
6. "Covered by the organization trail, not verified" was never a distinct state
   from "covered nowhere".

The skill fixes this with a 20 row check matrix that runs identically every
time, a per resource coverage state, an explicit unverified state for the
organization trail with the operator's ARN and command, mandatory Event history
and attribution notes, and a rating an auditor can quote.

## Key Capabilities

- Trail inventory across every enabled Region with shadow trails de duplicated
  by ARN, plus CloudTrail Lake event data stores as coverage sources
- Organization trail attempted with the full trail ARN (never the name); when
  the agent's AWS tool blocks the cross account read, the affected resources
  are `CoveredByOrgTrail-Unverified` and Next Steps carries the ARN and the
  `GetEventSelectors` command for the operator
- Per resource coverage state for every S3 bucket, Lambda function and DynamoDB
  table in scope: `Covered`, `CoveredByOrgTrail-Unverified`, `Uncovered`,
  `Unknown`, `NotApplicable`, with the covering trail and selector note
- Basic and advanced event selector semantics (type wide values, bucket and
  prefix ARNs, `StartsWith`, `NotStartsWith`, `readOnly`, `eventName`
  allowlists including the multipart upload and `DeleteObjects` gap)
- Fixed 20 check matrix: management scope, global services, read and write,
  source and service event exclusions, data events per type, selector
  precision, Insights, stopped trails that removed coverage, delivery errors
  and recency, log file validation, KMS, destination bucket posture,
  organization trail readability and management coverage, Event history and
  attribution notes
- Required list mode: the user names buckets, functions and tables; each is
  reported as captured, not captured, or not found
- Inline data mode: paste trail, selector or status output with no account
  access and get the same evaluation, labelled `SUPPLIED DATA`
- Rating `Healthy`, `Attention`, `AtRisk`, `Indeterminate` with a one line
  Bottom line, and the exact operator change for every finding

## Prerequisites

An AWS DevOps Agent Space with the target account configured as a cloud source.

**No additional IAM permissions are required.** Every call is a read and every
one is granted by the AWS managed
[`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html)
(checked against policy version v12, October 2026):

- `cloudtrail:DescribeTrails`, `cloudtrail:ListTrails`,
  `cloudtrail:GetTrailStatus`, `cloudtrail:GetEventSelectors`,
  `cloudtrail:GetInsightSelectors`, `cloudtrail:ListEventDataStores`,
  `cloudtrail:GetEventDataStore` (`cloudtrail:GetTrail` is granted but never
  called; `DescribeTrails` returns every field used)
- `s3:ListAllMyBuckets`, `s3:GetBucketLocation`, `s3:GetBucketVersioning`,
  `s3:GetBucketObjectLockConfiguration`, `s3:GetBucketPublicAccessBlock`
- `lambda:ListFunctions`, `dynamodb:ListTables` (list calls only; the agent
  guardrail cancels `dynamodb:DescribeTable` as mutative and `lambda:GetFunction`
  is denied, neither is needed)
- `organizations:DescribeOrganization`,
  `organizations:ListDelegatedAdministrators`, `ec2:DescribeRegions`
- Optional context: `kms:DescribeKey`, `logs:DescribeLogGroups`, `iam:GetRole`
- Only when a required list names them: `sns:GetTopicAttributes`,
  `sns:ListTopics`, `sqs:ListQueues`, `sqs:GetQueueAttributes`

There is no CloudFormation template to deploy and no
`--additional-permissions-file` for the skill evaluation tool. Full table:
[references/permissions.md](https://github.com/aws/tools-for-devops-agent/blob/main/skills/cloudtrail-coverage-auditor/references/permissions.md).

The skill never calls `CreateTrail`, `UpdateTrail`, `DeleteTrail`,
`PutEventSelectors`, `PutInsightSelectors`, `StartLogging`, `StopLogging`,
`LookupEvents`, or any S3, KMS, Lambda, DynamoDB or Organizations write.

## Agent Types

This skill is used by the following agent type (selected in the Operator Web App
at upload time):

- **Chat tasks**: on demand questions such as "audit our CloudTrail
  configuration for our auditors" or "would CloudTrail record an object delete
  in our buckets".

If your Agent Space does not list **Chat tasks**, select **All agents**. Nothing
in the skill depends on a particular agent type.

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html)
in your Agent Space, import the skill directly. In the DevOps Agent web app, go
to Settings, Add Skill, Import from repository, then point to the
`skills/cloudtrail-coverage-auditor` directory. See
[Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Connect your personal GitHub account instead; once a connection exists you can import skills from any public repository, including this one.

**Option B: Upload as a zip file**

1. Zip the `cloudtrail-coverage-auditor/` directory (only allowed extensions):
   ```bash
   cd skills
   zip -r cloudtrail-coverage-auditor.zip cloudtrail-coverage-auditor/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```
2. In the AWS DevOps Agent web app, open the **Skills** page.
3. Choose **Add skill**, then **Upload skill**.
4. Drop the `cloudtrail-coverage-auditor.zip` file (max 6 MB).
5. Select the agent type **Chat tasks**, or **All agents** if your space lists a different set.
6. Choose **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to manage skills from CI/CD. Assign the skill
to the `CHAT` agent type. See
[Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills)
in the AWS DevOps Agent User Guide.

## How to Use This Skill

Describe the task in natural language. You do not need to name the skill.

- "Audit our CloudTrail configuration in this account. Our auditors need to know exactly what is and is not being captured."
- "If someone deletes an object from one of our S3 buckets or invokes a Lambda function, would CloudTrail record it? Check our trails."
- "Review the trail prod-single-region-trail and tell me what visibility gaps it has."
- "Our audit requires data event logging on these resources: S3 bucket finance-reports, Lambda function payroll-export, DynamoDB table employees in us-east-1. Check which of them CloudTrail actually captures today."
- "We are a member account in an AWS organization. Which part of our CloudTrail coverage comes from the organization trail, and can our auditors rely on Event history instead of a trail?"
- "Check CloudTrail coverage for us-east-1 only. Is anything in that Region not being logged, and are the logs actually being delivered?"
- "Here is our trail config, we have no console access right now. Tell me which of these buckets and functions have data events logged. [paste DescribeTrails and GetEventSelectors output]"
- "Evaluate this advanced event selector for our audit. [paste AdvancedEventSelectors JSON]"

The agent reads configuration through its native AWS tooling under the Agent
Space role and returns a Markdown report with a rating, a Bottom line, a trail
inventory, a per resource coverage table, severity ordered findings with the
operator change for each, the 20 row check matrix, what auditors should know,
what was not assessed, and next steps.

## Scope boundary versus adjacent skills

- `cloudtrail-cost-optimization` answers what CloudTrail costs and where the
  waste is; this skill answers what CloudTrail is not recording. The two read
  the same trail and selector fields and ask opposite questions: the cost skill
  finds the paid second copy and the scope that can be narrowed, this one
  confirms that at least one copy of every class of activity still exists and
  is delivered. Run the cost skill to cut spend, this one to confirm nothing
  an auditor needs was cut.
- `unified-security-cost-optimizer` is the custom agent that reduces spend on
  CloudTrail, Config and GuardDuty by routing to their cost skills; this skill
  is not part of that agent and never estimates a saving.
- Hand off: when the user asks about cost, whether duplicate trails are waste,
  or data event volume charges, the agent should use
  `cloudtrail-cost-optimization` instead of this skill. Inside this skill a
  second trail recording the same events is reported as a count ("recorded by
  N trails; coverage is not affected"), never as a finding, with no dollar
  figure. A stopped trail or a KMS or RDS source exclusion whose events another
  trail records is INFO here, not a gap, so a customer who followed the cost
  skill's advice does not get it reversed by this one.
- CIS and FSBP control scoring is Security Hub's job. This skill does not score
  controls; it reports configuration and per resource coverage.
- Log content analysis ("who deleted this bucket", "find the event") is the
  base agent's infrastructure change investigation. This skill reads
  configuration and status only; it never calls `LookupEvents` or reads a log
  file.
- S3 destination bucket resiliency (versioning, replication, Object Lock) is
  `storage-s3-resiliency-expertise`; this skill reports bucket posture on the
  trail destination only as INFO context.

## Limitations

- Control plane only. The skill reads trail, selector and status fields and
  resource inventories; it never reads a log file or Event history content.
- Baseline resource types are S3 general purpose buckets (`AWS::S3::Object`),
  Lambda functions and DynamoDB tables, the three types basic event selectors
  support. Advanced only types (`AWS::S3Outposts::Object`,
  `AWS::S3Express::Object`, `AWS::S3::AccessPoint`, `AWS::SNS::Topic`,
  `AWS::SQS::Queue`, `AWS::Cognito::IdentityPool`, `AWS::EKS::Cluster` and
  others) are not inventoried unless the user's required list names one; the
  report lists them as not assessed.
- DynamoDB streams are not separate rows: selecting a table logs its stream
  events by default, so the table row answers the stream question. Stream
  presence is not read (`DescribeTable` is cancelled by the agent guardrail); a
  one line note states that stream events follow the table's data events.
- Single account view. From a management or delegated administrator account the
  review covers that account's resources; organization trail data resources
  naming other accounts are reported as covering resources outside this account.
  An organization wide sweep is not part of this version.
- From a member account inside DevOps Agent, the organization trail's status
  and selectors cannot be read: the agent's AWS tool rejects cross account ARNs
  before the call reaches AWS, so `CoveredByOrgTrail-Unverified` is the normal
  result for every resource the organization trail could cover, and the rating
  caps at `Attention`. The CloudTrail API itself permits the read with the full
  ARN; the operator runs `aws cloudtrail get-event-selectors --trail-name <full
  ARN>` from the CLI or the management account to resolve the rows. The skill
  still makes the one ARN call so a future tool change is picked up. The same
  block applies to `DescribeTrails` with a `trailNameList` that contains the
  organization trail ARN (the call then returns nothing, so the own trails are
  lost too) and to `GetTrail` by that ARN; the skill calls `DescribeTrails` per
  Region with no `trailNameList` and never calls `GetTrail`.
- Inside DevOps Agent the report is rendered by the Context Gatherer subagent.
  The chat agent may relay a summary; the full report (Resource Coverage table,
  20 row Check Matrix, Not Assessed) is in the subagent's output. Ask "show the
  full report" to get it unchanged. The report's second line is a relay note
  asking the parent to deliver it unchanged.
- Pasted data (no account access) prompts are answered by the chat agent
  directly, so the skill applies only if the chat agent can load it. The chat
  agent's `skill_read` may report the skill as not found (observed when the
  asset had just been uploaded); the answer is then the base agent's.
- Cross account S3 buckets touched by this account's principals are logged by
  an `arn:aws:s3` selector but are not in this account's inventory and are not
  listed.
- Delivery recency thresholds (1 hour INFO, 24 hours HIGH) are heuristics;
  CloudTrail delivers about every 5 minutes but does not guarantee it, and quiet
  Regions can legitimately show older timestamps.
- The multipart upload and `DeleteObjects` gap in `eventName` allowlists is
  derived from the S3 event name list in the CloudTrail documentation; no AWS
  page states it as a caveat.
- Point in time: the report is valid for the configuration at evaluation time.

## Open questions for SME review

1. Organization trail readability: `GetEventSelectors` with the full trail ARN
   works from a member account from the CLI, but inside DevOps Agent the AWS
   tool rejects the cross account ARN before the call reaches AWS (observed on
   every live run, "ARN account ... not in target accounts"). Is that
   restriction expected to stay? If it can be lifted for CloudTrail
   organization trail ARNs, `CoveredByOrgTrail-Unverified` becomes rare; until
   then the operator resolves it from the CLI or the management account.
2. Does an organization trail selector `arn:aws:s3` (all buckets) cover member
   account buckets, or only the management account's? The documentation says
   member resource ARNs can be added and the console lists only management
   account resources; it does not state the wildcard's scope across accounts.
   The model assumes "all buckets in every account the trail logs".
3. Baseline type set: S3 objects, Lambda functions, DynamoDB tables only (basic
   selector types). Should SNS topics or SQS queues join the baseline, or stay
   request only?
4. Severity of `Uncovered` in baseline mode: HIGH (rating `Attention`) is
   proposed, CRITICAL only in required list mode. Agree?
5. Delivery age thresholds for L3 (1 h INFO, 24 h HIGH) given "about every 5
   minutes, not guaranteed" and quiet Regions.
6. CloudTrail Lake event data stores as coverage sources: include (proposed) or
   report separately?
7. Insights at LOW in the baseline, or INFO only?
8. E2 destination bucket posture: keep as INFO context, or drop to avoid
   overlap with `storage-s3-resiliency-expertise`?
9. Multipart event name gap (D4) is derived from the S3 event name list, not
   from a stated AWS caveat. Is that the right reading of "multipart operation
   filtering"?
10. `cloudtrail:LookupEvents` is in the policy. The skill does not call it (log
    analysis is out of scope). Agree, or should one lookup confirm that Event
    history is reachable?
11. Catalog vocabulary: `aws-services: "AWS CloudTrail"`, `technical-domains:
    "Security, Governance"`, `agent-types: "CHAT"`. OK? (`AWS Organizations` is
    not an approved `aws-services` value in this repository.)
12. Management account mode: single account view with "covers resources outside
    this account" notes for this version; organization wide sweep later. OK?
13. Why does the chat agent's `skill_read` fail for a skill the Context Gatherer
    loads in the same session? Is skill registration scoped to the subagent
    profile for `agent-types: CHAT`? Measured: in the functional harness the
    parent's `skill_read` returned "Skill not found" in 32 of 32 with_skill
    runs while the Context Gatherer loaded it every time (upload, ACTIVE, 45 s
    settle, then the task); on a standing agent space the parent loaded the
    same asset after a longer wait following upload. The harness now probes
    until the parent's own load succeeds before running the task.

## Non-production disclaimer

> ⚠ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
