# Report template and delegation

Read this file before writing the final answer (Step 8) and before handing any work to a sub-agent or parallel task.

## Report template

The user-facing answer always has this structure, in chat and in investigations. Prose may be short; the tables are never replaced by prose or a numbered list. When sub-agents gathered the evidence, the final answer carries forward the PERF ID, cost direction and verification metric they returned.

```
Assumptions: <defaults used, or the intake answers: target, peak, constraints>

## Summary
Verdict: <healthy | degraded | critical> against <target or baseline>.
Cause: <one sentence> (<Confirmed | Likely | Unconfirmed>).

| Rank | Change | Cost direction | Verification metric | PERF ID |
|---|---|---|---|---|
| 1 | <change that removes the cause> | <saves | neutral | adds cost> | <metric, expected value> | PERFxx-BPyy |
| 2 | ... | ... | ... | ... |
| 3 | <masking or interim change, labelled> | ... | ... | ... |

## Request path
| Hop | Resource type | p99 (unit) | Own-time share | Budget share | Discovered by |

## Bottleneck
Resource, evidence (metric, statistic, window, value with unit, threshold), label.
Symptom onset <UTC> and cause-signal onset <UTC>.
Magnitude check: <predicted> against <measured>, with the arithmetic.
Mechanism linking the resource to the user-facing symptom.
Why the first fix ranks above any capacity change.

## Hypotheses considered
| Hypothesis | Evidence for | Evidence against | Status (Confirmed, Likely, Unconfirmed, Ruled out by timing, scope, history or magnitude) |

## Findings
| ID | Severity | Resource | Well-Architected area | Finding | Evidence |

## Recommendations
| Rank | Change | Expected effect | Effort | Cost direction | Risk | Verification metric | PERF ID |

## Telemetry gaps
What could not be measured, which call failed with which error class, and how to enable it.

## Next review
Validating test and alarm changes.
```

### Rules for the template

- **Summary first.** The Summary block is always present, also in a short chat answer.
- **Recommendations.** Every row has a cost direction (saves, neutral, adds cost) and a PERF ID from `well-architected-mapping.md`. Quantify the expected effect where the evidence allows, for example the predicted post-change duration from the magnitude check. Express verification windows relative to the change time (the 30 minutes before against the 30 minutes after), never as a fixed past timestamp.
- **Ranking.** Rank recommendations by impact on the target and effort. The change that removes a Confirmed cause ranks first. Masking or capacity changes (raising the slow component's own execution timeout, such as a function timeout; provisioned or reserved concurrency; a larger instance, more instances or tasks, autoscaling, read replicas; a larger downstream limit) rank below it, labelled interim or masking, with the reason in the Risk column. Resizing a caller's client timeout from the dependency's measured p99 is the fix for retry amplification, not masking. When the Confirmed cause is a capacity shortfall at legitimate load, the capacity change is the fix; when cold starts are Confirmed, provisioned concurrency is the fix; when a credit or burst cap is Confirmed, changing the instance class or credit mode to remove it is the fix, not masking. Each recommendation is its own row and its own command; never combine a masking change with the real fix (see `diagnosis-rules.md`, Masking fixes). Cutting the business workload is never a row.
- **Intake answers.** When intake answers were given, the Assumptions line states the target, the peak and the constraints, and the Bottleneck or Recommendations section shows the sizing arithmetic against the target (for example required concurrency = target rate x per-request duration, plus headroom for stated growth). Flag any recommendation that would break a stated constraint.
- **Labels.** Each cause has exactly one label, the same in every section.

### Severity

- **Critical.** The target is breached now and a saturated hot-path resource explains it.
- **High.** The target is at risk within the expected growth or next peak, or a hot-path resource saturates intermittently.
- **Medium.** Inefficiency without user impact today: overprovisioning, missing scaling policies, missing hot-path telemetry.
- **Low.** Hygiene and small improvements.

### Next review

Name the test that would validate the fix when one fits: load (expected peak), stress (breaking point), soak (slow degradation such as leaks), spike (sudden surge) or benchmark (A/B of a change). For alarms, prefer SLO burn-rate alarms and alarms per fault boundary (per Availability Zone, per operation) over single raw thresholds; use composite alarms to cut noise, anomaly detection where a static threshold does not fit, a runbook for every alarm, and a performance regression gate in CI/CD.

## Reconcile before sending

Run this check on the final answer, including any findings, root-cause cards and mitigation plans you produced:

1. Each cause carries one label everywhere. Remove or rewrite any telemetry gap that a later step resolved.
2. No two findings both claim to be the fundamental cause. Delete placeholder or stale findings.
3. No claim comes from another investigation, another workload or memory unless it was checked on this workload in this window.
4. Every recommendation row has a cost direction, a verification metric and a PERF ID.
5. Hygiene scan (below) passes.

## Report hygiene

Never print account IDs, full ARNs, private endpoint hostnames, VPC, subnet or security group IDs, private IP addresses, database resource IDs, secret names, IAM role, user or session names, or API IDs. This applies to the answer, findings, root-cause text, mitigation plans and example commands. Refer to resources by name and use placeholders such as `<account-id>`, `<db-endpoint>` or `<function-name>` in commands. Before sending, scan the text for 12-digit numbers, `arn:`, and dotted IPv4 addresses, and replace any match.

## Delegation

A sub-agent does not read `SKILL.md`. The task text you send is all it knows, so copy the rules that shape its output into it. Include this block, edited to the task:

```
Scope: account <named>, Region <named>. Do not search other Regions or accounts.
Units: state the unit next to every value; compute utilization against the real limit.
Failed calls: report the error class, retry once, use a fallback source; a cause
  resting on a failed read is Likely, not Confirmed.
Proof: for each candidate cause give onset time, a magnitude check with arithmetic,
  and evidence for and against. Rule changes out by timing, scope, history or
  magnitude; report only change events you read.
Twin: if a peer runs the same code, diff its configuration and request shape and
  compare the same metrics.
Caches: no cache or hit-ratio claim unless a cache exists in configuration or code.
Hygiene: no account IDs, ARNs, IPs, role or principal names in the output.
Return: findings with metric, statistic, window, value and unit, and a label.
```

For any task that proposes fixes or mitigation steps, add:

```
Fixes: rank by impact on the target and effort; the change that removes the cause
  ranks first. Rank masking changes (raising the slow component's own execution
  timeout such as a function timeout, provisioned or reserved concurrency, more
  capacity such as a larger instance, autoscaling or read replicas, a larger
  downstream limit) below it, labelled masking with the reason, as separate
  steps, never in the same command. Resizing a caller's client timeout from the
  dependency's measured p99, inside the caller's own deadline, is the fix for
  retry amplification, not masking. For each step give cost direction, a verification metric with
  the expected value, and a PERF ID. Check downstream capacity before raising a
  consumer cap. Do not propose cutting business load.
```

When the results return, keep their PERF IDs, cost directions and verification metrics in the final answer, and apply the Reconcile check before sending.
