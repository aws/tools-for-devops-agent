# Calculation Rules

These rules are mandatory for the LLM.

### 1. Current-day total

For any usage metric, an instant value queried during a UTC day means:

- total accumulated since `00:00:00 UTC` of the current day up to query time

Example:

- `sum(cx_data_usage_units)` at `2026-03-12 15:00 UTC` means total units consumed on `2026-03-12` from midnight until `15:00 UTC`

### 2. Completed-day total

For a completed UTC day, the correct daily total is:

- the last value observed before the next midnight UTC

Safe interpretation:

- use the end-of-day sample when available
- if end-of-day sampling is incomplete, the maximum value observed within that UTC day is usually a safe fallback because the series represent cumulative daily snapshots

Default rule:

- for comparisons, averages, trend analysis, and anomaly detection, usually exclude the current UTC day because it is partial
- only include the current UTC day when the user explicitly asks for "today so far", "current status", or another partial-day view
- if the current UTC day is excluded, say so explicitly and explain that it was excluded because it is partial and would distort completed-day comparisons

### 3. Delta within the same day

To compute a delta between two times on the same UTC day:

- `delta = value_at_t2 - value_at_t1`

Constraints:

- both timestamps must be inside the same UTC day
- both values must use the same label scope
- if the subtraction becomes negative, check whether a UTC midnight reset was crossed or the wrong label set was used

### 4. Delta across days

Never subtract two arbitrary samples across a UTC midnight boundary as if the series were continuous.

Instead:

- compute each day independently
- compare completed-day totals

Good:

- compare `total(2026-03-11)` vs `total(2026-03-10)`

Bad:

- `value(2026-03-11 00:05 UTC) - value(2026-03-10 23:55 UTC)`

### 5. Average daily usage

To compute average daily usage across multiple days:

- first compute one completed-day total per UTC day
- then average those daily totals

Do not:

- average intra-day snapshots directly
- average mixed partial-day and full-day samples unless the user explicitly asked for "average so far"

### 6. Remaining daily plan

Use:

- `remaining_units = max(plan_units_per_day - current_usage_units, 0)`

Where:

- `plan_units_per_day = cx_data_plan_units_per_day`
- `current_usage_units = sum(cx_data_usage_units)`

Important:

- `cx_data_plan_units_per_day` is a snapshot metric, so use the plan value that was valid at the time of the comparison
- if the plan changes mid-day, do not assume the earlier and later parts of the day had the same quota snapshot

### 7. Plan-consumption percentage

Use:

- `consumed_percent = 100 * current_usage_units / plan_units_per_day`

If plan is missing or zero:

- do not invent a percentage
- say that the plan quota metric is unavailable

### 8. Overage / PAYG

Use:

- `cx_data_usage_payg_units`

Interpretation:

- the amount of daily usage that exceeded the included daily plan

If the user asks for "did we exceed the plan?":

- compare `sum(cx_data_usage_units)` with `cx_data_plan_units_per_day`
- if available, also report `cx_data_usage_payg_units` as the overage amount

