# Delegation and output shape

Read this before you delegate any collection to a subagent, and before you write the first reply of a
review. It fixes three things: when the findings are delivered, what a finding row looks like, and what
a delegation prompt must carry.

## 1. One reply carries the review
The user, and any grader, may see only the first message that ends a turn. Status text holds no
findings. Live runs showed the platform closing a turn on every subagent completion. Closing text
that was empty cost nothing. Closing text such as "Still waiting on the Lambda slice" became the
graded reply. Runs that collected inline produced one reply.

### Mode: decide from counts, in your notes
Write one line before any deep collection, using the Step 2 inventory counts:
`inventory: functions=N tables=N apis=N machines=N mappings=N -> mode: inline | delegate(<why>)`
- Inline when functions <= 40 and every other family <= 25. Example: 30 functions, 3 tables and
  2 APIs is an inline review. A broad prompt ("how healthy is my serverless workload") is not a reason
  to delegate.
- Delegate only above those counts. Use one subagent per family. Never delegate a slice you also
  collect yourself.
- Do not call `subagent` until the inventory line exists.

### Wake-up rule (only if you delegated)
1. Launch all subagents in one batch. After the launch, write no text.
2. A turn that starts with "The background Task subagent ... completed" while other subagents are
   still pending writes no text at all. Not "waiting", not partial findings. Make the next tool call
   (for example read the next `references/checks-*.md`) or end the turn empty.
3. Only the turn in which the last subagent has completed writes the review.
4. Put the full scope, caps and slice rows in the launch prompt body. Do not rely on
   `preloaded_skills` alone.
5. If a subagent returns nothing usable, name the missing slice in the final reply. Do not report it
   healthy.

### Required reply shape
The reply begins with the literal heading below. Text that does not begin with it is not sent.
```
# Serverless health review: <region>
## Scope and budget
<regions, families, selection rule, caps, inventory table>
## Findings
<finding table from section 2, ordered by severity>
## Could not check
<check families not run and why, with the three states from section 3>
## Recommendations
<ordered actions with remediation snippets>
```
## 2. Finding table

Every finding is one row with these columns. The chat reply and the report artifact use the same
columns.

| Check id | Severity | Observed value | Source API | Doc or threshold source |
|---|---|---|---|---|
| SLS-SQS-002 | CRITICAL | queue `orders-q` `VisibilityTimeout` 30 s, consumer `order-worker` `Timeout` 60 s | `sqs.GetQueueAttributes`, `lambda.GetFunctionConfiguration` | Lambda best practices, SQS visibility timeout |

Rules:

- An observation without a check id is context, not a finding. Put it under a "Context" heading and
  keep it out of the severity counts, the verdict and the priority matrix.
- Take the check id, severity and threshold source from the catalog row. Do not paraphrase the id.
- Name the resource in the observed value, with the number that triggered the check.
- Add a recommendation and a remediation snippet after the table or as extra columns. Order rows by
  severity, then by blast radius, and state that basis in one line above the table.
- For an alarm-coverage or silent-failure question, add two columns: "Why it goes unnoticed" and
  "Absent control" (for example no DLQ, no `OnFailure` destination, no alarm on `IteratorAge`). Give
  each resource its own row.
- Never print a 12-digit AWS account ID. Identify the account by alias or its last four digits.

## 3. Keep three states apart

| State | Meaning | How to report |
|---|---|---|
| Measured zero | The API returned a datapoint of 0 | A real value. State it, for example "Throttles 0 over 7 days" |
| No datapoints | The call succeeded and returned no data | Say the metric emitted nothing in the window. Not a pass, and not a failure unless the check says so |
| Never queried | The call was not made, was denied, or the tool was unavailable | Name the check family and the reason in Scope Covered. Never show it as passing |

## 4. Delegation prompt

Subagents do not see this skill. A prompt that omits the rubric comes back with descriptive severities
and no check ids. Every collection prompt must carry, pasted in full:

1. The catalog rows (check id, severity, detection rule, source) for the slice from the matching
   `references/checks-*.md` file.
2. The severity table from SKILL.md.
3. The finding table columns from section 2 and the three states from section 3.
4. The scope and budget from Step 1, and the read-only rule.
5. A request to return one table row per finding, each with its check id.

Copyable block:

```
Read-only review of <family> in <region>, scope: <scope and caps>.
Return one table row per finding with columns: check id, severity, observed value, source API,
doc or threshold source. An observation with no check id is context, not a finding.
Use only these checks and severities: <paste catalog rows>.
Severity scale: CRITICAL, HIGH, MEDIUM, LOW, INFO (<paste severity table>).
Report measured zero, no datapoints and never queried as three different states.
Never call a mutating API. Report environment variables by key name only. Never print a
12-digit account ID.
```

When you list skills for a collection subagent, include `serverless-operation-review`.

## 5. Caller re-attaches ids

Before the final answer, check every row a subagent returned. If a row has no check id, match it to
the catalog row that fits, add the id and catalog severity, and say when you changed a severity. If no
catalog row fits, move the observation to Context. State in the answer that you re-attached ids.

## 6. Tools unavailable

If tool calls fail across the board (for example a platform error rather than `AccessDeniedException`),
reply with: nothing was checked, which check families were not run, and the error text. Do not infer
health from the absence of data, and do not give a verdict.
