# Report Format

Use this structure for every answer, in chat and in investigations. Keep the
headings and their order. Substitute the values in angle brackets. Leave out
a section only where this template says it's optional. In an investigation,
put the same content in the root cause, findings and mitigation.

## Template

```markdown
## Is EBS the cause?

**<Yes | No | Partly | Not confirmed>.** <One sentence: the primary cause, the volume or the
instance, and the time it started.>

## Cause

<The fixed wording of the primary finding from references/finding-logic.md.>

<Contributing findings, if any, one line each.>

## Evidence

| Time (UTC) | Resource | Signal | Value |
|---|---|---|---|
| <hh:mm> | <volume-id or instance-id> | <metric, status or event> | <value, before -> after> |

## Ruled out

| Check | Result |
|---|---|
| Volume limits | <ruled out with values, or the finding> |
| Instance EBS limit | <...> |
| Stall and status checks | <...> |
| Changes in the account (CloudTrail, AWS FIS) | <...> |
| Volume modification | <...> |
| Snapshot initialization | <...> |
| AWS Health | <hand-off result, or "not available: the Health API needs a Business Support+, Enterprise Support or Unified Operations plan"> |

## Changes in the window

<Every mutating CloudTrail event on the instance and its volumes, with time,
event, caller and target. Write "None" if there were none.>

## What to do

1. <The fix from the primary finding.>
2. <Next steps, alarms to add.>

## Support case draft

<Only for F2, F3 or F9 with no account-side cause. Otherwise leave this
section out.>

## Data gaps

<Calls denied, metrics not published, missing OS data, and how each one limits
the conclusion. Write "None" if there were none.>
```

## Support case draft

When the primary finding is F2, F3 or F9 and no account change explains it,
include a draft the user can paste, and hand off to the `support-cases` skill.
Open the case only if the user asks.

```markdown
Subject: EBS volume <volume-id> <stalled | I/O disabled | degraded> on <instance-id> since <start time UTC>

Region and Availability Zone: <region>, <az>
Instance: <instance-id> (<instance-type>)
Volume: <volume-id> (<type>, <size> GiB, <IOPS>, <throughput>), device <device>
Start: <time UTC>. End: <time UTC, or "ongoing">
Volume status: <status and details>, event <event-id> "<description>" from <NotBefore>
Attached EBS status check: <status> since <ImpairedSince>
Metrics: <VolumeStalledIOCheck, ops, queue length, latency with times>
Changes in the window: <none, or the list>
Impact: <what the application sees>
Already done: <waited N minutes, stop and start, and so on>
```

## Pre-send checks

Run these before sending. Fix any that fail.

1. The first line answers "Is EBS the cause?" with Yes, No, Partly or Not
   confirmed, as mapped from the primary finding in
   `references/finding-logic.md`: Partly for F1 and F4, No for F10, Not
   confirmed when no finding is confirmed, Yes for the rest.
2. Every number in Cause and Evidence comes from collected data, with its time.
3. The primary cause follows the priority order in `references/finding-logic.md`.
4. Any change named as the cause happened before the problem started and can
   explain the symptom.
5. No metric with empty results is described as 0, healthy or "no stall".
6. If IOPS fell while latency rose, the answer doesn't say demand fell.
7. If several volumes slowed at the same time, the instance EBS limit was
   checked.
8. The fix doesn't recommend adding volumes or raising volume limits for an
   instance limit.
9. No force-detach, and no detach or reattach while I/O is stuck.
10. No offer to run a change. Fixes are recommendations.
11. A support case is drafted only for F2, F3 or F9 with no account-side cause.
12. Every data gap is listed.
13. No tag or name is used as evidence of the cause.
14. No finding code (F1 to F10) or skill file name appears in the answer.
15. The latency before and after `T0` is given with values. For a volume or
    instance limit, the answer says the application waits longer than
    CloudWatch shows.
16. For a volume or instance limit, the fix is sized above the value
    observed at the limit, and the answer says real demand may be higher.
17. AWS Health was checked, or the reason it couldn't be is listed as a data
    gap.
18. Every statement about another volume (idle, busy, healthy) matches that
    volume's own metrics and status.
19. For an AWS FIS experiment, the end time is the action's start plus its
    duration.
20. The answer uses the headings above, in this order, in chat and in
    investigations.
