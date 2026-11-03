# Board Layout Reference

## The panels array

`create_board` takes a single `panels` array. Each panel must have a `type` field:

| type | Required fields | Optional fields |
|------|----------------|-----------------|
| `"query"` | `type`, `id` (query run PK like `QR-abc123`) | `name`, `description`, `chart_type`, `display_style`, `size` |
| `"slo"` | `type`, `id` (SLO PK) | `size` |
| `"text"` | `type`, `content` (Markdown, max 10000 chars) | `size` |

Panels appear on the board in the order listed. Order matters — put the most important context first.

## Grid system

The board uses a **12-column grid**. Panels wrap to the next row when total width exceeds 12.

Use `size: { "width": N, "height": N }` to control each panel:
- `width`: 1–12 columns (default fills available space)
- `height`: rows (default varies by panel type)

### Layout examples

**Stat row** — three stats side-by-side at the top:
```json
[
  { "type": "query", "id": "QR-...", "name": "Request Rate", "chart_type": "stat", "size": { "width": 4 } },
  { "type": "query", "id": "QR-...", "name": "Error Rate",   "chart_type": "stat", "size": { "width": 4 } },
  { "type": "query", "id": "QR-...", "name": "P95 Latency",  "chart_type": "stat", "size": { "width": 4 } }
]
```

**Full-width heatmap**:
```json
[{ "type": "query", "id": "QR-...", "name": "Latency Distribution", "size": { "width": 12, "height": 3 } }]
```

**Two graphs side-by-side**:
```json
[
  { "type": "query", "id": "QR-...", "name": "Request Rate", "size": { "width": 6 } },
  { "type": "query", "id": "QR-...", "name": "Error Rate",   "size": { "width": 6 } }
]
```

**SLO widget beside a summary graph**:
```json
[
  { "type": "slo",   "id": "SLO-...",  "size": { "width": 4 } },
  { "type": "query", "id": "QR-...",   "size": { "width": 8 } }
]
```

There's no one right layout. Design it to tell a story — context at the top, most important signals next, breakdowns below.

### Recommended layout from top to bottom

#### Row 1: Introduction — text panel + primary SLO

Place a text panel (width 8). If there is a primary SLO, place it alongside (width 4). The text panel should describe the board's purpose, link to relevant code or docs, and note what to watch for.

```
┌──── text (8) ─────┬── SLO (4) ──┐
```

#### Row 2: Other SLOs at 1/3 width

If there are additional relevant SLOs, place them in a row at width 4 each (up to 3 across).

```
├── SLO (4) ──┬── SLO (4) ──┬── SLO (4) ──┤
```

#### Row 3: Stat panels at 1/4 width

Key single-number metrics (P95 latency, error rate %, request count, unique users) work well as `chart_type: "stat"` at width 3, fitting 4 across.

```
├─ stat (3) ─┬─ stat (3) ─┬─ stat (3) ─┬─ stat (3) ─┤
```

#### Remaining rows: Queries with explanatory text

For the main query panels, use width 6 (two across) or width 12 (full width).

For particularly interesting or non-obvious queries, add a narrow text panel (width 3-4) next to the query (width 8-9) on the same row. Use the text panel to explain what to look for, what normal looks like, or what actions to take if values change.

```
├── text (3) ──┬──── query (9) ────────────┤
├──── query (6) ─────┬──── query (6) ──────┤
```

Not every query needs an explanatory text panel — just the ones where the meaning isn't obvious from the name alone, or where there's useful context about thresholds or expected behavior.

### Height tips

- Keep heights consistent within a row for visual alignment
- SLO panels work well at height 4
- Stat panels work well at height 4
- Simple chart-only query panels work at height 4
- Query panels with two graphs and `display_style: "chart"` need height 7
- For queries with `display_style: "combo"`, if they have no breakdowns, add 1 to height.
- For queries with `display_style: "combo"` and a breakdown, add 3-5 height units, depending on how many rows the table needs.
- Text panels for row headers work at height 1; explanatory text panels next to queries should match the query panel height
- Heatmap panels work at height 5

## Chart types

| value | Description |
|-------|-------------|
| `"default"` | Honeycomb chooses (correct for heatmaps; use when unsure) |
| `"none"` | Table only |
| `"line"` | Line chart |
| `"stacked"` | Stacked area chart |
| `"bar"` | Bar timeseries |
| `"stat"` | Single value / stat panel |
| `"categorical_bar"` | Categorical bar chart |
| `"pie"` | Pie chart |

Guidance:
- `"default"` for heatmaps — do not override this
- `"stat"` for single-number highlights (error rate %, unique users, P95 value)
- `"line"` for time-series comparisons and trends
- `"pie"` or `"categorical_bar"` for categorized breakdowns
- When there's a GROUP BY, `"combo"` display style shows both graph and table

## Display styles

| value | Description |
|-------|-------------|
| `"chart"` | Visualization only (tool default) |
| `"table"` | Data table only |
| `"combo"` | Both chart and table |

Use `"combo"` when there's a GROUP BY / breakdown — you want to see both the graph and the ranked table. Use `"chart"` for clean time series. Stat panels (`chart_type: "stat"`) pair with `"chart"` display.

## Preset filters

`preset_filters` creates interactive dropdown controls on the board — viewers can filter all graphs by a column value without editing queries. Maximum 5.

```json
{
  "preset_filters": [
    { "column": "http.route",       "alias": "Route" },
    { "column": "app.region",       "alias": "Region" },
    { "column": "app.account_tier", "alias": "Account Tier" }
  ]
}
```

Good candidates: route, region, account tier, deployment version, user type. Especially useful for boards shared across teams or used during incidents. If the service has meaningful segmentation columns, suggest preset filters.

## Tags

```json
{ "tags": ["team:platform", "tier:critical"] }
```

Use `list_boards` to see existing tags and follow those formats.

**Format rules:**
- **Keys**: lowercase letters only, max 32 chars, no hyphens
- **Values**: start with lowercase, can contain letters/numbers/`-`/`/`, max 128 chars
- ❌ WRONG: `"user-facing:true"` (hyphen in key)
- ✅ RIGHT: `"userfacing:true"`, `"tier:critical"`

## Duplicate query trick

Honeycomb rejects duplicate queries on a board. To show the same data in two formats (e.g., stat + line), add a trivially-true filter to one of them — for example `service.name exists`. Results are identical but the queries are technically different.

Keep the timeframe consistent between both panels so the numbers agree.
