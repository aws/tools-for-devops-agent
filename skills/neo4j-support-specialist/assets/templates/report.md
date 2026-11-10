# Neo4j diagnosis: {{target}}

| | |
| --- | --- |
| Platform | {{EKS cluster/namespace/release, ECS cluster/service, or EC2 instances}} |
| Neo4j | {{version and edition, from image tag or package}}, {{standalone or cluster of N}} |
| Window | {{start}} to {{end}} (UTC) |
| Trigger | {{alarm, webhook or request, one line}} |
| Overall | {{✅ no problem found in the evidence read, ⚠️ risk or partial evidence, or ❌ confirmed problem}} |

## Summary

{{Two to four sentences: what is wrong, how sure, what to do first.}}

## Findings

{{At most 5, highest severity first. Repeat this block per finding.}}

### {{P0 to P4}} {{❌ or ⚠️}} {{Short title}} ({{runbook issue, for example A1.1}})

- Evidence: `{{exact quoted line or field}}` from {{pod/task, log group or API}} at {{timestamp}}
- Cause: {{one or two sentences}}
- Impact: {{who or what is affected}}
- Reference: {{runbook issue}}

## Checked and fine

- ✅ {{check}}: {{evidence}}

## Evidence not available

| Source | Why not | What it would have answered |
| --- | --- | --- |
| {{for example debug.log}} | {{not shipped to CloudWatch Logs}} | {{database state, recovery, GC pauses}} |

## Recommendations

{{At most 5, in order. Each names the change, where it's made, and the finding it fixes.}}

1. {{action}}. Fixes {{finding}}.

## Operator commands

Run these and attach the output to the incident so a later run can use it.

```text
{{commands from operator-queries.md with names filled in}}
```

## Next steps

- {{what happens next, who does it}}

## For Neo4j Support

{{Only when a case is likely. From runbook A11.1: what was read, what to collect from each server.}}
