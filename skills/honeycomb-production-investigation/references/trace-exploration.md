# Trace Exploration Reference

Detailed guide to navigating and analyzing traces in Honeycomb, via the
MCP `get_trace` tool or the Honeycomb UI.

## Trace Structure

- **Trace**: Complete unit of work, often spanning multiple services
- **Span**: Single unit of instrumentation from one code location
- **Root span**: Top-level span (`is_root = true` or `trace.parent_id does-not-exist`)
- Standard fields: `name`, `service.name`, `duration_ms`, `trace.span_id`, `trace.trace_id`, `trace.parent_id`

## Using get_trace

### Parameters
- `environment_slug` (required): The environment to search in
- `trace_id` (required): The trace ID to fetch
- `view_mode`: Controls output detail level
  - `auto` (default): Smart collapsing — balances detail and readability
  - `compact`: Aggressive collapsing for very large traces
  - `full`: Show everything, including span events
  - `focused`: Show a specific span and its descendants (requires `focus_span_id`)
- `focus_span_id`: Span ID to focus on (used with `focused` view mode)
- `depth_limit`: Max depth from root (inclusive), limits output size
- `show_events`: Include span events (default: false for performance)
- `time_range`: How far back to search (default: 7 days). Use `"24h"`, `"7d"`, etc.

### Tips
- Start with `auto` view mode for most traces
- Use `compact` for traces with hundreds of spans
- Use `focused` + `focus_span_id` to zero in on a problematic subtree
- Set `show_events: true` when looking for error details or state changes
- Use `depth_limit` to see just the top-level structure of deep traces

## Trace Detail View (UI, 4 areas)

### 1. Trace Identification
- Unique trace ID, navigation controls, reload button
- Permalink for sharing

### 2. Trace Summary
- Metadata: span count, start timestamp, total duration
- Condensed waterfall: up to 6 depth levels with color coding
- Error highlighting on affected spans

### 3. Waterfall Representation
The main visualization showing span hierarchy and timing:
- **Horizontal bars**: Each bar is a span; width = duration; position = start time
- **Nesting**: Child spans indented under parents
- **Colors**: Default colored by `service.name` or `name`
- **Interactions**:
  - Click span to select and view details in sidebar
  - Collapse/expand by depth level
  - Collapse by ServiceName+Name combination
  - Zoom into subtrees (creates permalinkable view)
  - Search spans by field name or value
  - Customize visible fields in span labels

### 4. Trace Sidebar
Selected span details:
- All fields/attributes on the span
- Span events (timestamped annotations)
- Span links (cross-trace relationships)
- Minigraph (heatmap showing where this span falls in overall distribution)
- Filter actions: Add field as WHERE or GROUP BY to a new query

## What to Look For

### Performance Issues
- Spans with disproportionately long duration vs parent
- Sequential spans that could be parallelized
- Repeated similar spans (N+1 query patterns)
- Large gaps between child spans (missing instrumentation or idle time)

### Errors
- Operation spans with `error = true`, ERROR status, or low-cardinality error attributes
- Error spans near the root indicate top-level failures
- Error spans deep in the tree indicate dependency failures
- Full exception details may be on a trace-correlated Logs API event rather than the containing span
- Query exception event rows (`event.name=exception`, `exception.type exists`, `trace.trace_id exists`),
  then use the sampled trace ID with `get_trace`

### Instrumentation Gaps
- Gaps in the waterfall (time not accounted for by child spans)
- Missing service boundaries
- Spans without descriptive names or attributes
- Orphaned spans (no parent in the trace)

## Span Events and Correlated Log Events

Lightweight annotations attached to a span at a specific point in time (no duration).
- Visible in the trace sidebar when a span is selected
- Visible via `get_trace` when `show_events: true`
- Legacy OTel span events use `meta.annotation_type = "span_event"`, `meta.signal_type="trace"`,
  and the event name in `name`
- Logs API records emitted under an active span also appear as `meta.annotation_type="span_event"`,
  but use `meta.signal_type="log"`; their logical event name is usually in `event.name` and/or `body`
- Correlated log rows carry `trace.trace_id` and `trace.parent_id`; their `exception.*` fields
  remain on the event row and are not automatically hoisted onto the containing span
- Created by OTel `span.addEvent()`/equivalent or by a Logs API emit with active context

**MCP drill-down:** query the event row with `run_query`, include `trace.trace_id`, then call
`get_trace` with `show_events=true`. Do not expect the formatted `get_trace` annotation row to
contain every log attribute; use the original query sample for the exception payload.

## Span Links

Relationships between spans in different trace hierarchies.
- Use cases: async operations, fan-out/fan-in, cross-system correlation
- Fields: `meta.annotation_type = "link"`, `trace.link.span_id`, `trace.link.trace_id`
- Visible in trace sidebar; clickable to navigate to linked trace
