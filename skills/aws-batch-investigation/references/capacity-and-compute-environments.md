# Compute environments, capacity and retries

## Ordered compute environments are overflow, not fault tolerance

A job queue can list several compute environments with an order. The common assumption
is that if the first compute environment cannot provide capacity, Batch moves the work
to the next one. **It does not.**

Observed over a 45-minute stall on a queue with three compute environments, with
`RUNNABLE=6` and `RUNNING=0` throughout:

| Order | Type | `desiredvCpus` | Instances registered | ASG activity |
|---|---|---|---|---|
| 1 | Spot | 2 | 0 | 60 of 60 activities `Failed` |
| 2 | On-demand | 0 | 0 | `MaxSize` 0, zero activities |
| 3 | Spot | 0 | 0 | `MaxSize` 0, zero activities ever |

The decisive detail is **`MaxSize` 0 on the later Auto Scaling groups**. Batch sizes a
compute environment's ASG to what it intends to run there. `MaxSize` 0 means Batch never
asked for capacity — it did not try and fail, it never tried. Throughout the stall the
order-2 compute environment was `ENABLED`, `VALID` and configured for 32 vCPUs.

Batch **does** advance when a compute environment is genuinely **full**. In a separate
load run on the same queue set, all three compute environments carried tasks
simultaneously, reached their desired vCPU counts, and recorded zero ASG failures.

**Diagnostic rule.** A compute environment that cannot *launch* pins the queue behind
it. To distinguish the two cases:

- Later CEs at `MaxSize` 0 with no activities → Batch never asked. The order-1 CE is
  broken, not full. Fix the order-1 CE.
- Later CEs carrying tasks → the earlier CE filled up and Batch spilled over correctly.

Being `ENABLED` and `VALID` tells you nothing about whether a compute environment can
actually acquire instances. Always read the ASG activity history.

## Spot bid price too low

When a Spot compute environment's `bidPercentage` is below the current market
requirement, the ASG records repeated failures with this shape:

```
Could not launch Spot Instances. SpotMaxPriceTooLow - Your Spot request price of
<bid> is lower than the minimum required Spot request fulfillment price of <market>.
Launching EC2 instance failed.
```

This produces an indefinite stall, not an error: the queue holds jobs in `RUNNABLE`,
`desiredvCpus` stays above zero, and nothing ever launches. The compute environment
remains `ENABLED` and `VALID` the whole time.

## maxvCpus is not a hard ceiling

Observed twice: total `RUNNING` vCPUs exceeded the sum of the queue's compute
environment `maxvCpus` values, and a single compute environment reached `desiredvCpus`
32 against a configured `maxvCpus` of 20.

Do not conclude "the queue is at its configured capacity limit" from `maxvCpus` alone.
Treat it as a target Batch works toward, not a boundary it cannot cross.

## minvCpus holds instances indefinitely

A compute environment with `minvCpus` above zero keeps instances registered when there
is no work at all. This is billed continuously and is invisible in job-level metrics,
because there are no jobs.

In one observed environment a compute environment left at `minvCpus: 1` accrued roughly
85 billed instance-hours across three successive instances over a 175-hour window, at a
weighted mean CPU utilisation of 0.497%. Spot reclamation replaced the instance twice
without ever reducing the held capacity, so cumulative billed hours cannot be attributed
to a single instance ID.

When reviewing a Batch configuration, flag any compute environment with `minvCpus > 0`
that has no steady job arrival rate. The signal to check is idle vCPUs held over time,
not job failures.

## The retryStrategy trap

A job definition can declare a generous retry budget that never applies. Consider:

```json
{
  "retryStrategy": {
    "attempts": 5,
    "evaluateOnExit": [
      { "onStatusReason": "Host EC2*", "action": "RETRY" }
    ]
  }
}
```

`attempts: 5` suggests five tries. But `evaluateOnExit` is evaluated in order and the
only rule matches host-level EC2 failures. An **application** error matches no rule, so
the job exits permanently after a **single** attempt despite the five-attempt budget.

This is invisible without reading the resolved `retryStrategy`, which requires
`batch:DescribeJobs`. When an investigation finds a job that failed once against a
multi-attempt budget, read `evaluateOnExit` before concluding that retries were
exhausted.

## Fair share scheduling: weight controls order, not total allocation

On a fair-share queue, `weightFactor` in the scheduling policy controls **which share
runs first** and **the instantaneous split under contention**. It does not control total
allocation when every share submits identical demand and all of that work eventually
runs.

Measured across a single 37-minute run of 176 jobs spread over 8 shares:

- **Early contention (first ~9 minutes).** The four lowest-weight shares held 43 of 62
  running slots — 69.4%. The extremes were 15 concurrent slots for the lowest-weight
  share against 2 for the highest, a 7.5:1 ratio.
- **Whole run.** Aggregate share-minutes equalised: every share landed between 12.2% and
  13.4% of total. The four lowest-weight shares took 50.9% against 49.1% for the four
  highest — a dead heat.

The mechanism is visible as waves: low-weight shares dominate first, then high-weight
shares jump to full occupancy while others drop to zero, then they rotate back. Fair
share equalises **weighted usage over time**.

**Consequence for investigation.** A single snapshot of running jobs per share can show
the exact opposite of the run's overall behaviour. One observed snapshot had the two
highest-weight shares holding 20 slots each while four other shares held zero. Never
conclude a fair-share misconfiguration from one sample — compare cumulative
share-minutes across the whole contention window.

To demonstrate lower weight receiving more *total* compute you need sustained
oversubscription where some work never runs at all.
