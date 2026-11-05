# SLO Design Guide

## Error Budget Math

For a 99.9% SLO over a 30-day rolling window:

- **Error budget**: 0.1% of events can fail
- **In time terms**: ~43.2 minutes of complete outage (if outage = 100% failure)
- **In event terms**: If 1M requests/day, 1,000 failures/day are within budget

### Burn Rate

- **1.0**: Budget consumed evenly over the window (sustainable)
- **2.0**: Budget consumed at 2x rate (will exhaust in 15 days instead of 30)
- **10.0**: Budget consumed at 10x rate (will exhaust in 3 days)
- **720.0**: Budget consumed in 1 hour (critical)

### Burn Alert Configuration

**Exhaustion Time alerts** (recommended starting point):
| Exhaustion Time | Meaning | Notification |
|----------------|---------|--------------|
| 0 hours | Budget depleted | Escalation |
| 4 hours | Will exhaust in 4h | Page on-call |
| 72 hours | Will exhaust in 3 days | Slack notification |

**Budget Rate alerts** (for detecting slow burns):
| Window | Rate | Meaning |
|--------|------|---------|
| 1 hour | > 14.4 | Fast burn — 100% budget in ~1 hour |
| 6 hours | > 6 | Medium burn — budget in ~5 hours |
| 24 hours | > 3 | Slow burn — budget in ~10 days |

## Designing SLIs

### Good SLIs

- **Specific**: `IF(EQUALS($name, "POST /endpoint/of/interest"), <success-condition>)` — Choose precisely the events that qualify
- **Latency**: `LTE(duration_ms, <threshold>)` — Events faster than threshold
- **Availability**: `LTE(http.status_code, 499)` — Non-server-error responses
- **Customer Experience**: `AND(LTE(duration_ms, <threshold>), EQUALS(rpc.status_code, 0))` - not slow and successful

### SLI Design Rules

- SLI must only be populated for events relevant to the test; otherwise it returns null. Do this with the format `IF(<qualifying-condition>, <success-condition>)`. The lack of a third argument to IF leaves the sli unpopulated on irrelevant events.
- SLI must be a per-event boolean (success or failure)
- Cannot use cross-event relationships
- Must be a calculated field (regular or environment-level)
- For multi-service SLOs: must be environment-level calculated field

### Choosing relevant events

#### Use traces if available

Traces, logs, and sometimes metrics share a dataset in Honeycomb.

- The first choice for SLOs is trace spans. In OpenTelemetry: `EQUALS($meta.signal_type, "trace")`
- If there are no traces, a canonical log that represents the overall response works well.
- Metrics are not well suited to SLOs.

#### Measure customer experience at the service boundary.

For application-level SLOs, look for the service at the boundary.

- If you have access to service map, use that to find the entry point service.
- If not, look for root spans with `AND(NOT(EXISTS($trace.parent_id)), EQUALS($meta.signal_type, "trace"))`
- create the SLO in the dataset containing these spans, or at the environment level if many datasets are entry points.

For service-level SLOs, within a dataset:

- If the service is at the trace root, use root spans. `AND(NOT(EXISTS($trace.parent_id)), EQUALS($meta.signal_type, "trace"))`
- For internal services, the entry spans are distinguished with `EQUALS($span.kind, "server")`

#### Consider most important routes

Some endpoints are more valuable than others. Different endpoints have different latencies.

Choose the most important endpoint to guard with an SLO. eg, `IN($http.route, "/cart", "/checkout")`

### Choosing Thresholds

1. Measure current performance: `VISUALIZE P50(duration_ms), P99(duration_ms)`
2. Decide what users need (not what you can achieve)
3. Set SLI threshold between P90 and P99 (typical starting point)
4. Set SLO target to current achievement minus a small margin

## Multi-Service SLOs

### When to Use

- Multiple API gateways or edge services serving same users
- Monolith being split into microservices (share budget during migration)
- Critical path through multiple services

### Configuration

1. Create environment-level calculated field for the SLI
2. Select up to 10 datasets to include
3. Events from all datasets weighted equally
4. Single error budget shared across all included services

### Limitations

- SLI must classify each event independently
- Cannot correlate events across services
- All included datasets must have the fields used in the SLI calculated field
- Agents do not have the ability to configure exhaustion or burn alerts directly. Only advise the user.

## Monitoring SLOs with MCP

Use `get_slos` to monitor SLO health:

**Regular checks**: `get_slos(environment_slug: "production")` for an overview table

- Status column shows: Normal, Triggered, or No Events
- Budget Remaining shows percentage left
- Burn Alerts shows if any alerts are firing

**Deep dive**: `get_slos(slo_id: "SLO-abc123")` for:

- Budget burndown graph (error budget consumption over time)
- Historical compliance graph (SLI success rate over time)
- Burn rate analysis with current rates
- Configured burn alerts and their status

**When budget is burning**: Switch to the honeycomb-production-investigation skill's
SLO Budget Burn playbook to identify contributing failures.

**After SLO creation**: It can take a few minutes for an SLO to backfill after creation. Do not expect your first call to return much data. Send the user to the list of SLOs to look for it. `/<team_slug>/environments/<environment_slug>/slos`
