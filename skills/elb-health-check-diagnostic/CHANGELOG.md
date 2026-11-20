# Changelog

## 1.0.0

- Initial release. Read-only ELB/ALB/NLB target-health diagnostic with a
  deterministic decision tree that branches on target type first.
- Covers health-check config, SG/NACL blocks, subnet/AZ routability, target
  resource exhaustion (CPU/credits, network, EBS, ECS/EKS OOM, compared across
  targets), and deregistration/cross-zone tuning.
- When the health-check port differs from the traffic port, reports both fixes
  and leads with reverting to `traffic-port` unless the app is shown to listen
  on the health-check port.
- In the resource-exhaustion branch, checks CPU, network, and EBS even when
  one dimension is clearly exhausted, and fixes the saturation rather than the
  health-check timeout.
- Routes every target-health reason code, including `Target.NotInUse`,
  `Target.InvalidState`, `Target.NotRegistered`, `Target.IpUnusable`,
  `Target.HealthCheckDisabled` and `Elb.InternalError`.
- Handles NLBs without security groups, stateless NACL return paths, IP and ECS
  awsvpc targets, Lambda invoke permission, and ALB fail-open.
- Scope is ALB/NLB only. Classic and Gateway Load Balancers are excluded.
- Deployment correlation is timing-inferred. VPC Reachability Analyzer is a
  planned follow-up.
