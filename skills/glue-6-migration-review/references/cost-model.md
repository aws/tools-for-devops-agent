# Glue 6.0 Migration Cost Model

How to turn each legacy job's historical run performance into an estimated
current cost and an estimated Glue 6.0 cost. **All outputs are estimates** — they
are derived from published pricing and observed DPU-hours, not from a billed
invoice. Always state the assumptions and the region price used, and confirm the
current per-DPU-hour rate on the
[AWS Glue pricing page](https://aws.amazon.com/glue/pricing/) before finalizing.

## Billing basics

AWS Glue for Apache Spark bills per **DPU-hour**, per second, with a minimum
billed duration per run (the minimum differs by Glue version — Glue 2.0+ reduced
the minimum billing to 1 minute; 0.9/1.0 use a 10-minute minimum). A DPU is the
Glue processing unit; worker types map to DPUs as below.

| Worker Type | DPU per worker |
|---|---|
| Standard (legacy) | 1 DPU (2 executors) |
| G.1X | 1 DPU |
| G.2X | 2 DPU |
| G.4X | 4 DPU |
| G.8X | 8 DPU |
| G.025X (streaming, small) | 0.25 DPU |

> Confirm the mapping for newer/region-specific worker types before relying on
> it; the control-plane `WorkerType` plus `NumberOfWorkers` (or `MaxCapacity` for
> DPU-based 0.9/1.0/2.0 jobs) determines the DPUs in flight.

## Step A — Compute historical DPU-hours per job

For each run in the window (from `glue.GetJobRuns`):

```
run_DPU_hours = DPUs_in_flight × (ExecutionTime_seconds / 3600)
```

- Prefer the run's reported `DPUSeconds` when present:
  `run_DPU_hours = DPUSeconds / 3600`.
- Otherwise derive `DPUs_in_flight` from `WorkerType` × `NumberOfWorkers` (or
  `MaxCapacity` for DPU-based jobs), and use `ExecutionTime` (billed seconds,
  which already reflects the per-version minimum).
- Auto-scaling jobs (`--enable-auto-scaling`) bill on actual DPU-seconds used —
  always prefer `DPUSeconds` for these; the worker-count derivation overestimates.

Sum across all runs in the window:

```
current_cost = total_DPU_hours × price_per_DPU_hour(region)
```

## Step B — Project the Glue 6.0 cost

Glue 6.0 was announced with an approximately **30% lower price** than prior Glue
for Spark versions. Model the projected cost two ways and present both so the
estimate is honest about its bounds:

1. **Price-only (conservative, DPU-hours held constant):**
   ```
   glue6_cost_price_only = current_cost × (1 − price_reduction_fraction)
   ```
   Use `price_reduction_fraction = 0.30` as the baseline unless the live pricing
   page indicates otherwise for the region.

2. **Price + runtime improvement (optimistic band):** Glue 6.0's newer Spark
   runtime can reduce `ExecutionTime` for some workloads. Only apply a runtime
   improvement factor if there is a defensible basis for the specific workload;
   otherwise hold DPU-hours constant and note the potential additional upside
   qualitatively rather than inventing a number.

```
estimated_savings = current_cost − glue6_cost
```

## Presentation rules

- Report the **price-only** figure as the headline estimate (most defensible).
- Show the per-DPU-hour price and region used, the window length, and the run
  count behind each row.
- Round money to cents and DPU-hours to one decimal.
- If a job had **no runs** in the window, mark it `NOT_ASSESSED` for cost and say
  so — do not assume a cost.
- Add a totals row summing current cost, Glue 6.0 cost, and savings across all
  assessed jobs.
- Never present an estimate as a guaranteed bill. Recommend the user validate
  against Cost Explorer (`ce.GetCostAndUsage`, filtered to the Glue service and
  the job's cost-allocation tags) for the authoritative historical spend.

## Worked example (illustrative only)

A `glueetl` job on Glue 4.0, G.2X × 10 workers (20 DPU), ran 30 times last month
averaging 12 minutes billed each:

```
total_DPU_hours = 20 DPU × (12/60 h) × 30 runs = 120 DPU-hours
current_cost    = 120 × $price_per_DPU_hour
glue6_cost      = current_cost × 0.70        # ~30% lower
savings         = current_cost × 0.30
```

Substitute the live regional price for `$price_per_DPU_hour`.
