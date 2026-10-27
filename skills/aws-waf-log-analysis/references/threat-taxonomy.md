# Threat Taxonomy and Signatures

Map a confirmed signature to one of four buckets. Each lists the fields to emphasize and the
telltale signals. Resolve label meanings through `label-reference.md` (L-1 live lookup first, then
the bundled semantics) before concluding. Label names below are common examples, not a substitute
for that lookup. Known automation (B0) is reported separately and does not belong in any bucket
unless corroborating signals show it is also abusive.

Mitigations are not listed here. Use `remediation-patterns.md`: R-11 for the WAF-layer and
application-layer catalog and its decision rule, and R-10 for a Count-mode rate-based rule that
matches abuse.

## 1. Volumetric

High request volume in a short window, aiming to exhaust capacity or brute a resource.

- **Fields:** `timestamp` (spike vs median), `clientIp`, `clientAsn` (no ISP field; `clientAsn`
  needs an ASN match statement; see QA-17), `country`, `uri`, `rateBasedRuleList`.
- **Signals:** sharp bucket spikes (Q-01); a few IPs, IP prefixes or ASNs dominating (Q-03,
  Q-11, Q-17); `rateBasedRuleList` showing evaluation near or over `maxRateAllowed`;
  single-URI concentration. A rate-based rule in Count mode that keeps matching is a
  detected-not-blocked finding (bucket 4, Q-08, R-10).
- **Evasion variant:** low-and-slow. Many IPs each in the 3-5 request band collectively drive the
  volume (Q-11). This defeats naive rate limits, so pair volume analysis with IP banding.
- **Rule out first:** a single client with steady volume, a small fixed URI set and a stable
  non-browser fingerprint is more likely known automation (B0, Q-13) than an attack.

## 2. Bot / automation

Coordinated non-human traffic: scraping, credential or token abuse, inventory harvesting.

- **Fields:** `labels` (Bot Control signals, token id and token fingerprint), `ja3Fingerprint` /
  `ja4Fingerprint`, token (cookie or `x-aws-waf-token`), `httpMethod`, `referer`, `uri`.
- **Signals:** coordinated-activity and token-reuse labels; non-browser user agents or
  HTTP-library labels; one token id across many IPs with one token fingerprint and one user
  agent (redistribution of a genuine token, Q-16b; Q-16 without token labels); missing,
  expired or rejected token status (Q-18); endpoint focus on search, catalog or pricing.
- **Confirm with:** label co-occurrence (Q-10). A coordinated plus token-reuse plus non-browser
  cluster is a strong composite signature. Absence of a co-label proves nothing, because rule
  order and logging can hide labels.
- **Caution:** the user agent alone is spoofable and is also what benign tools send. Do not call
  a client a bot, or known automation, on the UA by itself.

## 3. Malicious injection / exploit

Requests probing for application vulnerabilities.

- **Fields:** `labels` (SQLi, XSS, LFI/RFI, Known Bad Inputs, anonymous-IP), `uri`, `args`,
  `httpMethod`, `terminatingRuleMatchDetails`, `nonTerminatingMatchingRules.ruleMatchDetails`.
- **Signals:** Core rule set and Known Bad Inputs labels (Q-09); SQLi or XSS match details (Q-06);
  suspicious payloads in `args`; scanning across many URIs from one origin (Q-12, compared with
  the window's per-IP median).
- **Rule order hides signals.** A bot or user-agent rule that terminates a request first stops
  later rules (including injection rules) from evaluating, so the injection labels never appear.
  When hunting injection, also look at what a bot-UA rule blocked (Q-02 on that rule, then Q-12
  for the same clients). In one observed case, a scanner UA was blocked by a bot-UA rule before
  any injection rule ran.

## 4. Missed-by-rule (detected-not-blocked)

The highest-value discovery: WAF labeled or matched the request but let it through.

- **Fields:** `action = ALLOW`, `terminatingRuleId = Default_Action`, `labels` present,
  `nonTerminatingMatchingRules`, `ruleGroupList[].nonTerminatingMatchingRules` (Count-mode
  matches), `rateBasedRuleList`.
- **Signals:** meaningful volume of ALLOW requests carrying threat labels (Q-09); a managed-rule
  label firing while its rule action is Count (Q-08, plus QA-08b on Athena, cross-checked with the Count
  overrides read in D-2); a rate-based rule in Count whose matches are high (Q-08, Q-01); high
  detection rate with near-zero block rate for a slice; a short burst from one client on a
  payment, checkout or login URI (Q-13b peak per minute, often ALLOW with a browser UA and no
  labels: card testing or credential stuffing, matched at most by a rate rule in Count); allowed
  requests from a client that other requests show is hostile (attacker residue, Q-19).
- **Method:** compute detection rate vs block rate per slice; cross-reference firing labels
  against the ACL's rule actions (D-2) to prove the enforcement gap.
- **Limit:** if the logging filter drops ALLOW records (D-3), this bucket is under-counted. State
  that detected-not-blocked analysis is limited, and never read a low count as "none".
- **This is usually a configuration finding**, not attacker capability, and often the fastest
  remediation (R-01, R-10).
