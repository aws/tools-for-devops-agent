# WAF DDoS investigation

## 1. Which rules acted (metrics)

Per-rule blocked, challenge and captcha over the last 24 hours (or the user's window), plus the
WebACL total from `Rule=ALL`.

- Anti-DDoS AMR sub-rules are `ChallengeAllDuringEvent`, `ChallengeDDoSRequests` and
  `DDoSRequests`. A rule that challenges is not necessarily AMR; a custom rule with a similar
  name is not AMR. If a custom rule did the challenging, say so.
- If the top rules together explain much less than the WebACL's total mitigated, the main
  mitigator is not in the list (a managed sub-rule without its own series, or one SEARCH did not
  discover). Find it from logs.

## 2. Did AMR declare an event

Look for the label `awswaf:managed:aws:anti-ddos:event-detected` in logs or label metrics. AMR
puts it on every request to the resource during an event, legitimate or not. A label metric is
reported under the action the request finally got, so check `AllowedRequests`,
`BlockedRequests`, `ChallengeRequests` and `CaptchaRequests` (label namespace
`awswaf:managed:aws:anti-ddos`). Absent means AMR did not trigger, whatever else challenged.

Per-request suspicion labels: `ddos-request`, `high-suspicion-ddos-request`, `medium-...`,
`low-...`. `challengeable-request` marks any GET whose URI is not exempted, event or not, so it
proves nothing on its own.

## 3. Find the exact spike

From the time series, find the peak hour, then re-query that hour at 1-minute granularity. Real
spikes are often 2-15 minutes. Use that window, not the day.

## 4. Who drove it (logs)

Top source IPs by volume across **all actions** over the spike window only (about three times
the spike length: a 5-minute spike, a 15-minute window). Flood traffic is often CHALLENGE, not
BLOCK.

For the top IPs, read the terminating rule per IP from logs. Do not infer per-IP attribution from
the aggregate rule table.

Exclude benign services: low-volume, regular, single-URI sources (about 2 per minute) get a label
check; `bot:verified` (Route 53 health checks, monitoring) is legitimate. Never recommend blocking
AWS infrastructure.

Count the drivers only after removing those services and the baseline clients, meaning clients
whose rate in the spike window is about their rate in the same-length window before it. State
the drivers' share: "N IPs sent X of the window's Y requests". List the driving IPs. A
distinct-IP count over the whole window counts health checks and users too. In a measured
flood, more than half of the window's distinct IPs were Route 53 health checks at about 2
requests per minute each.

When a rate-based rule keyed on the client IP blocked the flood, compare each driving IP's
first request with its first BLOCK by that rule (`terminatingRuleId`). ALLOWs before it are the
rule's detection delay (see "AWS WAF behaviour to state correctly" below). In a measured flood,
every ALLOW from a driving source came before its first BLOCK, thousands per source, and none
came after it. ALLOWs after the first BLOCK need another
explanation, but logs do not carry the rule's count, so first count the source's requests over
the rule's evaluation window yourself to see whether it was still above the limit. This
comparison does not apply to other keys, to CHALLENGE actions or to AMR.

## 5. Sanity checks

- If the top IPs total far less than the mitigated volume in metrics (for example under 1,000
  against 300,000), the log window or scope is wrong. Re-check before concluding.
- If the spike is all ALLOW with no labels at all while Bot Control is deployed, that is
  abnormal: Bot Control labels every request it inspects. Suspect a scope-down that excludes the
  path, or traffic before Bot Control was deployed.
- Bot labels and DDoS labels on the same sources: bot-driven flood. High volume with no labels:
  undetected bot or a distributed attack below per-IP thresholds.

## 6. Classify the shape

| Source spread | URIs | Reading | Typical controls |
|---|---|---|---|
| Tens of IPs or fewer, each far above the rate limit | Few | Concentrated flood from a small number of sources, not a widely distributed attack | Per-IP rate-based rule, which is usually what stops it; AMR |
| Tens of IPs or fewer, each far above the rate limit | Many random paths or query strings | Concentrated cache-busting flood | Per-IP rate-based rule, cache 403/404 at CloudFront |
| Hundreds of IPs or more, or any number each below the per-IP limit, even spread | Few | Classic distributed flood | AMR, rate-based rules keyed on something other than the IP |
| Hundreds of IPs or more, even spread | Many random paths or query strings | Cache-busting flood | Cache 403/404 at CloudFront, rate-based rules, AMR |
| Few IPs, each at or below the rate limit | Many | Scraper rather than flood | Bot Control Targeted, rate-based rule |

Count URIs on the path plus the query string: the log's `uri` field excludes the query string,
so a flood that busts the cache with random query strings shows few URIs on `uri` alone.

## AWS WAF behaviour to state correctly

- Rate-based rules usually start acting within 30 seconds, and AWS says it can take up to several
  minutes; in one measured flood each source's first block came 11-25 seconds after its first
  request. ALLOW before BLOCK at the start of a burst is normal. Logs show the configured limit and
  key, not the client's count. A burst that ends within that delay can exceed the limit with no rule
  action at all.
- AMR builds a traffic baseline for each protected resource, within minutes of being enabled. AWS
  recommends adding it during normal traffic. `DDoSRequests` blocks high-rate sources whether or not
  they run JavaScript. `ChallengeAllDuringEvent` challenges challengeable GET requests during an
  event; non-GET requests are not challenged.
- A challenge works only for a browser GET that accepts HTML. Other GETs (API JSON, media) get
  HTTP 202 and cannot proceed, so SPAs and fetch calls break during an event. Recommend an exempt
  URI regex for API paths; do not recommend disabling `ChallengeAllDuringEvent`. Challenging real
  users during an event is expected, and it stops when the event ends.
- AMR's blind spot is a widely distributed, low-rate attack below per-IP thresholds. For that,
  recommend Targeted Bot Control's coordinated activity detection, not disabling AMR.
- No AMR deployed and a flood happened: recommend deploying it.
