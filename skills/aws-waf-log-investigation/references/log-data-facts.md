# WAF log data facts, for both query engines

WAF logs reach you through one of two engines: Athena (logs in S3, directly or through Firehose)
or CloudWatch Logs Insights (logs in a log group). The analysis method is the same on both. The
facts below are where the engines differ or where a query is silently wrong on either. Each one
was measured on real WAF logs or is documented by AWS.

## Record shape (both engines)

- One JSON record per request, written compactly (no spaces after `:` or `,`).
- `timestamp` is UTC epoch milliseconds.
- `action` is the terminating action: ALLOW, BLOCK, CHALLENGE, CAPTCHA. **COUNT never appears
  as the top-level action.** A Count match is recorded on a request whose action is something
  else, usually ALLOW.
- `httpRequest.uri` excludes the query string; `httpRequest.args` holds it, unencoded by WAF
  (logged as the client sent it, JSON-escaped). `/app.js?v=2` logs `uri=/app.js`, `args=v=2`.
- The request body is never logged.
- `httpRequest.headers` is an array of `{name, value}`. Header-name case is whatever the client
  sent; compare names case-insensitively.
- `labels` is an array of `{name}` with fully namespaced names, for example
  `awswaf:managed:aws:bot-control:bot:verified`.
- `ja4Fingerprint` and `ja3Fingerprint` are present for CloudFront and ALB; absent for API
  Gateway and AppSync. `httpRequest.requestId` is the host service's request ID; on ALB it is
  the trace ID.
- Client-supplied quotes are backslash-escaped inside the JSON, so a header value cannot forge a
  `"ruleId":"X"` fragment. Matching on the JSON fragment is safe.

## Where a rule match is recorded

A match can live in six places. A filter that checks fewer misses exactly the Count matches a
Count-to-Block review is about.

| Situation | Where |
|---|---|
| Rule terminated the request | `terminatingRuleId` |
| Custom rule in Count mode | top-level `nonTerminatingMatchingRules[]` |
| Managed sub-rule overridden to Count (`RuleActionOverrides`) | `ruleGroupList[].nonTerminatingMatchingRules[]`, action `COUNT` (measured) |
| Whole group with `OverrideAction: Count` | Two entries: top-level `nonTerminatingMatchingRules[]` with the WebACL rule name and action `COUNT`, and `ruleGroupList[].terminatingRule` with the sub-rule and its own action, often `BLOCK` (measured). The record's action is whatever came next, usually ALLOW. |
| Legacy `ExcludedRules` | `ruleGroupList[].excludedRules` |
| Rate-based rule | `rateBasedRuleList[]`, keyed by `rateBasedRuleName` |

When a managed group terminates a request, `terminatingRuleId` is the group's rule name; the
actual sub-rule is in `ruleGroupList[].terminatingRule.ruleId`. A `BLOCK` inside `ruleGroupList`
for a group other than the one `terminatingRuleId` names is a group running in Count, not the rule
that blocked the request; this happens on BLOCK records too.

Match details carry `conditionType` and `location` for SQLi, XSS and other managed rules (for
example KnownBadInputs logs `REGEX` on `URI`, measured); `matchedData` is filled only for SQLi and
XSS. When
the rule terminated the request they are in `terminatingRuleMatchDetails`. When it only counted,
they are in that entry's `ruleMatchDetails`, top-level or inside `ruleGroupList`, and
`terminatingRuleMatchDetails` is empty (measured). For other managed rules, the sub-rule name tells
you what was inspected: `_QUERYARGUMENTS`/`_QUERYSTRING` the query string, `_URIPATH`/`_URI` the
path, `_COOKIE` the Cookie header, `_HEADER` headers, `_BODY` the body (not in logs). `matchedData`
is tokenizer output, not a slice of the request.

## Engine differences

| Topic | Athena | CloudWatch Logs Insights |
|---|---|---|
| Field names | The JSON SerDe lowercases keys: `httprequest.clientip`, `terminatingruleid`. String-typed JSON columns (for example `excludedrules`) contain lowercased keys, so search `"ruleid":"X"`, never `"ruleId"`. Values keep their case. | Original camelCase: `httpRequest.clientIp`, `terminatingRuleId`. Search raw JSON with `@message like '"ruleId":"X"'`. |
| Arrays (labels, headers, rule lists) | `UNNEST`, `any_match`, `filter`, `transform` see every element. | Dotted access (`labels.0.name`) reaches one element. Parsing gives only the **first** label per request. To filter on any label, match against the whole `"labels":[...]` text, not the whole `@message`: a bare `@message like 'bot'` also matches `Googlebot` in a UA or `/robots.txt` in a URI. |
| Nested Count matches | Unnest `rulegrouplist` and its `nonterminatingmatchingrules`. | A regex over `@message` captures only the first nested element unless written carefully; prefer a `"ruleId":"X"` substring test, plus a separate `rateBasedRuleName` test. |
| User-Agent | `element_at(filter(httprequest.headers, h -> lower(h.name)='user-agent'),1).value`. Do not `CROSS JOIN UNNEST(headers) WHERE name='user-agent'` for counts: requests with no UA vanish. | `parse @message /(?i)"name":"user-agent","value":"(?<ua>[^"]*)"/` |
| Time | Filter `"timestamp" BETWEEN start_ms AND end_ms` **and** a partition predicate. Render with `from_unixtime(timestamp/1000)` (UTC unless you shift it). | `@timestamp`; `bin()` buckets and displayed times are UTC. |
| Percentiles | `approx_percentile(x, 0.95)`, fraction 0-1. Passing 95 errors. | `pct(x, 95)`, 0-100. Passing 0.95 **silently** returns near the minimum. |
| Conditional counts | `sum(if(cond,1,0))` or `count_if(cond)` | `sum(if(cond,1,0))` |
| NULL in negations | `NOT regexp_like(NULL, ...)` is NULL and drops the row: guard with `x IS NULL OR NOT ...`. | `not like` keeps rows where the field is absent; to match only present fields add `ispresent(field)`. |
| Regex case | Case-sensitive; add `(?i)`. | Case-sensitive; add `(?i)`. |
| Row limits | `LIMIT n` is honoured. Ask for `n+1` to detect truncation. | The API `limit` parameter caps rows; the `| limit` clause did not, in measurement. Set both to `n+1`. No truncation flag is returned. |
| Cost driver | Bytes scanned. | Bytes scanned per log group. |

## Scoping to one WebACL

- **CloudWatch Logs.** A WAF log group can contain other WebACLs' records and non-WAF records (for
  example CloudFront standard access logs sent to the same group). Always filter `webaclId like
  '/webacl/<webacl-name>/'`. A bare `/<webacl-name>/` matches every WebACL when the name is
  `webacl`, because every ARN contains `/webacl/`. Sample a record's fields before trusting a raw
  count.
- **Athena.** If the table location is a bucket root or a prefix shared by several WebACLs
  (typical with Firehose), add `webaclid LIKE '%/webacl/<webacl-name>/%'`. S3 vended logs put the
  WebACL name in the path, so a table rooted at that WebACL's prefix is already scoped.
- WAF writes to many log streams per WebACL in CloudWatch Logs; never scope by stream name.

## Partitions (Athena)

- Partition paths are written by the delivery system, in its time zone: UTC for S3 vended logs,
  the stream's `CustomTimeZone` for Firehose (`DescribeDeliveryStream` shows it), whatever a
  custom pipeline used otherwise. A wrong zone prunes the wrong hours and returns zero rows.
- A partition directory is named by when its buffer opened, so it does not bound the timestamps
  inside it. **Widen the partition bounds by one interval on each side** and keep the exact
  `timestamp` filter. Without widening, measured losses were 5.7% and 8.1% of rows on 5-minute
  windows.
- Projection compares partition values as strings, so the format must be zero-padded and
  most-significant first (`yyyy/MM/dd/HH/mm`). **Write every partition literal in exactly the
  table's `projection.<col>.format`** (read it from `glue:GetTable`). A literal in another
  format compares wrongly and returns zero rows with no error: measured, `'2026-09-07 23:55:00'`
  against `yyyy/MM/dd/HH/mm` values excluded a whole week that held the answer, because `/`
  sorts after `-`.
- Do not convert epoch bounds by hand. Let Athena compute them:
  `"timestamp" >= to_unixtime(timestamp '2026-03-02 00:00:00') * 1000` (the literal is read as
  UTC). Hand-converted bounds failed twice in testing: one a year off (`1756684800000` is
  2025-09-01, not 2026-09-01) and one a day late. Both return zero rows with no error.
- A multi-week query over minute partitions reads tens of thousands of small objects and can be
  throttled by S3 (`SlowDown`). Split it into week-sized queries run one after another, and mark
  any chunk that failed as UNKNOWN.
- When you split a window, derive both predicates of each chunk from one pair of boundaries.
  A chunk from A to B gets a partition predicate from one interval before A to one interval
  after B, and a `timestamp` predicate of `>= A` and `< B`. The next chunk starts at B. In
  testing, chunks whose partition and epoch bounds were written separately left out a whole day
  between two chunks, and the only day the client was active fell in the gap.
- In each chunk, count the whole chunk and the target in one scan: `count(*)`,
  `min(timestamp)`, `max(timestamp)` and `count_if(<the narrowing filter>)`. A chunk whose total is
  zero has a broken predicate. On a site with steady traffic, each chunk's first and last
  timestamps sit close to A and B; one that starts or ends far inside them points to a gap. This
  is the positive control at no extra cost.
- A window outside `projection.<col>.range` returns zero rows, no error. Check the range first.
- Mixed buckets exist: hourly folders before a change, minute folders after. A minute-format
  table cannot reach the hourly era; an hourly-format table reads both, at hourly granularity.
- Daily or coarser partitions make every query a full-day scan.

## Logging configuration changes what the logs contain

- **Logging filter.** `LoggingFilter` with `DefaultBehavior: DROP` keeps only listed actions.
  Zero rows for another action does not mean no traffic. The `EXCLUDED_AS_COUNT` condition
  matches legacy excluded rules and rules with a rule action override of Count; a plain `COUNT`
  condition does not see legacy `excludedRules` entries. If ALLOW is dropped, bypass detection is
  impossible; if Count records are dropped, Count evaluation has to fall back to metrics.
- **Redacted fields.** `RedactedFields` replaces the value with the literal string `REDACTED`
  (key, header name and array length survive). It applies only to fields the matching rule
  inspected, so real and redacted values mix in one result. Filtering on a redacted field
  undercounts silently; grouping by it shows a `REDACTED` bucket.
- **Sampling of large values.** Header values and URIs are logged as sent; a raw `#` or space in
  the path reaches `uri` intact, so path text can be anything an attacker chose.

## Static assets

When measuring behaviour (URI diversity, page counts), exclude static assets so browser asset
loads do not inflate the signal. Use an anchored, case-insensitive suffix match:
`(?i)\.(js|mjs|css|map|png|jpg|jpeg|gif|bmp|ico|svg|svgz|webp|avif|tif|tiff|woff|woff2|ttf|otf|eot|mp4|webm|mov|avi|mp3|wav|ogg|m4a)($|\?)`.
Keep pdf, json, html, php, xml, txt, csv, documents and archives: they are business requests and
scrape targets. An unanchored pattern once excluded every `.json` request. Keep rows whose URI is
NULL (on Athena that needs the `IS NULL OR` guard).

## Zero results checklist

Before reporting "nothing found", rule out each of these and say which you checked:

1. The query failed or timed out (that is UNKNOWN, not zero).
2. The window is outside the table's projection range, or partitions are in another time zone.
3. A logging filter drops the action you asked about.
4. The WebACL scope filter or field name is wrong (camelCase on Athena, lowercase on CWL).
5. The field does not exist for this upstream (JA4 on API Gateway).
6. The metric for the same WebACL and window is also zero. If the metric is non-zero and an
   unfiltered log query for the window is zero, the log path is missing data.
7. Every literal in the predicate is right: partition values in the table's projection format,
   and epoch bounds computed by Athena from dates, not converted by hand.
8. A positive control returns rows: the same query, with the same time and partition predicates,
   without the narrowing filter (for example without the client IP). A control over another
   window proves nothing about this one. For a split window, every chunk needs its own control,
   and its first and last timestamps must sit close to its bounds (see "Partitions"). A query
   that cannot return rows for the control cannot return them for the question either.
