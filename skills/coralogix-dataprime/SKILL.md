---
name: coralogix-dataprime
description: DataPrime query language for logs/spans/custom datasets (shared syntax, patterns, and rules). Load when you need to write a DataPrime query to explore logs or spans. Also load in case the user asks for help with a DataPrime query or its generation.
metadata:
  author: "coralogix"
  version: "1.0.0"
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "CHAT,INCIDENT_TRIAGE,INCIDENT_RCA,INCIDENT_MITIGATION"
---

# DataPrime Skill - Shared Query Language

This skill is the shared DataPrime reference used by both logs and spans investigations.

## DataPrime Query Language

### Structure

DataPrime queries are structured as a sequence of commands, executed in order, and separated by `|` operator. The output of each command is the input of the next command. All queries must start with a source specification:
```dataprime
source logs
```

Comments are supported using the `#` or `//` syntax, similar to Python and C respectively.

### Datasets sources
Every query must start with a `source <name>` clause. Four categories are supported:
- **Primary datasets**: `source logs`, `source spans`. Use these for the vast majority of investigations.
- **RUM**: `source rum.events` for frontend/browser/mobile questions (JS errors, crashes, Web Vitals, page load, user interactions) — load the **`coralogix-rum`** skill. Query it directly; it is not a custom dataset and does not require the user to name it.
- **Custom user/system datasets**: `source <dataset_name>`. Only query a custom dataset when the user explicitly names it — never guess a dataset name. For fleet case analytics, use `source system/labs.cases.state_updates` and load the **`coralogix-case-analytics`** skill (minimum 1h time window, dedupe per `caseId`).
Note: For field discovery, `search_for_fields` only works for logs/spans.


### Data Representation

Data is represented with keypath prefixes:
- `$d` for user data (default, can be omitted)
- `$l` for user labels
- `$m` for metadata

### Example Queries

**Find the top 5 subsystems with the most errors:**

```dataprime
source logs
| filter [ERROR, CRITICAL].arrayContains($m.severity)
| groupby $l.subsystemname as subsystem aggregate count() as error_count
| orderby $d.error_count desc
| limit 5
```

**Find the slowest operations (slower than a second):**

```dataprime
source spans
| filter $m.duration > 1000000
| groupby $l.operationName as operation aggregate avg($m.duration) as avg_duration
| orderby avg_duration desc
| limit 5
```

## Important DataPrime Concepts

### Data Types
- **string**: Represents text. Enclosed in single quotes, e.g. `'some_text'`
- **number**: Represents a numeric value, e.g. `123`
- **boolean**: Represents a boolean value, e.g. `true` or `false`
- **timestamp**: Represents a date and time. Used as a number in nanoseconds since epoch. e.g. `1714636800000000000`
- **interval**: Represents a time interval, e.g. `1h`, `1d`, `1w`
- **array**: Represents a list of values, e.g. `[1, 2, 3]`
- **object**: Represents a dictionary of key-value pairs, e.g. `{{"name": "John", "age": 30}}`
- **null**: Represents a missing value/key, e.g. `null`

### Basic Syntax
- **Type casting**: Append `:<type>` to any keypath or expression to cast it — usable anywhere in a query
  - Cast types: `bool`, `number`, `string`, `timestamp`, `interval`
  - **`:timestamp`** — fields stored as nanosecond integers (e.g. `createdAt`, `resolvedAt`) must be cast before time arithmetic or method calls: `(resolvedAt:timestamp - createdAt:timestamp).toTimeUnit('m')`
  - Incompatible casts return `null` silently
  - Examples: `filter $d.http_error_code:number == 500`
- **Chaining conditions**: Use `&&` (AND) or `||` (OR) operators
  - Example: `filter $m.severity == ERROR && $d.http_error_code:number == 500`
- **Text search**: Use `~` operator for a **case-insensitive token match** (matches whole tokens, not arbitrary substrings) on a field.
  - Example: `filter $d.some_field ~ 'transaction failed'`
  - **`~` vs `contains()`:** `~` is a **case-insensitive, token-based** match — it matches whole tokens (words), so `~ 'timeout'` also matches `TIMEOUT` and `Timeout`. `contains()` is a **case-sensitive raw substring** match — `contains('time')` matches inside `timeout`, but only in that exact case. Use `~` for word/term search; use `contains()` when you need an exact-case partial-string match.

### Field Access
- **Chained field names**: `$d.tags.user_context.email`
- **Special characters**: Use `[]` operator instead of `.` operator
  - Example: `filter $d.http['status/code'] == 500`

### Standard Fields
- **`$m.timestamp`**: Log timestamp, e.g. `2021-01-01T00:00:00Z`
- **`$m.severity`**: Log severity (VERBOSE, DEBUG, INFO, WARNING, ERROR, CRITICAL) - special type, *without quotes*
    - *NEVER* use the severity values with quotes, use them as is (VERBOSE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Common labels**: `$l.subsystemname` and `$l.applicationname` - identify applications/services/environments
  - These are the two most high-level labels, all data in Coralogix is labeled with these two labels, which makes them very useful for filtering.
  - **Important**: Although these are the most high level labels, when the user mentions specific entities or information type to filter by - use `search_for_fields` tool for discovery first.
- **`$m.templateid`**: JSON schema identifier for the log (if applicable, null otherwise)

## Common Query Patterns

### Text Filtering
```dataprime
source logs | filter $d.some_field ~ 'transaction failed'
```

### Filtering by key existence
```dataprime
source logs | filter $d.some_field != null
```
** Note**: This is useful to filter out logs that don't contain a specific field.

### Lucene Syntax
Filter using Lucene syntax (`field:value`, field names relative to `$d`, combine with `AND`/`OR`/parens).
```dataprime
source logs | lucene 'some_field:"some_value"'
```

### Aggregations
```dataprime
source logs | aggregate count() as total_count
```

**Common aggregations**: `sum`, `avg`, `min`, `max`, `median`, `stddev`, `variance`, `percentile`, `distinct_count`, `approx_count_distinct`, `any_value`, `collect`, `max_by`, `min_by`
- Syntax: `aggregate <aggregation_name>($d.some_field) as <alias>`
- Example: `source logs | aggregate avg($d.connections_count) as avg_connections_count`
- **Percentile example**: `percentile(0.95, $d.some_field)`
- **`distinct_count` vs `approx_count_distinct`:** Exact `distinct_count` can be slow or run out of memory on high-cardinality fields. When an exact count isn't required, use `approx_count_distinct` instead.
- **`max_by(sortKey, expr)`** — returns `expr` from the row where `sortKey` is maximum; **`min_by(sortKey, expr)`** — minimum. Both require comparable types (`string`, `number`, `timestamp`, …).
  - Example: `groupby $d.user aggregate max_by($m.timestamp, $d) as latest_event` — returns the full payload of each user's latest event

**`count` as a standalone command** — counts rows in the current stream, returning a single result row:
- Syntax: `count [into <keypath>]`
- Example: `source logs | filter $d.status == 'error' | count`

### Time Filtering
```dataprime
source logs | filter $m.timestamp > now() - 1h
```
> **Note**: For simple time ranges, *always* use the `time_filters` parameter instead of filtering by time in queries.

### Grouping
Grouping can be performed using the `groupby` command. It can be used in combination with aggregations.
```dataprime
source logs | groupby $l.subsystemname as service aggregate count() as error_count
```

**Time-based grouping**:
```dataprime
source logs | groupby roundTime($m.timestamp, 1h) as hour aggregate count() as count
```

### Grouping by multiple fields
```dataprime
source logs | groupby $l.subsystemname as service, $l.applicationname as application aggregate count() as error_count
```

### Find the first non-null value from multiple fields
Coalescing can be performed using the `firstNonNull` function. It can be used to merge multiple fields into a single field.
```dataprime
source logs | create merged_field from firstNonNull($d.some_field, $d.some_other_field)
```

It can also be used in grouping (like any other function). For example, if the user asks for the top 5 errors by message, and there are multiple fields that contain the error message, try using:
```dataprime
source logs | groupby firstNonNull($d.error_message, $d.error_message_2) as error_message aggregate count() as error_count
```

### Advanced Operations

#### Wildfind Search (Last Resort)
```dataprime
source logs | wildfind 'some_value'
```
- Searches the value in all fields of all logs
- Note: Wildfind is a separate command from filtering, it can't be a condition within a filter command
- **Use as a last resort only**: `wildfind` can return a lot of irrelevant data because it matches across ALL fields. Always try `search_for_fields` first to find the specific field, then query using that field.
- **Performance consideration**: Use wisely as it comes at a cost

#### Deduplication
```dataprime
source logs | dedupeby $d.some_field
```
- Full syntax: `dedupeby <expr> keep N [orderby <expr> [asc|desc]]`
- `keep N` controls how many rows are retained per unique key; `orderby` makes the selection deterministic
- Common pattern — keep the latest row per key: `dedupeby $d.id keep 1 orderby $m.timestamp desc`
- Very useful with `$m.templateid` field to remove duplicate logs with same template/format
- **Caution**: Don't rely solely on deduplication - different logs can have the same template/format
- **Performance**: `dedupeby` cost scales with the number of **distinct keys** it tracks, so it gets slow and memory-heavy on high-cardinality or near-unique keys (e.g. a request id). Cardinality depends on your data and time window — a key like session or trace id can still be large. Keep `dedupeby` when you genuinely need one representative row per key; to cut cost, narrow the input first (tighter `filter`, smaller time window) rather than swapping in `filter`/`limit` (which does **not** keep one row per key) or an aggregation (which changes the row shape) unless that different output is acceptable. The `dedupeby <key> orderby ...` form (keep the latest row per key) is heavier still.

#### Distinct Values
```dataprime
source logs | distinct $d.some_field
```
- Useful to get unique values for a field (e.g., list of services/applications)

#### Multi-value Matching
```dataprime
source logs | filter ['value1', 'value2'].arrayContains($d.some_field)
```
- Useful to match a field to one of multiple values

#### Creating new fields
```dataprime
source logs | create total_time from $d.load_time:number + $d.run_time:number
```
- Useful to manipulate data in the query.

#### Conditional expressions
```dataprime
source logs | create label from if($d.status_code >= 500, 'error', 'ok')
```
- Syntax: `if(condition: bool, then: any, else: any?): any`
- Usable inside any expression context: `create`, `filter`, `choose`, `groupby`, `aggregate`
- `else` is optional — omitting it returns `null` when the condition is false
- Method notation also supported: `($d.status_code >= 500).if('error', 'ok')`

#### Exploding array fields into separate records
```dataprime
source logs | explode $d.tags into $d.tag original discard
```
- Turns each element of an array field into a separate record.
- **`original discard`** (default): keep only exploded output. **Prefer this** unless the other fields are required.
- **`original preserve`**: keeps other fields.
- Common pattern — count occurrences of each tag: `source logs | explode $d.tags into $d.tag | groupby $d.tag aggregate count() as c | orderby c desc`
- Overwrites existing keys.

#### Extracting values from strings using regex

Assume you have logs with the following user data structure:

```json
{
    "user_context": {
        "email": "john.doe@example.com",
        "name": "John Doe"
    }
}
```

You can extract the email domain using the following query:
```dataprime
source logs | extract $d['user_context']['email'] into domain using regexp(e=/@(.*)/)
```

the extracted value will be stored in `$d.domain._0` (indicating the first and only match)

You can then manipulate the created field, for example to get the distinct domains, use the query:
```dataprime
source logs | extract $d['user_context']['email'] into domain using regexp(e=/@(.*)/) | distinct $d.domain._0
```

additionally, you can use capturing groups in your regex to extract multiple values, and to name the extracted values.
For example, to extract the email domain and the email address, use the following query:
```dataprime
source logs | extract $d['user_context']['email'] into extracted_data using regexp(e=/(?<username>[a-zA-Z0-9._%+-]+)@(?<domain>.*)/) | choose $d.extracted_data.username as username, $d.extracted_data.domain as domain
```
the extracted values will be stored in `$d.extracted_data.username` and `$d.extracted_data.domain`

#### Extracting data from json strings

Assume you have logs with the following user data structure, they have a nested json string:

```json
{
    "user_context": "{\"email\": \"john.doe@example.com\", \"name\": \"John Doe\"}"
}
```

You can extract the email domain using the following query:
```dataprime
source logs | extract $d['user_context'] into parsed_user_context using jsonobject()
```

the extracted value will be stored in `$d.parsed_user_context` (as an object, not a string)

You can then access the fields of the extracted object, for example to get the distinct email addresses, use the query:
```dataprime
source logs | extract $d['user_context'] into parsed_user_context using jsonobject() | distinct $d.parsed_user_context["email"]
```

### Fetching sample logs for templates

When relying on templates to identify prominent errors or patterns in logs, you should fetch sample logs for the template to see what the logs look like.
This is also important for the user to make sense of the template. To do so, you can use the `any_value` aggregation function, to return a random sample of the expression. For example, to find the top 5 noisiest errors:
```dataprime
source logs | groupby $m.templateid aggregate any_value($d) as sample_message, count() as total_errors | order by total_errors desc | limit 5
```

#### Timestamp / Interval Arithmetic

| Expression | Result | Description |
|---|---|---|
| `timestamp - timestamp` | `interval` | Duration between two events |
| `timestamp + interval` | `timestamp` | Shift forward |
| `timestamp - interval` | `timestamp` | Shift backward |
| `timestamp / interval` | `timestamp` | Round down to time window (bucketing) |
| `interval / interval` | `number` | Ratio of two durations |
| `interval * number` | `interval` | Scale a duration |

Conversion functions (default unit: `nano` unless noted):

| Function | Returns | Example |
|---|---|---|
| `toInterval(n, unit)` | `interval` | `$m.timestamp / 1.toInterval('h')` — bucket by hour |
| `toTimeUnit(interval, unit?)` | `number` | `(resolvedAt:timestamp - createdAt:timestamp).toTimeUnit('m')` — use in `avg()`/`percentile()` |
| `toUnixTime(ts, unit?)` | `number` (default: `milli`) | `toUnixTime($m.timestamp, 's')` — raw epoch |

## Additional Commands and Functions
If needed, you can check additional commands and functions available by using the `list_dataprime_constructs` tool.
If you need to describe a specific command or function, you can use the `describe_dataprime_construct` tool.
If you are unsure of an instruction, describe it before using it.
If you get an error while using an instruction, describe the suspected instruction before fixing the issue.

## MCP tools

### `query_dataprime`

Execute a DataPrime query against Coralogix logs, spans, or named datasets.

- Logs require **`source logs`**; spans/traces require **`source spans`**
- Fleet case analytics require **`source system/labs.cases.state_updates`** — load **`coralogix-case-analytics`** alongside this skill
- **`query`**: DataPrime query to execute
- **`start_date`** / **`end_date`**: ISO 8601 UTC time range
- **`limit`**: maximum number of rows to return

### `search_for_fields`

Map user intent to DataPrime field paths under **`$d`** / **`$l`** / **`$m`** for logs or spans.

- **`search_items`**: 1–5 objects; each with exactly one of:
  - **`description`**: semantic search over field names and paths
  - **`value`**: substring match on schema-store example values
- **`source`**: **`logs`** (default) or **`spans`**

### `get_datetime`

Resolve relative natural-language time windows into **`start_date`** / **`end_date`** for **`query_dataprime`**.

### Command catalog (MCP tools)

| Tool | Purpose |
|------|--------|
| **`list_dataprime_commands`** | Returns JSON `count` and `items`. Use **`kind`**: `all`, `commands`, or `functions`. Optional **`name`**: case-insensitive substring on the catalog **key** only. |
| **`show_dataprime_command_details`** | Returns JSON for one entry: exact **`name`** and **`kind`** (`all`, `commands`, or `functions`). Full `syntax`, `description`, `category`; errors may suggest near matches. |
| **`list_dataprime_constructs`** | Plain-text index of all DataPrime **commands and functions** with short descriptions (parsed construct catalog). |
| **`describe_dataprime_construct`** | Full documentation for one construct: **`request`** with **`type`** (`command` or `function`) and **`id`**. |
