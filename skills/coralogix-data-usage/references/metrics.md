# Metric Naming In Queries

The exporter defines OTLP metric names such as `cx_data_usage` and `cx_data_usage_units`.

When these metrics are queried through Prometheus-style naming, the LLM must distinguish between:

- raw usage metrics that should be queried with the `_total` suffix
- metrics that should be queried without `_total`, even if they may still represent current-day accumulated values

Metrics that should use `_total` in Prometheus-style queries:

- `cx_data_usage_bytes_total`
- `cx_data_usage_tokens_total`
- `cx_system_data_sent_bytes_total`
- `cx_infrastructure_monitoring_events_total`
- `cx_data_usage_samples_total`

Metrics that should not use `_total`:

- `cx_data_usage_units`
- `cx_data_plan_units_per_day`
- `cx_data_usage_payg_units`

Important:

- `cx_data_usage_bytes_total` is the Prometheus-style query name for the exported metric `cx_data_usage`
- `cx_data_usage_units` stays `cx_data_usage_units`; it does not become `cx_data_usage_units_total`
- `cx_data_usage_units` still behaves like the other current-day accumulated usage metrics: it increases during the UTC day and resets at midnight UTC
- `cx_data_plan_units_per_day` is snapshot-like and should not use `_total`
- `cx_data_usage_payg_units` should also be queried without `_total`

### 1. `cx_data_usage_units`

Meaning:

- the canonical daily billable usage in units

Use when the user asks:

- how many units were consumed
- how much of the daily plan was used
- which pillar, feature, priority, or entity type consumed the most billable usage

Notes:

- this is the main metric for billing-style questions
- raw measurements may differ, but units are the normalized billing view
- the metric is exported with the usage dimensions of each underlying usage record, so it can be broken down by labels

### 2. `cx_data_plan_units_per_day`

Meaning:

- the customer's current daily plan quota in units

Use when the user asks:

- what is the daily plan
- what percentage of the plan was consumed
- how many units remain in the plan

Notes:

- this is exported as a snapshot-style metric
- each data point represents the daily plan that is in effect at that moment
- in the current implementation it is not exported with detailed breakdown labels like pillar or feature

Plan snapshot semantics:

- if a team starts the UTC day with a 50-unit daily plan, `cx_data_plan_units_per_day` will continuously report `50`
- if the plan is increased at `16:00 UTC` to `100` units per day, `cx_data_plan_units_per_day` will jump from `50` to `100`
- unlike cumulative usage metrics, this metric does not accumulate during the day and does not require delta calculations
- when answering "what was the plan at time T?", use the value of `cx_data_plan_units_per_day` at time `T`
- when answering "what is the current daily plan?", use the latest value of `cx_data_plan_units_per_day`

### 3. `cx_data_usage_payg_units`

Meaning:

- the customer's daily overage usage in units

Use when the user asks:

- how much PAYG / overage was consumed today
- how much usage exceeded the daily plan

Notes:

- this is only meaningful when PAYG is enabled
- in the current implementation it is not exported with detailed breakdown labels

### 4. `cx_data_usage`

Meaning:

- processed data size in bytes

Use when the user asks:

- how many processed bytes were consumed
- how raw processed bytes break down by pillar, entity type, priority, or feature

Notes:

- this is a raw measurement metric
- use it for byte-level analysis, not as the final answer for billing unless the user explicitly wants bytes

### 5. `cx_data_usage_tokens`

Meaning:

- AI evaluation tokens only

Use when the user asks:

- how many AI evaluation tokens were used
- which evaluators or AI-related traffic generated token usage

Notes:

- in current exporter behavior this corresponds to `measurement_type=evaluation`
- at the time of writing, this metric is only about AI evaluation tokens
- at the time of writing, this metric does not represent Olly tokens
- use `cx_data_usage_units` if the question is about how those tokens affected billing or plan consumption

### 6. `cx_system_data_sent`

Meaning:

- system egress bytes

Use when the user asks:

- how much system data was sent
- how much egress traffic was generated

Notes:

- this is a raw egress metric
- it is not the canonical source for plan-consumed units

### 7. `cx_data_usage_samples`

Meaning:

- processed metric samples

Use when the user asks:

- how many metric samples were processed

Notes:

- this is a raw measurement metric
- use `cx_data_usage_units` for billing-style answers

### 8. `cx_infrastructure_monitoring_events`

Meaning:

- infrastructure monitoring event count

Use when the user asks:

- how many infra monitoring events were ingested

Notes:

- depending on the producer path, the associated label may appear as `measurement_type=infra_monitoring_ingress_events` or as the more generic events family
- treat both as the same business concept for customer explanations

## Default Concept-To-Metric Mapping

Use these defaults when the user is vague:

- billing / plan usage / consumption / overage -> `cx_data_usage_units`, plus `cx_data_plan_units_per_day` and `cx_data_usage_payg_units` when relevant
- processed bytes / data volume / ingested data -> `cx_data_usage_bytes_total`
- AI evaluation tokens / evaluations -> `cx_data_usage_tokens_total`
- system bytes / egress -> `cx_system_data_sent_bytes_total`
- infra events -> `cx_infrastructure_monitoring_events_total`
- metric samples -> `cx_data_usage_samples_total`

Important token-scope rule:

- at the time of writing, `cx_data_usage_tokens_total` means AI evaluation tokens only
- do not use `cx_data_usage_tokens_total` for Olly tokens unless the metric definition changes in the future

If the user asks for both raw usage and billing effect, answer with both:

- raw measurement metric for scale
- `cx_data_usage_units` for billing impact

