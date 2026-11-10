---
name: elb-health-check-diagnostic
description: >-
  Diagnose unhealthy targets in an ALB/NLB/ELB target group. Use this skill
  whenever a prompt names a target group, load balancer, or ALB/NLB and says
  targets are unhealthy, health checks are failing, Target.Timeout or another
  target-health reason code appears, an UnHealthyHostCount alarm fires, or the
  load balancer returns 5xx/503 with no healthy targets. This includes EC2,
  IP, Lambda-target, ECS, and EKS targets, and intermittent health-check
  failures where security groups and NACLs already look correct. The skill
  runs a deterministic, read-only decision tree over the target group's health
  check config, per-target reason codes, security groups, NACLs, subnet/AZ
  routability, target resource utilization, and deregistration/cross-zone
  settings, then classifies the specific root cause and emits the corrected
  values. Read-only: it never modifies a security group, target group, or
  instance.
metadata:
  author: saadnu-aws
  version: "1.0.0"
  summary: "Read-only root-cause diagnosis for unhealthy ALB/NLB targets: classifies SG, NACL, health-check config, routability, or resource exhaustion and reports the fix."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "Elastic Load Balancing, Amazon EC2, AWS Lambda, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Networking, Operations"
---

# ELB Health-Check Diagnostic

Diagnose why ALB/NLB target-group targets are unhealthy and return the specific
corrected settings. The base agent can call the ELB APIs but has no ELB-specific
decision tree, so its answers vary run to run and routinely miss the
security-group / health-check-config interplay that causes most of these cases.
This skill encodes that tree deterministically.

> **Read-only.** This skill reads configuration and metrics and classifies the
> cause. It never modifies a security group, NACL, target group, or instance.
> Corrected values are reported for the operator to apply via their IaC.

## When to Use This Skill

- One or more targets in an ALB/NLB target group are `unhealthy`.
- An `UnHealthyHostCount` CloudWatch alarm is in ALARM.
- A load balancer returns 5xx with no healthy targets.

## Prerequisites

Read-only permissions (all covered by `AIDevOpsAgentAccessPolicy`):

- `elasticloadbalancing:DescribeTargetGroups`, `DescribeTargetHealth`,
  `DescribeTargetGroupAttributes`, `DescribeLoadBalancerAttributes`,
  `DescribeListeners`
- `ec2:DescribeSecurityGroups`, `DescribeNetworkAcls`, `DescribeSubnets`,
  `DescribeRouteTables`, `DescribeInstances`
- `cloudwatch:GetMetricData`

## Workflow

Target groups can point to EC2 instances, IPs, Lambda, or ECS awsvpc tasks, and
the network-path semantics differ (Lambda targets have no target-side SG; ECS
awsvpc tasks have per-task ENIs). **Branch on target type before any SG/NACL
logic.**

Copy this checklist and work through it in order:

- [ ] Step 1: Run `DescribeTargetHealth` and read each target's State + Reason code.
- [ ] Step 2: Branch on target type (instance | ip | lambda | ecs-awsvpc).
- [ ] Step 3: Route by reason code:
  - `Target.ResponseCodeMismatch` -> app returns non-200 on the HC path -> `HEALTH_CHECK_CONFIG` (path/matcher). Go to Step 6.
  - `Elb.InitialHealthChecking` + recent deploy -> `GRACE_PERIOD` or `DEPLOYMENT_DRAIN` (timing-inferred; see Notes). Go to Step 6.
  - `Target.DeregistrationInProgress` / flapping during deploys -> `DEREGISTRATION_OR_CROSSZONE` (`DescribeTargetGroupAttributes` / `DescribeLoadBalancerAttributes`). Go to Step 6.
  - `Target.Timeout` / `Target.FailedHealthChecks` -> continue to Step 4.
- [ ] Step 4: Check the network path, stopping at the first failure:
  - Health-check port/protocol/path vs. the app's actual listener. Mismatch -> `HEALTH_CHECK_CONFIG`.
  - ALB-outbound and target-inbound SG rules on the HC port. Target SG missing the HC port -> `SG_BLOCK`. If the HC port differs from the traffic port, report both fixes (see Step 6).
  - NACLs on the target subnet(s) for the HC port -> `NACL_BLOCK`.
  - Subnet/AZ routability (target subnet enabled on the LB; route tables) -> `ROUTABILITY`.
- [ ] Step 5: If Step 4 is all clean, check target resource exhaustion -> `RESOURCE_EXHAUSTION`. Check CPU, network, and EBS burst metrics even when one dimension is already obviously exhausted, and report which were ruled out. Load the metric list in [references/decision-tree.md](references/decision-tree.md#resource-exhaustion-metrics-step-5) only when you reach this step.
- [ ] Step 6: Map the cause class to its corrected setting using the table in [references/decision-tree.md](references/decision-tree.md#cause-classes-and-corrected-settings-step-6).
- [ ] Step 7: Validate before presenting: confirm the evidence for the chosen class was actually observed (a specific rule, reason code, or metric), not assumed; if a permission gap blocked a check, say which and scope the conclusion.
- [ ] Step 8: Report the cause class, affected targets, evidence, and the corrected setting for the operator to apply via IaC. Never apply it.

## Trigger path

On-demand (request-time) by default. When wired to an `UnHealthyHostCount`
alarm via EventBridge, it runs on the ALARM transition. Declare which mode is
in use in the investigation output.

## Notes and deferred items

- **Deployment correlation** is timing-inferred unless a read-only pull of
  ECS/ASG/CodeDeploy deployment events is available; the output labels the
  "deployment drain" bucket as inferred rather than verified.
- **VPC Reachability Analyzer** (an active path test for cases where static SG
  rules look correct but traffic still fails) is a fast-follow, pending a
  cost/latency and permission review — not part of v1.

## Scope — what this skill does NOT do

- Does not modify security groups, NACLs, target groups, or instances.
- Does not restart or replace targets.
- Does not run active path tests in v1 (Reachability Analyzer deferred).
