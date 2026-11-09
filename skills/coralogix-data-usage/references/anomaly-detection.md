# Anomaly Detection

The LLM should support anomaly detection, but it must do so conservatively and with explicit comparison logic.

### Scope

For anomaly detection, focus on actual usage metrics only:

- `cx_data_usage_units`
- `cx_data_usage_bytes_total`
- `cx_data_usage_tokens_total`
- `cx_system_data_sent_bytes_total`
- `cx_infrastructure_monitoring_events_total`
- `cx_data_usage_samples_total`

Exclude these from normal usage-anomaly detection:

- `cx_data_plan_units_per_day`
- `cx_data_usage_payg_units`

Reason:

- `cx_data_plan_units_per_day` is a plan snapshot, not usage
- `cx_data_usage_payg_units` is derived overage state, not the primary usage signal

### Default comparison strategy

The default anomaly strategy should be completed-day based.

The LLM should usually:

- exclude the current UTC day because it is partial
- compare completed UTC days to other completed UTC days
- prefer seasonality-aware baselines when the customer has weekday/weekend patterns

Only use current-day anomaly analysis when the user explicitly asks for it.

### Metric selection by user intent

Pick the anomaly metric that matches the user's requested concept:

- units anomaly -> `cx_data_usage_units`
- bytes anomaly -> `cx_data_usage_bytes_total`
- AI evaluation tokens anomaly -> `cx_data_usage_tokens_total`
- system egress anomaly -> `cx_system_data_sent_bytes_total`
- infra events anomaly -> `cx_infrastructure_monitoring_events_total`
- metrics samples anomaly -> `cx_data_usage_samples_total`

The LLM should not silently switch metric families. Use the [default concept-to-metric mapping](metrics.md#default-concept-to-metric-mapping) if the user is vague.

### Recommended anomaly method

When the user asks for anomalies, the LLM should describe both:

- whether an anomaly exists
- what comparison method would best explain it

Recommended default method:

- build a baseline from comparable completed UTC days
- prefer same-weekday comparisons when customer traffic is seasonal
- if weekday seasonality is not relevant or history is limited, use a recent completed-day baseline
- compare the selected day to the baseline in relative and absolute terms

Because there are no fixed thresholds in this document:

- the LLM should avoid hard-coded anomaly thresholds
- the LLM should explain that anomaly judgment depends on historical variability

### Root-cause breakdown order

When an anomaly is found, the LLM should break it down in this order:

- `measurement_type`
- `pillar`
- `entity_type`
- `priority`
- `feature_group_id`
- `feature_id`
- `application_name`
- `subsystem_name`

The goal is to explain not just that usage changed, but which slice of usage changed.

### What the LLM should suggest

The LLM should suggest the most useful next comparison for the specific anomaly.

Examples:

- if units are anomalous, suggest checking whether the increase is concentrated in a specific `measurement_type`, `priority`, or `feature_group_id`
- if bytes are anomalous, suggest checking whether the spike is isolated to one `pillar` or `entity_type`
- if AI tokens are anomalous, suggest checking whether one evaluator-related slice drove the increase
- if seasonality may matter, suggest comparing against equivalent weekdays instead of adjacent calendar days

### Plan changes

Plan changes are not usage anomalies by default.

The LLM should treat plan changes as:

- expected state changes unless they happen unusually often

This means:

- do not flag a single jump in `cx_data_plan_units_per_day` as a usage anomaly
- if the user asks about repeated or frequent plan changes, the LLM may describe that pattern as unusual state behavior

### Partial-day caution

If the user asks for anomaly detection including today:

- clearly state that the current UTC day is partial
- compare today-so-far only against historical values from the same point-in-day whenever possible
- make clear that a partial-day anomaly is less reliable than a completed-day anomaly

### Suggested language

The LLM should use language like:

- "Compared with recent completed UTC days, this looks unusual."
- "This appears to be driven mainly by `measurement_type=...` and `feature_group_id=...`."
- "Because today is still in progress, this should be treated as a provisional anomaly assessment."
- "This may reflect seasonality, so a same-weekday comparison is more reliable than a simple day-over-day comparison."

