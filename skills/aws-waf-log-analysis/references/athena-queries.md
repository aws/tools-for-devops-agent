# Athena Query Library for AWS WAF Logs

Read-only SELECT queries for investigating WAF activity. Bind the placeholders once from the table definition, then reuse them in every query. All times are UTC; the WAF `timestamp` field is milliseconds since epoch.

## Schema binding (do this first)

In AWS DevOps Agent the main agent binds these from `glue:GetTable` and passes them in (SKILL.md, "Bind schema and guard cost"); bind them yourself only if they are missing.

1. **`<req>`:** `httprequest.` for a nested request struct (for example `httprequest.clientip`), empty for flat top-level fields. The SQL below puts `<req>` in front of `clientip`, `uri`, `args`, `httpmethod`, `country` and `headers`.
2. **Label type:** `array<struct<name>>` means `x.name`, as written below. For `array<string>`, change the lambdas `x -> x.name` to `x -> x`, and the UNNEST aliases `l.name` and `co.name` to `l` and `co`.
3. **`<pf>`** from `projection.<key>.format` and `storage.location.template`: projection key `log_time`, format `yyyy/MM/dd/HH/mm` gives `log_time BETWEEN '2026/10/06/17/30' AND '2026/10/06/18/30'`; a non-projected `date` key gives `date BETWEEN '2026/10/06' AND '2026/10/07'`. `SHOW CREATE TABLE` is not needed.
4. **Rules.**
   - Use at most one `UNNEST` per query.
   - Always include `<pf>`; keep the window tight.
   - Add `AND webaclid = '<arn>'` when several web ACLs share a bucket.
   - Report `DataScannedInBytes` for every query you run.
   - Only run SELECT/WITH statements.
5. **Pick the workgroup, run, and poll.**
   - Workgroup: the one named in the request; otherwise one with managed query results enabled (`athena:ListWorkGroups`, then `athena:GetWorkGroup` and check `Configuration.ManagedQueryResultsConfiguration.Enabled`); otherwise `primary`. Record the choice under "Assumptions".
   - Run `athena:StartQueryExecution` in the table's Region with that workgroup.
   - Poll `athena:GetQueryExecution` once per query ID (not `athena:BatchGetQueryExecution`, which the README add-on policy does not grant) until `Status.State` is `SUCCEEDED`, `FAILED` or `CANCELLED`. Read `Statistics.DataScannedInBytes` from that response (the cost guard), then read rows with `athena:GetQueryResults` only after `SUCCEEDED`.
   - On an output-location, workgroup or permission error: record the error, include the bound SQL as advisory text, and continue on the degraded path (D-5 in `discovery-and-log-sources.md`).

`<table>` is the `database.table` name resolved from `glue:GetTable`. When no incident time is known, build the `<pf>` window from the skill's default-window rules (SKILL.md, "Defaults when input is missing").

Placeholders: `<table>`, `<pf>`, `<req>`, `<ip>`, `<uri>`, `<host>`, `<rule>` (terminating rule or rule group), `<sub_rule>` (rule inside a managed group), `<focus_label>`, `<token_id_prefix>` (first 12 characters of a token id from QA-16b).

Note on `<sub_rule>`: for a request stopped inside a rule group, `terminatingruleid` is the group and the inner rule is in `rulegrouplist`. The expression `element_at(filter(rulegrouplist, g -> g.terminatingrule IS NOT NULL), 1).terminatingrule.ruleid` extracts it.

---

### QA-01 — What happened when? (action by 5-minute bucket)

**Use when:** you need the shape of an incident: when blocking started and stopped, and whether allowed traffic dipped.

```sql
SELECT from_unixtime(floor(timestamp / 1000 / 300) * 300) AS bucket, action, count(*) AS requests
FROM <table> WHERE <pf>
GROUP BY 1, 2 ORDER BY 1, 2
```

**Interpret:** Normal is a steady ALLOW series with few or no denials. A block, CAPTCHA or CHALLENGE series that starts and ends sharply marks an event window; use its first and last bucket as the window for later queries. A drop in ALLOW at the same time as a rise in BLOCK warrants QA-02 and QA-04 to tell whether legitimate clients are affected; the buckets alone do not say.

### QA-02 — What is denying traffic? (terminating rules and sub-rules)

**Use when:** you need to know which rule (and which rule inside a managed group) is blocking or challenging requests, and how many clients are affected.

```sql
SELECT action, terminatingruleid AS rule,
       coalesce(element_at(filter(rulegrouplist, g -> g.terminatingrule IS NOT NULL), 1).terminatingrule.ruleid, '-') AS sub_rule,
       responsecodesent AS response_code,
       count(*) AS requests, count(DISTINCT <req>clientip) AS clients,
       min(from_unixtime(timestamp / 1000)) AS first_seen, max(from_unixtime(timestamp / 1000)) AS last_seen
FROM <table>
WHERE <pf> AND action IN ('BLOCK', 'CAPTCHA', 'CHALLENGE')
GROUP BY 1, 2, 3, 4
ORDER BY requests DESC
LIMIT 50
```

**Interpret:** One rule with very few clients and a bounded first/last window points to a single source. Many clients on one sub-rule points to a broad pattern or a false positive on legitimate users. `response_code` may be populated (for example a custom response code, or 202 for Challenge as seen in testing) or empty; when empty, assume the defaults: BLOCK = 403, CAPTCHA = 405, CHALLENGE = 202. Request counts can lag slightly because of late log delivery. Rule IDs and label strings differ in casing and namespace (for example rule `SizeRestrictions_BODY` produces label `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body`). Never construct a label from a rule ID; copy the exact string from QA-09 or from DescribeManagedRuleGroup.

### QA-03 — Who is affected by one sub-rule? (affected population)

**Use when:** you have a `<sub_rule>` from QA-02 and need to see who triggers it: IPs, countries, user agents, methods, URIs, TLS fingerprint.

```sql
SELECT <req>clientip AS client_ip, <req>country AS country,
       element_at(filter(<req>headers, h -> lower(h.name) = 'user-agent'), 1).value AS ua,
       <req>httpmethod AS method, <req>uri AS uri, ja4fingerprint AS ja4, count(*) AS requests
FROM <table>
WHERE <pf>
  AND element_at(filter(rulegrouplist, g -> g.terminatingrule IS NOT NULL), 1).terminatingrule.ruleid = '<sub_rule>'
GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY requests DESC LIMIT 50
```

**Interpret:** One IP with a browser-like user agent on one method and URI is a single client repeating a request. Many IPs sharing one user agent and JA4 value suggests a tool or botnet. A missing user agent (empty `ua`) is itself a signal for header-based rules. Use the same pattern with `terminatingruleid = '<rule>'` for rules that are not inside a group.

### QA-04 — What did the denied clients do when allowed? (allowed history)

**Use when:** you need to know whether the denied clients also sent allowed requests, which separates abuse from a rule that is simply too strict.

```sql
WITH denied AS (
  SELECT DISTINCT <req>clientip AS ip FROM <table>
  WHERE <pf>
    AND element_at(filter(rulegrouplist, g -> g.terminatingrule IS NOT NULL), 1).terminatingrule.ruleid = '<sub_rule>')
SELECT w.action, w.<req>httpmethod AS method, w.<req>uri AS uri,
       count(*) AS requests, count(DISTINCT w.<req>clientip) AS clients
FROM <table> w JOIN denied d ON w.<req>clientip = d.ip
WHERE <pf>
GROUP BY 1, 2, 3 ORDER BY requests DESC LIMIT 50
```

**Interpret:** A client that sent normal ALLOW requests (for example GET pages) and is blocked only on one method and URI suggests that specific request shape trips the rule. A client that is only ever denied suggests dedicated abuse traffic.

### QA-05 — Challenge and CAPTCHA behavior

**Not validated with data in testing:** the test table had no challenge or CAPTCHA rows, so the query was only confirmed to execute.

**Use when:** challenges or CAPTCHAs are in play and you need to see failure reasons, which clients receive them and whether they carry a WAF token.

```sql
SELECT action, challengeresponse.failurereason AS challenge_failure, captcharesponse.failurereason AS captcha_failure,
       <req>httpmethod AS method,
       coalesce(element_at(filter(<req>headers, h -> lower(h.name) = 'accept'), 1).value, '(none)') AS accept,
       coalesce(element_at(filter(<req>headers, h -> lower(h.name) = 'user-agent'), 1).value, '(none)') AS ua,
       cardinality(filter(<req>headers, h -> lower(h.name) = 'x-aws-waf-token')) > 0
         OR any_match(<req>headers, h -> lower(h.name) = 'cookie' AND h.value LIKE '%aws-waf-token=%') AS has_token,
       count(*) AS requests, count(DISTINCT <req>clientip) AS clients
FROM <table>
WHERE <pf> AND action IN ('CHALLENGE', 'CAPTCHA')
GROUP BY 1, 2, 3, 4, 5, 6, 7 ORDER BY requests DESC LIMIT 50
```

**Interpret:** No rows means no challenge or CAPTCHA action in the window. Challenged `POST` or non-HTML (`accept` is JSON or empty) requests commonly fail because API clients cannot run the challenge script. Many `has_token = false` rows with a failure reason point to clients that never completed the challenge. Check `has_token`, `accept` and `ua` together before concluding that real users are affected.

### QA-06 — What exactly matched? (match details)

**Use when:** you need the matched condition and sample data behind a blocking rule.

```sql
SELECT d.conditiontype, d.location,
       transform(slice(d.matcheddata, 1, 5), m -> substr(regexp_replace(regexp_replace(m, '(?i)%(3c|3e|22|27|60|3b)', '_'), '[<>"''`;(){}$|]', '_'), 1, 40)) AS sample_defanged,
       count(*) AS requests
FROM <table>
CROSS JOIN UNNEST(coalesce(element_at(filter(rulegrouplist, g -> g.terminatingrule IS NOT NULL), 1).terminatingrule.rulematchdetails,
                           terminatingrulematchdetails)) AS x(d)
WHERE <pf> AND action = 'BLOCK'
GROUP BY 1, 2, 3 ORDER BY requests DESC LIMIT 50
```

**Interpret:** Match details are not logged for every rule type. In testing, size-restriction and header-presence rules returned no rows here; that is normal, not an error. **Validated in testing:** SQLi rules logged `SQL_INJECTION` with `sensitivitylevel` `LOW` and a `location` (`ALL_QUERY_ARGS` or `BODY`); XSS rules logged `XSS` with no sensitivity level; regex-based rules (path traversal, SSRF, Log4J header) logged `REGEX` with locations such as `ALL_QUERY_ARGS`, `QUERY_STRING` or `ANY_HEADER`. For rules that log no details, use QA-03 and QA-07 to characterize the requests instead. When rows appear, `location` and `sample_defanged` show which part of the request matched; the sample is defanged in the query (special characters replaced, at most 40 characters per element; the `transform` is not validated), and never re-read raw `matcheddata`. `sample_defanged` is for use inside the querying subagent only (to classify the match); return class, count and `location` to the main agent, never the sample.

### QA-07 — Body size and oversize profile

**Use when:** a body-size or oversize-related rule is blocking, or you suspect requests exceed the inspection limit.

```sql
SELECT <req>uri AS uri, oversizefields, approx_percentile(requestbodysize, 0.5) AS p50_body,
       max(requestbodysize) AS max_body, max(requestbodysizeinspectedbywaf) AS max_inspected, count(*) AS requests
FROM <table>
WHERE <pf> AND requestbodysize > 0
GROUP BY 1, 2 ORDER BY requests DESC LIMIT 50
```

**Interpret:** Most URIs show small bodies. A URI whose `max_body` is far above its `p50_body` is where large requests concentrate. Compare `max_inspected` with `max_body`: if inspection stops at the web ACL's body limit while the body is larger, the remainder is not inspected. A non-empty `oversizefields` means WAF could not inspect all of that component. Empty `oversizefields` with a large body means the body was inspected in full.

### QA-08 — Count-mode and non-terminating matches

**Use when:** you want to know which rules are matching without blocking (Count mode), including rate-based rules that never reached their limit action.

```sql
SELECT r.ruleid, r.action, count(*) AS requests
FROM <table> CROSS JOIN UNNEST(nonterminatingmatchingrules) AS x(r)
WHERE <pf>
GROUP BY 1, 2 ORDER BY requests DESC LIMIT 50
```

**Interpret:** A Count rule with very high volume may reflect heavy traffic from a few sources (for example a load test or shared NAT address), but volume alone does not make it benign. Corroborate with QA-13 (small fixed URI set, stable JA4, steady rate over a long period, no other threat labels) before treating the source as known automation, and still report it. A Count rule that matches mostly the same clients as a later block is a candidate for blocking. No rows means no top-level Count-mode activity; run QA-08b for rule groups.

#### QA-08b — Rule-group Count matches (Athena only)

A separate query, because only one UNNEST is allowed. Logs Insights has no separate rule-group query: QI-08 covers both the top-level and the rule-group lists.

```sql
SELECT g.rulegroupid, cardinality(g.nonterminatingmatchingrules) AS n_rules, count(*) AS requests
FROM <table> CROSS JOIN UNNEST(rulegrouplist) AS x(g)
WHERE <pf> AND cardinality(g.nonterminatingmatchingrules) > 0
GROUP BY 1, 2 ORDER BY requests DESC LIMIT 50
```

**Not validated with data in testing:** QA-08b returned 0 rows in testing and was only confirmed to execute.

### QA-08c — Count-mode matches per client (who is behind a Count rule?)

**Use when:** QA-08 shows a Count-mode rule (often a rate-based rule) with high volume and you need to know which clients produce it. A dominant client can hide a second, smaller client that crossed the same limit in a short burst.

```sql
WITH m AS (
  SELECT <req>clientip AS client_ip, r.ruleid AS ruleid, r.action AS rule_action,
         floor(timestamp / 1000 / 300) AS b, <req>uri AS uri, <req>httpmethod AS method, timestamp AS ts
  FROM <table> CROSS JOIN UNNEST(nonterminatingmatchingrules) AS x(r)
  WHERE <pf>),
per_bucket AS (
  SELECT client_ip, ruleid, rule_action, b, count(*) AS n FROM m GROUP BY 1, 2, 3, 4)
SELECT p.client_ip, p.ruleid, p.rule_action, sum(p.n) AS requests, max(p.n) AS max_per_5min,
       (SELECT count(DISTINCT uri) FROM m WHERE m.client_ip = p.client_ip AND m.ruleid = p.ruleid) AS distinct_uris,
       (SELECT min(from_unixtime(ts / 1000)) FROM m WHERE m.client_ip = p.client_ip AND m.ruleid = p.ruleid) AS first_seen,
       (SELECT max(from_unixtime(ts / 1000)) FROM m WHERE m.client_ip = p.client_ip AND m.ruleid = p.ruleid) AS last_seen,
       (SELECT approx_most_frequent(3, method || ' ' || uri, 1000) FROM m WHERE m.client_ip = p.client_ip AND m.ruleid = p.ruleid) AS top_endpoints
FROM per_bucket p GROUP BY 1, 2, 3 ORDER BY requests DESC LIMIT 50
```

**Interpret:** One row per client and Count rule, with a single UNNEST (the bucketing is in a CTE). `max_per_5min` counts only the requests that matched the rule in the busiest 5-minute bucket; compare it with the rule's limit and window. `top_endpoints` gives the client's most frequent method and URI pairs with counts (the `approx_most_frequent` column is not validated; if it errors, drop it and run QA-01 filtered to that client with method and URI added); report a URI containing path traversal as `[traversal-lfi]`. Each client line names method, URI, requests and `max_per_5min` against the limit; a burst on a payment, checkout, login, signup or password-reset URI is a card-testing or credential-stuffing finding whatever its size (threat-hunting B-C). A short `first_seen` to `last_seen` span with a single URI is a burst against one endpoint; a long span with a steady rate and a small URI set is a candidate for known automation (corroborate with QA-13). Several rows for one rule means the Count volume is shared, so a dominant client does not explain the quieter ones. Matches are Count only; the requests were not stopped by this rule.

### QA-09 — Label frequency

**Use when:** you need an overview of which labels (managed-rule signals) the traffic carries.

```sql
SELECT l.name AS label, count(*) AS requests
FROM <table> CROSS JOIN UNNEST(labels) AS x(l)
WHERE <pf>
GROUP BY 1 ORDER BY requests DESC LIMIT 100
```

**Interpret:** A broad label such as a challengeable-request marker may appear on many requests and is not by itself suspicious. A specific rule label (for example a size or header label) with a small count that matches a QA-02 sub-rule confirms what that rule saw. Pick a `<focus_label>` for QA-10.

### QA-10 — Which labels co-occur with a focus label?

**Use when:** you have a `<focus_label>` and want to see whether it travels with other labels, forming a signature.

```sql
WITH scoped AS (
  SELECT labels FROM <table>
  WHERE <pf>
    AND contains(transform(labels, x -> x.name), '<focus_label>'))
SELECT co.name AS co_label, count(*) AS co_count,
       round(count(*) * 100.0 / (SELECT count(*) FROM scoped), 1) AS co_pct
FROM scoped CROSS JOIN UNNEST(labels) AS x(co)
WHERE co.name <> '<focus_label>'
GROUP BY 1 ORDER BY co_count DESC LIMIT 50
```

**Interpret:** First confirm the `<focus_label>` exists and is spelled exactly as in QA-09; a misspelled label also returns 0 rows. `co_pct` is the share of focus-label requests that also carry each other label. A high, stable `co_pct` across many requests means a composite signature. No rows means no other label was logged on those requests. That does not show the traffic is distinct: a missing co-label can simply mean the other rule never evaluated the request (earlier termination, rule order, or a rule scoped to other methods or paths). Never treat absence of a co-label as evidence about the traffic. To see what the focus requests actually carry, list their label sets without the `contains()` filter, restricted to the denied client or rule from QA-03: `SELECT array_join(transform(labels, x -> x.name), ' ; ') AS label_set, count(*) FROM <table> WHERE <pf> AND <req>clientip = '<ip>' AND action = 'BLOCK' GROUP BY 1`. `transform` is not an UNNEST, so the main pattern stays within the one-UNNEST rule.

### QA-11 — Per-IP request banding (low-and-slow detection)

**Use when:** you suspect traffic is spread across many IPs to stay under per-IP limits.

```sql
WITH ip_counts AS (
  SELECT <req>clientip AS client_ip, count(*) AS req FROM <table>
  WHERE <pf> GROUP BY 1)
SELECT CASE WHEN req = 1 THEN '1' WHEN req = 2 THEN '2' WHEN req BETWEEN 3 AND 5 THEN '3-5'
            WHEN req BETWEEN 6 AND 10 THEN '6-10' ELSE '11+' END AS band,
       min(req) AS band_min, count(*) AS ips, sum(req) AS total_requests
FROM ip_counts GROUP BY 1 ORDER BY band_min
```

**Interpret:** Add the event's focus filter (a rule, label or URI) to the inner `WHERE` to band only the suspect traffic. A large IP population in the `3-5` band that carries most of the requests indicates deliberate distribution under per-IP thresholds. A few IPs in `11+` carrying everything is a concentrated source, handled by per-IP controls.

### QA-12 — Distinct URIs per IP (crawling and scanning)

**Use when:** you suspect scraping or path scanning and want clients touching an unusually wide range of URIs.

```sql
WITH per_ip AS (
  SELECT <req>clientip AS client_ip, count(*) AS requests, count(DISTINCT <req>uri) AS distinct_uris,
         count_if(action <> 'ALLOW') AS denied
  FROM <table> WHERE <pf> GROUP BY 1)
SELECT client_ip, requests, distinct_uris, denied,
       (SELECT approx_percentile(distinct_uris, 0.5) FROM per_ip) AS median_distinct_uris
FROM per_ip WHERE distinct_uris >= 20 ORDER BY distinct_uris DESC LIMIT 50
```

**Interpret:** Compare each client's `distinct_uris` with `median_distinct_uris`, the median per IP in the same window. A client far above the median with a low `denied` count is crawling without being stopped. Lower the `>= 20` threshold for small sites. **Validated in testing:** a scanning client that was mostly allowed stood out with more than 200 distinct URIs against a per-IP median of 15 (threshold 20 surfaced it). With only a handful of IPs in the window the median is dominated by one or two clients, so read the other clients' own values too rather than relying on the median alone.

### QA-13 — Known-automation candidates (top talkers by volume and user agent)

**Use when:** you need to separate high-volume known automation (load tests, monitors, partner integrations) from suspicious traffic.

```sql
SELECT <req>clientip AS client_ip,
       arbitrary(element_at(filter(<req>headers, h -> lower(h.name) = 'user-agent'), 1).value) AS sample_ua,
       count(*) AS requests, count_if(action = 'ALLOW') AS allowed, count_if(action <> 'ALLOW') AS denied,
       count(DISTINCT <req>uri) AS distinct_uris,
       round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct_of_traffic
FROM <table> WHERE <pf>
GROUP BY 1 ORDER BY requests DESC LIMIT 20
```

**Interpret:** One address with a tool-style user agent, a small fixed set of URIs and a dominant share of traffic is a candidate for known automation, but a user agent is trivially spoofable. Require corroboration before classifying it: a small fixed URI set, a stable JA4, a steady rate over a long period, and no other threat labels. Even then, still report the source rather than silently excluding it. Low-volume clients with browser or empty user agents that appear in QA-02 are the ones to investigate. `sample_ua` shows one user agent, not all. A client with both `denied` and `allowed` requests is a candidate for the attacker-residue check (QA-19).

#### QA-13b — Sensitive-endpoint bursts and per-client peak rates (top talker set apart)

**Use when:** always on the Mode B fast path and in B-C (mandatory). A short burst from one client (for example a few hundred POSTs to a payment URI in under a minute) disappears in window totals that a load-testing or monitoring client dominates; this query ranks every client by its own peak rate, with the top talker sorted to the bottom so it cannot mask the others.

```sql
WITH r AS (
  SELECT <req>clientip AS client_ip, <req>httpmethod AS method, <req>uri AS uri, action, timestamp AS ts,
         (<req>httpmethod <> 'GET'
          OR regexp_like(<req>uri, '(?i)(pay|checkout|card|billing|login|signin|sign-in|logon|auth|signup|sign-up|register|password|passwd|reset|forgot|otp|verify)')) AS sensitive
  FROM <table> WHERE <pf>),
k AS (
  SELECT client_ip, 'endpoint' AS scope, method, uri, action, ts FROM r WHERE sensitive
  UNION ALL
  SELECT client_ip, 'client' AS scope, '*' AS method, '*' AS uri, action, ts FROM r),
b AS (
  SELECT client_ip, scope, method, uri, floor(ts / 60000) AS b1, count(*) AS n,
         count_if(action = 'ALLOW') AS allowed, min(ts) AS t0, max(ts) AS t1
  FROM k GROUP BY 1, 2, 3, 4, 5),
p AS (
  SELECT b.*, sum(n) OVER (PARTITION BY client_ip, scope, method, uri, floor(b1 / 5)) AS n5 FROM b),
q AS (
  SELECT client_ip, scope, method, uri, sum(n) AS requests, sum(allowed) AS allowed,
         max(n) AS peak_per_1min, max(n5) AS peak_per_5min,
         from_unixtime(min(t0) / 1000) AS first_seen, from_unixtime(max(t1) / 1000) AS last_seen
  FROM p GROUP BY 1, 2, 3, 4)
SELECT CASE WHEN client_ip = max_by(client_ip, IF(scope = 'client', requests, -1)) OVER () THEN 'top-talker' ELSE 'other' END AS cohort,
       client_ip, scope, method,
       CASE WHEN regexp_like(uri, '(?i)(\.\.|%2e%2e|/etc/|%2fetc|/proc/|%2fproc|win\.ini)') THEN '[traversal-lfi]' ELSE substr(regexp_replace(regexp_replace(uri, '(?i)%(3c|3e|22|27|60|3b)', '_'), '[<>"''`;(){}$|]', '_'), 1, 80) END AS uri_defanged,
       requests, allowed, peak_per_1min, peak_per_5min, first_seen, last_seen
FROM q ORDER BY cohort, peak_per_1min DESC LIMIT 60
```

**Interpret:** Two row types: `scope = 'endpoint'` is one row per (client, method, URI) for every non-GET request and every payment, checkout, card, login, signup or password-reset path (extend the regex with the site's own sensitive paths from D-2 scope-downs or Q-02); `scope = 'client'` is one row per client over all its requests. `peak_per_1min` is the busiest minute; `peak_per_5min` the busiest aligned 5-minute bucket, comparable with a rate-based rule's limit (D-2) when the rule uses a 5-minute window. `cohort = 'top-talker'` (the highest-volume client) sorts last: report its rows separately, under Known automation when B0 corroborates it; every `other` row is read on its own numbers, never against the top talker's. A row with a short `first_seen` to `last_seen` span, a high `peak_per_1min` and a POST to a payment or checkout URI is a card-testing candidate; on a login, signup or password-reset URI, a credential-stuffing or fake-account candidate. Each such row, and each `other` client whose `peak_per_5min` exceeds a rate-rule limit, is a finding (threat-hunting B-C), whatever its share of the window. The `UNION ALL` scans the window twice; keep the fast-path window. Not validated with data (written after runs in which a sub-minute burst of a few hundred payment POSTs went unreported under a load-test client with tens of thousands of requests).

### QA-14 — Shield Advanced automatic application layer mitigation

**Not validated with data in testing:** the test account has no Shield mitigation; both queries below were only confirmed to execute.

**Use when:** Shield Advanced automatic application layer DDoS mitigation may be active and you need to see what it terminated.

```sql
SELECT terminatingruleid AS rule,
       coalesce(element_at(filter(rulegrouplist, g -> g.terminatingrule IS NOT NULL), 1).terminatingrule.ruleid, '-') AS sub_rule,
       action, count(*) AS requests, count(DISTINCT <req>clientip) AS clients,
       min(from_unixtime(timestamp / 1000)) AS first_seen, max(from_unixtime(timestamp / 1000)) AS last_seen
FROM <table>
WHERE <pf> AND terminatingruleid LIKE 'ShieldMitigationRuleGroup%'
GROUP BY 1, 2, 3 ORDER BY requests DESC
```

**Interpret:** This query only shows requests that a Shield mitigation rule terminated (Block, or a Challenge/CAPTCHA action). Count-mode mitigation rules are non-terminating and never appear under `terminatingruleid`; use QA-14b for them. No rows here means no terminating Shield action in the window (or the feature is not enabled). Compare `first_seen` and `last_seen` with the event window from QA-01.

#### QA-14b — Shield mitigation rules in Count mode

```sql
SELECT g.rulegroupid, array_join(transform(g.nonterminatingmatchingrules, r -> r.ruleid), ',') AS rule_ids, count(*) AS requests
FROM <table> CROSS JOIN UNNEST(rulegrouplist) AS x(g)
WHERE <pf> AND g.rulegroupid LIKE '%ShieldMitigationRuleGroup%' AND cardinality(g.nonterminatingmatchingrules) > 0
GROUP BY 1, 2 ORDER BY requests DESC LIMIT 50
```

**Interpret:** Rows show which Shield mitigation rules matched in Count mode and how many requests they saw, which indicates what the mitigation would block if switched to Block. No rows means no Count-mode Shield matches in the window.

### QA-15 — Rule-out check for a host, path or client

**Use when:** you need to show whether a specific path, host or client was denied at all.

```sql
SELECT action, terminatingruleid AS rule, count(*) AS requests, count(DISTINCT <req>clientip) AS clients
FROM <table>
WHERE <pf>
  AND <req>uri LIKE '<uri>%'
GROUP BY 1, 2 ORDER BY requests DESC
```

To scope by client or host, add `AND <req>clientip = '<ip>'` or a host filter: `AND element_at(filter(<req>headers, h -> lower(h.name) = 'host'), 1).value = '<host>'`.

**Interpret:** Only `ALLOW` rows (from an explicit Allow rule or from `Default_Action`) mean nothing on that scope was denied, so WAF is not the cause of an error there. Explicit Allow rules are not denials; with a Block default action, `Default_Action` rows with action `BLOCK` are denials. Any BLOCK, CAPTCHA or CHALLENGE rows name the rule responsible and the number of clients hit; take that rule to QA-02 and QA-03.

### QA-16 — Token reuse and redistribution

**Use when:** CAPTCHA, Challenge or SDK-integrated apps are in use and you suspect one WAF token being reused across many IPs (token redistribution), **and** the logs carry no `awswaf:managed:token:id:` labels. Token labels are added only by token-aware rule groups (Bot Control, ATP, ACFP, Anti-DDoS; posture P1 or P2 in D-2b). When QA-09 or QA-18 shows them, run QA-16b instead: it keys on the token id WAF itself assigns and also gives the token fingerprint. This query, on the raw header or cookie (hashed), is the fallback for posture P0 or when the labels are missing. Whether the leading part of the cookie value equals the token id is not documented; do not join the two.

**Not validated with data in testing:** the test traffic carried no WAF tokens, so the query was only confirmed to execute.

```sql
SELECT to_hex(sha256(to_utf8(coalesce(element_at(filter(<req>headers, h -> lower(h.name) = 'x-aws-waf-token'), 1).value,
                regexp_extract(element_at(filter(<req>headers, h -> lower(h.name) = 'cookie'), 1).value, 'aws-waf-token=([^;]+)', 1))))) AS token_hash,
       count(DISTINCT <req>clientip) AS ip_count, count(*) AS requests,
       count(DISTINCT ja4fingerprint) AS distinct_ja4
FROM <table>
WHERE <pf>
  AND coalesce(element_at(filter(<req>headers, h -> lower(h.name) = 'x-aws-waf-token'), 1).value,
               regexp_extract(element_at(filter(<req>headers, h -> lower(h.name) = 'cookie'), 1).value, 'aws-waf-token=([^;]+)', 1)) IS NOT NULL
GROUP BY 1 HAVING count(DISTINCT <req>clientip) > 1
ORDER BY ip_count DESC LIMIT 50
```

Extraction notes:
- `headers` is an array of name/value structs. Pull one header with `element_at(filter(headers, h -> lower(h.name) = '<name>'), 1).value`; this avoids a second UNNEST.
- The query groups by `to_hex(sha256(to_utf8(<token_expr>)))`, so raw token values never enter the result or the agent's context. Never print token values; report the hash prefix and counts only.
- The token is in the `aws-waf-token` cookie inside the `Cookie` header (browser interstitial, JavaScript SDK and mobile SDK) or in an `x-aws-waf-token` header set by application integration code (see QA-18 for carriage). Parse the cookie with `regexp_extract(cookie, 'aws-waf-token=([^;]+)', 1)`.
- Tables can have `ja3fingerprint`, `ja4fingerprint` or both. Bind the column from `glue:GetTable`: use `ja4fingerprint` when present, otherwise `ja3fingerprint` (also in QA-03), and add the other when both exist.

**Interpret:** A token seen from several IPs while `distinct_ja4` stays 1 means a genuine token was extracted and redistributed (the TLS fingerprint is the same client library), not forged. A token shared by a few IPs from the same user is often a mobile or NAT address change. No rows means no tokens were present in the window, or no token-carrying traffic was reused.

#### QA-16b — Token reuse by token id (token labels)

**Use when:** the logs carry `awswaf:managed:token:id:` labels (QA-09 or QA-18) and you need to know whether one client session (token) is used from many IPs, and whether it is one genuine token being redistributed or many generated or shared ones.

**Not validated with data in testing:** the test windows had no token-id labels, so the query was confirmed to execute on the test table (0 rows) and its extraction and aggregation logic was checked only on synthetic inline rows.

```sql
WITH t AS (
  SELECT regexp_extract(array_join(transform(labels, x -> x.name), ','), 'awswaf:managed:token:id:([^,]+)', 1) AS token_id,
         regexp_extract(array_join(transform(labels, x -> x.name), ','), 'awswaf:managed:token:fingerprint:([^,]+)', 1) AS token_fp,
         <req>clientip AS ip, <req>country AS country, <req>uri AS uri, ja4fingerprint AS ja4,
         element_at(filter(<req>headers, h -> lower(h.name) = 'user-agent'), 1).value AS ua, timestamp AS ts
  FROM <table>
  WHERE <pf> AND any_match(labels, x -> x.name LIKE 'awswaf:managed:token:id:%')),
agg AS (
  SELECT token_id, count(DISTINCT ip) AS ip_count, count(*) AS requests,
         count(DISTINCT token_fp) AS distinct_fingerprints, count(DISTINCT ua) AS distinct_ua,
         count(DISTINCT ja4) AS distinct_ja4, count(DISTINCT country) AS distinct_countries,
         min(from_unixtime(ts / 1000)) AS first_seen, max(from_unixtime(ts / 1000)) AS last_seen
  FROM t GROUP BY 1),
top AS (
  SELECT token_id, max_by(uri, n) AS top_uri
  FROM (SELECT token_id, uri, count(*) AS n FROM t GROUP BY 1, 2) GROUP BY 1)
SELECT substr(a.token_id, 1, 12) AS token_id_prefix, a.ip_count, a.requests, a.distinct_fingerprints,
       a.distinct_ua, a.distinct_ja4, a.distinct_countries, a.first_seen, a.last_seen, top.top_uri
FROM agg a JOIN top ON a.token_id = top.token_id
WHERE a.ip_count > 1
ORDER BY a.ip_count DESC LIMIT 50
```

Notes: bind `ja4fingerprint` or `ja3fingerprint` from `glue:GetTable` as in QA-16. `transform` plus `regexp_extract` reads the labels without an UNNEST (an equivalent form is `element_at(filter(labels, x -> x.name LIKE 'awswaf:managed:token:id:%'), 1).name`). The CTE `t` is read twice, so bytes scanned are about twice a single pass; keep `<pf>` tight. Only a 12-character prefix of the token id is returned; report it truncated and never print token values. Add a focus filter (URI, country, label) inside `t` to scope it.

**Interpret:** Per token id: many IPs with `distinct_fingerprints` = 1 and `distinct_ua` = 1 (often one JA4 as well) means one genuine token was extracted from a real client and redistributed across a proxy or residential pool, not forged. Many user agents or fingerprints on one token id means the token is being generated or shared by different clients. Two or three IPs with one country and one fingerprint is often a mobile user changing networks. A short `first_seen` to `last_seen` span with a few requests per IP fits rotation under per-IP limits (compare QA-11). The fingerprint is not unique per client, so one fingerprint across many token ids is weaker evidence than many IPs on one token id. Bot Control `TGT_TokenReuse*` labels (QA-09) are the native per-5-minute version of this measure. No rows means no token id was seen from more than one IP in the window.

#### QA-16c — Drill into one token id (URIs and time buckets)

**Use when:** QA-16b surfaced a token id and you need its timeline and targets.

**Not validated with data in testing:** executed on the test table, 0 rows (no token-id labels).

```sql
SELECT from_unixtime(floor(timestamp / 1000 / 300) * 300) AS bucket, <req>uri AS uri, action,
       count(*) AS requests, count(DISTINCT <req>clientip) AS ips, count(DISTINCT <req>country) AS countries,
       count(DISTINCT regexp_extract(array_join(transform(labels, x -> x.name), ','), 'awswaf:managed:token:id:([^,]+)', 1)) AS token_ids
FROM <table>
WHERE <pf> AND any_match(labels, x -> x.name LIKE 'awswaf:managed:token:id:<token_id_prefix>%')
GROUP BY 1, 2, 3 ORDER BY 1, requests DESC LIMIT 200
```

**Interpret:** `<token_id_prefix>` is the 12-character prefix from QA-16b, so the full id never enters the output; `token_ids` greater than 1 means the prefix matched more than one token, so read the rows with that in mind. New IPs appearing in every bucket on the same few URIs (search, catalog, pricing) is a rotation pattern; ALLOW on every row with coordinated or token-reuse labels present is detected-not-blocked. A token used in one burst and never again fits a disposable token.

### QA-17 — IP-prefix concentration (/16 and /24)

**Use when:** traffic is spread over many IPs (QA-11) and you need to know whether they cluster in a few networks. WAF logs have no ISP field, and `clientAsn` is logged only when the Web ACL uses an ASN match statement (D-2), so prefix concentration and country are the in-log stand-ins for network attribution.

```sql
WITH p AS (
  SELECT <req>clientip AS ip, <req>country AS country,
         CASE WHEN strpos(<req>clientip, ':') > 0 THEN '(ipv6)'
              ELSE regexp_extract(<req>clientip, '^(\d+\.\d+)\.', 1) || '.0.0/16' END AS p16,
         CASE WHEN strpos(<req>clientip, ':') > 0
              THEN regexp_extract(<req>clientip, '^([0-9a-fA-F]*:[0-9a-fA-F]*:[0-9a-fA-F]*)', 1) || '::/48'
              ELSE regexp_extract(<req>clientip, '^(\d+\.\d+\.\d+)\.', 1) || '.0/24' END AS p24
  FROM <table> WHERE <pf>)
SELECT p16, p24, arbitrary(country) AS sample_country, count(DISTINCT country) AS countries,
       count(*) AS requests, count(DISTINCT ip) AS ips,
       sum(count(*)) OVER (PARTITION BY p16) AS p16_requests,
       sum(count(DISTINCT ip)) OVER (PARTITION BY p16) AS p16_ips,
       round(count(*) * 100.0 / sum(count(*)) OVER (), 2) AS pct_of_requests
FROM p GROUP BY 1, 2
ORDER BY p16_requests DESC, requests DESC LIMIT 100
```

Add the event's focus filter (a label, URI, country or token-id condition) to the inner `WHERE` to measure only the suspect slice. IPv6: all IPv6 rows share the `(ipv6)` /16 value, and `p24` holds the first three hextets as a rough /48; it is approximate when the address is logged in compressed form (`::` inside the first three groups). Not validated with IPv6 data.

**Interpret:** Many distinct IPs in a few /16s with 1 to 5 requests each is a pool (residential proxy, mobile carrier ranges or one hosting provider) rather than independent users; many IPs in one /24 often means one provider's address block. A slice spread evenly over hundreds of /16s looks more like a broad user base or a distributed botnet. Prefixes are not ISPs: if attribution matters, take the top prefixes to a WHOIS or IP-intelligence lookup outside this skill, or recommend an ASN match statement in Count so `clientAsn` is logged (R-11). Bot Control `TGT_TokenReuseAsn*` and `TGT_TokenReuseCountry*` labels (QA-09) are ASN- and country-aware signals WAF already computes. Validated in testing: one /16 holding 99% of requests from a single known-automation IP.

### QA-18 — Token-status profile (posture check)

**Use when:** you need to know whether clients on each path present WAF tokens and in what state (D-2b posture), before choosing QA-16b or QA-16, or in A3 when deciding `CLIENT_CANNOT_SOLVE`.

**Not validated with data in testing:** the test table had no token labels (executed; all token columns 0). The Logs Insights form was validated with `token:absent` data.

```sql
SELECT <req>uri AS uri, action, count(*) AS requests,
       count_if(contains(transform(labels, x -> x.name), 'awswaf:managed:token:accepted')) AS accepted,
       count_if(contains(transform(labels, x -> x.name), 'awswaf:managed:token:rejected')) AS rejected,
       count_if(contains(transform(labels, x -> x.name), 'awswaf:managed:token:rejected:expired')) AS rej_expired,
       count_if(contains(transform(labels, x -> x.name), 'awswaf:managed:token:rejected:domain_mismatch')) AS rej_domain,
       count_if(any_match(labels, x -> x.name IN ('awswaf:managed:token:rejected:not_solved', 'awswaf:managed:token:rejected:invalid'))) AS rej_other,
       count_if(contains(transform(labels, x -> x.name), 'awswaf:managed:token:absent')) AS absent,
       count_if(NOT coalesce(any_match(labels, x -> x.name LIKE 'awswaf:managed:token:%'), false)) AS no_token_label,
       count_if(any_match(<req>headers, h -> lower(h.name) = 'x-aws-waf-token')) AS via_header,
       count_if(any_match(<req>headers, h -> lower(h.name) = 'cookie' AND h.value LIKE '%aws-waf-token=%')) AS via_cookie
FROM <table>
WHERE <pf>
GROUP BY 1, 2 ORDER BY requests DESC LIMIT 50
```

Notes: `labels` can be NULL on records with no labels, so `no_token_label` uses `coalesce` (without it those records are silently not counted; observed in testing). For APIs with ids in the path, group by a path prefix instead of `<req>uri`, for example `regexp_extract(<req>uri, '^/[^/]*(/[^/]*)?')`. The `captcha:` namespace is the same pattern with `awswaf:managed:captcha:`.

**Interpret:** Divide each column by `requests` for shares and classify each path's posture as in D-2b: `no_token_label` near 100% is P0 there (use QA-16); a material `absent` share on ALLOW is P1 there (QA-11, QA-17 first); mostly `accepted` under strict enforcement is P2 (QA-16b first). `rej_expired` points to immunity time, `rej_domain` to `TokenDomains` (D-2). Carriage: WAF reads the token from the `aws-waf-token` cookie (browser interstitial, JavaScript SDK, and the documented mobile SDK examples) or from an `x-aws-waf-token` header (set deliberately by integration code, for example the JavaScript SDK `getToken()` for cross-domain calls). A header means an application integration, not the interstitial; a cookie alone does not tell browser from mobile SDK. Both 0 with token labels present can mean the headers were redacted (D-3).

### QA-19 — Attacker residue (what did blocked attackers get through?)

**Use when:** a client was blocked by an injection, bad-input or bot rule, and you need its ALLOW requests. Label-based checks (QA-08, QA-08b, QA-09 on ALLOW) cannot see an allowed probe that no rule labeled.

```sql
WITH attackers AS (
  SELECT DISTINCT <req>clientip AS ip FROM <table>
  WHERE <pf> AND action = 'BLOCK'
    AND regexp_like(terminatingruleid || '/' || coalesce(element_at(filter(rulegrouplist, g -> g.terminatingrule IS NOT NULL), 1).terminatingrule.ruleid, ''),
        '(?i)(sqli|xss|crosssitescripting|lfi|rfi|traversal|ssrf|log4j|badinputs|exploitable|restrictedext|badbot|botcontrol|php|wordpress|posix|unix|linux|windows|reputation|anonymous)')),
allowed AS (
  SELECT <req>clientip AS client_ip, <req>uri AS uri, coalesce(<req>args, '') AS args,
         CASE WHEN regexp_like(<req>uri || '?' || coalesce(<req>args, ''), '(?i)(\.\.|%2e%2e|/etc/|%2fetc|/proc/|%2fproc|win\.ini)') THEN 'traversal-lfi'
              WHEN regexp_like(coalesce(<req>args, ''), '(?i)(169\.254\.169\.254|meta-data)') THEN 'ssrf'
              WHEN regexp_like(coalesce(<req>args, ''), '(?i)((<|%3c)\s*(script|img|svg|iframe)|javascript:|onerror|onload)') THEN 'xss'
              WHEN regexp_like(coalesce(<req>args, ''), '(?i)(union.{1,12}select|sleep\(|drop.{1,12}table|''|%27)') THEN 'sqli'
              WHEN regexp_like(coalesce(<req>args, ''), '(?i)(\$\{jndi|%24%7bjndi|;\s*(cat|wget|curl)\s)') THEN 'cmd-rce'
              WHEN coalesce(<req>args, '') = '' THEN 'none'
              ELSE 'other' END AS args_class
  FROM <table>
  WHERE <pf> AND action = 'ALLOW' AND <req>clientip IN (SELECT ip FROM attackers))
SELECT client_ip,
       CASE WHEN regexp_like(uri, '(?i)(\.\.|%2e%2e|/etc/|%2fetc|/proc/|%2fproc|win\.ini)') THEN '[traversal-lfi]' ELSE substr(regexp_replace(regexp_replace(uri, '(?i)%(3c|3e|22|27|60|3b)', '_'), '[<>"''`;(){}$|]', '_'), 1, 80) END AS uri_defanged,
       args_class, count(*) AS requests,
       CASE WHEN args_class = 'traversal-lfi' THEN '[class only]' ELSE substr(regexp_replace(regexp_replace(arbitrary(args), '(?i)%(3c|3e|22|27|60|3b)', '_'), '[<>"''`;(){}$|]', '_'), 1, 40) END AS sample_defanged
FROM allowed GROUP BY 1, 2, 3 ORDER BY requests DESC LIMIT 50
```

Build the rule regex from the ACL: also OR in every custom Block or Challenge rule name from D-2 and the exact terminating rule-group names seen in QA-02. For the **blocked slice** of one rule (threat-hunting B-C), reuse the `allowed` CTE with `action = 'BLOCK' AND terminatingruleid = '<rule>'` instead of the ALLOW and attacker filters, and add the sub-rule expression from QA-02 as a column. **Validated in testing:** on an injection probe that WAF mostly blocked, it returned exactly the missed requests: one client, one application URI, class `traversal-lfi`, 15 allowed requests that no label-based check had surfaced. (The URI defang and the `[class only]` rule were added after that run and are not validated.)

**Interpret:** Every row is a missed-by-rule finding: a client that WAF identified as hostile still got these requests through. `uri_defanged` and `sample_defanged` are for use inside the querying subagent only. Return to the main agent the client, the URI (an application path without its query string, or `[traversal-lfi]` / the class for a payload-bearing path), `args_class`, `requests` and the field location (URI path when the URI column is `[traversal-lfi]`; otherwise query argument for any class other than `none`); never the sample or the raw `args`. `traversal-lfi`, `ssrf`, `xss`, `sqli` or `cmd-rce` on ALLOW means no rule caught that payload: name the managed sub-rule whose documented inspection target is that field location (for example a Linux operating system group's `_QUERYSTRING` sub-rule for a query-argument `/proc/` probe) and whether it is in the ACL (D-2). Give a reason for the miss only from the documented inspection target (L-1); otherwise "reason not determined". A `sqli` row that rests only on a quote (`'` or `%27`) can be a benign value (a name with an apostrophe): treat it as low confidence. `none` or `other` rows are the attacker's ordinary requests (reconnaissance) and still count. No rows means the blocked clients got nothing through in the window (if the logging filter keeps ALLOW records).

### QA-20 — Payload patterns inside one sub-rule (attack vs legitimate content, blocking or Count)

**Use when:** one managed sub-rule (for example a SQL injection, cross-site scripting or Log4j sub-rule) matches payload-bearing requests, in Block or in Count, and you need to split its matches into attack payloads and legitimate content (access-denied-triage, "Payload split inside one sub-rule"). Q-06 only covers terminating matches; this query reads the sub-rule's terminating **and** Count-mode (`nonterminatingmatchingrules` inside `rulegrouplist`) match details.

```sql
WITH m AS (
  SELECT action, <req>httpmethod AS method, <req>uri AS uri, <req>clientip AS client_ip, coalesce(<req>args, '') AS args, timestamp AS ts,
         if(g.terminatingrule.ruleid = '<sub_rule>', 'terminating', 'count') AS match_kind,
         coalesce(if(g.terminatingrule.ruleid = '<sub_rule>', g.terminatingrule.rulematchdetails),
                  element_at(filter(g.nonterminatingmatchingrules, r -> r.ruleid = '<sub_rule>'), 1).rulematchdetails) AS d,
         if(g.terminatingrule.ruleid = '<sub_rule>', terminatingrulematchdetails) AS td
  FROM <table> CROSS JOIN UNNEST(rulegrouplist) AS x(g)
  WHERE <pf>
    AND (g.terminatingrule.ruleid = '<sub_rule>' OR any_match(g.nonterminatingmatchingrules, r -> r.ruleid = '<sub_rule>'))),
p AS (
  SELECT action, match_kind, method, uri, client_ip, ts,
         CASE WHEN coalesce(cardinality(d), 0) > 0 THEN element_at(d, 1).location
              WHEN coalesce(cardinality(td), 0) > 0 THEN element_at(td, 1).location ELSE 'not logged' END AS location,
         CASE WHEN coalesce(cardinality(d), 0) > 0 THEN array_join(element_at(d, 1).matcheddata, ' ')
              WHEN coalesce(cardinality(td), 0) > 0 THEN array_join(element_at(td, 1).matcheddata, ' ') ELSE args END AS fragment,
         regexp_extract(args, '(?:^|&)([^=&]+)=', 1) AS first_arg
  FROM m)
SELECT location, first_arg AS query_arg, action, match_kind,
       substr(regexp_replace(regexp_replace(fragment, '(?i)%(3c|3e|22|27|60|3b)', '_'), '[<>"''`;(){}$|]', '_'), 1, 40) AS pattern_defanged,
       count(*) AS requests, count(DISTINCT client_ip) AS clients, count(DISTINCT uri) AS distinct_uris,
       arbitrary(method || ' ' || CASE WHEN regexp_like(uri, '(?i)(\.\.|%2e%2e|/etc/|%2fetc|/proc/|%2fproc|win\.ini)') THEN '[traversal-lfi]' ELSE split_part(uri, '?', 1) END) AS sample_endpoint,
       min(from_unixtime(ts / 1000)) AS first_seen, max(from_unixtime(ts / 1000)) AS last_seen
FROM p GROUP BY 1, 2, 3, 4, 5 ORDER BY requests DESC LIMIT 50
```

**Validated with data.**

**Interpret:** One row per (location, query argument, action, match kind, defanged pattern). `match_kind` `count` rows are Count-mode matches: those requests were not stopped by this sub-rule ("detected, not blocked" for the attack part). `location` is the matched component (`ALL_QUERY_ARGS`, `QUERY_STRING`, `BODY`, a header); `query_arg` is the first query-argument name (for example `q`); for `BODY`, the JSON field name shows only when the defanged pattern carries it. `not logged` means the sub-rule logged no match details: the pattern then comes from the query arguments, and a body match without details is "pattern not determinable". Classify each `pattern_defanged` inside the querying subagent as attack, legitimate content or not determinable (criteria in access-denied-triage, "Payload split inside one sub-rule"), then sum `requests` and `clients` per (sub-rule, verdict, location, query argument). Return to the main agent only the verdict, class, counts, distinct clients, field location, endpoint and a pattern summary in words; never `pattern_defanged` itself. Many rows with `requests` of 1 are normal (each payload differs); classify them as groups.

### QA-21 — Per-client profile of a denied population

**Use when:** one client or a small population (an IP, a user agent, a path set: for example a partner webhook) is denied by one rule, and you need one profile per client for the Symptom records: user agent, country, paths, blocked and allowed counts, first and last seen.

```sql
WITH denied AS (
  SELECT DISTINCT <req>clientip AS ip FROM <table>
  WHERE <pf> AND action IN ('BLOCK', 'CAPTCHA', 'CHALLENGE') AND terminatingruleid = '<rule>')
SELECT w.<req>clientip AS client_ip, w.<req>country AS country,
       element_at(filter(w.<req>headers, h -> lower(h.name) = 'user-agent'), 1).value AS ua,
       count_if(w.action IN ('BLOCK', 'CAPTCHA', 'CHALLENGE')) AS denied, count_if(w.action = 'ALLOW') AS allowed,
       count(DISTINCT w.<req>uri) AS distinct_uris,
       slice(array_agg(DISTINCT w.<req>httpmethod || ' ' || CASE WHEN regexp_like(w.<req>uri, '(?i)(\.\.|%2e%2e|/etc/|%2fetc|/proc/|%2fproc|win\.ini)') THEN '[traversal-lfi]' ELSE w.<req>uri END), 1, 5) AS endpoints,
       min(from_unixtime(w.timestamp / 1000)) AS first_seen, max(from_unixtime(w.timestamp / 1000)) AS last_seen
FROM <table> w JOIN denied d ON w.<req>clientip = d.ip
WHERE <pf>
GROUP BY 1, 2, 3 ORDER BY denied DESC LIMIT 50
```

**Validated with data.**

**Interpret:** One row per (client, country, user agent): each is one Symptom (access-denied-triage, "Per-client symptoms and IP-set evidence"). A client with `allowed` 0 was denied from its first request in the window, which is not evidence of attack by itself (verdict criteria). The number of rows (or QA-02 `clients`) is the measured distinct client count; report it instead of assuming the traffic is distributed or from one source. Several user agents on one IP, or the same user agent on many IPs, are separate facts: report both. `endpoints` lists up to five method and path pairs; a URI that carries a payload is reported as its class.
