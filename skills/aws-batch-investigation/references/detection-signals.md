# Choosing a detection signal for a stalled Batch queue

## The signals, compared

Measured against one reproducible scenario: a Spot compute environment with a
`bidPercentage` too low to ever be fulfilled, 6 jobs submitted within 8 seconds, and the
queue held at `RUNNABLE=6` / `RUNNING=0` for over 45 minutes.

Times are from job submission unless stated. Alarm configurations are given because the
numbers are meaningless without them.

| Signal | Time to fire | Configuration | Names the cause? |
|---|---|---|---|
| Unfulfilled vCPU alarm | 457s | 5 of 5 datapoints, 1-min period | **Yes** |
| Stuck-`RUNNABLE` alarm (widened) | 486s | 8 of 8 datapoints, 1-min period | No |
| Stuck-`RUNNABLE` alarm (narrow) | 213s | 3 of 3 datapoints, 1-min period | No |
| Polled webhook | 86s | 60s poll, 60s `RUNNABLE` threshold | No |
| Native "Job queue blocked" event | **never** | default | — |
| Silent OOM alarm | 53s from job stop | 1 datapoint | Yes |
| Silent timeout alarm | 123s from job stop | 1 datapoint | Yes |

## Recommendation

**Use an unfulfilled-vCPU alarm as the primary stall signal.** In this scenario it fired
31 seconds *faster* than the widened stuck-`RUNNABLE` alarm, and unlike that alarm it
identifies the cause rather than the symptom. A queue with jobs in `RUNNABLE` and
unfulfilled vCPUs above zero is a capacity-acquisition failure; a queue with jobs in
`RUNNABLE` and no unfulfilled vCPUs is something else.

**Keep a stuck-`RUNNABLE` alarm as a cause-agnostic backstop.** It catches stalls that
are not capacity-acquisition failures.

**Do not rely on the native "Job queue blocked" event for this scenario.** It did not
fire at any point during 45+ minutes of a genuinely stalled queue. This is a controlled
negative, not an absence of evidence: the queue was stalled, the event never arrived.

**Treat the silent-failure detectors as the highest-value additions,** because for them
the comparison is not "faster than X" but "detection versus none at all". Nothing else in
the stack reports a job that Batch itself called successful.

## The consecutive-datapoint trade is real

A stuck-`RUNNABLE` alarm evaluating `IF(running == 0, runnable, 0)` will fire on a
**cold start** — a queue scaling from zero legitimately has jobs in `RUNNABLE` with
nothing running yet.

Widening the alarm from 3 consecutive datapoints to 8 removed the observed false positive
but slowed genuine detection from 213s to 486s. That is 273 seconds of added latency
bought with one fewer false positive class. State the trade; do not present the widening
as free.

The threshold was chosen by replaying a real stored cold-start series through the alarm's
own metric math. The longest consecutive breach during that cold start was 3 minutes —
enough to trip 3-of-3, not enough to trip 8-of-8.

**How to pick your own threshold:** find a recorded legitimate scale-from-zero in your
own metric history, compute the longest consecutive run of
`running == 0 AND runnable > 0`, and set the datapoint count above it. A cold start that
lasts only one minute does not discriminate between 3 and 8 and cannot be used to justify
either.

## A short polling threshold cannot distinguish a cold start from a stall

A poller with a 60-second `RUNNABLE`-age threshold will report a stall for any queue
scaling from zero. Observed directly: a load run scaling up produced a webhook reading
"176 stuck RUNNABLE > 60s, 0 running" for what was simply normal startup.

Only **elapsed time** distinguishes a scale-from-zero from a real stall, which is exactly
why the alarm needs several minutes of consecutive breach. A poller running at a 60-second
interval structurally cannot make that distinction.

Two consequences:

1. Treat a fast polled signal as **advisory notice**, not as an incident. It is useful for
   speed and unreliable for correctness.
2. If a poller sends a webhook per interval, it will generate one alert per interval for
   the entire duration of a stall. Suppressing repeat notifications per queue per hour
   reduced this from one per minute to one per hour, measured across three hour buckets.
   Suppress the *notification*, not the metric — the metric is what the alarm evaluates.

Do not present a poller's time-to-detect as an improvement over another poller's when the
difference is smaller than the poll interval. Two measurements of 86s and 113s against a
60-second poll are the same result sampled at different alignments.

## Better: discriminate instead of suppress

Suppression reduces alert volume but does not reduce false positives — the wrong signal is
still wrong, just quieter.

An agent investigating a stuck-`RUNNABLE` report can make the distinction a poller cannot,
by reading the compute environment's ASG activity:

- Recent **failed** launch activities → real capacity-acquisition stall.
- Recent **successful** activities, or instances still registering → cold start, wait.
- `MaxSize` 0 on later compute environments while order-1 is failing → the queue is pinned
  behind a broken compute environment.

This is the check to run before concluding that a queue is stalled.
