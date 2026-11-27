# RCA Architectural Anti-Pattern Catalog (DevOps Agent skill)

Read-only, advisory DevOps Agent skill that classifies an account's recurring
incidents and resource topology against a named catalog of architectural
anti-patterns (single point of failure, synchronous coupling, missing
bulkheads, cascade-failure paths, retry storms, shared-fate deployment) and
returns a severity-ranked architectural-debt report in that vocabulary.

**Builds on, does not duplicate, the base agent.** It consumes the DevOps Agent
Topology graph and Proactive Incident Prevention output rather than
re-implementing topology discovery or cross-incident correlation. Its distinct
contribution is the named anti-pattern classification and the architectural-debt
report.

Owner: saadnu-aws.

> **Non-production disclaimer.** Provided for demonstration and evaluation.
> Read-only and advisory — all remediation is proposed, never executed. Apply
> any proposed changes through your own change-management and IaC process. Not
> an AWS service; no warranty.

## Use

Load into a DevOps Agent Agent Space (Chat tasks + Incident RCA). Works best
when the account already has a Topology graph and Proactive Incident Prevention
history for the skill to classify. See `SKILL.md` for the catalog and workflow
and `evals/` for the evaluation scenarios.
