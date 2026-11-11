# Notes on `iam-policy.json`

Attach the policy to the IAM role associated with your DevOps Agent Agent Space.

## Before applying

Replace `REGION` with the region your AWS Batch resources run in, or remove the
`Condition` block entirely to allow all regions.

The policy is deliberately a **plain IAM policy document** with no explanatory keys.
IAM rejects a policy containing any top-level element other than `Version`, `Id` and
`Statement` with `MalformedPolicyDocument`, so these notes live here instead of inline.

## Why two statements

They are split so you can grant the first alone.

`BatchSilentFailureDetection` is sufficient for the highest-value check in this skill —
scanning a queue for jobs that reported `SUCCEEDED` while `container.reason` or
`statusReason` shows the work was cut short. Both fields are on the `ListJobs` summary, so
no per-job `DescribeJobs` call is needed.

`BatchCapacityAndJobConfigInvestigation` adds the compute-environment and job-configuration
steps: ASG launch-failure diagnosis, the `MaxSize` 0 check that shows Batch never requested
capacity from a later compute environment, resolved container commands, and the
`retryStrategy` / `evaluateOnExit` effective-attempts check.

If you grant only the first statement, the skill still works — it will report the capacity
and retry checks as unavailable rather than guessing.

## Unverified

Whether `batch:DescribeJobs` supports resource-level ARNs. The AWS Service Authorization
Reference page did not render for automated retrieval at time of writing, so this is
recorded as unverified rather than asserted.

`Resource: "*"` narrowed by `aws:RequestedRegion` is the correct practical scoping either
way: job IDs are unpredictable, so a monitoring role cannot enumerate future job ARNs.

## Not included, deliberately

- `batch:DescribeJobDefinitions`
- `logs:GetLogEvents` on `/aws/batch/job`

Both were observed as real gaps during investigations — the first would settle whether an
invalid container command comes from the job definition or a submit-time override, the
second would confirm the container's own error output. They are left out so an operator
grants them against evidence rather than pre-emptively.
