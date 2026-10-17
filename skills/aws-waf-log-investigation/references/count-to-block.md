# Count-to-Block evaluation

A Count rule records what it would have blocked. Switching it to Block is safe when everything it
counts over a representative period is traffic you want blocked. So the evidence is **the whole
population of clients the rule matched over the whole observation window**, not the attack you
happened to see.

## 1. Inventory

From the WebACL configuration, list every Count rule:

- Custom rules with `Action: Count`.
- Managed groups with `OverrideAction: Count` (the whole group).
- Each `RuleActionOverrides` entry with `ActionToUse: Count` (one sub-rule).

The configuration does not list managed sub-rules whose default action is already Count, such as
`TGT_TokenAbsent` or `SQLiExtendedPatterns_QUERYARGUMENTS_RC_COUNT`. Find them from the logs:
the distinct rule IDs with action `COUNT` inside `ruleGroupList[].nonTerminatingMatchingRules`.

Get `CountedRequests` per rule with one MetricStat each, over the user's window or else the last
14 days, at a period CloudWatch still keeps for the window's oldest point (see
`references/metric-facts.md`; a finer period returns empty too). The `Rule` dimension is the
rule's `VisibilityConfig.MetricName` for a rule in the configuration, and the sub-rule name for a
managed sub-rule. WAF publishes only non-zero values, so an empty result means different things
depending on where the name came from:

- **Hits.** Needs a decision.
- **Empty, for a name taken from the configuration with `CloudWatchMetricsEnabled: true`, at a
  retained period.** Nothing matched in the window.
- **Empty, for anything else** (metrics disabled, a name not taken from the configuration, a
  query that failed). This is "no data", not zero. Judge it from the logs, and do not call it
  safe.

## 2. Classify

| Bucket | Rules | Decision |
|---|---|---|
| Keep in Count by design | `SizeRestrictions_BODY` (legitimate large uploads and rich-text bodies), `HostingProviderIPList` (VPNs, corporate proxies and integrations live on hosting IPs), `SignalNonBrowserUserAgent` and `CategoryHttpLibrary` (native apps, SDKs, health checks), `TGT_TokenAbsent` unless the client SDK or a Challenge issues tokens to real users (without tokens it matches every unverified request) | Explain why; do not recommend Block |
| Zero hits in the window | | No evidence either way. Low risk to switch only if the window holds representative traffic for what the rule inspects (peaks, campaigns, business cycles; for a `_BODY` rule, requests that carry bodies). Otherwise leave it as it is and say why. The logs never show what bodies were sent |
| Low false-positive prior with hits | `Log4JRCE*`, `JavaDeserializationRCE*`, rules named for a specific CVE | Signature of a specific exploit; still glance at the clients and paths before switching |
| Needs analysis | Everything else | Steps 3-4, one rule at a time, busiest first |

Rank the needs-analysis rules by hits, highest first. Analyse the busiest one or two in this
answer, list the rest as not yet analysed, and offer them at the end of the answer.

## 3. Evidence for one rule

1. **Find the peak.** Hourly `CountedRequests` over 14 days; the busiest hour is where client
   evidence is densest. Size the log window by volume: about 60 minutes below 1,000 per hour,
   15 minutes below 10,000, 5 minutes above.
2. **Find the rule's matches in logs.** A Count sub-rule's matches are in
   `ruleGroupList[].nonTerminatingMatchingRules` (action COUNT); a custom Count rule's in the
   top-level `nonTerminatingMatchingRules`. Check every location listed in `references/log-data-facts.md`.
3. **Check the log count against the metric** for the same aligned window. A large gap means a
   logging filter, scope or partition problem; resolve it before trusting log evidence. If Count
   records are filtered out of logging, evaluate from metrics and priors only (step 5).
4. **Look at the clients, both ends.** The top clients by matches and the clients with the fewest
   matches. Attackers are usually concentrated; the long tail of one-or-two-hit clients is where
   legitimate users hide.
5. **Look at the matched content** at the location the rule inspects (match details for SQLi and
   XSS; the inspected component otherwise). Present it raw.
6. **Look beyond the peak.** Before recommending Block, query the whole 14-day window for every
   distinct client that matched the rule, with its match count and paths. A peak-hour sample can
   be one attack; the decision has to cover everyone the rule would block.

For each client, use the false-positive signals: ALLOW history, pace, number of distinct rules,
paths, User-Agent, JA4, time pattern, bot labels, and whether the matched content is normal
language for that endpoint (see `references/false-positive.md`).

## 4. Decide

| Low-volume clients | High-volume clients | Outcome |
|---|---|---|
| All attack-shaped | All attack-shaped | Block |
| All attack-shaped | Mixed | Probably Block; check the mixed ones for NAT or shared egress |
| Any legitimate-looking | All attack-shaped | Scope down the legitimate slice, then Block the rest |
| Any legitimate-looking | Any legitimate-looking | Keep Count; design a scope-down first |
| Too little data | Anything | Keep Count and ask the user |

- If one host, path or method accounts for most legitimate matches, split the decision: exclude
  that slice and Block the rest.
- If one partner accounts for them, prefer a narrow host/path/method exception over an IP
  allowlist.
- If the logs are incomplete, keep Count. Do not Block on aggregate metrics alone.
- A sibling rule with no matches (for example `_BODY` next to `_QUERYARGUMENTS`) has no evidence
  either way; do not bundle it into the same recommendation.

State the evidence with counts: "rule X matched N requests from M clients in 14 days; all M are
<shape>". Name the clients you could not classify.

## 5. Without logs

Use the rule-type prior and say the result is metrics-only, not validated against request
content:

| Typical false-positive rate | Rules |
|---|---|
| Medium-high | XSS_BODY (rich text), GenericLFI_QUERYARGUMENTS, GenericRFI_QUERYARGUMENTS |
| Medium | XSS_QUERYARGUMENTS, SQLi_BODY (JSON with SQL-like content), SQLi_QUERYARGUMENTS (search and filter parameters), GenericLFI_BODY, GenericRFI_BODY, NoUserAgent_HEADER (health checks, internal services) |
| Low-medium | XSS_COOKIE, RestrictedExtensions_QUERYARGUMENTS |
| Low | SQLi_COOKIE, EC2MetaDataSSRF_BODY, EC2MetaDataSSRF_QUERYARGUMENTS |

## 6. After the switch

Change one rule at a time and leave 24-48 hours between changes. Watch the rule's
`BlockedRequests`, the WebACL's allowed and blocked totals, origin error rates and support
reports. Write the change as a plan in the same answer as the recommendation; a recommendation
to Block without the plan is not finished. The plan has five parts, each named: a backup of the
WebACL (the `get-web-acl` output saved to a file), the current LockToken, the full rule list for
the update (an update replaces all rules), validation, and rollback from the backup.

For CloudFront WebACLs, validate with metrics in us-east-1 and never add a `Region` dimension;
CloudFront metrics have none, and a query with it returns no datapoints. A managed sub-rule's
blocks are under the group's `MetricName` (`Rule=<group metric name>`) or under
`ManagedRuleGroup` + `ManagedRuleGroupRule`. `Rule=<sub-rule name>` carries only its
`CountedRequests` (measured), so it reads empty after the sub-rule is switched to Block.
