# Required Permissions for ECR Lifecycle Guard

Load this file when a source returns `AccessDenied`, when the operator asks what
to grant, or when preparing a skill evaluation run. The skill is read only and
control plane only; every action below is a read.

Managed policy column is `AIDevOpsAgentAccessPolicy` v11, verified 2026-10-26 at
https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html.

## IAM actions

| IAM action | In managed policy | Used for |
|---|---|---|
| `ecr:DescribeRepositories`, `ecr:DescribeImages` | Yes (`ecr:Describe*`) | Image set, tags, push time, `lastRecordedPullTime`, multi repo inventory |
| `ecr:GetLifecyclePolicy` | Yes | The attached policy text and `lastEvaluatedAt` |
| `ecr:StartLifecyclePolicyPreview` | **No** | Ask ECR to evaluate the policy (authoritative path) |
| `ecr:GetLifecyclePolicyPreview` | **No** | Read the preview result |
| `ecs:List*`, `ecs:Describe*` | Yes | Running tasks, services, ACTIVE task definitions |
| `batch:DescribeJobDefinitions` | **No** | ACTIVE job definition images |
| `lambda:ListFunctions` | Yes (`lambda:List*`) | Find `PackageType=Image` functions |
| `lambda:GetFunction` | **No** | `Code.ImageUri` and `Code.ResolvedImageUri` |
| `apprunner:ListServices`, `apprunner:DescribeService` | Yes | Service image identifiers |
| `eks:ListClusters` | Yes (`eks:List*`) | Cluster presence only |
| `cloudtrail:LookupEvents` | Yes, optional | Direct pull evidence, may be cancelled by the guardrail |
| `ec2:DescribeRegions` | Yes (`ec2:Describe*`) | Only for "all Regions" requests |
| `sts:GetCallerIdentity` | No IAM needed | Account id |

The four actions marked **No** are the delta the operator grants. The README
carries the inline policy JSON and the CloudFormation parameter. The skill runs
without them: the expiring set falls back to `SIMULATED`, and Batch and Lambda
become `AccessDenied` sources that push unreferenced images to `Expiring-Unknown`.

## Preview approval

`StartLifecyclePolicyPreview` is classified as a write action in the AWS service
reference for ECR, so the agent's tool policy may cancel it with a message like
`Cancelled mutative operation: ecr StartLifecyclePolicyPreview. This operation
requires an operator approval to execute.` The call computes which images the
policy would act on and changes no image, tag, policy or repository setting. It
is safe to approve. When cancelled: explain this once in one short paragraph,
ask for approval, and if it is not given continue with the simulation. Never
block the review waiting for approval, and never ask more than once per run.

## Skill evaluation tool

When running the skill evaluation tool, pass the four delta actions with
`--additional-permissions-file`; the README has the JSON.
