# Review report format

Use this layout for every Review mode answer. The checks behind each area are in [review-operational.md](review-operational.md). Severity values come from [finding-logic.md](finding-logic.md).

**The Summary table is required, not optional.** Every Review mode response MUST begin with the Summary table, and the table MUST list all six areas (capacity and quota headroom, observability, cost hygiene, resilience, encryption posture, deletion protection) in every response, even when an area has no findings or is `Indeterminate`. Do not open with prose, an offer to run the review, or the first area's detail table. Start with the Summary table, then the per-area tables below it. Do not add, rename, or drop areas, and do not invent ratings; use the six areas and the rating scheme as written.

## Layout

```
# Amazon EBS operational review: account 123456789012, Regions <list>

Scope: read-only. Inventoried <n> volumes, <n> snapshots, <n> alarms, Service Quotas for ebs, in <Regions>, on <date>.

## Summary
| Area | Rating | High | Medium | Low | Indeterminate |
|---|---|---|---|---|---|
| Capacity and quota headroom | ... | | | | |
| Observability | ... | | | | |
| Cost hygiene | ... | | | | |
| Resilience | ... | | | | |
| Encryption posture | ... | | | | |
| Deletion protection | ... | | | | |

## Capacity and quota headroom
| Severity | Resource | Finding | Evidence | Fix | Mutating? |
|---|---|---|---|---|---|

## Observability
(same table)

## Cost hygiene
(same table)

## Resilience
(same table)

## Encryption posture
(same table)

## Deletion protection
(same table)

## Not checked
- <API or area>: <reason> (for example "dlm:GetLifecyclePolicies held behind an approval gate")

## Proposed actions
Numbered list of mutating fixes, each with exact parameters, expected effect, cost direction and rollback. None was executed. Each needs a directed action approved on the approval card. Deletes are not directed actions: list them as manual customer steps that wait for owner confirmation.
```

The area rating is the highest severity of its findings. If every check in an area was unreadable, the rating is `Indeterminate`.

## Pre-render checklist

- The response begins with the Summary table, and the table lists all six areas with a rating for each.
- Every finding has evidence read from an API in this run.
- Throughput is in MiB/s.
- No mutating action was executed.
- No resource ID, price or number was invented. IDs are the ones returned by the APIs.
- The Not checked list names every API that failed or was gated.

## Sources

- Published AWS DevOps Agent skills (rated report pattern, format only): https://github.com/aws/tools-for-devops-agent
- Directed actions and approval: https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-working-with-directed-actions.html
