# ECR Lifecycle Guard Skill

A skill for AWS DevOps Agent that answers, for one Amazon ECR repository or for
every repository in an account, which images the lifecycle policy will remove at
its next evaluation and whether any of them is still in use or tagged as a
release. It is **read only**: it reports and never remediates.

## Purpose

An ECR lifecycle policy runs within 24 hours of an image meeting its criteria,
and a `tagStatus: any` catch all rule counts across every tag family without
knowing what is running. Operators find out when a task, job or function fails to
pull. Measured against a 26 image repository with a five rule policy in October
2026, the base agent produced the correct expiring list in one of four runs, never
called the ECR preview API, and twice called an image with a recorded pull "not a
concern" or "currently safe". ECR deleted that image the next day.

This skill makes the agent run ECR's own preview first, fall back to a documented
simulation of ECR's rule semantics when the preview cannot run, cross reference
every expiring image against ECS, AWS Batch, Lambda, App Runner, EKS presence and
recorded pull activity on every run, and return a fixed verdict for every image
instead of prose.

### Gap measured against the base agent

Measured on 2026-10-21 against a 26 image repository with a five rule policy
(untagged after 1 day, keep 2 `nightly-`, keep 5 `build-*`, `rc-` after 14 days,
`tagStatus: any` keep 6), four runs of the base agent without this skill:

1. The correct 12 image expiring set was produced in 1 of 4 runs. The others
   listed 9 images, 1 image, and a wrong set of 12 (expired `rc-*` and
   `build-8` to `build-12`, missed `build-1` to `build-7`).
2. An image with a recorded pull and no task definition (`v2.3.0`) was called
   "not a concern" in one run and "currently safe" in another. ECR's own preview
   listed it, and ECR deleted it within 24 hours.
3. `StartLifecyclePolicyPreview` and `GetLifecyclePolicyPreview` were never
   called (0 of 4). One run stated the start call "is blocked as a mutating
   operation in my read-only access" and stopped there.
4. `lastRecordedPullTime` was read only when the prompt hinted at direct pulls.
5. A one rule, six image control repository was handled correctly 6 of 6 times,
   so the failure is multi rule priority semantics, not ECR knowledge.
6. Even on that control repository, 1 of the 6 runs offered to rewrite the
   policy, which a read only review must never do.

The skill closes each gap with: preview first with a documented approval path, a
deterministic simulation as fallback, a mandatory in use cross reference on
every run, a fixed verdict table that leaves no room for "safe" prose, and a
hard rule that the skill reports and never remediates.

Live test round 1 (2026-10-27, skill on) exposed a flaw in the skill itself:
every expiring image had a CloudTrail `BatchGetImage` event 1 to 2 seconds after
its own `imagePushedAt`, emitted by the push, and the skill counted all of them
as consumer pulls (11 of 11 `Expiring-InUse`, 100 percent false positive) while
`lastRecordedPullTime` showed one real pull in the repository. The evidence
hierarchy and push correlation rule in `SKILL.md` are the fix.

## Key Capabilities

- Preview first: `StartLifecyclePolicyPreview` and `GetLifecyclePolicyPreview`,
  polled to `COMPLETE`, labelled `AUTHORITATIVE`
- Deterministic fallback simulation of the documented evaluation rules
  (priority order, higher rule claims its candidates, `imageCountMoreThan` by
  push time, `sinceImagePushed` and `sinceImagePulled` by age, prefix and
  pattern lists ANDed across entries), labelled `SIMULATED`
- Draft policy support: paste a policy JSON in chat and see what it would do
  before applying it
- In use cross reference by digest and tag: `lastRecordedPullTime`, running ECS
  tasks, ECS services and ACTIVE task definitions, Batch ACTIVE job definitions,
  Lambda container image functions, App Runner services, EKS cluster presence,
  optional CloudTrail pull events (events within 60 seconds of the push or from
  the pushing principal are excluded as push correlated)
- Fixed per image verdict: `Safe`, `Expiring-Unused`, `Expiring-InUse`,
  `Expiring-Unknown`; fixed repository rating: `Healthy`, `Attention`,
  `AtRisk`, `Indeterminate`
- Rule by rule table showing which rule claims which images and whether a rule
  removes an in use image
- Protected tag heuristic for `prod*`, `release*`, semantic versions, `latest`,
  `stable`, `hotfix*` governed only by a catch all
- A specific protective rule JSON handed to the operator, never applied
- Multi repository mode for "the account" or "all repos", worst repositories first

## Prerequisites

The Agent Space role needs read access to ECR, ECS, Batch, Lambda, App Runner,
EKS and CloudTrail. `AIDevOpsAgentAccessPolicy` (v11, checked 2026-10-26) covers
everything except these four actions:

```
ecr:StartLifecyclePolicyPreview
ecr:GetLifecyclePolicyPreview
batch:DescribeJobDefinitions
lambda:GetFunction
```

Attach them as an inline policy on the Agent Space role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EcrLifecycleGuardDelta",
      "Effect": "Allow",
      "Action": [
        "ecr:StartLifecyclePolicyPreview",
        "ecr:GetLifecyclePolicyPreview",
        "batch:DescribeJobDefinitions",
        "lambda:GetFunction"
      ],
      "Resource": "*"
    }
  ]
}
```

A parameter for this skill in the shared skill policies template at
[cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml)
is not part of this skill folder and lands in the same pull request as a
separate change (together with the `llms.txt` entry and the skills catalog
acronym). Until it is merged, use the inline policy above.

**The skill still runs without these four.** Without the preview actions the
expiring set is computed by the skill and labelled `SIMULATED`, which caps the
repository rating at `Attention` unless an in use image is found. Without the
Batch and Lambda actions those sources are reported as `AccessDenied` and every
expiring image with no other reference becomes `Expiring-Unknown`. Nothing is
guessed.

### Preview approval note

`StartLifecyclePolicyPreview` has the access level "Write" in the AWS service
reference for ECR, even though it only computes a result and changes no image,
tag, policy or repository setting. The DevOps Agent's tool policy may therefore
cancel it with a message similar to:

```
Cancelled mutative operation: ecr StartLifecyclePolicyPreview. This operation requires an operator approval to execute.
```

If you see this in chat, approving it is safe: nothing is deleted, archived or
modified. ECR records the preview as a `DryRunEvent` in CloudTrail. If you do not
approve, the skill continues with the simulation and labels the result
`SIMULATED`. The skill asks once per run and never blocks on the answer.

### Running the skill evaluation tool

Functional evaluations need the four delta actions. Pass them with the tool's
`--additional-permissions-file` option, using a file such as
`evals/additional-permissions.json`:

```json
[
  {
    "actions": [
      "ecr:StartLifecyclePolicyPreview",
      "ecr:GetLifecyclePolicyPreview",
      "batch:DescribeJobDefinitions",
      "lambda:GetFunction"
    ]
  }
]
```

## Limitations

- Control plane only. EKS pod image references need the Kubernetes API, which is
  out of scope; an EKS cluster in the Region makes unreferenced expiring images
  `Expiring-Unknown`, never `Expiring-Unused`.
- `lastRecordedPullTime` is refreshed by ECR at least once every 24 hours, so a
  pull in the last day may not be visible yet. The skill treats any recorded pull
  inside the window (default 30 days) as in use evidence and never treats a
  missing value as proof of non use.
- Direct pulls by EC2 hosts, CI runners or laptops leave no task or function
  definition. They are visible only through `lastRecordedPullTime` or the
  optional CloudTrail probe, which the agent guardrail may cancel.
- Consumers in other accounts or Regions that pull from this registry are not
  inventoried.
- The preview evaluates the images present at that moment and its results are
  kept by ECR for a limited time. The report states the evaluation time.
- The simulation follows the public documentation. Where ECR's evaluator and the
  documentation differ, the preview wins, which is why the preview runs first.
- `archive` actions are treated like `expire` for verdicts and shown in their own
  column. This is a design choice pending SME review.
- The ECS task definition scan is bounded at 200 ACTIVE ARNs; above that the
  skill describes the latest revision per family plus everything referenced by a
  running task or service and reports the source as `Partial`.
- Point in time: the report is valid for the image set at evaluation time.

## Agent Types

This skill is used by the following agent type (selected in the Operator Web App
at upload time):

- **Chat tasks**: on demand questions such as "which images will this policy
  delete" or "is it safe to leave the lifecycle policy as is".

If your Agent Space does not list **Chat tasks**, select **All agents**. Nothing
in the skill depends on a particular agent type.

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, import the skill directly. In the DevOps Agent web app, go to Settings, Add Skill, Import from repository, then point to the `skills/ecr-lifecycle-guard` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Connect your personal GitHub account instead; once a connection exists you can import skills from any public repository, including this one.

**Option B: Upload as a zip file**

1. Zip the `ecr-lifecycle-guard/` directory (only allowed extensions):
   ```bash
   cd skills
   zip -r ecr-lifecycle-guard.zip ecr-lifecycle-guard/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```
2. In the AWS DevOps Agent web app, open the **Skills** page.
3. Choose **Add skill**, then **Upload skill**.
4. Drop the `ecr-lifecycle-guard.zip` file (max 6 MB).
5. Select the agent type **Chat tasks**, or **All agents** if your space lists a different set.
6. Choose **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to manage skills from CI/CD. Assign the skill to the `CHAT` agent type. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to Use This Skill

Describe the task in natural language. You do not need to name the skill.

- "Which images in ECR repo payments-api will be deleted by the current lifecycle policy? Give me the exact list and tell me if any of them are still being used."
- "Is it safe to leave the lifecycle policy on payments-api as is? Our batch jobs run on EC2 and pull images directly from ECR."
- "Before I apply this lifecycle policy to repo example-api, tell me what it would delete: { ...policy JSON... }"
- "Across every ECR repository in this account in us-east-1, will any lifecycle policy delete an image we are still running?"
- "Are our prod-* and release-* tags protected from the keep newest 10 rule on repo checkout-service?"
- "An image tag v3.1.0 disappeared from our ECR repo yesterday and the ECS service failed to start. Was it the lifecycle policy, and what else is at risk?"
- "Show me, rule by rule, what the lifecycle policy on repo worker keeps and expires."
- "Which images in repo api-gateway have not been pulled in 60 days and would a sinceImagePulled rule be safe?"

The agent reads configuration through its native AWS tooling under the Agent
Space role, runs or simulates the preview, cross references in use sources, and
returns a Markdown report with a verdict for every expiring image.

## Scope boundary versus adjacent skills

- `ecs-operation-review` covers ECS cluster, service and task operational
  posture. This skill reads ECS only to learn which images are referenced.
- `aws-eks-operations-review` covers EKS. This skill records EKS cluster presence
  only and never inspects pods.
- No other skill in this repository reads ECR lifecycle policies. Image push and
  pull authentication, replication, pull through cache and scanning are out of
  scope here and are not covered by this skill.

## Open questions for SME review

1. Preview approval versus simulation only: should the skill keep attempting
   `StartLifecyclePolicyPreview` and ask for approval when the guardrail cancels
   it, or should it ship simulation only and treat the preview as an operator
   step?
2. Is the guardrail classification of `StartLifecyclePolicyPreview` as mutative
   stable across Agent Spaces, and can the platform allowlist it?
3. Should `archive` actions count as deletion risk for the in use verdict, as
   the skill does today?
4. Is a 30 day default pull recency window right for `lastRecordedPullTime`?
5. Is the protected tag pattern set (`^prod`, `^release`, `^v?\d+\.\d+\.\d+`,
   `^latest$`, `^stable$`, `^hotfix`) and the LOW severity appropriate?
6. Is the 200 ARN bound on the ECS ACTIVE task definition scan acceptable?
7. EKS: presence only, or should the skill use the agent's Kubernetes API access
   (`eks:AccessKubernetesApi` is in the managed policy) to read pod image
   references?
8. CloudTrail probe: do `BatchGetImage` and `GetDownloadUrlForLayer` pulls
   appear reliably in `LookupEvents`, and is the `cloudtrail` namespace
   cancelled by the guardrail in your Agent Space?
9. Preview result retention: how long does ECR keep a completed preview before
   it reports `EXPIRED`? The public documentation does not state it.
10. Catalog vocabulary: `Amazon ECR` is not an approved `aws-services` value in
    this repository, so the skill is tagged `Amazon ECS`. Should `Amazon ECR` be
    added?
11. Should cross account consumers (task definitions in other accounts pulling
    this registry) be in scope?
12. Does `PutLifecyclePolicy` reject a policy whose `tagStatus: any` rule does
    not carry the highest `rulePriority` number? The parameters page states the
    requirement but not the rejection behaviour, so check P2 reports a violation
    as INFO rather than assuming an attached policy can never violate it.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
