# WAF IP investigation

The goal is to say what this address is, with evidence, before anyone acts on it. Blocking a
shared address or a verified service causes an outage; leaving a bot unprofiled hides a bypass.

## 1. Identity first

- Labels: the exact label `bot:verified` (with `bot:name:*`, `bot:organization:*`) is ground
  truth for a known service; Bot Control verifies it from the request's origin IP.
  `bot:user_triggered:verified` and `bot:developer_platform:verified` are treated like
  unverified bots. Route 53 health checks carry `bot:verified`, `bot:name:route53_health_check`
  and UA `Amazon-Route53-Health-Check-Service`; their ranges are the `ROUTE53_HEALTHCHECKS`
  entries in AWS `ip-ranges.json`. Never recommend blocking verified services.
- A UA that claims a service without `bot:verified`: possible spoofing, flag it.
- `signal:known_bot_data_center` or `signal:cloud_service_provider:<name>`: hosting or cloud
  origin. Common for scanners, also for
  legitimate integrations and corporate proxies.
- Regular, low-rate, single-URI traffic (about 2 per minute to `/`) is the shape of monitoring.
  Check its labels before attributing it to anything.

## 2. Is it one client or many behind one address

Count distinct User-Agents and distinct JA4 fingerprints for the IP.

- More than one UA means either NAT (several real users behind one egress) or one client rotating
  UAs. Run the test below whenever there is more than one UA, whatever the JA4 count: a JA4
  identifies the TLS library, so users of one browser family can share it. Tell them apart from
  the UA strings, with version numbers stripped:
  - Several operating systems and several browser families: NAT or shared egress.
  - Five or more UAs that collapse to one or two templates, with machine pace or a JA4 that does
    not fit the claimed browser: rotation by one client.
  - A few templates of one common browser at human pace: cannot tell. A small office looks like
    this; say so rather than calling it rotation.
  - Classify iPhone and iPad UAs as iOS even though they contain "Mac OS X".
- If it is shared egress, blocking it affects many users. Say so and recommend rules keyed on
  behaviour (rate, path, label) instead of the address.
- If the UA list could not be retrieved, the answer is unknown, not "NAT".

## 3. Behaviour

Over the window, all actions:

- Actions and terminating rules (ALLOW versus BLOCK versus CHALLENGE share, which rules).
- Pace: peak and average requests per minute, active minutes, and when blocking started.
- Breadth: unique non-static URIs, path prefixes.
- Query strings it sent, shown raw; attack-shaped arguments that were allowed are a lead.
- Labels over its requests (bot, token, Anti-DDoS suspicion).
- UA and JA4. A JA4 that does not fit the claimed browser is the spoofing signal: compare it
  with the JA4 of other clients claiming the same browser that behave like people.

## 4. Who else sent the same requests

Look for other IPs that sent the same kind of requests in the window, over about the same time
span: the same path templates (`/item/<sku>` rather than one item page), query parameter
names, payload shapes and pace. Leave static assets and landing pages such as `/` and `/login`
out of the match, because everyone requests them. A fleet that splits the work sends few
identical URIs, so match on the pattern, not on exact URIs. Do not match on JA4 or UA, which
unrelated clients can share. If others did, this IP is one member of a group. Say how many, and that
blocking this address alone stops only its share. Saying that an IP acted alone needs this
query, because a profile of one IP cannot show it.

## 5. Verdict

Check identity before any of these.

| Evidence | Verdict |
|---|---|
| Five or more UAs that collapse to one or two templates (step 2), and peak above about 50 per minute | High: bot rotating its User-Agent |
| Peak above about 200 per minute and more than 50 URIs | High: automated scraper |
| Peak above about 200 per minute and fewer than 10 URIs | High: endpoint hammering |
| More than 50 unique non-static URIs | Likely crawler or scraper; ask about partners |
| Otherwise | Cannot determine; ask for business context |

If the pace or breadth query failed, report the verdict as unknown rather than letting a missing
number fall to zero.

Mostly ALLOW with suspicious behaviour: continue with `references/bypass.md`. Mostly BLOCK and it
looks like a person: continue with `references/false-positive.md`.

## 6. Recommending a block

Only after the identity, NAT and step 4 checks. For a single concentrated source with no
legitimate relationship, an IP set is fine; note that cloud-hosted scanners change addresses, so pair it with
a behaviour-based rule. List what matched, what did not, and one other explanation for the same
pattern.
