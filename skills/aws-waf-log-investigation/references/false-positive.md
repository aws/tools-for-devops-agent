# WAF false-positive investigation

The question is never "did a rule match" (it did). It is "does this client behave like a person
or system the business serves, and does the matched content look like normal language for this
endpoint". Attack traffic and legitimate traffic can trip the same rule; what tells them apart is
everything around the block.

## Before querying

- For a complaint you need the client IP and an approximate time. Also useful: the URL, what the
  user was doing, and how the block showed up (403, CAPTCHA, timeout). With a specific IP, go
  straight to the targeted investigation; do not start with a broad scan.
- Logs are required for a full investigation. Without logging, `GetSampledRequests` can show a
  sample of the last 3 hours if sampling is enabled; say that it is a sample, and suggest enabling
  logging.
- If a logging filter is active, confirm ALLOW records exist in the window. The ALLOW history is
  the strongest signal here. Without it, do not guess; offer to design a scope-down only if the
  user already knows it is a false positive.
- Do not assume the user is right. Verify with the logs.

## Targeted investigation (one IP)

Collect these for the IP over the window, all actions. Each is an independent question.

1. **What blocked it, exactly.** The terminating rule, and for a managed group the sub-rule from
   `ruleGroupList[].terminatingRule.ruleId`. Read the `ruleGroupList` entry for the group that
   `terminatingRuleId` names: a BLOCK inside any other group's entry comes from a group running in
   Count (see `references/log-data-facts.md`). If the IP has no BLOCK in the window, say so and
   check the log path (metric versus unfiltered query) before concluding it was never blocked.
2. **Its ALLOW history.** ALLOW:BLOCK ratio, and what it was doing before and after the block:
   which pages, in what order, at what pace. Someone who browsed `/page/1` to `/page/35` at human
   speed and then got blocked on a search is a very different client from one whose first and
   only requests are blocked.
3. **Pace.** Peak and average requests per minute.
4. **Breadth of matching.** How many distinct rules terminated its non-ALLOW requests.
5. **The blocked requests themselves.** URI, method and query string (`httpRequest.args`) of each
   block, quoted as logged. The query string is logged even when match details are empty.
6. **Why it matched.** For SQLi and XSS rules, the match details show the matched location and
   fragment: `terminatingRuleMatchDetails` when the rule blocked, the matching entry's
   `ruleMatchDetails` when it only counted. For other rules, the sub-rule name tells you the
   inspected component (see `references/log-data-facts.md`); read that component from the record.

Read the matched content as language, not as a signature. `best way to drop table tennis
lessons` contains SQL keywords and is a normal search phrase. `0 UNION ALL SELECT NULL,version()--`
is not. A natural-language sentence, a product name, a file path
a real user would type, or markup an editor normally produces all point toward a false positive.
Note any text transformations configured on the rule: the fragment you see is after transformation.

## Reading the signals

| Signal | Points to false positive | Points to real attack |
|---|---|---|
| ALLOW:BLOCK for the IP | High (above about 10:1); a real browsing history around the block | Zero ALLOW, or ALLOW only on probe paths |
| Pace | Human (below about 10 per minute) | Machine (above about 200 per minute) |
| Rules triggered | One rule, one specific content trigger | Three or more distinct rules: scanning |
| Blocked URIs | Business paths the site really serves | `/admin`, `/wp-login.php`, `/.env`, paths the site does not have |
| Matched content | Natural language, business data | Payload syntax: quote-comment, stacked queries, `<script>`, `../` chains |
| Identity | Known customer, partner, office egress, `bot:verified` service | Hosting/datacenter IP with no business relation |

These thresholds are starting points. A partner API can legitimately run above 200 per minute; a
low-traffic site makes ratios noisy. Say which way each signal points and why.

Zero ALLOW on its own is ambiguous: an attacker and a first-time visitor blocked on their first
request look the same. Use the other signals.

## Verdicts

- **"WAF-side likely false-positive candidate, needs business confirmation."** Several signals
  point to a legitimate client and none to an attack (for example: real browsing history, human
  pace, a single rule, natural-language match). State what confirmation is missing: the user's
  report, the business owner, session or account evidence, or a controlled replay.
- **"Not a false positive."** Machine pace with no ALLOW history and several distinct rules, or
  an unmistakable payload.
- **"Cannot determine."** Mixed or thin signals. Ask: are these URIs normal business flow? Is
  this IP a known customer, partner or internal service? Does this endpoint accept content that
  looks like code (HTML, XML, SQL-like filters)?

Never write "confirmed false positive" from WAF logs alone. If a query behind any signal failed,
the verdict refuses; a failed ALLOW query produces exactly the zero that reads as "attacker".

## Proactive scan (no specific IP)

To find legitimate users hidden among blocked traffic:

1. Take IPs with few blocks in the window (fewer than about 10). Dedicated attackers usually
   have many.
2. For each, count its ALLOWs. Drop those with none.
3. Candidates are IPs with ALLOW:BLOCK above about 5:1. Present them as candidates for the
   targeted investigation, not as false positives.

"No candidates" does not mean no false positives. Say why the scan may have missed them (no
low-block IPs, the window missed business hours, nobody fit the profile).

## Challenge and CAPTCHA complaints

A user who "gets a CAPTCHA every time" or "the app breaks" was not blocked by a rule match in the
usual sense. Their request reached a Challenge or CAPTCHA rule without a valid token. Read the
records with action `CHALLENGE` or `CAPTCHA` for the client or the path:

1. **Which rule issued it, and on which URIs and methods.** Group by URI and method.
2. **Could this request ever pass?** Only a browser `GET` with `Accept: text/html` over HTTPS
   receives the interstitial and can solve it. Anything else gets the status code with no way to
   proceed: HTTP 202 for a challenge, 405 for a CAPTCHA. That includes API calls expecting JSON,
   `POST` and other non-`GET` methods, CORS preflights, media and native apps. A rule that
   challenges API paths breaks them for everyone; recommend excluding those paths, or using the
   rule only where clients already hold a token.
3. **Why the token failed.** `challengeResponse.failureReason` or `captchaResponse.failureReason`.
   AWS documents the values but not their meanings; these are the likely readings:
   - `TOKEN_MISSING` on API or app paths: the client cannot run the script at all.
   - `TOKEN_DOMAIN_MISMATCH`: the token domain configuration does not cover this host, common
     with several domains or a CDN in front.
   - `TOKEN_EXPIRED` on browser paths: real users meeting friction, for example long sessions
     against a short immunity time.
   - `TOKEN_INVALID`: the token could not be read, possibly tampered; lean toward abuse rather
     than a false positive, and say it is a lean.
4. **Was an Anti-DDoS event active?** If records carry
   `awswaf:managed:aws:anti-ddos:event-detected`, `ChallengeAllDuringEvent` challenged every
   challengeable request; that is expected and ends with the event (see `references/ddos.md`).
   `challengeable-request` alone is on almost every request the group sees and proves nothing.

## Before you call a blocked request an attack

In an attack investigation it is tempting to file every blocked request under the attack. Run
the targeted checks on any blocked IP that also has a browsing history, a single rule match and
natural-language content. One legitimate user blocked by an attack-detection rule is a finding
the owner needs; leaving it inside an "attack, already blocked, no action needed" summary hides
it.

## If it is a false positive

Recommend a scope-down rather than disabling or loosening the rule globally:

- Before proposing any slice, count everything the rule matched on that slice over a wider
  window (days, not the complaint's minutes). If attack payloads hit the same path, a path
  exception lets them through; say so, and narrow further or leave the decision to the owner with
  that trade-off stated.
- Exclude the narrowest slice that explains it: the specific URI path, plus method or host if
  needed. A scope-down can use any nestable statement, but the request body is not in the logs,
  so a body-based scope-down cannot be checked against them.
- For a managed sub-rule, override that sub-rule to Count and add a label-based custom rule that
  blocks on its label outside the excluded slice, or use the group's scope-down statement.
- Prefer a narrow path/method exception over an IP allowlist for a partner.
- Write it as a change plan with a backup of the WebACL, the LockToken step, and rollback.
