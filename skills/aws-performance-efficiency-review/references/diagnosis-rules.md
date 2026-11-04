# Diagnosis rules

Read this file before naming a cause (Step 4), before calling any cause Confirmed, and whenever a magnitude check, a peer comparison or a change rule-out is needed. `SKILL.md` keeps the short form of each rule; this file holds the full rule and the worked arithmetic.

## Confidence labels

- **Confirmed.** Two independent signals: utilization against its real limit plus a saturation or error signal (OOM kills or task stop reasons, throttles, queue length, evictions, `DBLoad` above vCPU with CPU waits), the onset matches, and the magnitude check passes.
- **Likely.** One signal, or a cause that still rests on a read that failed.
- **Unconfirmed.** A plausible mechanism with no direct signal. Never list an Unconfirmed finding as a cause.

Assign each cause one label and use it in every section. Do not call the same cause both fundamental and unproven. A claim of change over time (data growth, traffic growth, gradual degradation) needs a metric that shows the change over the window; without one it is Unconfirmed and is not used as a mechanism.

## Failed calls

When a call needed to confirm a cause fails:

1. Report the exact error class (access denied, throttling, not found, other).
2. Retry once if the resource is on the request path. Name the missing permission for an access-denied error.
3. Use a fallback source that carries the same fact, for example the configured memory size printed on every Lambda `REPORT` log line, the configuration recorded in a CloudTrail update event, a deployment template, or trace segments for a SQL statement.
4. A cause that still depends on the failed read stays **Likely**, never Confirmed, until a fallback supplies the fact. Say which read would promote it.

Do not retry calls to an account or Region that is not on the request path, and do not name such an account in the report.

## Bounded effort

- Work in the account and Region the user named. If none is named, use the account and Region where the topology places the entry point.
- Search another Region or account only when the entry point is not found there, and stop as soon as it is found. Never sweep Regions to look for more data.
- Stay on the resources in the request path. Do not enumerate or assume roles into accounts outside it.
- Stop expanding once the bottleneck is Confirmed and the end-to-end time is accounted for.

## Units and limits

Confirm each metric's unit from its metadata or `metrics-by-service.md` before calling a resource saturated, and compute utilization against the actual limit, not the raw value. Some metrics are absolute quantities: `ECS/ContainerInsights` `MemoryUtilized` and `CpuUtilized` are megabytes and CPU units; divide by `MemoryReserved` or `CpuReserved`, or use `AWS/ECS` `MemoryUtilization`, which is a percent. Put the unit next to every value.

## Differential diagnosis

Before naming a cause, list the competing explanations and rule each in or out with a specific observation:

- a deployment or configuration change;
- a traffic, arrival-rate or request-shape change (payload size, items per request, mix of operations);
- a slow, throttled or failing dependency;
- caller behaviour: client timeouts and retries (work amplification);
- a degraded single member of a fleet, a single Availability Zone or a single revision;
- a limit that looks like headroom (`hidden-limits.md`);
- historical errors that predate the window.

For a gradual regression also weigh traffic growth, feature accumulation, infrastructure drift (stale scaling policies), data growth (query-plan changes, falling index selectivity), dependency changes and a retry storm.

Report the result as the "Hypotheses considered" table (hypothesis, evidence for, evidence against, status). Status is one of Confirmed, Likely, Unconfirmed or Ruled out, and says which test ruled it out (timing, scope, history or magnitude).

## Ruling a change in or out

A change that coincides with the window start is not a cause unless its timing, its magnitude and its scope match the symptom. Apply these tests in order:

1. **Timing.** The change must land at or before the symptom onset.
2. **Scope.** If the same change was applied to a healthy peer and a degraded peer, it cannot explain on its own why only one is degraded. Rule it out by scope as the sole cause. It can still interact with a configuration difference that only the degraded peer has, so keep that combination in the differential until the configuration diff rules it out.
3. **History.** If the same symptom appeared on earlier days before the change existed, the change is not the cause. Recurrence on earlier days is a second, independent test.
4. **Magnitude.** The change must be large enough to produce the measured effect. A log-verbosity or metadata-only change does not explain a multi-fold duration increase unless a measurement shows it does.

Never invent change history. State only what the change events you read show (which resources were updated, which values changed, when). Do not describe a change as a revert, a no-op or a cap change unless an event or a configuration diff shows it. If change events were not read, say so.

## Onset timing

Record the onset timestamp of the symptom and of each candidate's signal. A candidate whose signal starts after the symptom, or hours away from it, is ruled out or demoted from Confirmed.

## Magnitude check

A Confirmed cause must account for the measured symptom with arithmetic, not prose. Estimate what the cause predicts, compare with what was measured, and label any remainder unexplained. Worked forms:

- **Capacity drop.** A capacity drop of ratio r predicts a throughput drop of about r. Compare with the observed throughput change.
- **Backlog.** Backlog growth rate = arrival rate - completion rate. The gap times the window equals the backlog built.
- **Served rate under a concurrency cap.** Maximum served rate = concurrency limit / mean duration. Compare with the arrival rate of attempts, not of user requests.
- **Effective concurrency.** Effective concurrency = completion rate x mean duration (Little's law). Compare it with the configured reserved or maximum concurrency before calling that setting headroom or the cap.
- **Work amplification.** Attempts arriving at a dependency = originating request rate x attempts per request. Attempts per request = (served + rejected or throttled attempts) / originating requests. A ratio above 1 means callers multiply the load, but it is not proof of a cause on its own. Amplification is the cause only when both hold: originating rate x 1 attempt fits the dependency's capacity (for example concurrency limit / single-attempt duration), and the amplified attempt rate exceeds that capacity. If the originating rate at one attempt already exceeds capacity, the capacity shortfall is the cause and the retries make it worse.
- **Rate change.** When the request rate also changed, compute what the old configuration would do at the new rate alone. If the rate change by itself stays inside capacity, it is a trigger at most, not the cause.

### Lambda memory and CPU

Lambda allocates CPU in proportion to configured memory, and at 1,769 MB a function has the equivalent of one vCPU (AWS Lambda Developer Guide, page `lambda/latest/dg/configuration-memory.html`). Inference, not stated on that page: at 1,769 MB the function has one vCPU's worth, so code that runs on one thread is not expected to gain CPU above it; confirm by measuring. In the formulas below, effective memory is min(memory, 1,769 MB) for single-threaded code and the configured memory for code that uses several threads. For CPU-bound work:

1. Split duration into compute time and wait time. Wait time is the time spent in downstream calls, read from trace segments or logged timings.
2. Estimate the compute-time ratio between two memory settings as the inverse of the effective memory ratio: a function at effective memory M1 takes up to about M2 / M1 times as long on compute as the same code at effective memory M2, for the same request shape. This is an estimate and an upper bound of the gain, and it applies only to the CPU-bound part. Wait time, memory-bound sections and fixed overheads do not scale with it.
3. Compare the estimate with the measured p50 ratio (same percentile, same request shape, same window). If they agree, memory explains the slowdown.
4. Predict the post-change duration: new duration = compute time x (current effective memory / proposed effective memory) + wait time. This is a best case. Check it against the timeout with margin, and state it so the verification metric has a target. The prediction is not a result: confirm it by measuring the same percentile at the same request shape after the change.

When a twin runs the same code at a different memory size, use it for steps 2 and 3; otherwise use the request-shape ratio between busy and quiet periods.

### Cold starts

Rule cold starts in or out by magnitude, not by "unchanged" or by intuition:

- The Lambda `Duration` metric does not include initialization (cold start) time (AWS Lambda Developer Guide, page `lambda/latest/dg/monitoring-metrics-types.html`). Initialization appears only as `Init Duration` on the `REPORT` log line of a cold invocation. A shift in `Duration` p50 therefore cannot come from initialization.
- Cold-start contribution to the caller-observed mean end-to-end latency = share of invocations with an `Init Duration` x mean `Init Duration`. Read the caller-observed latency from the caller's own metric or trace segment, not from `Duration`.
- Compare that contribution with the shift in caller-observed end-to-end latency between baseline and incident.
- If most slow invocations carry no `Init Duration`, or the contribution is a small fraction of the shift, rule cold starts out and say which number did it.
- Provisioned concurrency removes initialization only. It does not shorten a warm invocation that is CPU-bound or waiting on a dependency.

## Control twin

A twin is a peer that runs the same code: a sibling function with the same code hash or handler, a consumer of the same image digest, a service built from the same artifact, or another member of the same fleet.

When a twin exists, using it is mandatory in chat and in investigations:

1. Diff the configuration: memory or instance size, timeout, reserved, provisioned or maximum concurrency, client timeouts and retry settings, scaling policy, environment variables.
2. Diff the request shape: rate, payload size, records per request, operation mix, callers.
3. Compare the same metrics side by side: duration percentiles, concurrency, throttles, queue flow, errors.
4. Use the result to rule out the shared factors. If the twin is healthy with the same code, the same dependency and the same request shape, then the code, the payload and the dependency are ruled out, and the configuration difference is the leading candidate.

If no twin exists, say so in the Hypotheses table. Do not describe a twin's load or configuration without reading it.

## Caches and field names

Do not claim a cache, a hit ratio or a miss rate from a field name alone. A log field or attribute whose name contains "hit", "miss" or "cache" can mean something else (for example a flag that a lookup returned a value). Before any cache finding, confirm that a cache exists in configuration (an ElastiCache or DAX resource, a CDN, a cache setting) or in code. Without that confirmation the claim is Unconfirmed and is not a cause or a fix.

## Retry amplification

When the attempts a dependency receives exceed the requests callers originated (attempts per request above 1):

- A ratio above 1 is not proof on its own; some retrying is normal. Apply the magnitude test (the Work amplification form under Magnitude check): originating rate x 1 attempt must fit the dependency's capacity while the amplified attempt rate exceeds it. Only then is the caller's timeout and retry policy the root cause. If the dependency cannot serve the originating rate at one attempt per request, its capacity is the cause and the retries make it worse.
- Compare the client timeout with the dependency's p99 at single-attempt load (a period with attempts per request near 1 at a matched originating rate). A busy-window p99 can itself be inflated by retries, because abandoned attempts queue in front of new ones; prefer the single-attempt p99 and say which one you used. A timeout below that p99 abandons normal tail requests and re-issues them.
- Rank first: resize the caller's client timeout from that p99 plus a margin, keep it inside the caller's own deadline (all attempts and backoff must finish before the caller itself times out or its upstream budget runs out), and retry at one layer only, with backoff, jitter and a retry budget. This client-timeout change is the fix, not masking.
- Rank below, labelled masking: raising the dependency's concurrency, capacity or quota. Extra capacity fills with abandoned attempts while the timeout stays below the tail.
- Note that throttled attempts are usually not counted in the dependency's invocation or request count (for Lambda, `Throttles` is separate from `Invocations`), so that count understates the load arriving.

## Baselines and regime changes

- A baseline is a stable period with real traffic before the fault. Never use a zero-traffic, pre-traffic or in-fault period.
- If the rate, the request shape or the configuration changed inside the metric history, split the history into regimes and re-baseline on the current regime before sizing or comparing. Do not apply a previous regime's rates to today. Applies to chat and investigation alike.
- Compare like with like: same percentile, same period, matched rate. State the rate next to every baseline value.

## Masking fixes

A masking fix hides the symptom without removing the cause:

- raising the slow component's own execution timeout, for example a Lambda function timeout or a job timeout (the slow path still runs and now holds concurrency longer);
- provisioned or reserved concurrency (removes initialization or reserves slots; does not shorten the work);
- more capacity: a larger instance, more instances, tasks or consumers, autoscaling, read replicas, or a larger downstream limit (raises concurrent load on a saturated dependency, or fills with retries);
- raising a downstream quota while callers amplify.

Not masking:

- Resizing a caller's client timeout from the dependency's measured p99 is the fix for retry amplification (see Retry amplification). Do not label it masking and do not confuse it with raising the slow component's own execution timeout.
- When the Confirmed cause is a capacity shortfall at legitimate load (the magnitude check shows the originating demand at one attempt per request exceeds capacity), the capacity change is the fix.
- When cold starts are Confirmed by the init-share arithmetic (Cold starts), provisioned concurrency is the fix.
- When a credit or burst cap is the Confirmed cause, changing the instance class or credit mode to remove that cap removes the cause and is not masking.

Rules:

- Rank a masking fix below the change that removes the cause, and label it interim or masking with the reason it masks.
- Never bundle a masking fix into the same command, template change or deployment step as the real fix. Bundling hides whether the real fix worked, because the verification metric moves for both reasons, and it leaves the masking change in place after the cause is gone.

## Capacity and load

- Before raising a consumer cap (event source maximum concurrency, consumer count, worker threads), check the downstream capacity it will feed: database connections and write capacity, table capacity mode and throttles, API quotas. Raising a cap raises the downstream call rate. Pair the change with that check.
- Cutting the business workload (lowering the producer rate, dropping requests, disabling a feature) is never a ranked fix. Removing an artificial cap or limit outranks it. Automatic load shedding under overload is a protection mechanism, not a fix for a sizing problem.

## Common mistakes (full list)

- Recommending a larger instance when the saturated resource is a database or another dependency.
- Treating low `CPUUtilization` on a burstable instance as idle while the credit balance is near zero.
- Reading Lambda average duration while p99 approaches the timeout, or judging a Lambda function's CPU without reading its memory size.
- Reading low memory use on a Lambda function as headroom when memory also sets its CPU share.
- Blaming the load balancer when `TargetResponseTime` shows the time is in the targets.
- Reading a megabyte metric as a percent.
- Averaging across baseline and incident windows; comparing a baseline p50 with an incident p99; calling traffic flat when the rates do not match.
- Using a zero-traffic, pre-traffic or in-fault period as the baseline, or sizing against a previous regime.
- Asserting data growth, traffic growth or gradual degradation without a metric that shows it.
- Reporting Compute Optimizer output without checking whether the resource is on the hot path, or letting a failed Compute Optimizer call stop the report.
- Reporting an error that predates the window or the last deployment as a current defect.
- Trusting a fleet aggregate; picking an outlier by a fixed threshold instead of peers (IQR, MAD, top-contributor share); treating a passing shallow health check as health.
- Skipping an available twin, or describing a twin's load or configuration without reading it.
- Blaming a change that merely coincides with the window start, or one applied to healthy and degraded peers alike; inventing what a change did.
- Calling a cause Confirmed when its signal starts after onset, when it explains only part of the symptom, or when it rests on a failed read.
- Ruling cold starts in or out without the init-share arithmetic, or attributing a shift in Lambda `Duration` to initialization (`Duration` excludes init time).
- Claiming a cache problem from a field name.
- Ranking raising a downstream limit above fixing a retry policy that amplifies load, or setting a client timeout below the dependency's p99.
- Calling retry amplification the cause from a ratio above 1 without the magnitude test, sizing a client timeout from a retry-inflated busy-window p99, or setting it beyond the caller's own deadline.
- Labelling a caller's client-timeout resize as masking, or treating a raise of the slow component's own execution timeout as a fix.
- Ranking a masking fix above the real fix, presenting them as equals, or bundling them in one command.
- Raising a consumer cap without checking downstream capacity; ranking a cut in business load as a fix.
- Recommending more consumers or tasks before a per-member cap (per-partition throughput, per-instance network or EBS burst, a concurrency limit) is explained.
- Missing bimodal latency that several percentiles or a histogram would show.
- Scaling on CPU when users feel latency or queue age; assuming Auto Scaling absorbs a sudden spike.
- Alarming on raw thresholds instead of SLO burn rate per fault boundary, or leaving an alarm without a runbook.
- Retrying or naming an off-path account; sweeping Regions the user did not name.
- Asking the user for topology, metrics or configuration the agent can read, asking more than three intake questions, asking twice, or asking at all during an investigation; skipping intake in chat and delegating or investigating when the target, the peak and the constraints are all missing; or ignoring the intake answers in the sizing and the recommendations.
- Reporting latency with no SLI, SLO or target framing, or not deriving the error budget and burn rate when an Application Signals SLO exists.
- Reading latency, throughput, error rate and utilization on different windows instead of together, or concluding from an average.
- Replacing the recommendations table with prose or a numbered list, or leaving a row without a cost direction or a PERF ID, in chat or in an investigation.
- Omitting the answer-first summary table at the top, or dropping it when shortening a chat answer.
- Naming a cause without a differential: listing competing explanations and ruling each in or out with a specific observation.
- Keeping two contradictory "fundamental cause" findings, or importing a claim from another investigation or memory without checking it on this workload.
