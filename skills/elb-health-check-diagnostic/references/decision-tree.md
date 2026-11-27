# ELB Health-Check Diagnostic — Reference

Lookup material for the steps in `SKILL.md`. Load only the section the
current step points to.

## Resource-exhaustion metrics (Step 5)

Use when the reason is `Target.Timeout` and the health-check config, SG, NACL
and routability checks are all clean — the health check may be timing out
because the target is saturated. Pull target metrics
(`cloudwatch:GetMetricData`) with instance/volume-type awareness so credit
metrics only apply where relevant:

- CPU: `CPUUtilization`; for burstable types `CPUCreditBalance` /
  `CPUSurplusCreditBalance`.
- Network: `NetworkIn/Out`, `NetworkPacketsIn/Out`.
- EBS, by volume type (`ec2:DescribeVolumes`):
  - gp2, st1, sc1: `BurstBalance`.
  - gp3 has no burst balance. Use `VolumeQueueLength` and compare ops and
    throughput with the volume's provisioned IOPS and throughput.
  - `EBSIOBalance%` and `EBSByteBalance%` are instance-level metrics, and only
    for instance types that burst on EBS (`ec2:DescribeInstanceTypes`).
- Memory: not published by default. It needs the CloudWatch agent. If the agent
  is not installed, say memory was not checked.
- For ECS/EKS targets: task/pod-level CPU and `OOMKilled` events, not just host
  metrics. Read ECS stopped reasons with `ecs:DescribeTasks` (exit code 137 or
  "OutOfMemoryError"); EKS needs `eks:Describe*` plus Kubernetes API read access.

**Compare across all targets in the group** — exhaustion is usually isolated to
1–2 targets, while a config/SG issue hits the whole group uniformly. The spread
is itself a classification signal.

**Fix the saturation, not the timeout.** Raising `HealthCheckTimeoutSeconds`
only hides an exhausted target. Lead with the fix for the saturated dimension
(for example, `CpuCredits: unlimited` or a larger instance type), and mention a
timeout change only as a secondary adjustment.

## Cause classes and corrected settings (Step 6)

| Class | What it means | Corrected setting reported |
|---|---|---|
| `HEALTH_CHECK_CONFIG` | HC port/protocol/path/matcher doesn't match the app, or health checks are disabled (`Target.HealthCheckDisabled`) | the port/path/matcher to set, or whether to enable health checks |
| `SG_BLOCK` | Target SG doesn't allow the LB on the HC port | the inbound rule to add (source = LB SG, HC port; for an NLB without security groups, source = the NLB private IPs or VPC CIDR); see the split-port note below |
| `NACL_BLOCK` | A subnet NACL denies the HC port or the ephemeral return path (NACLs are stateless) | the inbound and outbound NACL entries to adjust, on both subnets |
| `ROUTABILITY` | Target AZ not enabled on the LB (`Target.NotInUse`), target group not in a listener rule, or routing gap | AZ/subnet to enable on the LB, listener rule to add, or route to add |
| `RESOURCE_EXHAUSTION` | Target saturated (CPU/net/EBS/OOM) | the saturated dimension + which targets |
| `GRACE_PERIOD` | HC grace too short for app startup | recommended grace seconds |
| `DEPLOYMENT_DRAIN` | Targets fail while a deployment replaces them (`Elb.InitialHealthChecking` after a deploy). **Timing-inferred**, not verified | the ECS/ASG health-check grace period to cover startup, and `deregistration_delay.timeout_seconds` to cover in-flight requests |
| `DEREGISTRATION_OR_CROSSZONE` | Dereg delay / cross-zone tuning causes flapping | the attribute to tune |
| `TARGET_STATE` | Target stopped or terminated, not registered, or its IP is used by a load balancer (`Target.InvalidState`, `Target.NotRegistered`, `Target.IpUnusable`) | the target to start, register, or replace; not a network change |
| `LB_INTERNAL` | `Elb.InternalError`: the failure is on the load balancer side, not the target | none; do not attribute it to the target. Recheck, then open an AWS Support case if it persists |

**Matcher and protocol version.** For HTTP/1.1 and HTTP/2 the matcher takes
HTTP codes 200-499 (default 200) and the path is a URI. For gRPC the matcher
takes status codes 0-99 (default 12) and the path is `/package.service/method`
(default `/AWS.ALB/healthcheck`). A protocol-version mismatch (for example HTTP/2
health checks against an HTTP/1.1-only app) shows up as
`Target.ResponseCodeMismatch` or `Target.Timeout`; check the target group's
protocol version.

**Split health-check port with `SG_BLOCK`.** When the HC port differs from the
traffic port and the target SG only allows the traffic port, the split itself
may be the mistake. Report both fixes and say which one the evidence supports:

1. Set the health check back to `traffic-port`. Lead with this unless you
   observed evidence that the app listens on the HC port (for example, a
   dedicated health endpoint in the app or IaC config).
2. If the HC port is an intentional dedicated port, add the inbound rule
   (source = LB SG, HC port) and confirm the app listens there.
