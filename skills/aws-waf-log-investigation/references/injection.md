# WAF injection investigation

Run every step. The step most often skipped, profiling the source and listing what it got
through, is the one that changes the answer.

## 1. Which rules actually detect injection here

Read the WebACL configuration; do not infer from rule names (a rule called `block-bad-stuff` may
be the SQLi detector, and `sqli-allowlist` is not one).

- Custom rules: any `SqliMatchStatement` or `XssMatchStatement` in the statement tree, including
  inside `And`, `Or` and a rate-based rule's scope-down. Do not count a match nested under `Not`:
  that inverts it (an allowlist, not a detector). Ignore rules whose action is Allow. Keep Count
  rules: a detector in shadow mode is exactly what you may be investigating.
- Managed groups: `AWSManagedRulesSQLiRuleSet`, `AWSManagedRulesCommonRuleSet` (XSS, LFI, RFI,
  size, bad bots), `AWSManagedRulesKnownBadInputsRuleSet` (Log4j, Java deserialization, bad
  host headers), plus any application-specific groups (PHP, WordPress, Linux, Unix, Windows).
- Note which detectors are overridden to Count: their matches are allowed.
- Customer rule groups you did not inspect: name them as not inspected.

If there is no injection detection at all, that is the finding: attacks would neither be blocked
nor visible as matches.

## 2. Which detector fired, and how much

Rank detectors by matches in the window from the data (metrics per rule, then logs), not by
configuration order. Include Count-mode detectors: their matches are in
`nonTerminatingMatchingRules`, top-level for custom rules and inside `ruleGroupList` for managed
sub-rules (see `references/log-data-facts.md`). The request then goes on to later rules, and
is usually allowed.

If no detector fired, say so and check the log path: per-rule metric for the window, logging
filter dropping BLOCK or COUNT, WebACL scope. Cross-check per rule, never at WebACL level: a
WebACL busy with rate-limit blocks says nothing about the SQLi series.

## 3. What was targeted and what was sent

For the busiest detector: target URIs and methods, the matched location and fragments (SQLi and XSS
carry match details: `terminatingRuleMatchDetails` for blocks, the entry's `ruleMatchDetails` for
counts; for others read the inspected component named by the sub-rule), User-Agents and JA4
fingerprints.

Present payloads raw. Classify them by technique (UNION-based, boolean blind, stacked queries,
command execution, reflected XSS, traversal) without claiming any would have worked against the
application.

## 4. Who sent it

The attacking sources are the IPs that sent attack payloads (blocked, or matched by a detector in
Count) during the attack's time span. Select them by those requests, never with a JA4 or UA
filter: a query for "all traffic with the attacker's JA4" pulls in every unrelated client that
uses the same TLS library, and every count built on it is wrong. Then give source IPs, countries,
ASN if known, and how the volume spreads across them.

| Shape | Reading | Typical response |
|---|---|---|
| Many IPs, the same payload sequence and timing, even spread (often one JA4) | One tool run from many hosts | Rate-based or label/fingerprint-keyed rules; IP blocks will not hold |
| One to three IPs | Concentrated source | IP set or rate-based rule, after ruling out NAT and shared egress |
| Many IPs, many fingerprints, low volume each | Untargeted background scanning | Rules already match it; monitor, no new rule |

A shared JA4 says the hosts run the same TLS client, not that they share an operator or intent.
Check what else in the window carries the same JA4 before using it as evidence (SKILL.md Step 3).
Before treating a single source as malicious, check its identity and whether it is a shared or
NAT address (`references/ip-profile.md`).

## 5. What the same sources got through

**List every request the source IPs sent, not only blocked ones.** Group by action, URI and
terminating rule. Scanners send probes that no rule matches; those were ALLOWED and reached the
origin. Typical examples: `/.git/config`, `/server-status`, `/phpinfo.php`, `/.aws/credentials`,
backup archives. Report them as "N requests from the attacking sources were allowed", with the
paths. Never state "nothing reached the origin" from BLOCK rows.

Also check whether any detector in Count mode matched requests that were allowed: those payloads
reached the origin with a match on record.

## 6. Separate legitimate users from the attack

Before filing every blocked request under the attack, account for every IP with a BLOCK in the
window: its block count, first and last block, terminating rules, ALLOW count and JA4. Define
the attack by its timing and payload sequence; a shared JA4 or UA does not make an IP part of
it. Summarise the IPs that fit as one group (count, time span, top members) and list the ones
that do not fit one by one.

An IP that does not fit is its own group. If it looks like a person (an ALLOW browsing history,
a single rule match, natural-language content), run `references/false-positive.md` on it and
make it a separate finding. Otherwise call it a separate scanner, or unclassified. Background
scanning has no single attack window, so classify those IPs one by one. Report the attack's
totals without the blocks of the IPs that do not fit, and report those IPs' blocks separately.

## 7. Conclude within the evidence

- Blocked payloads: "injection attempts, blocked by <rule>". Not "the attack failed".
- Allowed payloads with a Count-mode match, or attack-shaped requests allowed with no match:
  "possible injection bypass lead". Ask for origin access logs, response codes and application
  errors for those requests. WAF logs cannot show whether the application was exploited.
- "The rule is enabled but did not block this payload": confirm the request was ALLOWED, confirm
  no injection rule matched it, confirm the rule is in Block mode, then explain the coverage gap
  (which component the rule inspects, transformations, body size limits).

## Recommendations

- A detector overridden to Count that matched real attack traffic: evaluate switching it to
  Block with `references/count-to-block.md`; do not recommend it from attack traffic alone.
- Allowed probes for sensitive paths: these are an application exposure question first (do those
  paths exist, are they protected), then optionally a custom rule.
- Sources spread across many cloud IPs: prefer rate-based rules, Bot Control, or ASN- and
  label-based rules over IP sets of the current addresses.
