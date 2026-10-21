# PromQL query patterns

Use these patterns with `query_promql_range`, which returns a series over a window, and `query_promql_instant`, which returns one value per series at a moment. Pass `time` to `query_promql_instant` to pick the moment. Replace `checkout` with the service from the investigation.

## Range query settings

- `step`: about 20 points per series. Use `3m` for one hour, `20m` for six hours, `1h` for one day and `8h` for one week.
- `limit`: the samples kept per series, from 1 to 200.
- Keep the number of series small with `sum by (...)` or `topk(10, ...)`. The tool truncates large results.

## Span metrics

Coralogix Span Metrics turn spans into request, error and duration metrics. Coralogix documents these names and labels:

| Metric | Labels |
|---|---|
| `calls_total` | `service_name`, `span_name`, `span_kind`, `status_code`, `http_method` |
| `duration_ms_bucket`, `duration_ms_sum`, `duration_ms_count` | The same labels; buckets also have `le` |
| `db_calls_total` | `service_name`, `span_name`, `status_code`, `db_system`, `db_namespace`, `db_operation_name`, `db_collection_name` |
| `db_duration_ms_bucket`, `db_duration_ms_sum`, `db_duration_ms_count` | The same labels; buckets also have `le` |

Durations are in milliseconds.

### Check the label values first

```
count by (span_kind, status_code) (last_over_time(calls_total{service_name="checkout"}[1h]))
```

The OpenTelemetry span metrics connector usually writes `status_code="STATUS_CODE_ERROR"` for failed spans, and `span_kind="SPAN_KIND_SERVER"` or `span_kind="SPAN_KIND_CLIENT"`. Use the values this query returns. To list the services, run `count by (service_name) (last_over_time(calls_total[1h]))`.

If `calls_total` returns nothing, the account may not use Span Metrics or may use other metric names. Search for them:

```
count by (__name__) ({__name__=~".*calls.*|.*duration.*_bucket"})
```

### Request rate per operation

```
sum by (span_name) (rate(calls_total{service_name="checkout", span_kind="SPAN_KIND_SERVER"}[5m]))
```

### Error ratio

```
sum(rate(calls_total{service_name="checkout", status_code="STATUS_CODE_ERROR"}[5m]))
/
sum(rate(calls_total{service_name="checkout"}[5m]))
```

To find the failing operation, use `sum by (span_name)` on both sides.

### Latency percentiles

```
histogram_quantile(0.95, sum by (le) (rate(duration_ms_bucket{service_name="checkout"}[5m])))
```

For each operation, replace `sum by (le)` with `sum by (le, span_name)`.

### Downstream calls

Client spans are the calls the service makes to other services:

```
histogram_quantile(0.95, sum by (le, span_name) (rate(duration_ms_bucket{service_name="checkout", span_kind="SPAN_KIND_CLIENT"}[5m])))
```

### Database calls

Latency per database operation:

```
histogram_quantile(0.95, sum by (le, db_system, db_operation_name) (rate(db_duration_ms_bucket{service_name="checkout"}[5m])))
```

Failed database calls:

```
sum by (db_system, db_operation_name) (rate(db_calls_total{service_name="checkout", status_code="STATUS_CODE_ERROR"}[5m]))
```

## Baselines

Add `offset` inside the selector to read an earlier period. This query compares the request rate with the same time one day earlier:

```
sum(rate(calls_total{service_name="checkout"}[5m]))
/
sum(rate(calls_total{service_name="checkout"}[5m] offset 1d))
```

A result of 2 means twice the rate of one day earlier. Use `offset 1w` for weekly patterns. With `query_promql_instant`, set `time` to the alert time to read the values at the start of the incident.

## Infrastructure and other metrics

Metric names depend on how the account collects metrics, for example through the OpenTelemetry Collector, Prometheus or CloudWatch metric streams. Search by keyword:

```
count by (__name__) ({__name__=~".*cpu.*"})
```

Also try `.*memory.*`, `.*restart.*` or the name of the AWS service. Read a few series to see the labels of a metric:

```
topk(3, last_over_time(<metric name>[10m]))
```

Then rank the workloads by that metric:

```
topk(10, max by (<workload label>) (max_over_time(<metric name>[5m])))
```

## Coralogix alerts as metrics

If the team turned on alert aggregation in Coralogix, the `cx_alerts` metric records alert firings. This query shows which alerts fired in the last hour, which helps find related alerts:

```
sum by (alert_def_name, alert_def_priority) (max_over_time(cx_alerts{alert_status="Triggered"}[1h]))
```

No result means that no alert fired in the window or that alert aggregation is off.
