# AWS WAF CloudWatch metric facts

Metrics are the most reliable WAF data source: no partition layout, logging filter, query
engine or log delivery problem can touch them. They are also coarse (no IP, URI or payload).
Use them first for "how much, when, which rule", then logs for "who and what".

## Where and how

- Namespace `AWS/WAFV2`. CloudFront-scope WebACL metrics are in **us-east-1**.
- **Dimensions.** CloudFront WebACLs carry **no `Region` dimension** (measured): use
  `WebACL` + `Rule`. REGIONAL WebACLs require `Region=<region>` in every query, including inside
  `SEARCH()` schemas. A query with the wrong dimension set returns an empty, successful result.
- `Rule=ALL` is the WebACL total. `Rule` values are the rules' `VisibilityConfig.MetricName`,
  not their `Name`. Take them from the WebACL configuration.
- A managed sub-rule appears as `Rule=<sub-rule name>` only for what it counted. What it blocked
  is under the group's `Rule=<group metric name>` and under `ManagedRuleGroup` +
  `ManagedRuleGroupRule` (measured: `Rule=<sub-rule name>` returned nothing for an hour in which the other two
  carried the same non-zero block count).
- Other dimension sets exist: `LabelName`+`LabelNamespace`, `Country`, `Attack`, `Device`,
  `ManagedRuleGroup`(+`ManagedRuleGroupRule`), `VulnerabilityCategory`, bot dimensions. Per-country
  and per-label counts are available without logs.
- Metrics: `AllowedRequests`, `BlockedRequests`, `CountedRequests`, `ChallengeRequests`,
  `CaptchaRequests`, `ChallengesSolved`, `CaptchasSolved`, plus sampled bot visibility metrics.

## Absence is not zero

- **Sparse publishing.** A rule that matched nothing in a period publishes no datapoint. On one
  measured WebACL, 4 of 11 rules had no metric at all for 24 hours. Missing means "no data", not
  "never fires".
- **Wrong names look like quiet rules.** A `MetricStat` for a rule name that does not exist
  returns `StatusCode: Complete` with empty values. So does a period finer than the retention for
  that age of data. Use names from configuration, and pick the period from the **oldest** point
  in the window (60 s data kept ~15 days, 300 s ~63 days, 3600 s ~455 days).
- **Rules with metrics disabled** (`CloudWatchMetricsEnabled: false`) publish nothing; their
  absence carries no information.
- **Managed sub-rules publish under their own names**, including ones that never appear in your
  configuration (for example `TGT_TokenAbsent`). The configuration is not a complete list of
  metric names.

## SEARCH versus MetricStat

- `SEARCH()` only discovers series with datapoints in roughly the **last 14 days, measured from
  now**, regardless of the window you query. A quiet rule or an old window can make SEARCH return
  nothing although data exists for that window.
- An explicit `MetricStat` has no discovery step. Before saying "no activity" from a SEARCH, run
  a MetricStat on `Rule=ALL` for the same window and metric set. If it shows traffic, the
  SEARCH result is partial, say so.
- Avoid period 86400. Daily buckets start at your query's start time, so the same event lands
  on different "days" depending on when you ask. Use hourly buckets and group by day in your
  own time zone.

## Hit rate

- Denominator: `AllowedRequests + BlockedRequests + ChallengeRequests + CaptchaRequests` on
  `Rule=ALL`. These are the terminating outcomes, mutually exclusive.
- **Never add `CountedRequests` to the denominator.** Count is non-terminating; a counted
  request also ends as allowed or blocked, so adding it double-counts.
- Rule numerator: that rule's blocked + challenge + captcha + counted.
- A rule-level rate (metrics) and an endpoint-level rate (logs grouped by URI) have different
  denominators; do not compare them. Under a logging filter, endpoint rates from logs are wrong in
  an unpredictable direction; prefer metrics.

## Cross-checking metrics against logs

- Metric > 0 and log rows = 0 for the same WebACL and window: the log path missed data (filter,
  partition, scope or delivery). Do not report the window as quiet.
- For a zero result on a filtered query (one IP, one URI), use two witnesses: the WebACL metric
  and an unfiltered log query over the same window. Only "metric > 0, unfiltered logs = 0" is a
  log-path problem. Both zero is a quiet window. Metric zero but logs non-zero is metric lag.
- Partial gaps: compare only windows aligned to the metric period (an unaligned window measured a
  10.6% false gap). Below about 5% the difference is indistinguishable from timestamp skew.
- A WebACL-level check can hide a per-rule gap: a WebACL that blocked hundreds of thousands of
  requests by rate limit had an empty SQLi series. Compare per rule.

## Bot Control and token labels in metrics and logs

Measured on Bot Control `Version_6.1`, inspection level COMMON, with no client SDK and no
Challenge rule in front of normal traffic:

- 1533 of 1535 requests carried `awswaf:managed:token:absent`.
- `TGT_TokenAbsent` (default action Count) matched every request that was not a verified bot.

So when tokens are never issued, `TGT_TokenAbsent` counts and `token:absent` labels measure
"unverified traffic", not bots. A spike in them is a traffic spike, nothing more. They become a
bot signal only where a client SDK, Challenge or CAPTCHA issues tokens to real browsers.
