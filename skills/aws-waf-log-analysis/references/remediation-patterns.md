# Remediation Patterns (advisory)

These patterns are the advice the agent gives in step A7 of `access-denied-triage.md` and in the advisory mitigations of Mode B. They are **advisory only**. The agent never applies them, never runs a command that changes a resource, and never presents a mutating CLI or API call. Describe the change in prose so that a human can review and apply it with their own change process.

**How to present a pattern**

- Pick the **narrowest** pattern that fixes the observed (rule, action) pair. Prefer scoping to one sub-rule, URI and method over a rule-group-wide change, and prefer any scoped change over an Allow.
- Mark each pattern as **reduces** (lowers the impact or frequency but leaves part of the pattern) or **eliminates** (stops the observed pattern for the affected scope), for the specific finding.
- Always include a **Count-first validation step**: deploy the new or changed rule in Count, watch its matches in logs (Q-08 (QA-08 / QI-08), QA-08b for rule-group sub-rules) and `CountedRequests` metrics for a representative period, then switch to the terminating action. A rule placed **after** a rule that blocks can never see the blocked requests (a terminating action ends evaluation), so a later label rule cannot be validated while the earlier sub-rule still blocks; use the label-rule sequence in R-01 for that case.
- Name what a human should confirm before acting (for example, that the excluded client really is the partner, or that the excluded URI cannot carry attack payloads).
- Never recommend loosening a rule for traffic judged `CORRECT_MITIGATION`. Never recommend turning a rule or rule group off as the fix (deleting it, removing it from the ACL, or a blanket Count override of a whole group), nor removing the Web ACL or disassociating it from a resource. Scoped sub-rule Count overrides paired with a label rule (R-01) and the R-08 options with their stated trade-off are allowed.
- Never recommend switching a whole managed rule group, or all of its sub-rules, from Count to Block, or removing its `RuleActionOverrides` wholesale, even when a Count-mode sub-rule shows real attacks (detected, not blocked). Enforcement is per sub-rule, scoped to the affected path and field, with a label-based exception (or a scope-down) for the legitimate pattern, validated in Count first (R-01, "Enforcing a Count-mode sub-rule"). Removing one sub-rule's override is the same as a site-wide Block of that sub-rule: recommend it only when Q-20 showed no legitimate matches for it anywhere.
- Use exact rule and label names as they appear in the logs or `GetWebACL`. Rule names and label names can differ in casing (rule `SizeRestrictions_BODY`, label `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body`); copy labels from Q-09 (QA-09 / QI-09), never build them from rule IDs.

| ID | Pattern | Typical verdict |
|---|---|---|
| R-01 | Override one managed sub-rule to Count, then block on its label with a scoped exception; enforce a Count-mode sub-rule the same way | `FALSE_POSITIVE` or `MIXED` on one sub-rule; a sub-rule in Count that detected attacks |
| R-02 | Size-rule exception for specific URIs | `FALSE_POSITIVE` on `SizeRestrictions_BODY` |
| R-03 | Scope-down statement on the managed rule group | `FALSE_POSITIVE` for one known client |
| R-04 | Correct a wrong entry in a custom block IP set; otherwise an IP-based exception for a verified partner, scoped to the denying rule only (never an Allow rule) | `FALSE_POSITIVE` or `CLIENT_CANNOT_SOLVE` for a verified partner (the exception is the last resort) |
| R-05 | Restrict Challenge/CAPTCHA to HTML GETs | `CLIENT_CANNOT_SOLVE` |
| R-06 | Client integration (WAF JavaScript or mobile SDK) and `TokenDomains` | `CLIENT_CANNOT_SOLVE` |
| R-07 | Block or rate-based rule instead of Challenge on machine-to-machine endpoints | `CLIENT_CANNOT_SOLVE` on API endpoints |
| R-08 | Shield L7AM action to Count, or migrate to the Anti-DDoS managed rule group | `FALSE_POSITIVE` or `MIXED` from L7AM |
| R-09 | Anti-DDoS rule group tuning | `CLIENT_CANNOT_SOLVE` or `MIXED` from Anti-DDoS |
| R-10 | Rate-based rule from Count to scoped Block | abuse detected but not stopped |
| R-11 | WAF-layer and application-layer mitigations for abuse | `CORRECT_MITIGATION` gaps, token abuse |

---

## R-01 - Override one managed sub-rule to Count, then block on its label with a scoped exception

**When it applies:** one sub-rule of a managed rule group blocks legitimate requests on a well-defined scope (a URI, method, host, client or field content), and the sub-rule is still valuable everywhere else; or a sub-rule in Count detected real attacks and has to be enforced without blocking the legitimate content it also matches.

**Change (prose):** in the managed rule group reference, add a rule action override that sets only that sub-rule to Count. The sub-rule still adds its label to matching requests. Then add a custom rule **after** the rule group (higher priority number) whose statement is: the request has that sub-rule's label AND NOT (the scoped exception, for example URI path starts with the affected path and method is POST). Its action is Block (with the same custom response, if one was used). Requests outside the exception are still blocked exactly as before.

**Effect:** eliminates the false positive inside the exception scope; protection elsewhere is unchanged. The exception scope itself loses that one sub-rule's protection, so keep it as narrow as possible.

**Count-first validation (label-rule sequence):** a Block ends evaluation, so a label rule placed after the sub-rule never sees the requests the sub-rule blocks. Validate in this order:

1. Override the sub-rule to Count. It stops blocking but still adds its label.
2. Add the label rule with the scoped exception, with action Count. Deploy steps 1 and 2 in the same change.
3. Over a representative window, compare the label rule's matches with all requests that carry the sub-rule's label (Q-08 (QA-08 / QI-08) and QA-08b for the sub-rule's Count matches, Q-09 (QA-09 / QI-09) for the label). The label rule should match every labelled request outside the exception and none inside it.
4. Switch the label rule to Block.

**Reduced-protection window:** between steps 1 and 4 the sub-rule's traffic is counted but not blocked anywhere. Keep that window short: deploy steps 1 and 2 together, use the shortest review window that still covers the application's normal traffic cycle, and schedule step 4 in advance. The Count-first sequence above is the recommendation.

**Mixed matches inside one blocking sub-rule** (Q-20 split it into legitimate content and attack payloads, verdict `MIXED`): the exception in the label rule is the legitimate part's scope, not the whole path when the path also carries attacks. Write it as: label AND NOT (affected path AND method), plus a second Block rule for label AND affected path AND a match statement for the attack pattern classes Q-20 showed (for example an XSS match or a regex for event-handler attributes on the body field; a JNDI-lookup-with-remote-host regex), described as classes, not literal payloads. Both start in Count.

**Enforcing a Count-mode sub-rule (detected, not blocked).** When a sub-rule overridden to Count matched real attacks and Q-20 also found legitimate content in its matches (or in a sibling sub-rule's matches):

1. Keep the group's `RuleActionOverrides` as they are. Never switch the whole group or all its sub-rules to Block.
2. Per sub-rule with attack matches, add a label rule after the group: that sub-rule's label (copied from Q-09) AND the affected path (and method) AND NOT (the legitimate pattern's scope: for example the catalog search terms or the field that carries business text), action Count.
3. A sub-rule whose matches were all legitimate content (for example a body sub-rule that matched only product descriptions on one path) stays in Count, or is enforced only outside that path with the same label-rule form.
4. Over a representative window, confirm the label rule matches every attack request Q-20 found and none of the legitimate ones (Q-08 and QA-08b, Q-20 rerun on the label rule), then switch it to Block.

Effect: *reduces* to *eliminates* the detected-not-blocked attack part on that path, with no new false positives on the legitimate content. Name in "Verify before acting" that a human should confirm the legitimate pattern's scope with the application owner.

**Alternative (explicitly labelled, not the default): straight to Block.** When the exception is well understood (one exact path and method, confirmed from Q-03 and Q-04), a human may choose to put the label rule straight into Block in the same change as step 1. This avoids the reduced-protection window, but the risk is that an error in the label rule's statement or exception scope blocks legitimate traffic, or lets attack traffic through, without a Count review first. If chosen, watch the label rule's `BlockedRequests` and the excluded path closely right after the change and be ready to roll back.

---

## R-02 - Size-rule exception for `SizeRestrictions_BODY` on specific URIs

**When it applies:** `SizeRestrictions_BODY` in the Core rule set (`AWSManagedRulesCommonRuleSet`) blocks legitimate large bodies (forms, uploads, large JSON) on specific URIs, while the same clients' other requests are allowed.

**Change (prose):** apply R-01 to `SizeRestrictions_BODY`: override it to Count, then add a custom rule after the group that blocks on its label (copy the exact label from the logs, for example `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body`) AND NOT (URI path is the affected path AND method is the affected method). Optionally add your own size constraint for the excluded URI (a body-size statement with a limit that fits the application's real maximum) so that the exception does not accept bodies of any size.

Also check `AssociationConfig.RequestBody` in the Web ACL (D-2). It sets how much of the body WAF inspects for each resource type; the CloudFront default inspection size is 16 KB, and limits differ by resource type. Compare with `requestBodySizeInspectedByWAF` and `oversizeFields` from Q-07 (QA-07 / QI-07): content beyond the inspection limit is not inspected by any rule, so raising the inspection limit (which can affect cost) or handling oversize content explicitly may matter for the excluded URI. Raising `AssociationConfig.RequestBody` does **not** change the `SizeRestrictions_BODY` threshold (8 KB) and never fixes this false positive by itself; it only affects content-inspection rules on the excluded URI.

**Effect:** eliminates the false positive on the excluded URI and method; with your own size constraint, it reduces rather than removes size protection there.

**Count-first validation:** follow R-01's label-rule sequence: override `SizeRestrictions_BODY` to Count and add the label rule (and any new size constraint) in Count in the same change; confirm the label rule matches all labelled oversize requests outside the excluded URI and method and none of the legitimate large submissions on it; then switch the label rule (and size constraint) to Block. Size protection is reduced site-wide between the override and the switch, so keep that window short. Count-first is the recommendation; going straight to Block is only the explicitly labelled alternative in R-01 (reduced-protection window), with the risk stated there.

---

## R-03 - Scope-down statement on the managed rule group to exclude a known client

**When it applies:** a known, verified client (a partner, a monitoring service, a scheduled job) trips one or more rules in a managed group, and the client can be identified reliably.

**Change (prose):** add a scope-down statement to the managed rule group reference so that the group evaluates only requests that are NOT from that client. Identify the client with an IP set of its documented egress addresses, or with a header the client controls (for example a shared secret header added by the partner, or a header added by an upstream proxy you own). Prefer the IP set when the addresses are stable; a header can be copied by anyone who learns it, so treat it as a weaker identifier and keep its value secret.

**Effect:** eliminates the denial for that client. The excluded client gets none of the group's protection, so this is broader than R-01.

**Count-first validation:** before changing the scope-down, add a Count rule that matches the same client condition and confirm in logs that it matches only the intended client's requests (Q-03 (QA-03 / QI-03) for that rule's population).

---

## R-04 - IP-based exception for a verified partner, scoped to the denying rule only (use with caution)

**When it applies:** a partner with fixed, verified egress addresses keeps being denied by one rule, and narrower patterns (R-01, R-03, and for Challenge or CAPTCHA R-05, R-06 and a path scope-down) are not practical. For `CLIENT_CANNOT_SOLVE`, R-04 ranks below R-05, R-06 and the path scope-down of the challenge rule: list it last, if at all, and say why (egress addresses change, and the address loses that rule's protection).

**Change (prose):** use the partner's verified addresses only as an exclusion on the rule that denies it: a scope-down statement on that Challenge, CAPTCHA or blocking rule (or on the managed group reference, R-03) of the form "NOT (source IP in <partner IP set>)", preferably combined with the partner's paths or host (for example "NOT (IP in set AND URI path starts with `/api/`)"), or a label-scoped rule that excludes the set (R-01). Every other rule keeps evaluating the partner's requests.

**Entry in a custom block IP set (the narrowest fix, before any exception).** When the denying rule is a custom Block rule on a customer-managed IP set and `wafv2:GetIPSet` shows the client's IP inside one entry (access-denied-triage, "Per-client symptoms and IP-set evidence"), the fix is to correct that entry: remove it, or narrow the CIDR so it no longer covers the verified partner, after the owner confirms that the address belongs to the partner and how the entry got there. *Eliminates* the denial for that client; every rule still evaluates it. Validate by checking in logs (Q-21 for the client) that the client's requests are allowed afterwards and that no other client covered by the old entry needs it. Report a similarly named allow or trusted set only as a finding (exists, referenced or not); do not recommend adding the client to it or referencing it from an Allow rule.

**Never** add the client's address to an IP set that an Allow-action rule references (an existing "allow" or trusted-address set included), and never create such an Allow rule: Allow is terminating and ends evaluation, so every rule after it, including managed rule groups, rate-based rules, Bot Control, Anti-DDoS and Shield L7AM mitigation, is skipped for that address, and a compromised or shared address gets unrestricted access. When D-2 shows an existing Allow rule on an IP set, name it only to say the client must not be added to it.

**Effect:** eliminates the denial by that one rule for the partner's addresses (and paths); all other protection stays.

**Count-first validation:** first add the same match (IP set AND paths) as a Count rule and confirm it matches only the partner's traffic (correct addresses, expected paths). List under "Verify before acting" that a human should confirm with the partner that the address list is complete and owned by them, and review the set regularly.

---

## R-05 - Restrict Challenge/CAPTCHA to HTML GETs

**When it applies:** a Challenge or CAPTCHA rule hits clients that cannot solve it: API calls, JSON requests, browser fetch/XHR, health checks, partner integrations. This is the first-ranked fix for `CLIENT_CANNOT_SOLVE` (with R-06 for clients you control), above any R-04 IP-based exception; never suggest adding the client to an IP set used by an Allow rule (R-04).

**Change (prose):** narrow the Challenge or CAPTCHA rule (or add a scope-down statement to the rule group that applies it) so that it only applies when all of these hold: the URI path does not start with any API prefix the affected client uses (for example `/api/`, the first and simplest scope-down to name), the `Accept` header contains `text/html`, and the method is GET. Build the exclusion from the affected client's full URI set (Q-03 (QA-03 / QI-03)): every non-HTML path it hits must be covered, including `/` or page paths it calls with a non-HTML `Accept`, not just an API prefix; the `Accept` and method conditions cover those when the path list cannot. For a managed sub-rule with a Challenge action (for example Bot Control `TGT_*`), use R-01's shape: override the sub-rule to Count and apply Challenge in a custom rule after the group on its label with these conditions.

**Effect:** eliminates the lockout for non-HTML and API requests. Those requests are then no longer challenged, so pair this with R-07 for API endpoints if they need protection.

**Count-first validation:** for a custom Challenge or CAPTCHA rule, add the narrowed condition as a separate Count rule next to it and confirm it matches the browser page loads and none of the API or non-GET requests seen in Q-05 (QA-05 / QI-05), then replace the rule's condition. For a managed sub-rule, follow R-01's label-rule sequence (a challenge also ends evaluation, so a later label rule cannot see challenged requests until the sub-rule is in Count): override the sub-rule to Count and add the label rule in Count together, review, then switch the label rule to Challenge. The sub-rule challenges nobody in between, so keep that window short as described in R-01.

---

## R-06 - Client integration for token acquisition, and `TokenDomains`

**When it applies:** the challenged clients are your own browser single-page application or mobile app, and they must keep passing Challenge or CAPTCHA (for example Bot Control targeted rules or Anti-DDoS soft mitigation).

**Change (prose):** integrate the AWS WAF client application integration: the JavaScript integration for browser apps (it acquires the token and attaches it to fetch calls), or the AWS WAF mobile SDK for Android and iOS apps. For apps that span several subdomains or domains, set the Web ACL's `TokenDomains` to include every domain that should accept the token, so tokens acquired on one host are not `rejected:domain_mismatch` on another.

**Effect:** eliminates `TOKEN_MISSING` and domain-mismatch failures for clients that integrate. It does not help third-party scripts or partners you cannot change (use R-05 or R-07 for them).

**Count-first validation:** with the integration released, check in logs that the clients carry `awswaf:managed:token:accepted` (Q-09 (QA-09 / QI-09), Q-05 (QA-05 / QI-05)) while the rule is still in Count or scoped to a test path, before enforcing it widely.

---

## R-07 - Block or rate-based rule instead of Challenge on machine-to-machine endpoints

**When it applies:** an endpoint is called by scripts, servers or partners that will never run a challenge, and the endpoint still needs protection.

**Change (prose):** exclude the endpoint from Challenge and CAPTCHA (R-05), and protect it instead with rules that do not need client cooperation: a rate-based rule with action Block scoped to the endpoint, Block rules on labels from managed groups, or authentication at the API layer.

**Effect:** eliminates the challenge lockout; reduces abuse risk on the endpoint to what the replacement rules catch.

**Count-first validation:** run the rate-based rule in Count for a representative period and confirm the limit sits above legitimate peak rates per aggregation key (Q-11 (QA-11 / QI-11) for per-IP rates, Q-13 (QA-13 / QI-13) for top talkers).

---

## R-08 - Shield Advanced L7AM: action to Count, or migrate to the Anti-DDoS managed rule group

**When it applies:** Shield Advanced automatic application layer DDoS mitigation blocks legitimate clients, for example blocks that continue after `DDoSDetected` returns to 0 on traffic that matches the pre-event baseline.

**Change (prose):** these are the documented options. (a) In the Shield Advanced protection for the affected resource, change the automatic application layer mitigation action from Block to Count. Mitigation rules keep matching and can be watched in logs (Q-14b: QA-14b / QI-14b) but no longer block. (b) Migrate from L7AM to the AWS WAF Anti-DDoS managed rule group (`AWSManagedRulesAntiDDoSRuleSet`). The AWS WAF Developer Guide states that from March 26, 2026 the Anti-DDoS managed rule group became the default solution for HTTP request flood protection and supersedes L7AM; existing Shield Advanced customers can keep using L7AM (https://docs.aws.amazon.com/waf/latest/developerguide/ddos-automatic-app-layer-response.html). The rule group offers soft (Challenge) and hard (Block) mitigation with tunable sensitivity (R-09). Do not edit the `ShieldMitigationRuleGroup_*` rule group itself; Shield manages it.

**Effect:** (a) eliminates the false-positive blocks but also removes automatic blocking during future events, so state that trade-off. (b) reduces false positives through tunable sensitivity and exemptions while keeping automatic mitigation.

**Count-first validation:** with (a), the Count mode itself is the validation: watch QA-14b / QI-14b during the next event to see what would have been blocked. With (b), add the Anti-DDoS rule group with its rules overridden to Count first and review its labels and matches before enforcing.

---

## R-09 - Anti-DDoS rule group tuning

**When it applies:** the Anti-DDoS managed rule group challenges or blocks legitimate clients during events: intermittent lockouts on API paths, or broad challenges of all traffic.

**Change (prose):**

- **Exempt non-challengeable paths.** Add exempt URI regular expressions (`ExemptUriRegularExpressions` in the rule group's `ClientSideActionConfig`) for paths that cannot take a challenge (APIs, health checks, partner callbacks). Documented behavior (https://docs.aws.amazon.com/waf/latest/APIReference/API_ClientSideAction.html and https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-anti-ddos.html):
  - The regex is matched against the request's host immediately followed by its normalized URI path, without scheme, query string or fragment (for example `www.example.com/api/orders`). A pattern anchored to the start of the path, such as `^/api/`, never matches.
  - The path is normalized first (empty segments, including a trailing slash, and `.` segments removed, `..` resolved), so `/api/` is evaluated as `/api`.
  - Only `GET` requests are challengeable; the `challengeable-request` label is never added to other methods.
  - Requests that match an exempt regex are not evaluated by `ChallengeAllDuringEvent` or `ChallengeDDoSRequests`, whatever their action overrides. The documentation describes the exemption only for these two challenge rules, so do not assume it exempts requests from `DDoSRequests` (Block).
  - The documented starting point is `\/api(\/|$)|\.(acc|avi|css|gif|jpe?g|js|mp[34]|ogg|otf|pdf|png|tiff?|ttf|webm|webp|woff2?)$`, to be reviewed for the application. Between 1 and 5 regexes are allowed.
  - The `Accept` header is not part of the exempt match. Whether a challenged client can actually show the interstitial still depends on the general Challenge behavior (it is served only when `Accept` includes `text/html`).
- **Use sensitivity-based challenges instead of challenging everything.** `ChallengeAllDuringEvent` challenges every challengeable request while the resource is under attack. Override it to Count so that `ChallengeDDoSRequests` is evaluated (it is evaluated only when the previous rule is overridden to Count), and tune the challenge `Sensitivity` in `ClientSideActionConfig` (LOW matches only high-suspicion requests, MEDIUM matches medium and high, HIGH, the default, matches all suspicion levels) so that only suspected attack sources are challenged. Tune `SensitivityToBlock`, used by `DDoSRequests`, the same way if blocks hit baseline clients.

**Effect:** exemptions eliminate challenge lockouts on the exempted paths (they lose soft mitigation); sensitivity tuning reduces collateral challenges during events.

**Count-first validation:** review the rule group's labels (`event-detected`, `ddos-request` with low, medium or high suspicion, `challengeable-request`) in logs (Q-09 (QA-09 / QI-09), Q-10 (QA-10 / QI-10)) to see which clients each sensitivity level would hit before changing it. Confirm that the exempt pattern removes `challengeable-request` from the intended paths only.

---

## R-10 - Rate-based rule in Count that matches abuse: switch to a scoped Block

**When it applies:** a rate-based rule in Count matches abusive traffic (detected but not stopped), for example card testing on a payment endpoint or credential stuffing on login, seen in Q-08 (QA-08 / QI-08) and `ratebasedrulelist`. A client whose Q-08c burst is concentrated on a payment, checkout, login, signup or password-reset URI qualifies whatever its size; the fix for it is this pattern scoped to that URI (a new path-scoped rate-based rule, validated in Count first, if the existing rule is site-wide). Excluding a known-automation IP from the site-wide rule may be needed before any Block, but it is not the fix for the abuse.

**Change (prose):** switch the rate-based rule to Block, scoped with a scope-down statement to the abused path (for example the payment or login endpoint) rather than the whole site. Choose aggregation keys that separate abusers from legitimate users behind shared egress: client IP when sources are distinct, the forwarded IP header when a trusted proxy or CDN sits in front, or custom keys (for example a session cookie, an API key header, or IP combined with a header) when many users share one NAT or corporate address. Set the limit from observed legitimate peak rates, not from the abuser's rate.

**Effect:** reduces the abuse to the rate limit on that path; it does not eliminate low-and-slow abuse below the limit (check Q-11 (QA-11 / QI-11)).

**Never** recommend switching a site-wide rate-based rule to Block when a known-automation client or a shared egress IP (NAT, corporate proxy) exceeds the limit: that blocks legitimate traffic. Scope it to the abused path, or exclude the verified automation with a scope-down, first. Say so explicitly in the output, naming the client: "Switching the site-wide rate-based rule <rule> from Count to Block is not recommended: it would block <client> (<known automation or shared egress>), which exceeds the limit." List the path-scoped rule for a card-testing or credential-stuffing burst first among the mitigations.

**Count-first validation:** the rule is already in Count; before switching, confirm which keys exceeded the limit and that none of them are known legitimate automation (Q-13 (QA-13 / QI-13) with corroboration) or shared egress used by many real users (Q-08c (QA-08c / QI-08c) lists the keys per client).

---

## R-11 - WAF-layer and application-layer mitigations for abuse

**When it applies:** traffic is judged `CORRECT_MITIGATION` but part of it gets through (detected-not-blocked, Count rules, valid tokens, attacker residue, card testing or credential stuffing), or abuse rides on genuine tokens or on SDK and mobile clients that WAF cannot challenge. Present recommendations under a "Recommended mitigations" heading with two sub-headings, "WAF layer" and "Application layer", and mark each as reduces or eliminates for the observed pattern.

**WAF layer**

- Close enforcement gaps: reference firing labels in a Block rule, or change offending rule actions from Count or CAPTCHA to Block, scoped narrowly (geography + endpoint + label) to limit collateral impact. For a managed sub-rule in Count, enforce per sub-rule with the R-01 "Enforcing a Count-mode sub-rule" sequence, with an exception for the legitimate content Q-20 found; never the whole group or all its sub-rules.
- Endpoint and geography-scoped rule: geography AND URI AND an OR of the relevant labels.
- Rate-based rules with appropriate aggregation keys (IP, forwarded IP, or custom keys) for volumetric patterns (see R-10).
- **Attacker residue** (Q-19 (QA-19 / QI-19)): the allowed requests carry no labels, so a rule that matches labels cannot catch them. Match the request component the residue used: for a query-argument residue, a string or regex match statement on query arguments scoped to the affected path, or the managed sub-rule that inspects the query string (for example `LFI_QUERYSTRING` in `AWSManagedRulesLinuxRuleSet`); for a URI-path residue, the matching `_URIPATH` sub-rule or a scoped URI-path match. A `UriPath` rule never covers a query-argument residue. Cover every LFI class the residue showed: relative-traversal patterns (dot-dot-slash and its encodings) do not match absolute-path LFI, so a custom match also needs the absolute-path classes (absolute references to OS process-information and system-configuration directories, and their encoded forms), described as classes in the advisory text, not as literal probe strings. Check in D-2 whether that group is already in the ACL, and validate in Count first. Marked *reduces* unless the Count run shows it matches every residue request.
- Redistributed tokens (Q-16b (QA-16b / QI-16b), or Q-16 (QA-16 / QI-16) without token labels): rate-based rules cannot count distinct IPs per token, so a custom rate rule cannot do this. Use the Bot Control targeted rules that do: `TGT_TokenReuseIp*`, `TGT_TokenReuseCountry*` and `TGT_TokenReuseAsn*` (Low/Medium/High thresholds in `label-reference.md`). Keep the group's own actions as they are and add label rules after it that Block (or CAPTCHA, for browser clients only) on those labels, or on `TGT_ML_CoordinatedActivity*` labels, AND the affected country AND the affected paths. `TGT_TokenReuseIpLow` (more than 2 IPs) also catches legitimate mobile users changing networks: use the Medium or High labels for Block and keep Low in Count for visibility. Start the label rules in Count, compare their matches with the legitimate baseline, then enforce.
- No ASN in the logs: add any ASN match statement in a Count rule (the ASNs from an external lookup of the Q-17 prefixes, or a broad list). `clientAsn` is logged only when an ASN match statement is used, so this adds ASN attribution to the logs without blocking anything.
- Caveat: CAPTCHA is ineffective for non-browser mobile and SDK clients, and blocking on redistributed but valid tokens risks real users behind shared egress addresses. Validate against the baseline first.

**Application layer** (needed when abuse rides on valid tokens or SDK clients)

- Progressive or tiered authentication for high-value or search-intensive access.
- Client integrity and app attestation, plus request signing with timestamp validation.
- Token-to-device binding: bind a token to a device fingerprint at issue time and reject mismatches. This is the durable fix for redistributed genuine tokens; the WAF token-reuse rules only reduce it.
- Shorter token lifetimes and forced rotation on suspicious usage; roll out regionally first.
- Card testing on a payment endpoint: velocity limits per card, session, account and device in the payment flow, step-up or CAPTCHA on the payment form for browser users, and the payment processor's fraud controls (*eliminates* when enforced per card and account; the WAF rate rule only *reduces*).
- Credential stuffing or fake sign-ups: per-account lockout and throttling, breached-password checks, and multi-factor authentication or email verification.

**Decision rule:** if the signature is redistribution of genuine tokens AND the legitimate client is a non-browser mobile or SDK app, WAF-layer controls reduce but do not eliminate the pattern. Recommend application-layer controls as the durable fix, with WAF changes as immediate harm reduction.

**Count-first validation:** every new WAF-layer Block rule starts in Count; confirm its matches against the known-legitimate baseline (Q-04 (QA-04 / QI-04), Q-13 (QA-13 / QI-13)) before enforcing. Application-layer changes follow the application's own staged rollout.
