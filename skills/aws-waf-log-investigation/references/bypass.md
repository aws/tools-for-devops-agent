# WAF bypass detection

A bypass leaves no rule match. So this method reads **ALLOW** traffic and looks for behaviour
that a person using the site would not produce. Reviews that only read BLOCK and COUNT records
cannot find any of this.

Logging must include ALLOW. If a logging filter drops ALLOW, say that bypass detection is not
possible until ALLOW is logged.

## 1. Is there an anomaly at all (metrics)

Compare this week's `AllowedRequests` on `Rule=ALL` with the previous week's.

- Below 2x: no significant volume anomaly. A scan can still find low-volume abuse.
- 2x to 3x: moderate; ask whether a launch, campaign or seasonal event explains it.
- 3x or more: significant. If mitigated requests (blocked + challenge + captcha) also rose
  strongly, WAF is catching part of it. If they did not, the extra traffic is being allowed.
- A previous week of zero makes any ratio meaningless; say so.
- Check for the Anti-DDoS `event-detected` label to see whether AMR declared an event (where to
  look is in `references/ddos.md`).

Then scan 1-2 hours: the window the user gave, or else the peak hour of `AllowedRequests` and the
hour around it.

## 2. Scan allowed traffic

Exclude static assets (see `references/log-data-facts.md`) and requests labelled `bot:verified`
from every signal. Each signal is independent; report each, and mark any whose query failed as
UNKNOWN rather than empty.

| Signal | What to look for | Default threshold per window | Why |
|---|---|---|---|
| Crawlers | Unique non-static URIs per IP | more than 50 | People view a handful of pages; crawlers walk the catalogue |
| Repeaters | Many requests to few URIs per IP | more than 200 requests to fewer than 10 URIs | Brute force, credential stuffing, inventory polling |
| Datacenter, unclassified | `signal:known_bot_data_center` or `signal:cloud_service_provider:<name>`, without `bot:verified` or `bot:unverified` | more than 50 requests | Hosting traffic Bot Control saw but did not identify. Cloud-hosted clients often carry only the `cloud_service_provider` signal (measured: every request from a cloud-hosted scraper fleet carried it, and none carried `known_bot_data_center`) |
| Scripted clients | UA contains curl, python-requests, wget, httpie, go-http-client, java/, okhttp, libwww-perl | more than 10 requests per IP and UA | Honest automation that was allowed |
| Distributed tool | Per JA4: unique IPs, total requests, unique URIs | more than 10 IPs and 500 requests and 50 URIs | One client library run from many hosts; URI breadth filters out popular browser fingerprints |
| UA rotation | Per JA4: unique UAs and unique IPs | more than 5 UAs from fewer than 5 IPs | One TLS stack claiming to be many browsers; few IPs keeps large NAT egress out |
| UA/TLS mismatch | A browser UA whose JA4 is also carried by traffic that is plainly not that browser: scanners blocked for payloads, scripted-client UAs, or many hosts in several regions sending the identical UA string. Compare with the JA4s of clients that claim the same browser and behave like people. Sharing a JA4 with scanners is a reason to look; flag a client only if its own behaviour is not a person's | any volume | The UA is a header the sender chose; the JA4 reflects the TLS library actually used |
| Token sharing | Requests with `token:accepted`, grouped by the `awswaf:managed:token:id:<id>` label: unique IPs per token id | judge the count | One solved session used from many IPs: a botnet passing a token around |

Thresholds are absolute counts for a 1-2 hour window. Scale them with the window and the site:
a large catalogue site has honest users above 50 pages, and a 6-hour window passes them more
easily.

Token sharing notes: group by the token id label, never by the cookie or the token value. One
session can carry several different token values (each acquisition re-encrypts part of it), and
the JS SDK sometimes sends the token in an `x-aws-waf-token` header with no cookie. Tokens exist
only where a client SDK, Challenge or CAPTCHA issues them; with Bot Control Common alone, every
request is `token:absent` and this signal is unavailable.

## 3. From fingerprint to groups to behaviour

A JA4 row names no IP, and one JA4 can cover several unrelated groups. Pick the fingerprint that
matters and list the IPs behind it in the same window, each with its first and last request,
request count, unique URIs, actions and terminating rules. Split them into groups by when they
were active and what they requested. The fingerprint supports a group but does not define one.
Name the groups you set apart, such as scanners blocked for payloads, a single blocked user or a
few stray hosts, instead of folding them in. Re-apply the signal's threshold to each group: a
JA4 that crossed the distributed-tool threshold only because unrelated groups were counted
together is not a distributed-tool finding. Then profile the busiest members of each group with
`references/ip-profile.md`, restricted to ALLOW.

Profile per IP: peak and average requests per minute, unique non-static URIs, the query strings
it sent (attack-shaped arguments that were allowed are a direct bypass lead), actions over time,
labels, UA and JA4.

## 4. Verdict per IP

Check identity first: a `bot:verified` crawler can legitimately be fast and broad. Then:

| Evidence | Verdict |
|---|---|
| `known_bot_data_center` or `cloud_service_provider`, peak above about 50 per minute, no `bot:` label | High: undetected datacenter bot |
| Scripted-client UA and no `bot:` label | High: Bot Control missed it (missing, or the relevant sub-rule is in Count) |
| Peak above about 200 per minute and more than 50 URIs | High: scraper |
| Peak above about 200 per minute and fewer than 10 URIs | High: endpoint hammering (brute force or flood participant) |
| More than 50 URIs, no `bot:` label, moderate pace | Likely scraper; ask whether it is a known partner or crawler |
| Browser UA, plausible browser JA4, moderate pace | Cannot determine; ask the user |

"High" here is strong WAF-side evidence. To the user it is still "probable abuse" or "possible
lead". Confirmation of impact needs origin or business data.

If the labels query failed, refuse the verdict: an empty label list from a failure reads exactly
like "Bot Control did not classify it", which pushes every branch toward "bypass".

## 5. Report

- List each signal with its candidates, or "none found", or "UNKNOWN: <reason>".
- For each group, give its members, its window, its request count and the paths it walked (for
  example `/item/<sku>`).
- End with a mitigation plan for each High or Likely finding, chosen from the directions below
  and written as a plan for a person to apply (SKILL.md Step 4). For "Cannot determine", say
  what evidence would decide it instead.
- If every signal is empty and none failed: "no obvious bypass in this window". That is not a
  guarantee; nothing crossed a threshold.
- If every signal is empty and some failed: you cannot say whether bypass candidates exist.
- If metrics show ALLOW traffic but an unfiltered log query returns nothing, the problem is the
  log path, not the traffic.

## Remediation directions

- No Bot Control: deploy it. Common level misses bots that send a browser UA.
- Bot Control present but missed: consider Targeted level, which needs the client SDK (web,
  mobile) for its token-based rules. Recommend it only when datacenter or automated traffic shows
  active abuse, not merely because it exists.
- High pace: rate-based rules, keyed per IP or on a header/label for distributed sources.
- Shared tokens: Targeted Bot Control's token reuse rules (`TGT_TokenReuseIp*`).
- An Allow rule keyed on something the client controls (UA, a header, a cookie) is a bypass by
  design; key it on an IP set, ASN, or WAF token instead.
- To let the origin act on WAF's classification, forward labels as headers with dynamic label
  interpolation.
