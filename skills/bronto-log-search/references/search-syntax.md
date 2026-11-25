# Bronto search syntax reference

Bronto's search syntax is a subset of SQL: the `search_filter` is the `WHERE` clause of a `SELECT`. Subqueries and joins are not supported.

## Reserved fields

| Field | Meaning |
| --- | --- |
| `@raw` | The full raw text of the event |
| `@origin` | The IP address Bronto received the event from |

Fields whose names start with `$`, such as `$service`, `$hostname` and `$pattern_id`, are resource attributes and other metadata Bronto adds. Free-text search does not match them; filter on them by name, in double quotes.

## Boolean operators

| Operator | Example |
| --- | --- |
| `AND` | `log_level = 'ERROR' AND path = '/checkout'` |
| `OR` | `status = 500 OR status = 503` |
| `NOT` | `NOT log_level = 'DEBUG'` |

## Comparison operators

| Operator | Example | Notes |
| --- | --- | --- |
| `=` | `log_level = 'ERROR'` | |
| `!=`, `<>` | `log_level != 'INFO'` | |
| `<`, `<=`, `>`, `>=` | `duration_ms > 1000` | |
| `[NOT] LIKE` | `path LIKE '/api/%'` | `%` matches any run of characters; case-sensitive; strings only |
| `[NOT] ILIKE` | `message ILIKE '%timeout%'` | As `LIKE`, ignoring case |
| `IS [NOT] NULL` | `"exception.type" IS NOT NULL` | `IS NULL` is true when the event has no such field |
| `[NOT] IN` | `status IN (500, 502, 503)` | The list may mix types, and may hold fields: `'10.0.0.5' IN (source_address, destination_address)` |

## Precedence

From highest to lowest. Use parentheses to change the order.

1. `=`, `!=`, `<>`, `<`, `>`, `<=`, `>=`
2. `LIKE`, `ILIKE`, `IS NULL`, `IN` and their `NOT` forms
3. `NOT`
4. `AND`
5. `OR`

## Quoting

| Quotes | Used for | Example |
| --- | --- | --- |
| Single `'...'` | String values | `'timeout exceeded'` |
| Double `"..."` | Field names | `"status_code"` |

- An unquoted word next to an operator is a field name.
- Double-quote a field name that contains any of `= ! ? . , < > - + * / % ^ & |`.
- Escape a quote by doubling it: `'O''Brien'`.

## Free text

A word or quoted string on its own is expanded to a case-insensitive match on the raw event:

```
username AND (500 OR 404)
```

becomes

```
@raw ILIKE '%username%' AND (@raw ILIKE '%500%' OR @raw ILIKE '%404%')
```

Quote a free-text term if it contains spaces or is one of `AND`, `OR` or `NOT`.

## Data types

| Type | Literal |
| --- | --- |
| Integer | Unquoted digits: `500` |
| Decimal | Unquoted digits with one `.`: `0.25` |
| String | Single-quoted: `'500'` |

Bronto converts types where it makes sense: an event with `duration=0.1291` matches both `duration < 1` and `duration < '1'`. A field holding a string, such as `'null'`, is never compared numerically, so `duration > 100` does not match it.

## Functions

| Function | Example |
| --- | --- |
| `LOWER` | `LOWER(user_name) = 'alice'` |

## Regular expressions

Regular expression operators are an early access feature and may not be enabled for the organization. If a query using them fails, fall back to `LIKE` or `ILIKE`.

| Operator | Meaning |
| --- | --- |
| `REGEXP`, `RLIKE`, `~` | Matches the RE2 pattern |
| `NOT REGEXP`, `NOT RLIKE`, `!~` | Does not match |
| `~*` | Matches, ignoring case |

The pattern does not need to match the whole value: `colou?r` matches `My favourite colour is red`. RE2 has no lookahead or lookbehind.

Named capture groups, such as `@raw REGEXP '^(?<ts>.*?)\|(?<component>.*?)\|'`, extract fields at query time from unparsed logs. The captured fields can be used in aggregates, `group_by_keys` and `select`, but not elsewhere in the same filter.

## Limits

- 16,000 characters per query.
- 400 expressions per query, counting comparisons, boolean operators and free-text terms.
