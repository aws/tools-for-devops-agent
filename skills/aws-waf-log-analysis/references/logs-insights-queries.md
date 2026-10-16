# CloudWatch Logs Insights Query Library for AWS WAF Logs

Read-only queries for investigating WAF activity when the logs are in a CloudWatch Logs log group (the group name starts with `aws-waf-logs-`). Query IDs mirror the Athena library: `QI-NN` answers the same question as `QA-NN` in `athena-queries.md`. All times are UTC. Use this library when no Athena table exists or when the log group is the only log destination; otherwise Athena is better for joins and for the label queries (QA-09, QA-10) which are clumsier here.

## Conventions (read first)

1. **Query language.** All queries below use the Logs Insights query language (QL) except where noted. They are started with `logs:StartQuery` against `<log_group>` and a start and end time, and read with `logs:GetQueryResults`. Do not use the PPL or SQL languages for label counting; see QI-09.
2. **Field names are flattened with dots.** WAF logs are JSON, and Logs Insights discovers nested fields as `httpRequest.clientIp`, `httpRequest.uri`, `httpRequest.httpMethod`, `httpRequest.country`, `challengeResponse.failureReason`, `captchaResponse.failureReason`, `labels.0.name`, plus the top-level `action`, `terminatingRuleId`, `responseCodeSent`, `ja4Fingerprint`, `requestBodySize`, `oversizeFields`. Field names are case-sensitive: they are camelCase here (Athena lower-cases them).
3. **Arrays are the weak spot.** Array elements are addressed by position (`labels.0.name`, `labels.1.name`, and so on), and the order of elements is not guaranteed. Counting labels this way needs one query per position (see QI-09 for the bounded procedure). For `headers`, `ruleGroupList`, `terminatingRule` and `ruleMatchDetails`, do not rely on positional fields. Extract them from `@message` with a regex `parse`, as the queries below do. Case-insensitive header names use `(?i:name)` inside the regex.
4. **`parse` takes the first match in each record.** If a request has several rule-group entries, `parse` returns the first one only. State this limit when you report counts built on a parsed field.
5. **Window rule.** Choose the time range with the start and end parameters of `StartQuery`, not with `filter @timestamp`. Prefer the narrowest window first (the incident window, or the default from SKILL.md, "Defaults when input is missing") and widen only if the result is empty. Logs Insights bills by data scanned and a wide window on a busy web ACL is slow.
6. **Cost and truncation.** Every query result reports `statistics.bytesScanned`; report it for each query you run. A query returns at most 10,000 rows and a `limit` of up to 10,000 can be set; the queries below use `limit 50` or `limit 100`, except the QI-09 per-position and label-set queries, which use `limit 1000`; say so when a result is capped. Poll `GetQueryResults` until `status` is `Complete`; `Failed`, `Cancelled` or `Timeout` means the result is not usable.
7. **Multiple web ACLs in one log group.** Add `filter webaclId like /<web_acl_name>/` as the first line when several web ACLs share a log group. (Not validated.)
8. **Rules.** Read-only: only `StartQuery` and `GetQueryResults`. No `PutQueryDefinition`, no changes to the log group.
9. **Missing fields.** A `stats ... by` on a field that no record has returns a row with an empty group or no rows. Treat that as "not present in the window", not as an error.
10. **Escape `/` in regex literals.** A regex literal in Logs Insights is delimited by `/`, so every literal slash inside it must be written `\/`. An unescaped slash is rejected with a `MalformedQueryException` (validated). Write the path `/api/login` as `/^\/api\/login/`.

Placeholders: `<log_group>`, `<ip>`, `<ip_list>` (comma-separated quoted IPs, for example `"203.0.113.10", "203.0.113.11"`), `<uri>`, `<host>`, `<rule>` (terminating rule or rule group), `<sub_rule>` (rule inside a managed group), `<focus_label>`, `<pos>` (label array position), `<uri_path>` (URI path after the leading slash, each further slash escaped as `\/`; see QI-15), `<web_acl_name>`, `<token_id_prefix>` (first 12 characters of a token id from QI-16b).

Note on `<sub_rule>`: for a request stopped inside a rule group, `terminatingRuleId` is the group and the inner rule is only in `ruleGroupList`. The regex `parse @message /"terminatingRule":\{"ruleId":"(?<subRule>[^"]+)"/` extracts it, because the top-level field is named `terminatingRuleId` and so never matches `"terminatingRule":{`. Records stopped by a rule outside a group have an empty `subRule`.

---

### QI-01 — What happened when? (action by 5-minute bucket)

**Use when:** you need the shape of an incident: when blocking started and stopped, and whether allowed traffic dipped.

```
stats count(*) as requests by bin(5m) as bucket, action
| sort bucket asc
```

**Interpret:** Normal is a steady ALLOW series with few or no denials. A block, CAPTCHA or CHALLENGE series that starts and ends sharply marks an event window; use its first and last bucket as the window for later queries. Buckets with no requests are absent from the output, not zero. A drop in ALLOW at the same time as a rise in BLOCK warrants QI-02 and QI-04 to tell whether legitimate clients are affected; the buckets alone do not say.

### QI-02 — What is denying traffic? (terminating rules and sub-rules)

**Use when:** you need to know which rule (and which rule inside a managed group) is blocking or challenging requests, and how many clients are affected.

```
filter action in ["BLOCK", "CAPTCHA", "CHALLENGE"]
| parse @message /"terminatingRule":\{"ruleId":"(?<subRule>[^"]+)"/
| stats count(*) as requests, count_distinct(httpRequest.clientIp) as clients, min(@timestamp) as firstSeen, max(@timestamp) as lastSeen
  by action, terminatingRuleId, subRule, responseCodeSent
| sort requests desc | limit 50
```

**Interpret:** One rule with very few clients and a bounded first/last window points to a single source. Many clients on one sub-rule points to a broad pattern or a false positive on legitimate users. `responseCodeSent` may be populated (for example a custom response code, or 202 for Challenge as seen in testing) or empty; when empty, assume the defaults: BLOCK = 403, CAPTCHA = 405, CHALLENGE = 202. An empty `subRule` means the terminating rule is not inside a rule group. Request counts can lag slightly because of late log delivery. Rule IDs and label strings differ in casing and namespace (for example rule `SizeRestrictions_BODY` produces label `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body`). Never construct a label from a rule ID; copy the exact string from QI-09 or from DescribeManagedRuleGroup.

### QI-03 — Who is affected by one rule or sub-rule? (affected population)

**Use when:** you have a `<rule>` or `<sub_rule>` from QI-02 and need to see who triggers it: IPs, countries, user agents, methods, URIs, TLS fingerprint.

```
filter terminatingRuleId = "<rule>"
| parse @message /"name":"(?i:user-agent)","value":"(?<ua>[^"]*)"/
| stats count(*) as requests by httpRequest.clientIp, httpRequest.country, ua, httpRequest.httpMethod, httpRequest.uri, ja4Fingerprint
| sort requests desc | limit 50
```

For a sub-rule inside a managed group, replace the first line with `filter @message like /"terminatingRule":\{"ruleId":"<sub_rule>"/`.

**Interpret:** One IP with a browser-like user agent on one method and URI is a single client repeating a request. Many IPs sharing one user agent and JA4 value suggests a tool or botnet. A missing user agent (empty `ua`) is itself a signal for header-based rules. If every row has `requests` of 1 or 2, the grouping is too fine; drop `httpRequest.uri` and `ja4Fingerprint` from the `by` list and read the populations first. A browser-looking user agent proves nothing alone, because it is trivially spoofable; compare `ja4Fingerprint` and the URI pattern.

### QI-04 — What did the denied clients do when allowed? (allowed history)

**Use when:** you need to know whether the denied clients also sent allowed requests, which separates abuse from a rule that is simply too strict.

Logs Insights has no joins, so this is two steps.

Step 1: run QI-03 and collect the `httpRequest.clientIp` values into `<ip_list>`.

Step 2:

```
filter httpRequest.clientIp in [<ip_list>]
| stats count(*) as requests, count_distinct(httpRequest.clientIp) as clients by action, httpRequest.httpMethod, httpRequest.uri
| sort requests desc | limit 50
```

**Interpret:** A client that sent normal ALLOW requests (for example GET pages) and is blocked only on one method and URI suggests that specific request shape trips the rule. A client that is only ever denied suggests dedicated abuse traffic. If step 1 returned many IPs, use the top 20 by requests and say that the rest were not checked. Step 2 rows with only the denying action mean the clients never had an allowed request in the window.

### QI-05 — Challenge and CAPTCHA behavior

**Use when:** challenges or CAPTCHAs are in play and you need to see failure reasons, which clients receive them and whether they carry a WAF token.

```
filter action in ["CHALLENGE", "CAPTCHA"]
| parse @message /"name":"(?i:user-agent)","value":"(?<ua>[^"]*)"/
| parse @message /"name":"(?i:accept)","value":"(?<accept>[^"]*)"/
| fields (@message like /x-aws-waf-token|aws-waf-token=/) as hasToken
| stats count(*) as requests, count_distinct(httpRequest.clientIp) as clients
  by action, challengeResponse.failureReason, captchaResponse.failureReason, httpRequest.httpMethod, accept, ua, hasToken
| sort requests desc | limit 50
```

**Interpret:** `hasToken` is 1 when the record contains a WAF token header or cookie and 0 otherwise. No rows means no challenge or CAPTCHA action in the window. Challenged `POST` or non-HTML (`accept` is JSON or empty) requests commonly fail because API clients cannot run the challenge script. Many `hasToken = 0` rows with failure reason `TOKEN_MISSING` point to clients that never completed the challenge. Check `hasToken`, `accept` and `ua` together before concluding that real users are affected. A scripted client typically shows a library user agent (for example `python-requests/...`), `accept` of `application/json` or `*/*` and `hasToken = 0`; the same pattern from a real browser user agent is also possible, so one signal alone is not enough.

**Not validated with data:** the scripted-client pattern.

### QI-06 — What exactly matched? (match details)

**Use when:** you need the matched condition and location behind a blocking rule.

```
filter action = "BLOCK"
| parse @message /"ruleMatchDetails":\[\{[^\]]*?"conditionType":"(?<cond>[^"]+)"/
| parse @message /"ruleMatchDetails":\[\{[^\]]*?"sensitivityLevel":"(?<sens>[^"]+)"/
| parse @message /"ruleMatchDetails":\[\{[^\]]*?"location":"(?<loc>[^"]+)"/
| stats count(*) as requests by cond, sens, loc
| sort requests desc | limit 50
```

**Not validated with data on Logs Insights** (executed, 0 rows). Each field has its own `parse` because key order inside a match-detail object is not guaranteed (on the Athena side, SQLi details carried `sensitivityLevel` `LOW` while XSS and regex details carried none; see QA-06), and a key that is not logged then leaves its column empty instead of dropping the row. Only the first match-detail object of each record is read.

**Interpret:** Match details are not logged for every rule type. A header regex rule logs `REGEX` / `HEADER` with no sensitivity level, so an empty `sens` is normal; size-restriction and header-presence rules log nothing, so the query returns no rows or empty columns (both validated on Athena). SQLi and XSS condition type, sensitivity level and location: expected per WAF log format; not validated. Matched sample data is nested deeper and is not extracted here; do not read raw records for payload text. Characterize payloads by class with QI-19 step 2 (filtered to the blocking rule) and return class, count and location only to the main agent. Use QI-03 and QI-07 to characterize rules that return no details.

### QI-07 — Body size and oversize profile

**Use when:** a body-size or oversize-related rule is blocking, or you suspect requests exceed the inspection limit.

```
filter requestBodySize > 0
| stats count(*) as requests, pct(requestBodySize, 50) as p50Body, max(requestBodySize) as maxBody, max(requestBodySizeInspectedByWAF) as maxInspected
  by httpRequest.uri, oversizeFields
| sort requests desc | limit 50
```

**Not validated with data** (executed, 0 rows; field names from the WAF log format documentation; an absent field gives an empty result or blank column).

**Interpret:** Most URIs show small bodies. A URI whose `maxBody` is far above its `p50Body` is where large requests concentrate. Compare `maxInspected` with `maxBody`: if inspection stops at the web ACL's body limit while the body is larger, the remainder is not inspected. A non-empty `oversizeFields` means WAF could not inspect all of that component. Empty `oversizeFields` with a large body means the body was inspected in full.

### QI-08 — Count-mode and non-terminating matches

**Use when:** you want to know which rules are matching without blocking (Count mode), including rules inside managed rule groups and rate-based rules that never reached their limit action (rate-based rules in Count mode appear in the top-level list; validated on Athena only).

```
filter @message like /"nonTerminatingMatchingRules":\[\{/
| parse @message /"nonTerminatingMatchingRules":\[\{"ruleId":"(?<countRule>[^"]+)","action":"(?<countAction>[^"]+)"/
| stats count(*) as requests by countRule, countAction
| sort requests desc | limit 50
```

**Interpret:** The regex matches the first non-empty `nonTerminatingMatchingRules` list in each record, whether it is at the top level or inside a rule-group entry, so a record with Count matches in several places is counted once, under the first. Validated: it surfaces managed rules in Count mode (action `COUNT`). The log also carries an `overriddenAction` for such a match; read a raw record when you need to know what the group's own action would have been. A Count rule with very high volume may reflect heavy traffic from a few sources (for example a load test or shared NAT address), but volume alone does not make it benign. Corroborate with QI-13 (small fixed URI set, stable JA4, steady rate over a long period, no other threat labels) before treating the source as known automation, and still report it. A Count rule that matches mostly the same clients as a later block is a candidate for blocking. No rows means no Count-mode activity.

### QI-08c — Count-mode matches per client (who is behind a Count rule?)

**Use when:** QI-08 shows a Count-mode rule with high volume and you need to know which clients produce it.

```
filter @message like /"nonTerminatingMatchingRules":\[\{/
| parse @message /"nonTerminatingMatchingRules":\[\{"ruleId":"(?<countRule>[^"]+)","action":"(?<countAction>[^"]+)"/
| stats count(*) as requests, count_distinct(httpRequest.uri) as distinctUris, min(@timestamp) as firstSeen, max(@timestamp) as lastSeen by httpRequest.clientIp, countRule, countAction
| sort requests desc | limit 50
```

**Interpret:** Like QI-08, the regex reads only the first non-empty `nonTerminatingMatchingRules` list in each record, so a record with Count matches in several places is attributed to the first one only. A short `firstSeen` to `lastSeen` span with few URIs is a burst against one endpoint; a long span with a steady rate and a small URI set is a candidate for known automation (corroborate with QI-13). There is no per-5-minute maximum in this form: to compare a burst with a rate limit and name its endpoint, run QI-01 filtered to that client (add `and httpRequest.clientIp = "<ip>"`) with 5-minute bins and `httpRequest.httpMethod`, `httpRequest.uri` added to the `by` list. Each client line names method, URI, requests and the busiest 5-minute count against the limit (threat-hunting B-C). Several rows for one rule means the volume is shared, so a dominant client does not explain the quieter ones.

### QI-09 — Label frequency

**Use when:** you need an overview of which labels (managed-rule signals) the traffic carries.

Logs Insights QL cannot expand an array into one row per element, so count the labels by array position and add the counts per label. Procedure:

1. Run the label-set query below first. The largest number of `{"name":...}` entries in any returned set is the maximum labels per record, `max`. If the output hit its `limit`, raise the limit before trusting `max`.
2. Run the per-position query for `<pos>` = 0 to `max - 1`. Each position is a full scan of the window, so cost grows with `max`; keep the window narrow.
3. Sum `n` per label name across positions. Ignore the row with an empty `labels.<pos>.name`; it counts records with fewer labels than `<pos>+1`.
4. Get the total with `stats count(*) as total` over the same window and compute shares from it.

```
stats count(*) as n by labels.<pos>.name
| sort n desc | limit 1000
```

If any position returns exactly 1000 rows, the list is truncated; narrow the window or filter first and report the truncation. The label-set query:

```
parse @message /"labels":\[(?<labelSet>[^\]]*)\]/
| stats count(*) as requests by labelSet
| sort requests desc | limit 1000
```

**Interpret:** A broad label such as a challengeable-request marker may appear on every request and is not by itself suspicious. A specific rule label with a small count that matches a QI-02 sub-rule confirms what that rule saw. The label-set query shows which labels travel together per distinct set; many distinct sets mean small counts per set. Copy a `<focus_label>` exactly as shown for QI-10.

**Validated:** the positional QL form. PPL (`expand`) and SQL (`UNNEST`) forms do not give per-label counts for log-group queries; do not use them.

### QI-10 — Which labels co-occur with a focus label?

**Use when:** you have a `<focus_label>` and want to see whether it travels with other labels, forming a signature.

```
filter @message like /"<focus_label>"/
| parse @message /"labels":\[(?<labelSet>[^\]]*)\]/
| stats count(*) as requests by labelSet
| sort requests desc | limit 50
```

**Interpret:** First confirm the `<focus_label>` exists and is spelled exactly as in QI-09; a misspelled label also returns 0 rows. Each row is a complete label set carried by requests that include the focus label; the other labels in the set are the co-labels, and `requests` over the sum of all rows gives the share. A high, stable share for one set across many requests means a composite signature. Sets can differ even for traffic from the same clients (validated). No rows means the focus label never appeared. A set that lacks a co-label does not show the traffic is distinct: a missing co-label can simply mean the other rule never evaluated the request (earlier termination, rule order, or a rule scoped to other methods or paths). Never treat absence of a co-label as evidence about the traffic. To see what a denied client carries, add `and httpRequest.clientIp = "<ip>"` to the filter and drop the label from it.

### QI-11 — Per-IP request banding (low-and-slow detection)

**Use when:** you suspect traffic is spread across many IPs to stay under per-IP limits.

```
stats count(*) as req by httpRequest.clientIp
| fields req, httpRequest.clientIp, (req > 10) * 4 + (req > 5 and req <= 10) * 3 + (req >= 3 and req <= 5) * 2 + (req = 2) * 1 as bandCode
| stats count(*) as ips, sum(req) as totalRequests, min(req) as bandMin by bandCode
| sort bandCode asc
```

**Interpret:** `bandCode` 0 = 1 request, 1 = 2 requests, 2 = 3-5, 3 = 6-10, 4 = 11 or more per IP. Add the event's focus filter (a rule, label or URI) as a first `filter` line to band only the suspect traffic. A large IP population in band 2 that carries most of the requests indicates deliberate distribution under per-IP thresholds. A few IPs in band 4 carrying everything is a concentrated source, handled by per-IP controls. **Not validated with multi-band data** (executed).

### QI-12 — Distinct URIs per IP (crawling and scanning)

**Use when:** you suspect scraping or path scanning and want clients touching an unusually wide range of URIs.

```
stats count(*) as requests, count_distinct(httpRequest.uri) as distinctUris, sum(action != "ALLOW") as denied by httpRequest.clientIp
| filter distinctUris >= 20
| sort distinctUris desc | limit 50
```

**Interpret:** A client far above the typical `distinctUris` with a low `denied` count is crawling without being stopped. Logs Insights has no median over groups here; get the baseline by running the same query without the `filter` line and reading a few mid-table rows. Lower the `>= 20` threshold for small sites. `count_distinct` is approximate for large counts. Validated: scanning clients stand out by distinct URIs. With few IPs in the window, read each client's own value rather than a median.

### QI-13 — Known-automation candidates (top talkers by volume and user agent)

**Use when:** you need to separate high-volume known automation (load tests, monitors, partner integrations) from suspicious traffic.

```
parse @message /"name":"(?i:user-agent)","value":"(?<ua>[^"]*)"/
| stats count(*) as requests, sum(action = "ALLOW") as allowed, sum(action != "ALLOW") as denied, count_distinct(httpRequest.uri) as distinctUris, count_distinct(ja4Fingerprint) as distinctJa4, earliest(ua) as sampleUa by httpRequest.clientIp
| sort requests desc | limit 20
```

**Interpret:** One address with a tool-style user agent, a small fixed set of URIs and a dominant share of traffic is a candidate for known automation, but a user agent is trivially spoofable. Require corroboration before classifying it: a small fixed URI set, a stable JA4 (`distinctJa4` of 1), a steady rate over a long period, and no other threat labels. Even then, still report the source rather than silently excluding it. Low-volume clients with browser or empty user agents that appear in QI-02 are the ones to investigate. `sampleUa` shows one user agent, not all. A client with both `denied` and `allowed` requests is a candidate for the attacker-residue check (QI-19). The `allowed` sum (`action = "ALLOW"`) is not validated; `denied` uses the validated QI-12 form. Compute the share of traffic by dividing a client's `requests` by the total from a plain `stats count(*)` over the same window.

#### QI-13b — Sensitive-endpoint bursts and per-client peak rates (top talker set apart)

**Use when:** always on the Mode B fast path and in B-C (mandatory); same question as QA-13b. Two `stats` commands: the first counts per minute, the second takes the peak.

Endpoint scope (one row per client, method and URI for non-GET requests and sensitive paths):

```
fields httpRequest.clientIp as client, httpRequest.httpMethod as method, httpRequest.uri as uri
| filter method != "GET" or uri like /(?i)(pay|checkout|card|billing|login|signin|sign-in|logon|auth|signup|sign-up|register|password|passwd|reset|forgot|otp|verify)/
| stats count(*) as perMin by client, method, uri, bin(1m) as minute
| stats sum(perMin) as requests, max(perMin) as peakPer1min, min(minute) as firstMinute, max(minute) as lastMinute by client, method, uri
| sort peakPer1min desc | limit 60
```

Client scope: drop the `filter` line and `method`, `uri` from both `by` lists (one row per client with `peakPer1min`); run it a second time with `bin(5m)` for `peakPer5min` to compare with a rate-based rule's limit. Start the three queries together.

**Interpret:** as QA-13b. Logs Insights cannot name the top talker inside the query: take it from QI-13 in the same pass, report its rows separately (Known automation when B0 corroborates it), and read every other client on its own peak numbers. A POST burst on a payment or checkout URI (short `firstMinute` to `lastMinute` span, high `peakPer1min`) is a card-testing candidate; on login, signup or password-reset URIs, credential stuffing or fake-account creation. Each such row, and each other client whose `peakPer5min` exceeds a rate-rule limit, is a finding. Never group by `httpRequest.args`. A URI that carries a payload is reported as its class (`[traversal-lfi]`), not as the string. Validated with data (endpoint and client-scope variants executed against a WAF log group).

### QI-14 — Shield Advanced automatic application layer mitigation

**Not validated with data** (both queries executed, 0 rows).

**Use when:** Shield Advanced automatic application layer DDoS mitigation may be active and you need to see what it terminated.

```
filter terminatingRuleId like /^ShieldMitigationRuleGroup/
| parse @message /"terminatingRule":\{"ruleId":"(?<subRule>[^"]+)"/
| stats count(*) as requests, count_distinct(httpRequest.clientIp) as clients, min(@timestamp) as firstSeen, max(@timestamp) as lastSeen
  by terminatingRuleId, subRule, action
| sort requests desc | limit 50
```

**Interpret:** This query only shows requests that a Shield mitigation rule terminated (Block, or a Challenge/CAPTCHA action). Count-mode mitigation rules are non-terminating and never appear under `terminatingRuleId`; use QI-14b for them. No rows here means no terminating Shield action in the window (or the feature is not enabled). Compare `firstSeen` and `lastSeen` with the event window from QI-01.

#### QI-14b — Shield mitigation rules in Count mode

```
filter @message like /ShieldMitigationRuleGroup/ and @message like /"nonTerminatingMatchingRules":\[\{/
| parse @message /"ruleGroupId":"(?<shieldGroup>[^"]*ShieldMitigationRuleGroup[^"]*)","terminatingRule":(?:null|\{[^}]*\}),"nonTerminatingMatchingRules":\[\{"ruleId":"(?<countRule>[^"]+)"/
| stats count(*) as requests by shieldGroup, countRule
| sort requests desc | limit 50
```

**Interpret:** Rows show which Shield mitigation rules matched in Count mode inside `ruleGroupList` and how many requests they saw, which indicates what the mitigation would act on under its configured action (Shield sets the action, which can be Block, Challenge or Count). No rows means no Count-mode Shield matches in the window. The regex shape was validated with another managed group name; Shield rows were not validated. If a group entry has several Count matches, only the first rule of that entry is reported. The `\{[^}]*\}` part that skips a `terminatingRule` object stops at the first closing brace, so it fails (no match, row dropped) when that object contains nested objects such as `ruleMatchDetails`; an entry with a terminating rule is not a Count-only case anyway, but expect under-counting if such records exist.

### QI-15 — Rule-out check for a host, path or client

**Use when:** you need to show whether a specific path, host or client was denied at all.

```
filter httpRequest.uri like /^\/<uri_path>/
| stats count(*) as requests, count_distinct(httpRequest.clientIp) as clients by action, terminatingRuleId
| sort requests desc
```

Slashes inside the regex must be escaped (Convention 10). Everything: `filter httpRequest.uri like /^\//`. A path: `filter httpRequest.uri like /^\/api\/login/` (so `<uri_path>` is `api\/login`). Escape other regex characters in the path as well (for example `.` as `\.`).

To scope by client, add `| filter httpRequest.clientIp = "<ip>"`. The host is a request header, not a field, so parse it first:

```
parse @message /"name":"(?i:host)","value":"(?<host>[^"]*)"/
| filter host = "<host>"
```

Put these two lines before the `stats` line.

**Interpret:** Only `ALLOW` rows (from an explicit Allow rule or from `Default_Action`) mean nothing on that scope was denied, so WAF is not the cause of an error there. Explicit Allow rules are not denials; with a Block default action, `Default_Action` rows with action `BLOCK` are denials. Any BLOCK, CAPTCHA or CHALLENGE rows name the rule responsible and the number of clients hit; take that rule to QI-02 and QI-03. An empty result means no requests reached WAF for that scope in the window, which is a different finding from "not denied". With a host filter, check the spelling and form of the host value first (the Host header can include a port, or differ from the public name); run the `parse` line alone with `stats count(*) by host` to see the values that exist.

### QI-16 — Token reuse and redistribution

**Use when:** CAPTCHA, Challenge or SDK-integrated apps are in use and you suspect one WAF token being reused across many IPs (token redistribution), **and** the logs carry no `awswaf:managed:token:id:` labels. When QI-09 or QI-18 shows token labels (posture P1 or P2 in D-2b), run QI-16b instead; this raw header or cookie query is the fallback for posture P0 or missing labels. Whether the leading part of the cookie value equals the token id is not documented; do not join the two.

**Not validated with data** (executed, 0 rows).

```
parse @message /"name":"(?i:x-aws-waf-token)","value":"(?<hdrToken>[^"]+)"/
| parse @message /aws-waf-token=(?<cookieToken>[^;"]+)/
| fields coalesce(hdrToken, cookieToken) as token
| filter ispresent(token)
| stats count_distinct(httpRequest.clientIp) as ipCount, count(*) as requests, count_distinct(ja4Fingerprint) as distinctJa4 by token
| filter ipCount > 1
| sort ipCount desc | limit 50
```

**Interpret:** A token seen from several IPs while `distinctJa4` stays 1 means a genuine token was extracted and redistributed (the TLS fingerprint is the same client library), not forged. A token shared by a few IPs from the same user is often a mobile or NAT address change. No rows means no tokens were present in the window, or no token-carrying traffic was reused. Token values are never printed: Logs Insights has no hash function, so `token` holds the raw value in the query result. In the output, show at most a short prefix and suffix (for example the first and last 4 characters) or redact it entirely, and report counts, not the token text.

#### QI-16b — Token reuse by token id (token labels)

**Use when:** the logs carry `awswaf:managed:token:id:` labels (QI-09 or QI-18) and you need to know whether one client session (token) is used from many IPs, and whether it is one genuine token being redistributed or many generated or shared ones.

**Not validated with data** (executed, 0 rows: the test log group had no token-id labels). The `parse` shape and `substr` were validated on the `token:absent` status label.

```
filter @message like /awswaf:managed:token:id:/
| parse @message /awswaf:managed:token:id:(?<tokenId>[^"]+)"/
| parse @message /awswaf:managed:token:fingerprint:(?<tokenFp>[^"]+)"/
| parse @message /"name":"(?i:user-agent)","value":"(?<ua>[^"]*)"/
| fields substr(tokenId, 0, 12) as tokenIdPrefix
| stats count_distinct(httpRequest.clientIp) as ipCount, count(*) as requests, count_distinct(tokenFp) as distinctFingerprints,
  count_distinct(ua) as distinctUa, count_distinct(ja4Fingerprint) as distinctJa4, count_distinct(httpRequest.country) as distinctCountries,
  min(@timestamp) as firstSeen, max(@timestamp) as lastSeen, earliest(httpRequest.uri) as sampleUri by tokenIdPrefix
| filter ipCount > 1
| sort ipCount desc | limit 50
```

Notes: grouping is on a 12-character prefix (`substr` is zero-based), so the full token id never enters the result; prefix collisions are possible but unlikely. `sampleUri` is one URI, not the top one; use QI-16c for the URI mix. `count_distinct` is approximate for large counts.

**Interpret:** Many IPs on one token id with `distinctFingerprints` = 1 and `distinctUa` = 1 means one genuine token was extracted and redistributed, not forged. Otherwise interpret as QA-16b in `athena-queries.md`. No rows means no token id was seen from more than one IP in the window.

#### QI-16c — Drill into one token id (URIs and time buckets)

**Use when:** QI-16b surfaced a token id and you need its timeline and targets.

**Not validated with data** (executed, 0 rows).

```
filter @message like /awswaf:managed:token:id:<token_id_prefix>/
| parse @message /awswaf:managed:token:id:(?<tokenId>[^"]+)"/
| stats count(*) as requests, count_distinct(httpRequest.clientIp) as ips, count_distinct(httpRequest.country) as countries,
  count_distinct(tokenId) as tokenIds by bin(5m) as bucket, httpRequest.uri, action
| sort bucket asc | limit 200
```

**Interpret:** New IPs appearing in every bucket on the same few URIs (search, catalog, pricing) is a rotation pattern; ALLOW on every row while coordinated or token-reuse labels are present is detected-not-blocked. `tokenIds` greater than 1 means the prefix matched more than one token. Do not print `tokenId` itself; it exists only for the count.

### QI-17 — IP-prefix concentration (/16 and /24)

**Use when:** traffic is spread over many IPs (QI-11) and you need to know whether they cluster in a few networks (no ISP field; `clientAsn` needs an ASN match statement; see QA-17).

```
parse httpRequest.clientIp /^(?<p16>\d+\.\d+)\.(?<o3>\d+)\./
| fields concat(p16, ".0.0/16") as prefix16, concat(p16, ".", o3, ".0/24") as prefix24
| stats count(*) as requests, count_distinct(httpRequest.clientIp) as ips, count_distinct(httpRequest.country) as countries,
  earliest(httpRequest.country) as sampleCountry by prefix16, prefix24
| sort requests desc | limit 100
```

For the /16 roll-up, drop `o3` and `prefix24` (`parse httpRequest.clientIp /^(?<p16>\d+\.\d+)\./`, group `by prefix16`). Add the event's focus filter as a first `filter` line. IPv6 addresses do not match the regex and collect in one row with empty prefixes; for them, parse the first three hextets (`/^(?<v6>[0-9a-fA-F]*:[0-9a-fA-F]*:[0-9a-fA-F]*)/`, a rough /48, approximate for compressed addresses; not validated).

**Interpret:** Many distinct IPs in a few /16s with 1 to 5 requests each is a pool (residential proxy, mobile carrier ranges or one hosting provider) rather than independent users. A slice spread evenly over hundreds of /16s looks more like a broad user base or a distributed botnet. Prefixes are not ISPs; attribution options are in QA-17. Compute each row's share of the window by dividing `requests` by a plain `stats count(*)` over the same window (Logs Insights has no window functions). Validated: executes and groups IPv4 clients by /16 and /24.

### QI-18 — Token-status profile (posture check)

**Use when:** you need to know whether clients on each path present WAF tokens and in what state (D-2b posture), before choosing QI-16b or QI-16, or in A3 when deciding `CLIENT_CANNOT_SOLVE`.

```
fields (@message like /"awswaf:managed:token:accepted"/) as acc, (@message like /"awswaf:managed:token:rejected"/) as rej,
  (@message like /"awswaf:managed:token:rejected:expired"/) as rejExpired, (@message like /"awswaf:managed:token:rejected:domain_mismatch"/) as rejDomain,
  (@message like /"awswaf:managed:token:rejected:(not_solved|invalid)"/) as rejOther, (@message like /"awswaf:managed:token:absent"/) as abs, (@message like /awswaf:managed:token:/) as anyTokenLabel,
  (@message like /"name":"(?i:x-aws-waf-token)"/) as hdr, (@message like /aws-waf-token=/) as ck
| stats count(*) as requests, sum(acc) as accepted, sum(rej) as rejected, sum(rejExpired) as rejectedExpired, sum(rejDomain) as rejectedDomain,
  sum(rejOther) as rejectedOther, sum(abs) as absent, count(*) - sum(anyTokenLabel) as noTokenLabel, sum(hdr) as viaHeader, sum(ck) as viaCookie by httpRequest.uri, action
| sort requests desc | limit 50
```

Notes: an alias in `fields` cannot be reused as a `stats` output name (`MalformedQueryException: Ephemeral field is already defined`; validated), hence the short names. For APIs with ids in the path, group by a parsed path prefix instead of `httpRequest.uri`. The `captcha:` namespace is the same pattern with `awswaf:managed:captcha:`.

**Validated with data:** `token:absent` on 100% of challenged requests on every path, `accepted` and `rejected` 0, no token header or cookie (a scripted client that never solved the challenge). Accepted, rejected and carriage columns not validated with data.

**Interpret:** Divide each column by `requests` for shares and classify each path's posture as in D-2b: `noTokenLabel` near 100% is P0 there (use QI-16); a material `absent` share on ALLOW is P1 there (QI-11, QI-17 first); mostly `accepted` under strict enforcement is P2 (QI-16b first). `rejectedExpired` points to immunity time, `rejectedDomain` to `TokenDomains` (D-2). Header-versus-cookie carriage: see QA-18 in `athena-queries.md`. `viaHeader` and `viaCookie` both 0 while token labels are present can mean the headers were redacted (D-3).

### QI-19 — Attacker residue (what did blocked attackers get through?)

**Use when:** a client was blocked by an injection, bad-input or bot rule, and you need its ALLOW requests. Label-based checks (QI-08, QI-09 on ALLOW) cannot see an allowed probe that no rule labeled.

Step 1: list the clients blocked by those rules and collect them into `<ip_list>`.

```
filter action = "BLOCK"
| parse @message /"terminatingRule":\{"ruleId":"(?<subRule>[^"]+)"/
| filter terminatingRuleId like /(?i)(sqli|xss|crosssitescripting|lfi|rfi|traversal|ssrf|log4j|badinputs|exploitable|restrictedext|badbot|botcontrol|php|wordpress|posix|unix|linux|windows|reputation|anonymous)/ or subRule like /(?i)(sqli|xss|crosssitescripting|lfi|rfi|traversal|ssrf|log4j|badinputs|exploitable|restrictedext|badbot|botcontrol|php|wordpress|posix|unix|linux|windows|reputation|anonymous)/
| stats count(*) as blocked by httpRequest.clientIp
| sort blocked desc | limit 100
```

Step 2: their ALLOW requests, with one flag per payload class instead of the raw query string.

```
filter action = "ALLOW" and httpRequest.clientIp in [<ip_list>]
| fields replace(replace(replace(replace(replace(replace(replace(replace(replace(tolower(httpRequest.uri), "<", "_"), ">", "_"), "'", "_"), "\"", "_"), ";", "_"), "%3c", "_"), "%3e", "_"), "%27", "_"), "%22", "_") as uriSafe
| fields (httpRequest.uri like /(?i)(\.\.|%2e%2e|\/etc\/|\/proc\/|win\.ini)/ or httpRequest.args like /(?i)(\.\.|%2e%2e|\/etc\/|%2fetc|\/proc\/|%2fproc|win\.ini)/) as lfi,
  (httpRequest.args like /(?i)(169\.254\.169\.254|meta-data)/) as ssrf,
  (httpRequest.args like /(?i)((<|%3c)\s*(script|img|svg|iframe)|javascript:|onerror|onload)/) as xss,
  (httpRequest.args like /(?i)(union.{1,12}select|sleep\(|drop.{1,12}table|'|%27)/) as sqli,
  (@message like /(?i)(\$\{jndi|%24%7bjndi)/) as rce
| stats count(*) as requests, sum(lfi) as traversalLfi, sum(ssrf) as ssrfHits, sum(xss) as xssHits, sum(sqli) as sqliHits, sum(rce) as rceHits
  by httpRequest.clientIp, uriSafe
| sort requests desc | limit 50
```

Build the rule regex from the ACL: also OR in every custom Block or Challenge rule name from D-2 and the exact terminating rule-group names seen in QI-02. For the **blocked slice** of one rule (threat-hunting B-C), run step 2 with `filter terminatingRuleId = "<rule>"` instead of the ALLOW and client filter. `uriSafe` is the URI lowercased and defanged as in SKILL.md, "Output", for use inside the querying subagent only; return to the main agent the application path, or `[traversal-lfi]` / the class when the URI itself carries the payload, plus class and count. Never group by `httpRequest.args`, which would return raw payloads. A `sqliHits` count that rests only on a quote (`'` or `%27`) can be a benign value: treat it as low confidence. **Not validated with data:** the flag sums and the `replace`/`tolower` chain (the `fields (... like /.../) as flag` form is validated in QI-18 on `@message` only).

**Interpret:** as QA-19 in `athena-queries.md`: every row is a missed-by-rule finding; a non-zero class column names the payload class that got through (report class and count, never raw text); rows with all flags 0 are the attacker's ordinary requests and still count. Return the field location with each row (URI path when `uriSafe` itself carries the class; otherwise query argument) and give a miss reason only from the rule's documented inspection target (L-1), otherwise "reason not determined".

### QI-20 — Payload patterns inside one sub-rule (attack vs legitimate content, blocking or Count)

**Use when:** as QA-20 in `athena-queries.md`: one managed sub-rule matches payload-bearing requests, in Block or in Count, and you need to split its matches into attack payloads and legitimate content. QI-06 reads only the first match detail of a terminating rule; this query reads the entry of `<sub_rule>` wherever it appears (terminating rule or Count-mode `nonTerminatingMatchingRules`).

```
filter @message like /"ruleId":"<sub_rule>"/
| parse @message /"ruleId":"<sub_rule>","action":"(?<subAction>[^"]+)"(?<detail>[^\]]{0,600})/
| parse detail /"location":"(?<loc>[^"]+)"/
| parse detail /"matchedData":\[(?<md>[^\]]*)/
| parse @message /"terminatingRuleMatchDetails":\[\{"conditionType":"[^"]*","location":"(?<tloc>[^"]*)","matchedData":\[(?<tmd>[^\]]*)\](?:,"matchedFieldName":"(?<field>[^"]*)")?/
| parse httpRequest.args /^(?<queryArg>[^=&]+)=/
| fields coalesce(loc, tloc) as location, coalesce(md, tmd, httpRequest.args) as fragment
| fields substr(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(tolower(fragment), "<", "_"), ">", "_"), "'", "_"), "\"", "_"), ";", "_"), "`", "_"), "$", "_"), "|", "_"), "%3c", "_"), "%3e", "_"), "%27", "_"), "%22", "_"), 0, 40) as patternSafe
| stats count(*) as requests, count_distinct(httpRequest.clientIp) as clients, count_distinct(httpRequest.uri) as distinctUris, earliest(httpRequest.httpMethod) as sampleMethod, min(@timestamp) as firstSeen, max(@timestamp) as lastSeen
  by action, subAction, location, field, queryArg, patternSafe
| sort requests desc | limit 50
```

**Validated with data.** `subAction` is the sub-rule's own action in the record: `COUNT` for a Count-mode match (the request was not stopped by this sub-rule), `BLOCK` for a terminating one; `action` is the request's final action. `detail` stops at the first `]`, so `md` holds the matched tokens of the first match-detail object only; an empty `location` means the sub-rule logged no match details, and `fragment` then falls back to the query arguments. `queryArg` is the first query-argument name only. To name the endpoint of one pattern group, rerun with `filter` on that `patternSafe` value and `stats count(*) by httpRequest.httpMethod, httpRequest.uri` (report a payload-bearing URI as its class). Never group by raw `httpRequest.args` or `md`.

**Interpret:** as QA-20: classify each `patternSafe` inside the querying subagent as attack, legitimate content or not determinable (access-denied-triage, "Payload split inside one sub-rule"); return per (sub-rule, verdict) the counts, distinct clients, field location (`location`, `field`, `queryArg`), endpoint and a pattern summary in words, never `patternSafe`. Only SQL injection and cross-site scripting matches log `matchedData` and a location; other managed sub-rules (for example `Log4JRCE_BODY`) log no match detail, so their split by payload is "not determinable from logs": report it as such.

### QI-21 — Per-client profile of a denied population

**Use when:** as QA-21: one client or a small population is denied by one rule, and you need one profile per client for the Symptom records.

Step 1: run QI-03 for the rule (or sub-rule) and collect the `httpRequest.clientIp` values into `<ip_list>`.

Step 2:

```
filter httpRequest.clientIp in [<ip_list>]
| parse @message /"name":"(?i:user-agent)","value":"(?<ua>[^"]*)"/
| stats sum(action != "ALLOW") as denied, sum(action = "ALLOW") as allowed, count_distinct(httpRequest.uri) as distinctUris, min(@timestamp) as firstSeen, max(@timestamp) as lastSeen
  by httpRequest.clientIp, httpRequest.country, ua
| sort denied desc | limit 50
```

For the paths, rerun step 2 with `stats count(*) as requests by httpRequest.clientIp, action, httpRequest.httpMethod, httpRequest.uri` (report a payload-bearing URI as its class, as QI-19 `uriSafe`). Add `clientAsn` to the `by` list only when the ACL uses an ASN match statement.

**Validated with data.** One row per client and user agent; `denied` and `allowed` add up to the client's requests in the window.

**Interpret:** as QA-21: one row per client and user agent, each one Symptom; the row count (or QI-02 `clients`) is the measured distinct client count.
