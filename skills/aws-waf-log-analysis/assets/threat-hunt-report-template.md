# Report Template — AWS WAF Threat Hunt

Use this structure for the hunting report artifact produced in SKILL.md, Step B7 (Mode B only). Fill every `<placeholder>` from the investigation records and the log subagent's table; never recompute, round or add a finding the records lack. Keep the section order so recurring hunts diff cleanly. When the runtime cannot create an artifact, put the same sections into the final message after the Output template block.

Artifact naming: `waf-threat-hunt-<web-acl-name>-<YYYY-MM-DD>.md`

Data handling for every section: payloads as class and count plus field location only ("sqli ×75, query argument"); URIs defanged per the SKILL.md defang rule, path traversal shown as the class `traversal-lfi`; no tokens, cookies, authorization values or match-detail samples.

## Report Header

```
# AWS WAF Threat Hunt — <web-acl-name> (<CLOUDFRONT | REGIONAL / region>)
Date: <YYYY-MM-DD> | Window: <start UTC> to <end UTC> | Protected resource: <resource>
Backend: <Athena table | Logs Insights log group | degraded: metrics and sampled requests>
```

## Scope and Assumptions

- Web ACLs and resources covered; window and why (requested or default)
- Backend, queries run, bytes scanned
- Defaults applied, fallbacks used, calls not completed (exact error code)
- Logging-filter limit (ALLOW records dropped or not), redacted fields
- Baseline exclusions (known automation, from B0)

## Executive Summary

- One sentence per confirmed finding: class, client, what WAF did, primary number
- Overall: what WAF caught, what it missed and why (same wording as the Root Cause record)
- Top recommended mitigation

## Findings

One row per confirmed threat finding (one per Cause record), in the order of the records.

| # | Class | Client (IP, UA class) | Rule / sub-rule | Action | Count | Window (UTC) |
|---|-------|-----------------------|-----------------|--------|-------|--------------|
| 1 | <injection / scan / card testing / credential stuffing / bot / volumetric / missed-by-rule> | <client> | <`RuleGroup` / `SubRule`, or "not matched by any rule"> | <BLOCK / ALLOW / COUNT / CHALLENGE / CAPTCHA, with split> | <n> | <first> to <last> |

Classify a blocked portion as `CORRECT_MITIGATION`. Use exact rule and sub-rule IDs, never label casing alone.

## Detected, Not Blocked

- Rate-based rules in Count: one line per client over the limit (UA class, method, URI, requests, `max_per_5min` against the limit, classification)
- Count-mode matches and threat labels on ALLOW requests: rule, label, count, and the rule that would have acted
- Sensitive-path bursts (Q-13b): method, URI, requests, peak per minute and per 5 minutes, first to last seen

Write "none found (<query IDs>)" when empty.

## Known Automation

Required section; write "none found" when empty. Per client: UA class, rate profile, URI set, labels seen, corroboration, effect on rate rules, and what was excluded from baselines. Never called a flood, abusive or an attack, and never grouped with an attacker.

## Attacker Residue

Per blocked attacker: ALLOW count, payload class (`args_class`) and count, field location, the miss reason from the rule's documented inspection target or "reason not determined", or "none allowed (Q-19)". Class and count only.

| Client | ALLOW count | Payload class × count | Field location | Miss reason |
|--------|-------------|-----------------------|----------------|-------------|

## Recommended Mitigations

Advisory only; validate each change in Count first; never disable or remove a rule group or the Web ACL, and never add a client to an Allow IP set.

### WAF layer

Ranked; each item cites R-xx, is marked *reduces* or *eliminates*, and is scoped to the abused path, method, rule or country. For card testing or credential stuffing, item 1 is a path-scoped rate-based rule on that method and URI (R-10, Count first). When known automation or shared egress exceeds the site-wide rate rule, include: "Switching the site-wide rate-based rule <rule> from Count to Block is not recommended: it would block <client> (<known automation or shared egress>), which exceeds the limit."

### Application layer

Paired measures (R-11), for example payment velocity limits per card, session or account; CAPTCHA or step-up on the payment form; payment-processor fraud controls; removing or protecting exposed admin and dot-file paths; input validation for the residue's field.

## Coverage and Gaps

- ACLs, window and backend covered; queries that failed or returned partial data
- Logging-filter or degraded-path limits; unverified label meanings
- Configuration changes: found, none found, or "not checked (<reason>)"
- What would raise confidence

## AI-generated

Findings are AI-generated and need human verification before anyone acts on them.
