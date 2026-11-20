---
name: elb-health-check-diagnostic
description: >-
  Diagnose unhealthy targets in an Application Load Balancer (ALB) or Network
  Load Balancer (NLB) target group. Use this skill whenever a prompt names an
  ALB/NLB target group and says targets are unhealthy, health checks are
  failing, Target.Timeout or another target-health reason code appears, or the
  load balancer returns 5xx/503 with no healthy targets. Also use it when an
  investigation starts from an UnHealthyHostCount alarm in the
  AWS/ApplicationELB or AWS/NetworkELB namespace. This includes EC2, IP,
  Lambda, ECS, and EKS targets, and intermittent health-check failures where
  security groups and NACLs already look correct. The skill runs a
  deterministic, read-only decision tree over the target group's health check
  config, per-target reason codes, security groups, NACLs, subnet/AZ
  routability, target resource utilization, and deregistration/cross-zone
  settings, then classifies the specific root cause and emits the corrected
  values. Not for Classic Load Balancers (AWS/ELB namespace) or Gateway Load
  Balancers (AWS/GatewayELB namespace). Read-only: it never modifies a
  security group, target group, or instance.
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

- One or more targets in an ALB/NLB target group are `unhealthy`, `unused`, or
  `unavailable`.
- An investigation starts from an `UnHealthyHostCount` alarm in the
  `AWS/ApplicationELB` or `AWS/NetworkELB` namespace. The skill does not set up
  the alarm or any EventBridge rule itself.
- A load balancer returns 5xx. Read the ALB fail-open note in Step 1 first.

Not for Classic Load Balancers or Gateway Load Balancers. See Gotchas.

## Prerequisites

Read-only permissions, all covered by `AIDevOpsAgentAccessPolicy` through its
`Describe*`/`List*` wildcards and the listed `Get*` actions:

- ELB: `elasticloadbalancing:DescribeTargetGroups`, `DescribeTargetHealth`,
  `DescribeTargetGroupAttributes`, `DescribeLoadBalancers` (LB security groups,
  enabled AZs and subnets), `DescribeLoadBalancerAttributes`,
  `DescribeListeners`, `DescribeRules`
- EC2: `ec2:DescribeSecurityGroups`, `DescribeNetworkAcls`, `DescribeSubnets`,
  `DescribeRouteTables`, `DescribeInstances`, `DescribeNetworkInterfaces` (IP
  and ECS awsvpc targets), `DescribeVolumes`, `DescribeInstanceTypes`
- CloudWatch: `cloudwatch:GetMetricData`
- ECS/EKS/Auto Scaling, only for those target types: `ecs:DescribeTasks`,
  `ecs:DescribeServices`, `autoscaling:DescribeAutoScalingGroups`, `eks:Describe*`
- Lambda targets: `lambda:GetPolicy`

If a call is denied, say which check it blocked and scope the conclusion.

## Workflow

Target groups can point to EC2 instances, IPs, Lambda, or ECS awsvpc tasks, and
the network-path semantics differ (Lambda targets have no target-side SG; ECS
awsvpc tasks have per-task ENIs). **Branch on target type before any SG/NACL
logic.**

Copy this checklist and work through it in order:

- [ ] Step 1: Run `DescribeTargetHealth` and read each target's State + Reason code.
  - **ALB fail-open.** If every target in the group is unhealthy, the ALB routes
    to all of them anyway. A 5xx with "no healthy targets" may therefore be the
    application failing, not a routing gap. Check target health and application
    errors before assuming the load balancer rejects requests.
- [ ] Step 2: Branch on target type (instance | ip | lambda | ecs-awsvpc).
  - **Lambda:** no target SG or NACL. Check the function's resource policy
    (`lambda:GetPolicy`) allows `elasticloadbalancing.amazonaws.com` to invoke
    it, and check the `Errors` and `Throttles` metrics. The default
    health-check timeout is 30 seconds.
  - **IP / ECS awsvpc:** find the target ENI with `ec2:DescribeNetworkInterfaces`
    to get its security groups. `DescribeInstances` only covers instance targets.
- [ ] Step 3: Route by state and reason code:
  - `Target.ResponseCodeMismatch` -> app returns a code outside the matcher on the HC path -> `HEALTH_CHECK_CONFIG` (path/matcher). Go to Step 6.
  - `Elb.InitialHealthChecking` + recent deploy -> `GRACE_PERIOD` or `DEPLOYMENT_DRAIN` (timing-inferred; see Notes). Go to Step 6.
  - `Target.DeregistrationInProgress` / flapping during deploys -> `DEREGISTRATION_OR_CROSSZONE` (`DescribeTargetGroupAttributes` / `DescribeLoadBalancerAttributes`). Go to Step 6.
  - `Target.Timeout` / `Target.FailedHealthChecks` -> continue to Step 4.
  - `unused` / `Target.NotInUse` -> either the target's AZ is not enabled on the LB, or the target group is not referenced by a listener rule. Compare the target's AZ with `DescribeLoadBalancers` and check `DescribeRules`. Class `ROUTABILITY`. Skip Step 4 and go to Step 6.
  - `unused` / `Target.InvalidState`, `Target.NotRegistered`, `Target.IpUnusable` -> the target is stopped or terminated, not registered, or its IP belongs to a load balancer. Not a network cause. Class `TARGET_STATE`. Report the observed state. Go to Step 6.
  - `unavailable` / `Target.HealthCheckDisabled` -> health checks are off for the target group (the default for Lambda target groups). This is not a failure. Class `HEALTH_CHECK_CONFIG`; report whether that is intended. Go to Step 6.
  - `Elb.InternalError` -> the failure is on the load balancer side. Do not attribute it to the target. Class `LB_INTERNAL`. Go to Step 6.
- [ ] Step 4: Check the network path, stopping at the first failure:
  - Health-check port/protocol/path vs. the app's actual listener. Mismatch -> `HEALTH_CHECK_CONFIG`.
  - Security groups on the HC port. Use `DescribeLoadBalancers` to see the LB's security groups.
    - ALB, or NLB with security groups: the target SG must allow the HC port from the LB SG. Missing -> `SG_BLOCK`.
    - NLB without security groups: the target SG must allow the HC port from the NLB's private IPs or the VPC CIDR. Missing -> `SG_BLOCK`.
    - If the HC port differs from the traffic port, report both fixes (see Step 6).
  - NACLs are stateless, so check both directions on both subnets. Missing -> `NACL_BLOCK`.
    - Target subnet NACL: inbound on the HC port from the LB subnets, and outbound ephemeral ports (1024-65535) back to them.
    - LB subnet NACL: the reverse (outbound to the HC port, inbound ephemeral ports from the target subnets).
  - Subnet/AZ routability (target subnet enabled on the LB via `DescribeLoadBalancers`; route tables) -> `ROUTABILITY`.
- [ ] Step 5: If Step 4 is all clean, check target resource exhaustion -> `RESOURCE_EXHAUSTION`. Check CPU, network, and EBS burst metrics even when one dimension is already obviously exhausted, and report which were ruled out. Load the metric list in [references/decision-tree.md](references/decision-tree.md#resource-exhaustion-metrics-step-5) only when you reach this step.
- [ ] Step 6: Map the cause class to its corrected setting using the table in [references/decision-tree.md](references/decision-tree.md#cause-classes-and-corrected-settings-step-6).
- [ ] Step 7: Validate before presenting: confirm the evidence for the chosen class was actually observed (a specific rule, reason code, or metric), not assumed; if a permission gap blocked a check, say which and scope the conclusion.
- [ ] Step 8: Report the cause class, affected targets, evidence, and the corrected setting for the operator to apply via IaC. Never apply it.

## Gotchas

- **Not for Classic Load Balancers or Gateway Load Balancers.** Classic Load
  Balancers (`AWS/ELB`) have no target groups or ELBv2 reason codes. Gateway
  Load Balancer target groups (`AWS/GatewayELB`) differ: no LB security group,
  a default TCP:80 health check, GENEVE on UDP 6081, and traffic is dropped
  instead of failing open. If the prompt describes either, say the skill does
  not apply and stop.
- **Lambda targets have no target-side security group.** Do not apply SG or
  NACL logic to them.
- **ECS awsvpc tasks have one ENI per task.** Read the SG from the task ENI.
- **Target groups have no grace period.** Read it from the ECS service
  (`ecs:DescribeServices`, `healthCheckGracePeriodSeconds`) or the Auto Scaling
  group (`autoscaling:DescribeAutoScalingGroups`, `HealthCheckGracePeriod`).
- **Deployment correlation is timing-inferred.** Label `DEPLOYMENT_DRAIN` as
  inferred unless deployment events were actually read.
- **NACLs are stateless.** A missing ephemeral-port return rule looks like a
  timeout with clean security groups.

## Notes and deferred items

- **VPC Reachability Analyzer** (an active path test for cases where static SG
  rules look correct but traffic still fails) is a fast-follow, pending a
  cost/latency and permission review. It is not part of v1.
- **Gateway Load Balancer support** (GENEVE reachability, `target_failover`,
  appliance health) is a follow-up skill, not part of this one.

## Scope — what this skill does NOT do

- Does not modify security groups, NACLs, target groups, or instances.
- Does not restart or replace targets.
- Does not diagnose Classic Load Balancers or Gateway Load Balancers.
- Does not run active path tests in v1 (Reachability Analyzer deferred).
