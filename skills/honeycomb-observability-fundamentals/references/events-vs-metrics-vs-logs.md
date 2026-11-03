# Events vs Metrics vs Logs: A Detailed Comparison

This reference shows the same operation — processing an HTTP checkout request — instrumented
three ways. The instrumentation effort is roughly equivalent; the analytical power is not.

## The Operation

A checkout endpoint that:
1. Receives a POST request from a user
2. Validates the cart
3. Charges a payment provider
4. Returns success or failure

## As a Structured Event (Span)

### Go
```go
func handleCheckout(w http.ResponseWriter, r *http.Request) {
    ctx, span := tracer.Start(r.Context(), "checkout")
    defer span.End()

    span.SetAttributes(
        attribute.String("user.id", getUserID(r)),
        attribute.String("tenant.name", getTenant(r)),
        attribute.String("plan.tier", getPlanTier(r)),
        attribute.String("deployment.version", buildVersion),
        attribute.Float64("cart.total", cart.Total),
        attribute.Int("cart.item_count", len(cart.Items)),
        attribute.String("payment.provider", "stripe"),
        attribute.Bool("feature.new_checkout_flow", isNewFlow(r)),
    )

    result, err := processCheckout(ctx, cart)
    if err != nil {
        span.SetStatus(codes.Error, err.Error())
        span.SetAttributes(attribute.String("error.type", errorType(err)))
    }
    span.SetAttributes(attribute.Bool("checkout.success", err == nil))
}
```

### Python
```python
@tracer.start_as_current_span("checkout")
def handle_checkout(request):
    span = trace.get_current_span()
    span.set_attribute("user.id", request.user.id)
    span.set_attribute("tenant.name", request.tenant.name)
    span.set_attribute("plan.tier", request.user.plan_tier)
    span.set_attribute("deployment.version", BUILD_VERSION)
    span.set_attribute("cart.total", cart.total)
    span.set_attribute("cart.item_count", len(cart.items))
    span.set_attribute("payment.provider", "stripe")
    span.set_attribute("feature.new_checkout_flow", is_new_flow(request))

    try:
        result = process_checkout(cart)
        span.set_attribute("checkout.success", True)
    except CheckoutError as e:
        span.set_status(StatusCode.ERROR, str(e))
        span.set_attribute("error.type", type(e).__name__)
        span.set_attribute("checkout.success", False)
```

### Node.js
```javascript
async function handleCheckout(req, res) {
  return tracer.startActiveSpan("checkout", async (span) => {
    span.setAttribute("user.id", req.user.id);
    span.setAttribute("tenant.name", req.tenant.name);
    span.setAttribute("plan.tier", req.user.planTier);
    span.setAttribute("deployment.version", BUILD_VERSION);
    span.setAttribute("cart.total", cart.total);
    span.setAttribute("cart.item_count", cart.items.length);
    span.setAttribute("payment.provider", "stripe");
    span.setAttribute("feature.new_checkout_flow", isNewFlow(req));

    try {
      const result = await processCheckout(cart);
      span.setAttribute("checkout.success", true);
    } catch (err) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
      span.setAttribute("error.type", err.constructor.name);
      span.setAttribute("checkout.success", false);
    } finally {
      span.end();
    }
  });
}
```

### What you can query

From this single event, at any time in the future, without changing code:

- `P99(duration_ms) GROUP BY tenant.name` — which tenant is slow?
- `COUNT WHERE checkout.success = false GROUP BY error.type` — what errors are failing checkouts?
- `HEATMAP(duration_ms) WHERE user.id = "abc123"` — what's this user's experience?
- `AVG(cart.total) WHERE checkout.success = true GROUP BY plan.tier` — revenue by tier
- `COUNT GROUP BY deployment.version, checkout.success` — did the new deploy break checkouts?
- **BubbleUp**: select the slow region → BubbleUp automatically finds that `deployment.version=2.3.1`
  AND `feature.new_checkout_flow=true` AND `tenant.name=acme` are overrepresented in slow requests

## As Metrics

### Go (Prometheus-style)
```go
var (
    checkoutTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{Name: "checkout_total"},
        []string{"status", "payment_provider"},
    )
    checkoutDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{Name: "checkout_duration_seconds"},
        []string{"status"},
    )
)

func handleCheckout(w http.ResponseWriter, r *http.Request) {
    start := time.Now()
    result, err := processCheckout(r.Context(), cart)
    duration := time.Since(start).Seconds()

    status := "success"
    if err != nil {
        status = "failure"
    }
    checkoutTotal.WithLabelValues(status, "stripe").Inc()
    checkoutDuration.WithLabelValues(status).Observe(duration)
}
```

### What you can query

- `rate(checkout_total{status="failure"})` — are errors increasing?
- `histogram_quantile(0.99, checkout_duration_seconds)` — P99 latency

### What you can't query

- Which user is affected? (no `user.id` label — too many unique values)
- Which tenant? (could add, but each new label dimension multiplies time series)
- Is the new checkout flow causing this? (can't add `feature.new_checkout_flow` without
  doubling time series count)
- What's the cart value for failed checkouts? (histograms can't carry additional context)
- **BubbleUp equivalent**: not possible. You'd need to pre-define every comparison.

### The cardinality trap

Adding `user.id` as a Prometheus label with 100,000 users creates 100,000 time series
*per metric*. With 10 metrics, that's 1 million time series. Add `tenant.name` (1,000
values) and it's 100 million. This is the curse of dimensionality — the reason metrics
systems force you to keep labels low-cardinality, which strips away the context you need
most during incidents.

## As Logs

### Go (structured logging with slog)
```go
func handleCheckout(w http.ResponseWriter, r *http.Request) {
    start := time.Now()
    result, err := processCheckout(r.Context(), cart)
    duration := time.Since(start)

    logger.Info("checkout completed",
        "user_id", getUserID(r),
        "tenant", getTenant(r),
        "plan_tier", getPlanTier(r),
        "cart_total", cart.Total,
        "item_count", len(cart.Items),
        "duration_ms", duration.Milliseconds(),
        "success", err == nil,
        "error", err,
    )
}
```

### What you can query (with a good log backend)

With structured logging and a capable backend, you can search and filter:
- `user_id="abc123" AND success=false` — did this user's checkout fail?
- `tenant="acme" AND duration_ms > 5000` — slow checkouts for Acme

### What's harder or impossible

- **Aggregation**: P99 latency across all checkouts requires scanning every log line.
  Log backends that support this are essentially reinventing column stores.
- **BubbleUp equivalent**: No log backend automatically compares distributions across
  all fields to find differentiators. You'd manually query each field one at a time.
- **Correlation across services**: Logs from different services aren't automatically
  linked. You need to add and propagate a correlation ID (which is what trace context is).
- **Sampling-aware counts**: If you sample logs, counts are off. OTel spans carry
  sampling rate metadata so Honeycomb can adjust automatically.

## Summary

| Capability | Structured Event (Span) | Metric | Structured Log |
|---|---|---|---|
| High-cardinality fields (user.id) | Native, zero cost | Cardinality explosion | Possible but hard to aggregate |
| Aggregate queries (P99, COUNT) | Native | Native | Expensive full scan |
| Arbitrary GROUP BY at query time | Any attribute | Only pre-defined labels | Limited by backend |
| BubbleUp (auto-diff outliers) | Native | Not possible | Not possible |
| Cross-service correlation | Trace context | Manual | Manual correlation IDs |
| Duration tracking | Built in (span start/end) | Manual histogram | Manual timestamps |
| Sampling-aware | Automatic adjustment | N/A | Manual or absent |

The takeaway: the same `span.SetAttribute("user.id", userID)` call that produces a
structured event could instead be a metric label (cardinality bomb) or a log field
(hard to aggregate). Same effort, vastly different analytical power.
