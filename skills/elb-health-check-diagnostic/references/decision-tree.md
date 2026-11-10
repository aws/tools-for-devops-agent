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
- EBS (gp2/gp3 burst): `EBSIOBalance%`, `BurstBalance`, `VolumeQueueLength`.
- For ECS/EKS targets: task/pod-level CPU and `OOMKilled` events, not just host
  metrics.

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
| `HEALTH_CHECK_CONFIG` | HC port/protocol/path/matcher doesn't match the app | the port/path/matcher to set |
| `SG_BLOCK` | Target SG doesn't allow the LB on the HC port | the inbound rule to add (source = LB SG, HC port); see the split-port note below |
| `NACL_BLOCK` | Subnet NACL denies the HC port | the NACL entry to adjust |
| `ROUTABILITY` | Target subnet/AZ not enabled on the LB, or routing gap | subnet to enable / route to add |
| `RESOURCE_EXHAUSTION` | Target saturated (CPU/net/EBS/OOM) | the saturated dimension + which targets |
| `GRACE_PERIOD` | HC grace too short for app startup | recommended grace seconds |
| `DEREGISTRATION_OR_CROSSZONE` | Dereg delay / cross-zone tuning causes flapping | the attribute to tune |

**Split health-check port with `SG_BLOCK`.** When the HC port differs from the
traffic port and the target SG only allows the traffic port, the split itself
may be the mistake. Report both fixes and say which one the evidence supports:

1. Set the health check back to `traffic-port`. Lead with this unless you
   observed evidence that the app listens on the HC port (for example, a
   dedicated health endpoint in the app or IaC config).
2. If the HC port is an intentional dedicated port, add the inbound rule
   (source = LB SG, HC port) and confirm the app listens there.
