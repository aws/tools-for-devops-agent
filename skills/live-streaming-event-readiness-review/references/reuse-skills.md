# LSE Readiness — reuse map

This skill is an orchestrator. It owns the LSE-specific checklist and the
cross-pillar risk view, and delegates per-service depth to the skills below.
Invoke the reuse skill, then fold its PASS/FAIL findings into the matching rows
here — cite it, don't duplicate its full report. If a reuse skill is not
installed in the Agent Space, grade the row from `discovery.md` evidence and note
that the deeper review was not available.

| Reuse skill | Covers | Pillars / IDs it feeds | How to use it here |
|---|---|---|---|
| `service-quota-check` | AWS service quota values, utilization, increase history | **QTA1–QTA5**, NET (NAT/EIP quotas), CAP5 (Lambda concurrency vs quota) | Authoritative source for every quota value — never guess limits. Pull increase-request history to confirm early submissions are *granted*, not pending. |
| `aws-eks-operations-review` | EKS graded review — Karpenter/diversification, PDBs, control plane, scalability, resilience | **CAP1, CAP3, CAP4, CAP7**, RES3/RES5 (EKS workloads) | When the critical path runs on EKS, run it and fold its Scalability/Resilience/Control-Plane findings into CAP/RES. Heavyweight — run once, reuse evidence. |
| `ecs-operation-review` | ECS/Fargate operational review | CAP1, CAP7 (ECS capacity providers), RES3/RES5 (ECS) | ECS-based critical path — fold capacity-provider diversification and isolation findings into CAP/RES. |
| `rds-operation-review` | RDS/Aurora configuration, replicas, resilience | **DAT3**, RES5 | For relational state on the critical path — read-replica scaling and Multi-AZ posture feed DAT3. |
| `msk-operations` | MSK cluster operations | OBS/DAT if MSK is the telemetry/eventing backbone | Only if MSK carries event-critical messaging or telemetry. |
| `aws-health-events` | Scheduled changes / maintenance events | **RES6** | Preferred source for maintenance-overlap detection; check every event-critical service's Region against the event window. |
| `eks-upgrade-readiness` | EKS version lifecycle / upgrade safety | **RES7**, SUP3 | For an EKS cluster near end of standard support — assess upgrade readiness so a forced auto-upgrade doesn't land in the freeze/event window. |
| `support-cases` | Open AWS support cases | SUP context, residual-risk flags | Surface open cases on event-critical services near the event window. |
| `investigation-cost-guardrail` | Keeps read volume/cost bounded | whole review | Apply during discovery so a large multi-service, multi-Region review stays cheap. |
| `eks-upgrade-readiness` | EKS upgrade safety | SUP3 (change freeze) | If an EKS upgrade is pending near the event, a mid-window upgrade violates the change freeze — flag it. |

## Ordering

1. `investigation-cost-guardrail` (wrap the whole review).
2. `service-quota-check` early — quota ceilings gate CAP and NET conclusions.
3. `aws-eks-operations-review` / `ecs-operation-review` / `rds-operation-review`
   for whichever carries the critical path.
4. `aws-health-events` and `support-cases` for RES6 and residual-risk context.

## Boundaries

- These reuse skills provide **depth**; this skill provides the **event lens** —
  it reframes their generic findings in terms of viewer impact at peak and the
  weeks-to-event timeline.
- Do not let a reuse skill's own report format override this skill's report
  contract (SKILL.md §S6). Extract findings; render once here.
