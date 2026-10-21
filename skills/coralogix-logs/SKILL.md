---
name: coralogix-logs
description: Log-specific concepts, fields, field discovery usage, and troubleshooting patterns. The `dataprime` skill should be loaded alongside this skill. Load when you need to explore logs in your investigation or to answer a question about logs.
metadata:
  author: coralogix
  version: 1.0.0
  summary: Log-specific concepts, fields, field discovery usage, and troubleshooting patterns. The `dataprime` skill should be loaded alongside this skill. Load when you need to explore logs in your investigatio
  tier: partner-managed
  agent_types: GENERIC
---

# Logs Skill - Analyzing logs via Coralogix

This skill describes how to discover and analyze logs using your available tools.

## Objectives

- Use the available tools to help the user find the observability data they need.
- Investigate issues and get to the root cause of the issue.
- Retrieving data is quick, no need to ask the user to wait.
- After conducting your investigation, suggest next steps on how to proceed.

## Core Workflow

### Step 1: Understand the User's Request
Carefully analyze what the user is asking for. Identify the key entities, time frames, and the type of information they need. Determine whether they are looking for specific logs, aggregated data, trends, or root cause analysis.

### Step 2: Identify the Relevant Data
Before writing any query, think about what data and fields could answer the user's question. Consider which log fields, labels, or metadata would be most relevant. Do not assume you know the field names. Each customer's data schema is unique.

### Step 3: Discover Fields (Only When Needed)
Field discovery is **only required for customer-specific fields**. Standard fields are always available and should be used directly.

**Standard fields that are ALWAYS available (no discovery needed):**
- `$m.severity` - Log severity (VERBOSE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `$m.timestamp` - Log timestamp
- `$l.applicationname` - Usually used to identify the application/service/environment/region - meaning varies but the field always exists.
- `$l.subsystemname` - Usually used to identify the subsystem/service/environment/region - meaning varies but the field always exists.

**Skip field discovery when:**
- The query only uses standard fields listed above
  - "Show me the last 15 errors" → Just run: `source logs | filter $m.severity == ERROR | limit 15`
  - "Errors in the 'payment_service' subsystem" → Just run: `source logs | filter $m.severity == ERROR && $l.subsystemname == 'payment_service'`
- The user is looking for a very specific error message, use wildfind directly instead of using field discovery.
  - "Show me the logs with this error: 'Transaction failed'" → Just run: `source logs | wildfind 'Transaction failed'`
- The user explicitly mentions the field names they want to use (e.g., "filter by `$d.customer_id`")
- The fields have already been discovered earlier in the conversation — check the conversation history before calling discovery tools again

**Use field discovery** when the skip conditions above don't apply
- Use **`search_for_fields`** to batch-search for fields by description and/or value (up to 5 searches at once).

See the "Field Discovery Methods" section below for detailed guidance on how to use the `search_for_fields` tool.

### Step 4: Build and Execute the Query
Construct your DataPrime query using the discovered fields, then execute it with `query_dataprime` (Start query with `source logs`). If the query fails, analyze the error message, fix the query, and retry.
You may check if an existing dashboard already tracks the same concept — reusing a known-good query is faster and keeps analysis consistent with existing monitoring:
- `search_queries(search_type="semantic", query_text="error rate by service")` — find queries by meaning
- `search_queries(search_type="by_field", field_path="http.status_code")` — find queries referencing a specific field

### Step 5: Analyze Results and Iterate
Review the query results and assess whether the user's question has been answered:
- If the results are incomplete or raise follow-up questions, return to Step 3 to discover additional fields and craft new queries.
- If findings suggest deeper investigation is needed (e.g., a spike in errors points to a specific service), continue the investigation by querying for more context.
- Iterate as needed until you have a comprehensive understanding of the situation.

### Step 6: Consolidate Investigation Output
Before ending the investigation loop, make sure you have:
- The key insights and conclusions supported by query results.
- The most important evidence artifacts and query outcomes that led to those conclusions.
- Practical next steps or actions for the user to consider.


## RUM (Real User Monitoring)

- **You CAN analyze and provide insights on RUM data**, even though you cannot see RUM sessions directly.
- **RUM lives in its own `rum.events` dataset** — NOT in `source logs`. Query it with `source rum.events` and read flat `$d.*` fields. Do NOT filter by `$l.subsystemname == 'cx_rum'` — the `rum.events` dataset has no subsystem label. Load the **`coralogix-rum`** skill for the full field catalog and query patterns.
- **What you can do with RUM data**:
  - Query RUM events to analyze user behavior, page performance, errors, and frontend issues
  - Filter by RUM-specific fields like page URLs, user actions, browser types, device information
  - Aggregate RUM metrics such as page load times, error rates, user session patterns
  - Identify frontend performance issues, JavaScript errors, and user experience problems
- **What you cannot do**: You cannot see or analyze RUM sessions as a complete unit (session replay, session flows, etc.), but you CAN analyze the individual RUM events that make up those sessions.
- **When users ask about RUM**: Acknowledge that you can help with RUM analysis. Query `source rum.events` (load the `coralogix-rum` skill) and provide insights based on the events you find.

## Available Tools

- **`search_for_fields`**: Batch search for log fields by description and/or value. Supports up to 5 searches at once. Use this to discover field names for your DataPrime log queries.

For complete DataPrime syntax and patterns, load the `dataprime` skill if it wasn't already loaded.

## Field Discovery Methods

**Important**: Never assume you know the fields you need to use. Each customer's data is unique, and you must discover fields using `search_for_fields`.

**`search_for_fields`** - Batch search for fields by description and/or value (up to 5 search items at once).

Each search item can be one of:
- **Description search**: `{"description": "..."}` - Find fields by their semantic purpose
- **Value search**: `{"value": "..."}` - Find fields containing a specific entity/name

**When to use description search**:
- You know the **type** of field you need (e.g., "customer identifier", "order ID", "environment")
- Wide descriptions work well: "fields that may identify customers", "fields representing transactions"
- **Tip**: The more descriptive you are, the more likely you will find the right field.

**When to use value search**:
- You know a **specific entity/name** but not what field it belongs to
- Works for entities like: "production2", "John Doe", "Microsoft", "eu-west-1"
- **Do NOT use** for numbers, IDs that are likely to have very high cardinality (e.g. order id), or error messages — these won't yield useful results.

**Combining searches** - You can search for multiple things at once:
```json
[
  {"description": "fields containing customer identifiers"},
  {"value": "Acme Corp"}
]
```

**Examples**:
- User asks "Acme Corp is experiencing issues" → `[{"value": "Acme Corp"}, {"value": "acme"}]`
- User asks "Which customers had most errors?" → `[{"description": "fields containing customer identifiers or names"}]`
- User asks "What's the number of errors per environment in the last hour, excluding the `qa` and `staging` environments?" → `[{"description": "fields representing environments"}, {"value": "qa"}, {"value": "staging"}]`
- User asks "Issues with order ID `abc-123`" → `[{"description": "fields representing order IDs"}]` (search by type, not by the id itself)
- User asks "Customer Acme Corp's orders are failing" → `[{"description": "customer identifier fields"}, {"description": "order ID fields"}, {"value": "Acme Corp"}, {"value": "acme"}]`

**Why prefer description over value for known types**: UUIDs/IDs often appear in multiple fields. Searching by type helps find the *semantically correct* field (e.g., `order_id` vs `correlation_id`).

**Additional discovery methods**:
The `search_for_fields` tool only has access to the most common fields. Sometimes data resides in unstructured fields requiring regex extraction. In such cases, filter by specific services or severity to retrieve sample logs, then scan them to discover extraction patterns.

> **`~` (text match):** `~` is a **case-insensitive, token-based** match — `~ 'timeout'` also matches `TIMEOUT`/`Timeout`, and it matches whole tokens (words), not arbitrary substrings. For a **case-sensitive raw substring** match, use `contains()` instead. See the operator reference in the `dataprime` skill.

> **Avoid "schema-agnostic" approaches as a first choice**: `wildfind` searches ALL fields and can return irrelevant data. Always try `search_for_fields` first. Only use `wildfind` as a fallback when field discovery fails.

## Troubleshooting Guidelines

### Zero Results
If you get 0 results, change **one thing at a time**. Keep the query window as **narrow** as possible and widen it deliberately — start from the window you already have rather than jumping straight to a huge range:

1. **Relax the filters** - remove the most restrictive condition first:
   - **Field availability**: The fields you're filtering by might only be available in a subset of logs
   - **Value mismatch**: You may be using values that don't match the field (e.g., assuming something is a subsystem name when it's actually something else)
2. **Verify field names** - use `search_for_fields` or retrieve a sample of logs to inspect the actual schema.
3. **Extend the time range** (unless the user specified a time frame) - widen it gradually from your current window (e.g. `now-1h` → `now-6h` → `now-24h`) rather than jumping straight to a huge range.

> **Important**: Do NOT make multiple changes at once (e.g., extending time AND relaxing filters in the same query). Make one change, run the query, and evaluate the results before making another change. This helps you understand what actually fixed the issue.

**Other considerations**:
- **RUM data**: RUM is a separate `rum.events` dataset queried with `source rum.events` (not `source logs`), so RUM/frontend events do not appear in log queries. Load the `coralogix-rum` skill when analyzing RUM. If a RUM query on `rum.events` returns 0 results, do NOT switch to `source logs`/`cx_rum` — report that no RUM data was found instead.

### Best Practices
- **Start simple - query first, discover later**: For basic queries using standard fields (`$m.severity`, `$m.timestamp`, `$l.applicationname`, `$l.subsystemname`), just run the query directly. Don't call field discovery tools unnecessarily.
    - Example: "Show me the last 15 errors" → Immediately run `source logs | filter $m.severity == ERROR | limit 15`
    - Example: "Errors in the last hour" → Immediately run `source logs | filter $m.severity == ERROR`
    - Generally, keep your queries simple. Don't use `choose` to select specific fields, don't group by templates, don't add extra aggregations - unless the user specifically asks for it or the logs are very large.
- **Verify assumptions about custom fields**: Don't assume customer-specific field names - verify with available tools. But standard fields like `$m.severity` are guaranteed to exist.

## Important Notes
- When generating charts, unix timestamps are automatically converted in the front end for the user, so you don't need to convert them.
- The Field Discovery tool (`search_for_fields`) does not return artifact ids for citations, so you don't need to cite it.
- When a user asks you to only build a query, you must test it by running it with the `query_dataprime` tool to validate the syntax, and fix according to the results.
    > **Note**: When the user explicitly asks to *build a query*, 0 results is acceptable—the query may be intended for other data sources or historical times not currently available.

## Related Skills

- If the question is about a specific service/pod/entity's RED metrics, health, or resource
  saturation, load the `service-catalog` skill first — it's a faster, curated path than raw log
  queries for that data. Come back here to correlate a catalog signal (e.g. elevated error rate)
  with the underlying log events.

## MCP tools

### `query_dataprime`

Execute a DataPrime query against Coralogix logs.

- Pipeline must start with **`source logs`**
- **`query`**: DataPrime query to execute
- **`start_date`** / **`end_date`**: ISO 8601 UTC time range
- **`limit`**: maximum number of rows to return

### `get_datetime`

Resolve relative natural-language time windows into **`start_date`** / **`end_date`** for **`query_dataprime`**.
