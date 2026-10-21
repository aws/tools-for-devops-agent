---
name: coralogix-spans
description: Span-specific concepts, fields, duration handling, and investigation patterns. Load when you need to explore spans in your investigation or to answer a question about spans. For service-level error rate, latency percentiles, throughput, or health, load the `service-catalog` skill instead — it is the pre-aggregated path for those; use this skill when you need individual traces, span attributes, or span-level detail the catalog does not expose. Always load the `dataprime` skill together with this one before writing any query.
metadata:
  author: coralogix
  version: 1.0.0
  summary: Span-specific concepts, fields, duration handling, and investigation patterns. Load when you need to explore spans in your investigation or to answer a question about spans. For service-level error ra
  tier: partner-managed
  agent_types: GENERIC
---

# Spans Skill - Analyzing spans via Coralogix

This skill describes how to discover and analyze spans using your available tools.

## Objectives
- Use the available tools to help the user find the observability data they need
- Summarize potential issues or root causes based on your analysis
- After conducting your investigation, suggest next steps on how to proceed.

> **Note**: Retrieving the data is quick, no need to ask the user to wait.

## Core Workflow

### Step 1: Understand the User's Request
Carefully analyze what the user is asking for. Identify the key entities, time frames, and the type of information they need. Determine whether they are looking for specific spans, latency analysis, service dependencies, or root cause investigation.

### Step 2: Identify the Relevant Data
Before writing any query, think about what data sources and fields could answer the user's question. Consider which span fields, labels, or metadata would be most relevant. Do not assume you know the field names — exact `$d.*` attribute names depend on the instrumentation and can differ across tenants, so verify `$d` fields with a sample query (or `search_for_fields`) before assuming they exist.

### Step 3: Discover Fields (Only When Needed)
Field discovery is only required for customer-specific fields. Standard fields are always available and should be used directly.

**Standard fields that are ALWAYS available (no discovery needed):**
- `$m.timestamp` - The span timestamp
- `$m.duration` - The span duration in microseconds
- `$l.applicationName` - The application name (environment/service identifier)
- `$l.subsystemName` - The subsystem name (environment/service identifier)
- `$l.serviceName` - The service name (logical service unit)
- `$l.operationName` - The operation name (span title)
- `$d.traceID` - The trace ID
- `$d.spanID` - The span ID
- `$d.parentId` - Parent span ID. Root spans have `parentId == null` (not an empty string).

**Skip field discovery when:**
- The query only uses standard fields listed above
  - "Show me slow spans" → Just run: `source spans | filter $m.duration > 1000000`
  - "Latency in the checkout subsystem" → Just run: `source spans | filter $l.subsystemName == 'checkout' | aggregate avg($m.duration) as avg_latency`
- The user explicitly mentions the field names they want to use (e.g., "filter by `$d.customer_id`")
- The fields have already been discovered earlier in the conversation - check the conversation history before calling discovery tools again

**Use field discovery** when the skip conditions above don't apply:
- Use **`search_for_fields`** to batch-search for fields by description and/or value (up to 5 searches at once).

See the "Field Discovery Methods" section below for detailed guidance on how to use the `search_for_fields` tool.

### Step 4: Build and Execute the Query
Construct your DataPrime query using discovered fields, then execute it with `query_dataprime` (Start query with `source spans`). If the query fails due to syntax errors or invalid fields, analyze the error message, fix the query, and retry.
You may check if an existing dashboard already tracks the same concept — reusing a known-good query is faster and keeps analysis consistent with existing monitoring:
- `search_queries(search_type="semantic", query_text="p99 latency by service")` — find queries by meaning
- `search_queries(search_type="by_field", field_path="metadata.service")` — find queries referencing a specific field

### Step 5: Analyze Results and Iterate
Review the query results and assess whether the user's question has been answered:
- If the results are incomplete or raise follow-up questions, return to Step 3 to discover additional fields and craft new queries.
- If findings suggest deeper investigation is needed (e.g., high latency in a specific service), continue the investigation by querying for more context.
- Iterate as needed until you have a comprehensive understanding of the situation.

### Step 6: Consolidate Investigation Output
Before ending the investigation loop, make sure you have:
- The key insights and conclusions supported by evidence.
- The significant query outcomes and artifacts that support these findings.
- Practical next steps or actions for the user to consider.

## Available Tools

- **`search_for_fields`**: Batch search for span fields by description and/or value. Supports up to 5 searches at once. Use this to discover field names for your DataPrime span queries.
- **`get_service_map_relations_graph`**: Gets information about interactions and relationships between services.

For complete DataPrime syntax and patterns, load the `dataprime` skill if it wasn't already loaded.

## Field Discovery Methods

**Important**: Don't assume you know customer-specific field names. Use `search_for_fields` to discover fields when the standard fields listed above aren't sufficient.

**`search_for_fields`** - Batch search for fields by description and/or value (up to 5 search items at once). Don't forget to use `source="spans"`.

Each search item can be one of:
- **Description search**: `{"description": "..."}` - Find fields by their semantic purpose
- **Value search**: `{"value": "..."}` - Find fields containing a specific entity/name

**When to use description search**:
- You know the **type** of field you need (e.g., "customer identifier", "transaction ID", "environment")
- Wide descriptions work well: "fields that may identify customers", "fields representing transactions"
- **Tip**: The more descriptive you are, the more likely you will find the right field.

**When to use value search**:
- You know a **specific entity/name** but not what field it belongs to
- Works for entities like: "production2", "John Doe", "Microsoft", "eu-west-1"
- **Do NOT use** for UUIDs, numbers, or error messages—these won't yield useful results.

**Combining searches** - You can search for multiple things at once:
```json
[
  {"description": "fields containing customer identifiers"},
  {"value": "John Doe"}
]
```

**Examples**:
- User asks "John Doe is experiencing issues" → `[{"value": "John Doe"}]`
- User asks "Which customers had most errors?" → `[{"description": "fields containing customer identifiers or names"}]`
- User asks "Customer John Doe's orders are slow" → `[{"description": "customer identifier fields"}, {"description": "order ID fields"}, {"value": "John Doe"}]`

**Additional discovery methods**:
The `search_for_fields` tool only has access to the most common fields. Sometimes data resides in unstructured fields requiring regex extraction. In such cases, use `wildfind` or filter by specific services to retrieve sample spans, then scan them to discover extraction patterns.

## Investigation Tips

### Zero Results
If you get 0 results, consider:
- **Field availability**: The fields you're filtering by might only be available in a subset of spans. Maybe the field doesn't exist in spans that match a used filter.
- **Value mismatch**: You may be using values that don't match the field (e.g., assuming something is a subsystem name when it's actually something else), or a name is typed differently.
- **Time range**: The time range might be too narrow — widen it **gradually** from your current window (e.g. `now-1h` → `now-6h` → `now-24h`) rather than jumping straight to a huge range.

### Best Practices
- **Start simple**: Always start with simpler queries.
- **Use field discovery**: Leverage other tools for unknown field names or values before running a query.
- **Verify assumptions**: Don't assume field names - verify with available tools.
- **Retrieve sample complete data**: When investigating a specific issue, don't rely solely on aggregations, retrieve a sample of the data to analyze it yourself, you may find important information you didn't think of in advance.

## Important Notes
- The Field Discovery tool (`search_for_fields`) does not return artifact ids for citations, so you don't need to cite it.
- When a user asks you to only build a query, you must test it by running it with the `query_dataprime` tool to validate the syntax, and fix according to the results.
    > **Note**: When the user explicitly asks to *build a query*, 0 results is acceptable—the query may be intended for other data sources or historical times not currently available.

## Related Skills

- If the question is about a specific service/pod/entity's RED metrics, health, or resource
  saturation, load the `service-catalog` skill first — it's a faster, curated path than raw span
  queries for that data. Come back here to correlate a catalog signal (e.g. elevated latency) with
  the underlying spans/traces.

## MCP tools

### `query_dataprime`

Execute a DataPrime query against Coralogix spans.

- Pipeline must start with **`source spans`**
- **`query`**: DataPrime query to execute
- **`start_date`** / **`end_date`**: ISO 8601 UTC time range
- **`limit`**: maximum number of rows to return

### `search_for_fields`

Map user intent to DataPrime field paths for spans.

- **`search_items`**: 1–5 objects; each with exactly one of **`description`** or **`value`**
- **`source`**: **`spans`** (default **`logs`** — set to **`spans`** for span queries)

### `get_service_map_relations_graph`

Service dependency graph from Coralogix tracing.

- **`time_range`** (optional): **`start_time`** and **`end_time`** in ISO-8601 UTC; defaults to the last hour
- **`service_name`** (optional): if omitted, returns a compact full service-map adjacency graph; if set, returns services interacting with that service including **`nodes`** and **`edges`**

### `get_datetime`

Returns the current UTC time as ISO 8601. Use for **`start_date`** / **`end_date`** on **`query_dataprime`**, or **`time_range`** bounds on **`get_service_map_relations_graph`**.
