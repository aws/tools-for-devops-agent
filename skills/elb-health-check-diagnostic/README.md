# ELB Health-Check Diagnostic

Read-only DevOps Agent skill that diagnoses why ALB/NLB target-group targets
are unhealthy. It runs a deterministic decision tree, branching on target type
first, over the health-check config, per-target reason codes, security groups,
NACLs, subnet/AZ routability, target resource exhaustion, and
deregistration/cross-zone settings. It then classifies the root cause and
reports the corrected settings for the operator to apply.

Scope: Application and Network Load Balancer target groups only. It is not for
Classic Load Balancers or Gateway Load Balancers.

> **Non-production disclaimer.** Provided for demonstration and evaluation.
> Read-only: it never modifies a security group, NACL, target group, or
> instance. Apply any reported corrections through your own change-management
> and IaC process. Not an AWS service; no warranty.

## Prerequisites

- An AWS DevOps Agent Agent Space with the target account associated.
- The read-only permissions listed in `SKILL.md`. All are covered by
  `AIDevOpsAgentAccessPolicy`.

## Setup

Add the `elb-health-check-diagnostic` folder to your Agent Space as a skill.
It targets the `CHAT` and `INCIDENT_RCA` agent types.

## Sample prompts

- "Target group my-app-tg has an unhealthy target. Diagnose the specific root
  cause and give me the corrected settings."
- "Targets in my-web-tg are failing health checks with Target.Timeout, but the
  security groups and NACLs look correct. What's the root cause?"
- "The Lambda target behind my-lambda-alb shows unhealthy. Why?"

## Cause classes

`HEALTH_CHECK_CONFIG`, `SG_BLOCK`, `NACL_BLOCK`, `ROUTABILITY`,
`RESOURCE_EXHAUSTION`, `GRACE_PERIOD`, `DEPLOYMENT_DRAIN` (timing-inferred),
`DEREGISTRATION_OR_CROSSZONE`, `TARGET_STATE`, `LB_INTERNAL`. See
`references/decision-tree.md` for the corrected setting reported for each.

## Evaluation

`evals/` holds the `skill-eval` structure, best-practices, and functional
results. The functional scenarios cover a security-group block on a split
health-check port, a Lambda target returning a non-200 response, and
CPU-credit exhaustion on one of two burstable targets, plus one negative case.

## Owner

saadnu-aws
