# Changelog

## 1.0.0

- Initial version: read-only Systems Manager review with one section per capability. Automation review: failed, timed-out and cancelled executions, rate-control and alarm settings on multi-target runs, account-owned runbook findings, and AWS-owned alternatives for recurring failures.
- Review round 2: a preflight step verifies `use_aws` with one read call before the reviews start (a missing tool now produces the blocked report and Recommendation in seconds), and the reviews run in-session rather than in subagents, which don't inherit tools.
- Review round 3: multi-account parents are inspected per location with `get-automation-execution` (optional read-only `ssm:GetAutomationExecution`; denied access or a `TargetLocationsURL`-only execution reports those checks as Not checked), and the absolute `MaxConcurrency` comparison honours `ResolvedTargets.Truncated` and incomplete child queues.
- Review round 4: the preflight resolves the Region scope first and stops only when the `use_aws` tool itself is unavailable; a failed API call follows the normal retry and Not-checked rules. The optional `ssm:GetAutomationExecution` grant is provisioned by the `EnableSsmAutomationExecutionRead` parameter of the skill-policies CloudFormation template.
