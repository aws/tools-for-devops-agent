---
name: aws-performance-efficiency-review
description: Cross-service performance analysis of an AWS application, aligned with the Performance Efficiency pillar of the AWS Well-Architected Framework. Use this skill when a user asks why an application or service is slow, where the latency comes from, what the bottleneck is, whether resources are right-sized, or whether the workload will scale for a peak, or asks for a performance review. Also use it in an investigation when the symptom is high latency, rising p99, timeouts, throttling, retries, queue backlog, or saturation of CPU, memory, IOPS, connections or concurrency. Traces the path from the entry point (load balancer, queue, stream or schedule) through its dependencies, finds the constraining resource with the USE and RED methods, and returns ranked fixes mapped to Well-Architected best practices. Covers Lambda, ECS, EKS, EC2, EBS, RDS and Aurora, DynamoDB, ElastiCache, SQS, ALB and API Gateway. Triggers on "performance review", "why is it slow", "bottleneck", "backlog", "p99".
metadata:
  author: kshtepa
  version: "1.0.0"
  summary: "Finds where an AWS application spends its time and which resource limits it, then ranks fixes against the Well-Architected Performance Efficiency pillar. Read-only."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "Amazon CloudWatch, AWS X-Ray, Amazon EC2, Amazon ECS, Amazon EKS, Amazon RDS, AWS Service Quotas"
  aws-devops-agent-skills.technical-domains: "Capacity Planning, Observability, Databases"
---

# AWS Performance Efficiency Review

Find where an application spends its time, which resource limits it, and what to change. Every conclusion cites the metric, the resource, the window and the value that supports it.

Native AWS read APIs only: CloudWatch, CloudWatch Logs, X-Ray, Application Signals, Compute Optimizer, RDS Performance Insights and the describe APIs of the services on the path. Read-only: recommend changes, never apply them.

## Instructions

Copy this checklist into your working notes and tick each step as it is done. Each step depends on the one before it; the sections below give the detail.

- [ ] Step 0: Intake (chat only): ask for target, peak and constraints if they are missing, then wait
- [ ] Step 1: Scope and target: entry point, goal, window, baseline, target
- [ ] Step 2: Map the path from the entry point to the deepest dependency
- [ ] Step 3: Measure each hop (RED) and pick the suspect hop
- [ ] Step 4: Find why (USE, breakdown, twin, callers, changes, differential)
- [ ] Step 5: Run the service deep checks that apply to the suspect
- [ ] Step 6: Right-size with Compute Optimizer or the workload's own metrics
- [ ] Step 7: Map every finding to a Well-Architected PERF ID
- [ ] Step 8: Write the report from the template, then run the reconcile and hygiene checks

Read the top gotchas and the evidence rules before Step 1. When you delegate, copy the delegation block into the task text.

## Step 0: Intake (chat only, first action)

Do this before anything else, before delegating to a sub-agent and before investigating. It applies to every new chat question, including a follow-up asked in the same conversation as an earlier investigation.

1. Do one quick read of what you can discover yourself (an Application Signals SLO, existing alarms). Never ask for topology, metrics or configuration you can read.
2. If the request still lacks any of these, ask at most three short numbered questions in ONE message, then end the turn and wait:
   - the performance target (an SLO, a p99, a throughput or a queue-age objective);
   - the expected peak or growth (for any sizing or scale question);
   - the constraints (a cost ceiling, what cannot change, a change freeze).
3. Use the answers as inputs: size against the target with explicit arithmetic (Little's law: required concurrency = rate x per-request duration), add headroom for stated growth, keep every recommendation inside the constraints and flag any that would break one.

Skip intake when the request already states all three. If the user declines or says to continue, or no human is in the loop, proceed with defaults in an Assumptions line and never ask twice. In an investigation (Incident RCA) never ask; use defaults and list them in an Assumptions line.

## Top gotchas

Read these before Step 1.

1. **Rank the fix above capacity, and keep masking fixes separate.** The change that removes the Confirmed cause ranks first; masking fixes rank below it, labelled masking, and are never bundled with it.
2. **Retry amplification before capacity, proven by magnitude.** Compare originating requests with the dependency's Invocations plus Throttles; a ratio above 1 is not proof of retry amplification without the magnitude test; once proven, a caller client timeout sized from the dependency p99 is the fix, not masking.
3. **Use the control twin.** Comparing with a twin that runs the same code is mandatory; a healthy twin with the same request shape rules out the code, payload and dependency.
4. **Lambda memory is the CPU setting.** Read Lambda `MemorySize` (with the `REPORT` line as fallback) before judging CPU; low memory use is not headroom on a CPU-bound function.
5. **Magnitude with arithmetic.** A Confirmed cause must account for the measured symptom in numbers, and a predicted gain counts only once measured after the change.
6. **Rule changes out by timing, scope and history.** A change shared by healthy and degraded peers is ruled out by scope as the sole cause, earlier recurrence by history; never invent change history.
7. **Cold starts by magnitude.** Lambda `Duration` excludes init, so rule cold starts in or out by init share against caller-observed latency, never by `Duration`.
8. **No cache from a field name.** Make no cache claim from a field name; without a cache in configuration or code, the claim is Unconfirmed.
9. **Failed read means Likely.** A cause resting on a failed read stays Likely, not Confirmed, until a fallback source supplies the fact.
10. **Stay in scope.** Stay in the named account and Region (or where the entry point is), and never sweep Regions or probe off-path accounts.
11. **Re-baseline on the current regime.** If rate, request shape or configuration changed inside the history, re-baseline on the current regime before comparing or sizing.
12. **Check downstream before raising a consumer cap.** A higher consumer cap raises the downstream call rate, so check that capacity first.
13. **Never rank cutting business load as a fix.** Lowering the producer rate or dropping work is never a ranked fix; removing an artificial cap outranks it.
14. **Hygiene.** No account IDs, ARNs, IP addresses, role or principal names anywhere in the answer, findings or commands.

Full rule and worked arithmetic for each gotcha: `references/diagnosis-rules.md`, sections "Masking fixes" (1), "Retry amplification" (2), "Control twin" (3), "Lambda memory and CPU" (4, with `references/hidden-limits.md`, "Lambda memory sets CPU share"), "Magnitude check" (5), "Ruling a change in or out" (6), "Cold starts" (7), "Caches and field names" (8), "Failed calls" (9), "Bounded effort" (10), "Baselines and regime changes" (11) and "Capacity and load" (12, 13); hygiene (14) is in `references/report-and-delegation.md`, "Report hygiene".

## Evidence rules

- Percentiles (p50, p90, p99), never averages alone. Compare like with like: same percentile, same period, matched rate.
- A finding states metric, dimension, statistic, window, value with unit, and the threshold it crossed. Confirm units and compute utilization against the real limit (`references/metrics-by-service.md`).
- Label every cause **Confirmed** (two independent signals, onset and magnitude match), **Likely** (one signal, or a failed read) or **Unconfirmed** (never listed as a cause). One label per cause, used everywhere.
- Separate the bottleneck from its symptoms. A pool or concurrency limit at its maximum behind a slow dependency is a consequence (in-flight = rate x latency) unless it saturated first.
- Missing telemetry is a finding. For a failed call, report the error class, retry once if on-path, name the missing permission for access denied, and use a fallback.
- Give each recommendation a cost direction (saves, neutral, adds cost) and say when a performance fix raises cost.
- Keep API calls bounded: one `GetMetricData` call per resource with all its metrics. Stop expanding once the bottleneck is Confirmed and end-to-end time is accounted for.

## Step 1: Scope and target

1. **Entry point.** Resolve it through the Agent Space topology, or the account and Region the user named. It may be a load balancer, an API, a queue, a stream, a schedule or a batch job. Map upstream and downstream neighbours of any single named resource.
2. **Goal.** Investigation (something got slow) or review (efficiency, scale).
3. **Window.** Investigation: 1 hour before onset to now, plus the same window 7 days earlier. Review: 14 days. Keep incident and baseline values separate. For a time-of-day complaint, compare the same hours on at least two days and busy against quiet hours, with rate and request shape per period. Read `references/logs-and-statistics.md` (Windows and baselines) when choosing a baseline or when the regime changed.
4. **Target.** From intake or an Application Signals SLO; otherwise the baseline, and say no objective was defined. Read `references/logs-and-statistics.md` (Targets, SLOs and error budgets) when an SLO or end-to-end target exists.

## Step 2: Map the path

Build the ordered hops from the entry point to the deepest dependency:

1. Agent Space topology.
2. `application-signals.ListServices` and `ListServiceDependencies`, then `xray.GetServiceGraph` for per-edge latency and errors.
3. Without either, infer from configuration: target groups, services behind them, security group references, endpoint environment variables, event source mappings, database and cache endpoints. Mark inferred hops unconfirmed.

For async and batch work, map producer, queue or stream, consumers, and what consumers call; list each consumer fleet member. Record each hop's type, Region and how it was discovered. Note peers that run the same code (twins) for Step 4. No traces is a Process and culture finding.

## Step 3: Measure each hop (RED)

One `cloudwatch.GetMetricData` call per hop for rate, errors and duration p50, p90, p99 (metric names in `references/metrics-by-service.md`). Use a period that gives 100 to 1,440 points. Compute each hop's own time, its share of end-to-end p99, its budget share when a target exists, and its change against baseline. Read latency, throughput, errors and utilization on the same window.

For queues and streams, RED is arrival rate, completion rate, backlog and age, and per-message duration from logs; read `references/logs-and-statistics.md` (RED for async and batch workloads, Little's law and flow, Query patterns) when the entry point is not a request.

Exclude one-minute transients at deployments or scaling events from the steady-state peak. The hop with the largest own-time share or regression is the suspect; carry two if close.

## Step 4: Find why (USE, breakdown, differential)

- [ ] 4.1 **Saturation.** For each suspect, check utilization, saturation and errors on CPU, memory, IOPS, network, connections, concurrency and capacity units. Thresholds: `references/bottleneck-patterns.md`; state the one applied. Saturation signals (throttles, queue length, credit balance at zero, connections at maximum, evictions) outrank utilization. Read `references/hidden-limits.md` whenever a resource looks under-used while the symptom persists (burst credits, baselines, per-partition limits, Lambda concurrency and memory-sets-CPU).
- [ ] 4.2 **Break down.** Split latency, errors, throughput and utilization by operation, member, Availability Zone, revision and caller. Pick outliers against peers (IQR, MAD, top-contributor share), not a fixed threshold. A passing shallow health check does not prove health.
- [ ] 4.3 **Twin.** If a twin exists, diff configuration and request shape and compare the same metrics (mandatory; `references/diagnosis-rules.md`, Control twin).
- [ ] 4.4 **Callers.** Compare client timeouts with the dependency's p99 at single-attempt load and count attempts per originating request. Above 1 is a candidate for work amplification, confirmed only by the magnitude test in `references/diagnosis-rules.md` (Retry amplification). For goodput, load shedding, scaling lag and modal paths (cold caches, fallbacks, failover), read `references/bottleneck-patterns.md` (Overload and dependency behaviour).
- [ ] 4.5 **Changes and history.** Read deployments and configuration changes in the window (change history, CloudTrail, ECS deployments, Lambda versions, RDS events). Check the timestamp of every error; errors before the window or the last deployment are historical. Compare the rate with baseline: latency rising with rate is capacity, at flat rate look for a change or a dependency.
- [ ] 4.6 **Differential.** List competing explanations and rule each in or out by timing, scope, history or magnitude. Record symptom and cause onset times. Do the magnitude check with arithmetic. Read `references/diagnosis-rules.md` before naming any cause.

## Step 5: Service deep checks

Run only those that apply to the suspect: databases (Performance Insights load by wait and statement), Lambda (memory, timeout, concurrency, `REPORT` lines, cold starts), other compute scaling, caches and NoSQL, queues and streams, callers and retries, network path. Read `references/metrics-by-service.md` (Deep checks by service) for the calls and comparisons.

## Step 6: Right-sizing

Call `compute-optimizer.GetEnrollmentStatus`; if it is not active, report it as a finding. Otherwise call the recommendation API for each resource type on the path (EC2, Auto Scaling group, EBS, Lambda, ECS, RDS). Report each `finding` as returned with the top option, its performance risk and projected utilization. Overprovisioned off the hot path is a cost finding; Underprovisioned on the hot path supports the bottleneck. Without memory metrics on EC2, say the recommendation uses CPU and network only. If Compute Optimizer is unavailable for any reason, right-size from the workload's own metrics and say Compute Optimizer was not used and why.

## Step 7: Map to Well-Architected

Map every finding to one Performance Efficiency area (architecture selection, compute and hardware, data management, networking and content delivery, process and culture) and a PERF best-practice ID from `references/well-architected-mapping.md`. Name a design principle in the rationale where it fits.

## Step 8: Report

Read `references/report-and-delegation.md` before writing the answer and follow its template. The answer, in chat and in investigations, always has:

1. **Assumptions** line (defaults, or the intake target, peak and constraints).
2. **Summary**: verdict, cause with its label, and a top-3 table with Rank, Change, Cost direction, Verification metric, PERF ID.
3. **Request path**, **Bottleneck** (evidence, onsets, magnitude arithmetic, mechanism, why the fix outranks capacity), **Hypotheses considered** (hypothesis, evidence for, evidence against, status), **Findings**, **Recommendations** (Rank, Change, Expected effect, Effort, Cost direction, Risk, Verification metric, PERF ID), **Telemetry gaps**, **Next review**.

Tables are never replaced by prose. Every recommendation row has a cost direction, a verification metric and a PERF ID, and masking rows are labelled and separate. Before sending, run the "Reconcile before sending" and "Report hygiene" checks in `references/report-and-delegation.md`.

## Delegation

A sub-agent does not read this file. Copy the delegation block from `references/report-and-delegation.md` into every task text: scope (named account and Region only), units, the failed-call rule, onset, magnitude and change rule-out, twin, cache and hygiene rules. For tasks that propose fixes, add the ranking block (fix first, masking separate, cost direction, verification metric, PERF ID, downstream check, no load cuts). Keep their PERF IDs, cost directions and verification metrics in the final answer.

## Reference files

| File | Read when |
|---|---|
| `references/diagnosis-rules.md` | Before naming or labelling any cause; for magnitude arithmetic, twin, change rule-out, cold starts, retries, caches, masking fixes; full list of common mistakes |
| `references/report-and-delegation.md` | Before writing the final answer or delegating; report template, severity, hygiene, delegation blocks |
| `references/metrics-by-service.md` | Choosing metrics, units and dimensions; Step 5 deep checks |
| `references/bottleneck-patterns.md` | Applying thresholds; matching a symptom pattern to a likely cause |
| `references/hidden-limits.md` | A resource looks under-used but the symptom persists |
| `references/logs-and-statistics.md` | Baselines, windows, SLOs, async RED, Logs Insights queries, outlier statistics, Little's law |
| `references/well-architected-mapping.md` | Assigning a PERF ID to each finding and recommendation |
