# Label Reference

Labels are the main signal for what an AWS WAF rule group saw. Names alone are hints. Resolve a label from the live API first (L-1), then from the bundled tables, and report anything in neither as "meaning unverified". This file is advisory reading material.

Last verified: 2026-10-11 (live `DescribeManagedRuleGroup`, CLOUDFRONT scope, default version of each group, plus the AWS documentation pages cited per group). Rows tagged "docs only" were on a docs page but not in that API output.

## L-1 Live label lookup (preferred when permitted)

1. Get the managed rule group name and `Version` from the ACL (D-2 in `references/discovery-and-log-sources.md`). A null version means the current default. `wafv2:ListAvailableManagedRuleGroupVersions` (covered by `wafv2:List*`, in the default policy) lists the versions and the current default.
2. Call `wafv2:DescribeManagedRuleGroup` with vendor, group name, scope and that version. Read `Rules[].Name` and `AvailableLabels[].Name`. Match labels exactly as returned; casing differs from rule names (rule `SizeRestrictions_BODY` emits `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body`). Some groups (Bot Control) may need a version or configuration; if the call errors, use the bundled table and say so.
3. `wafv2:DescribeManagedRuleGroup` is not in the default agent policy; it is part of the skill's opt-in IAM add-on. If it is denied:
   - Record in Assumptions that live lookup was denied and the bundled tables (dated above) were used.
   - Get the exact label strings in this traffic from the logs: label frequency Q-09 (QA-09 in `references/athena-queries.md`; QI-09 (per-position counts and its label-set query) in `references/logs-insights-queries.md`).
   - Take meaning from the bundled tables. A label in neither the API output nor these tables follows the unverified-label rule.
4. Groups change by version. A label in the logs that is missing from a table may belong to a newer version; verify through L-1 when permitted, otherwise report it as unverified.

## Namespace guide

| Namespace | Source | Notes |
|---|---|---|
| `awswaf:managed:aws:<group>:<signal>` | AWS managed rule group (for example `core-rule-set`, `known-bad-inputs`, `sql-database`, `amazon-ip-list`, `anonymous-ip-list`, `anti-ddos`, `bot-control`) | `<group>` is a short label name, not the rule group name. Labels are visible only to rules that run after the group. |
| `awswaf:managed:token:*`, `awswaf:managed:captcha:*` | Token management, added by Bot Control, Anti-DDoS, ATP, ACFP | Token status. `token:id:<id>` and `token:fingerprint:<id>` carry session and browser identifiers. |
| `awswaf:managed:aws:anti-ddos:*` | Anti-DDoS | Group labels (`event-detected`, `challengeable-request`, `*-suspicion-ddos-request`) plus rule labels. |
| `awswaf:managed:aws:bot-control:bot:*`, `:signal:*`, `:targeted:*` | Bot Control | `bot:` identifies the bot; `signal:` and `targeted:signal:` are request indicators; `targeted:aggregate:*` are volumetric and ML aggregates. |
| `awswaf:<account-id>:webacl:<web-acl-name>:<label>` | Custom rule in a web ACL | Added only by rules whose author configured `RuleLabels`; the author chooses the name. |
| `awswaf:<account-id>:rulegroup:<rule-group-name>:<label>` | Custom rule group | Same, scoped to the rule group. |
| Rate-based rule labels | Rate-based rules | A rate-based rule is a custom rule: its labels are the ones configured in its `RuleLabels`, under the namespaces above. The docs do not describe an automatic label; confirm by reading the rule (D-2). |

Docs: https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-labeling.html, https://docs.aws.amazon.com/waf/latest/developerguide/waf-labels.html, https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-label-requirements.html.

## Unverified-label rule

A label found in the logs that is in neither the live API output (L-1) nor the tables below is reported as "meaning unverified". Do not infer meaning from the name or build a remediation on it; list it for follow-up. Custom labels (account namespace) are verified by reading the rule that adds them (D-2).

## Reading the tables

Each row gives rule, label, what it detects (one line) and a common false-positive pattern. Rows that share one family (the same detection on several request components) are grouped: the rules and labels are listed in the same order, and the location suffix names the component (`_BODY` request body, `_COOKIE` cookie, `_HEADER` request headers, `_QUERYARGUMENTS` query argument values, `_QUERYSTRING` query string, `_URIPATH` URI path). Every false-positive entry carries a source tag:
- `(observed)`: seen in validation traffic.
- `(AWS docs)`: stated on the cited AWS documentation page.
- `(general)`: the skill author's reasoning about what the rule inspects. It is not from AWS documentation; present it to the user as a possibility to check, never as a fact.

A dash means no pattern is documented or claimed. Rule action is Block unless stated, but the ACL may override it to Count; the label is added either way.

## Token labels

Docs: https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-labeling.html. Added by Bot Control, Anti-DDoS, ATP and ACFP. The `token:` prefix reports the challenge status, the `captcha:` prefix the CAPTCHA status.

| Labels | Meaning | Common false-positive pattern |
|---|---|---|
| `awswaf:managed:token:id:<identifier>` | Client session id from token management. Can change when the client acquires a new token. No CloudWatch metric. Key for token reuse (Q-16b); report truncated. | Not a threat signal by itself |
| `awswaf:managed:token:fingerprint:<fingerprint>` | Robust browser or device fingerprint; stays the same across token acquisitions; not unique to one client. No CloudWatch metric. | Many real users of one app version can share a fingerprint (general) |
| `awswaf:managed:token:absent`<br>`awswaf:managed:captcha:absent` | No token, or it could not be read | On all challenged requests from a scripted client (observed); not an attack signal alone |
| `awswaf:managed:token:accepted`<br>`awswaf:managed:captcha:accepted` | Valid, unexpired solution and valid domain | — |
| `awswaf:managed:token:rejected`<br>`awswaf:managed:captcha:rejected` | Token present but unacceptable; a `rejected:*` reason label accompanies it | See reasons |
| `awswaf:managed:token:rejected:not_solved`<br>`awswaf:managed:captcha:rejected:not_solved` | Token lacks the challenge or CAPTCHA solution | — |
| `awswaf:managed:token:rejected:expired`<br>`awswaf:managed:captcha:rejected:expired` | Timestamp older than the ACL's token immunity time | Long-lived sessions (general) |
| `awswaf:managed:token:rejected:domain_mismatch`<br>`awswaf:managed:captcha:rejected:domain_mismatch` | Token domain does not match the ACL token domain configuration | Multi-domain sites with an incomplete token domain list (general) |
| `awswaf:managed:token:rejected:invalid`<br>`awswaf:managed:captcha:rejected:invalid` | Token could not be read | — |

## Rule group tables

### Core rule set

`AWSManagedRulesCommonRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `UserAgent_BadBots_HEADER` | `awswaf:managed:aws:core-rule-set:BadBots_Header` | `User-Agent` values of common scanners (for example `nessus`, `nmap`). See Notes C1. | Authorised scanners or monitors with scanner-like User-Agents (general) |
| `CrossSiteScripting_BODY`<br>`CrossSiteScripting_COOKIE`<br>`CrossSiteScripting_QUERYARGUMENTS`<br>`CrossSiteScripting_URIPATH` | `awswaf:managed:aws:core-rule-set:CrossSiteScripting_Body`<br>`awswaf:managed:aws:core-rule-set:CrossSiteScripting_Cookie`<br>`awswaf:managed:aws:core-rule-set:CrossSiteScripting_QueryArguments`<br>`awswaf:managed:aws:core-rule-set:CrossSiteScripting_URIPath` | Cross-site scripting patterns in the component named by the suffix. | Rich-text editors and CMS content posts (general) |
| `EC2MetaDataSSRF_BODY`<br>`EC2MetaDataSSRF_COOKIE`<br>`EC2MetaDataSSRF_QUERYARGUMENTS`<br>`EC2MetaDataSSRF_URIPATH` | `awswaf:managed:aws:core-rule-set:EC2MetaDataSSRF_Body`<br>`awswaf:managed:aws:core-rule-set:EC2MetaDataSSRF_Cookie`<br>`awswaf:managed:aws:core-rule-set:EC2MetaDataSSRF_QueryArguments`<br>`awswaf:managed:aws:core-rule-set:EC2MetaDataSSRF_URIPath` | Attempt to reach EC2 instance metadata (SSRF) in the component named by the suffix. | Applications that legitimately handle URLs in input (general) |
| `GenericLFI_BODY`<br>`GenericLFI_QUERYARGUMENTS`<br>`GenericLFI_URIPATH` | `awswaf:managed:aws:core-rule-set:GenericLFI_Body`<br>`awswaf:managed:aws:core-rule-set:GenericLFI_QueryArguments`<br>`awswaf:managed:aws:core-rule-set:GenericLFI_URIPath` | Local file inclusion or path traversal (such as `../../`) in the component named by the suffix. | Parameters carrying relative file paths (general) |
| `GenericRFI_BODY`<br>`GenericRFI_QUERYARGUMENTS`<br>`GenericRFI_URIPATH` | `awswaf:managed:aws:core-rule-set:GenericRFI_Body`<br>`awswaf:managed:aws:core-rule-set:GenericRFI_QueryArguments`<br>`awswaf:managed:aws:core-rule-set:GenericRFI_URIPath` | Remote file inclusion: URL with an IPv4 host embedded in the component named by the suffix. | Parameters that legitimately carry URLs with IP hosts, such as callbacks (general) |
| `NoUserAgent_HEADER` | `awswaf:managed:aws:core-rule-set:NoUserAgent_Header` | Request has no `User-Agent` header. | Health checkers and scripts that send no User-Agent (observed) |
| `RestrictedExtensions_QUERYARGUMENTS`<br>`RestrictedExtensions_URIPATH` | `awswaf:managed:aws:core-rule-set:RestrictedExtensions_QueryArguments`<br>`awswaf:managed:aws:core-rule-set:RestrictedExtensions_URIPath` | System file extensions unsafe to serve (such as `.log`, `.ini`) in the component named by the suffix. | Applications that legitimately reference such files (general) |
| `SizeRestrictions_BODY` | `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body` | Request body over 8 KB. | Legitimate large form posts (observed) |
| `SizeRestrictions_Cookie_HEADER` | `awswaf:managed:aws:core-rule-set:SizeRestrictions_Cookie_Header` | Cookie header over 10,240 bytes. | Applications that accumulate large cookies (general) |
| `SizeRestrictions_QUERYSTRING` | `awswaf:managed:aws:core-rule-set:SizeRestrictions_QueryString` | Query string over 2,048 bytes. | Long tracking or filter query strings (general) |
| `SizeRestrictions_URIPATH` | `awswaf:managed:aws:core-rule-set:SizeRestrictions_URIPath` | URI path over 1,024 bytes. | — |

Notes C1: Label casing differs from rule names (rule `SizeRestrictions_BODY` gives label `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body`, and a rule ending `_QUERYARGUMENTS` gives a label ending `_QueryArguments`). `UserAgent_BadBots_HEADER` blocks scanner User-Agents and ends evaluation, so rule groups ordered after it never label those requests; rule order changes which labels appear (observed). Body rules inspect only up to the ACL body size limit and continue on oversize (AWS docs).

### Known bad inputs

`AWSManagedRulesKnownBadInputsRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `ExploitablePaths_URIPATH` | `awswaf:managed:aws:known-bad-inputs:ExploitablePaths_URIPath` | URI path of known exploitable application paths (such as `web-inf`). | — |
| `Host_localhost_HEADER` | `awswaf:managed:aws:known-bad-inputs:Host_Localhost_Header` | `Host` header indicating localhost. | Internal tests sending `Host: localhost` (general) |
| `JavaDeserializationRCE_BODY`<br>`JavaDeserializationRCE_HEADER`<br>`JavaDeserializationRCE_QUERYSTRING`<br>`JavaDeserializationRCE_URIPATH` | `awswaf:managed:aws:known-bad-inputs:JavaDeserializationRCE_Body`<br>`awswaf:managed:aws:known-bad-inputs:JavaDeserializationRCE_Header`<br>`awswaf:managed:aws:known-bad-inputs:JavaDeserializationRCE_QueryString`<br>`awswaf:managed:aws:known-bad-inputs:JavaDeserializationRCE_URIPath` | Java deserialization RCE patterns (for example CVE-2022-22963/22965) in the component named by the suffix. | — |
| `Log4JRCE_BODY`<br>`Log4JRCE_HEADER`<br>`Log4JRCE_QUERYSTRING`<br>`Log4JRCE_URIPATH` | `awswaf:managed:aws:known-bad-inputs:Log4JRCE_Body`<br>`awswaf:managed:aws:known-bad-inputs:Log4JRCE_Header`<br>`awswaf:managed:aws:known-bad-inputs:Log4JRCE_QueryString`<br>`awswaf:managed:aws:known-bad-inputs:Log4JRCE_URIPath` | Log4j RCE patterns (such as `${jndi:ldap://...}`) in the component named by the suffix. | — |
| `PROPFIND_METHOD` | `awswaf:managed:aws:known-bad-inputs:Propfind_Method` | HTTP method `PROPFIND`. | WebDAV clients (general) |
| `ReactJSRCE_BODY` | `awswaf:managed:aws:known-bad-inputs:ReactJSRCE_Body` | Request body patterns for CVE-2025-55182. | — |

### Admin protection

`AWSManagedRulesAdminProtectionRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `AdminProtection_URIPATH` | `awswaf:managed:aws:admin-protection:AdminProtection_URIPath` | URI paths reserved for web server or application administration (such as `sqlmanager`). | Legitimate admin access by operators (general) |

### SQL database

`AWSManagedRulesSQLiRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-use-case.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `SQLi_BODY`<br>`SQLi_COOKIE`<br>`SQLi_QUERYARGUMENTS`<br>`SQLi_URIPATH` | `awswaf:managed:aws:sql-database:SQLi_Body`<br>`awswaf:managed:aws:sql-database:SQLi_Cookie`<br>`awswaf:managed:aws:sql-database:SQLi_QueryArguments`<br>`awswaf:managed:aws:sql-database:SQLi_URIPath` | SQL injection (WAF SQLi match, sensitivity Low) in the component named by the suffix. | Free-text, search or code-snippet fields containing SQL-like text (general) |
| `SQLiExtendedPatterns_QUERYARGUMENTS` | `awswaf:managed:aws:sql-database:SQLiExtendedPatterns_QueryArguments` | SQL injection patterns not covered by the base `SQLi_*` rule, in the query argument values. | Free-text fields containing SQL-like words (general) |

Notes: (docs only; verify with L-1) `SQLiExtendedPatterns_BODY` (`awswaf:managed:aws:sql-database:SQLiExtendedPatterns_Body`), `SQLiExtendedPatterns_HEADER` (`awswaf:managed:aws:sql-database:SQLiExtendedPatterns_Header`) and `SQLiExtendedPatterns_URIPATH` (`awswaf:managed:aws:sql-database:SQLiExtendedPatterns_UriPath`) are on the docs page but were not in the default-version API output.

### Linux operating system

`AWSManagedRulesLinuxRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-use-case.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `LFI_HEADER`<br>`LFI_QUERYSTRING`<br>`LFI_URIPATH` | `awswaf:managed:aws:linux-os:LFI_Header`<br>`awswaf:managed:aws:linux-os:LFI_QueryString`<br>`awswaf:managed:aws:linux-os:LFI_URIPath` | Linux-specific local file inclusion (such as `/proc/version`) in the component named by the suffix. | — |

### POSIX operating system

`AWSManagedRulesUnixRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-use-case.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `UNIXShellCommandsVariables_BODY`<br>`UNIXShellCommandsVariables_HEADER`<br>`UNIXShellCommandsVariables_QUERYSTRING` | `awswaf:managed:aws:posix-os:UNIXShellCommandsVariables_Body`<br>`awswaf:managed:aws:posix-os:UNIXShellCommandsVariables_Header`<br>`awswaf:managed:aws:posix-os:UNIXShellCommandsVariables_QueryString` | POSIX shell command or variable patterns (such as `echo $HOME`) in the component named by the suffix. | Technical content posted to forms (general) |

### Windows operating system

`AWSManagedRulesWindowsRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-use-case.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `PowerShellCommands_BODY`<br>`PowerShellCommands_COOKIE`<br>`PowerShellCommands_QUERYARGUMENTS` | `awswaf:managed:aws:windows-os:PowerShellCommands_Body`<br>`awswaf:managed:aws:windows-os:PowerShellCommands_Cookie`<br>`awswaf:managed:aws:windows-os:PowerShellCommands_QueryArguments` | PowerShell command injection patterns in the component named by the suffix. | Technical content posted to forms (general) |
| `WindowsShellCommands_BODY`<br>`WindowsShellCommands_HEADER`<br>`WindowsShellCommands_QUERYARGUMENTS`<br>`WindowsShellCommands_URIPATH` | `awswaf:managed:aws:windows-os:WindowsShellCommands_Body`<br>`awswaf:managed:aws:windows-os:WindowsShellCommands_Header`<br>`awswaf:managed:aws:windows-os:WindowsShellCommands_QueryArguments`<br>`awswaf:managed:aws:windows-os:WindowsShellCommands_UriPath` | Windows shell command injection patterns in the component named by the suffix. | Technical content posted to forms (general) |

Notes: (docs only; verify with L-1) `WindowsShellCommands_QUERYSTRING` (`awswaf:managed:aws:windows-os:WindowsShellCommands_QueryString`) is on the docs page but was not in the default-version API output.

### PHP application

`AWSManagedRulesPHPRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-use-case.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `PHPHighRiskMethodsVariables_BODY`<br>`PHPHighRiskMethodsVariables_HEADER`<br>`PHPHighRiskMethodsVariables_QUERYSTRING`<br>`PHPHighRiskMethodsVariables_URIPATH` | `awswaf:managed:aws:php-app:PHPHighRiskMethodsVariables_Body`<br>`awswaf:managed:aws:php-app:PHPHighRiskMethodsVariables_Header`<br>`awswaf:managed:aws:php-app:PHPHighRiskMethodsVariables_QueryString`<br>`awswaf:managed:aws:php-app:PHPHighRiskMethodsVariables_URIPath` | PHP code injection patterns (such as `fsockopen`, `$_GET`) in the component named by the suffix. | PHP code samples in posted content (general) |

### WordPress application

`AWSManagedRulesWordPressRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-use-case.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `WordPressExploitableCommands_QUERYSTRING` | `awswaf:managed:aws:wordpress-app:WordPressExploitableCommands_QUERYSTRING` | High-risk WordPress commands (such as `do-reset-wordpress`) in the query string. | — |
| `WordPressExploitablePaths_URIPATH` | `awswaf:managed:aws:wordpress-app:WordPressExploitablePaths_URIPATH` | Exploitable WordPress paths such as `xmlrpc.php`. | Sites that legitimately use XML-RPC (general) |

Notes: WordPress labels keep upper-case location suffixes.

### Amazon IP reputation list

`AWSManagedRulesAmazonIpReputationList`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-ip-rep.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `AWSManagedIPDDoSList` | `awswaf:managed:aws:amazon-ip-list:AWSManagedIPDDoSList` | Source IP identified as engaging in DDoS activity. Documented rule action is Count, so this label appears without a block (AWS docs). | — |
| `AWSManagedIPReputationList` | `awswaf:managed:aws:amazon-ip-list:AWSManagedIPReputationList` | Source IP identified as actively engaging in malicious activity (Amazon threat intelligence). | Shared or NAT addresses recently abused by others (general) |
| `AWSManagedReconnaissanceList` | `awswaf:managed:aws:amazon-ip-list:AWSManagedReconnaissanceList` | Source IP performing reconnaissance against AWS resources. | — |

Notes: these rules use the web request origin IP, which behind a proxy is the last proxy address (AWS docs).

### Anonymous IP list

`AWSManagedRulesAnonymousIpList`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-ip-rep.html

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `AnonymousIPList` | `awswaf:managed:aws:anonymous-ip-list:AnonymousIPList` | Source IP of known anonymizers (Tor nodes, temporary proxies, masking services). | Legitimate users behind VPNs or privacy proxies (general) |
| `HostingProviderIPList` | `awswaf:managed:aws:anonymous-ip-list:HostingProviderIPList` | Source IP of web hosting and cloud providers (not AWS addresses), which are less likely to source end-user traffic (AWS docs). | Server-to-server integrations and monitors hosted in clouds (general) |

### Anti-DDoS

`AWSManagedRulesAntiDDoSRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-anti-ddos.html

The API lists 23 labels for this group: the 9 below plus the 14 token and captcha labels, which are defined in "Token labels".

| Rule | Label | What it detects | Common false-positive pattern |
|---|---|---|---|
| `ChallengeAllDuringEvent` | `awswaf:managed:aws:anti-ddos:ChallengeAllDuringEvent` | Rule: challengeable request while the resource is under a detected DDoS event (action Challenge). | Legitimate browser users are challenged during an event (general) |
| `ChallengeDDoSRequests` | `awswaf:managed:aws:anti-ddos:ChallengeDDoSRequests` | Rule: request at or above the configured challenge sensitivity during an event; evaluated only if the previous rule is overridden to Count. | — |
| `DDoSRequests` | `awswaf:managed:aws:anti-ddos:DDoSRequests` | Rule: request at or above the configured block sensitivity during an event (action Block). | — |
| (group label) | `awswaf:managed:aws:anti-ddos:challengeable-request` | GET request whose URI is not exempted, so it can take the Challenge action. Applied whether or not an attack is in progress. | Present on most baseline GET traffic; not evidence of an attack (observed) |
| (group label) | `awswaf:managed:aws:anti-ddos:ddos-request` | Request from a source suspected of participating in an event. | — |
| (group label) | `awswaf:managed:aws:anti-ddos:event-detected` | The protected resource is in a detected DDoS event; added to every request to it, attack or legitimate. | Also on legitimate traffic (AWS docs) |
| (group label) | `awswaf:managed:aws:anti-ddos:high-suspicion-ddos-request` | Highly likely DDoS request. | — |
| (group label) | `awswaf:managed:aws:anti-ddos:low-suspicion-ddos-request` | Probable DDoS request. | — |
| (group label) | `awswaf:managed:aws:anti-ddos:medium-suspicion-ddos-request` | Very likely DDoS request. | — |

### Bot Control

`AWSManagedRulesBotControlRuleSet`. Docs: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-bot.html

Label prefix `awswaf:managed:aws:bot-control:`. `bot:name:*` labels are covered by the pattern row (coverage exception). `TGT_*` rules need tokens and do not see clients that never obtain one. The group also emits the token labels in "Token labels".

Notes B0 (applies to every `Category*` row below except `CategoryAI`): action Block applies to unverified bots only; verified bots are labelled, not blocked (AWS docs). `CategoryAI` blocks all matches, verified or unverified (AWS docs). The `Signal*` rules are not applied to verified bots (AWS docs). False positives for all Category and Signal rows: see Notes B1.

| Rule | Label(s) | What it detects |
|---|---|---|
| `CategoryAdvertising` | `awswaf:managed:aws:bot-control:CategoryAdvertising`<br>`awswaf:managed:aws:bot-control:bot:category:advertising` | Advertising bots. |
| `CategoryArchiver` | `awswaf:managed:aws:bot-control:CategoryArchiver`<br>`awswaf:managed:aws:bot-control:bot:category:archiver` | Archiving crawlers. |
| `CategoryContentFetcher` | `awswaf:managed:aws:bot-control:CategoryContentFetcher`<br>`awswaf:managed:aws:bot-control:bot:category:content_fetcher` | Bots fetching content on behalf of a user. |
| `CategoryEmailClient` | `awswaf:managed:aws:bot-control:CategoryEmailClient`<br>`awswaf:managed:aws:bot-control:bot:category:email_client` | Bots checking links in emails. |
| `CategoryHttpLibrary` | `awswaf:managed:aws:bot-control:CategoryHttpLibrary`<br>`awswaf:managed:aws:bot-control:bot:category:http_library` | Programming-language HTTP library clients. |
| `CategoryLinkChecker` | `awswaf:managed:aws:bot-control:CategoryLinkChecker`<br>`awswaf:managed:aws:bot-control:bot:category:link_checker` | Broken-link checkers. |
| `CategoryMiscellaneous` | `awswaf:managed:aws:bot-control:CategoryMiscellaneous`<br>`awswaf:managed:aws:bot-control:bot:category:miscellaneous` | Bots in no other category. |
| `CategoryMonitoring` | `awswaf:managed:aws:bot-control:CategoryMonitoring`<br>`awswaf:managed:aws:bot-control:bot:category:monitoring` | Uptime and performance monitors. |
| `CategoryScrapingFramework` | `awswaf:managed:aws:bot-control:CategoryScrapingFramework`<br>`awswaf:managed:aws:bot-control:bot:category:scraping_framework` | Web scraping frameworks. |
| `CategorySearchEngine` | `awswaf:managed:aws:bot-control:CategorySearchEngine`<br>`awswaf:managed:aws:bot-control:bot:category:search_engine` | Search engine crawlers. |
| `CategorySecurity` | `awswaf:managed:aws:bot-control:CategorySecurity`<br>`awswaf:managed:aws:bot-control:bot:category:security` | Vulnerability scanners and security audit bots. |
| `CategorySeo` | `awswaf:managed:aws:bot-control:CategorySeo`<br>`awswaf:managed:aws:bot-control:bot:category:seo` | SEO tool crawlers. |
| `CategorySocialMedia` | `awswaf:managed:aws:bot-control:CategorySocialMedia`<br>`awswaf:managed:aws:bot-control:bot:category:social_media` | Social media link-preview bots. |
| `CategoryAI` | `awswaf:managed:aws:bot-control:CategoryAI`<br>`awswaf:managed:aws:bot-control:bot:category:ai` | AI bots (blocks verified and unverified; Notes B0). |
| `CategoryPagePreview`, `CategoryWebhooks` (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:bot:category:page_preview`<br>`awswaf:managed:aws:bot-control:bot:category:webhooks`<br>rule labels `awswaf:managed:aws:bot-control:CategoryPagePreview`, `awswaf:managed:aws:bot-control:CategoryWebhooks` | Link/page-preview bots; webhook delivery bots. Legitimate webhook senders are a false-positive pattern (general). |
| `SignalAutomatedBrowser` | `awswaf:managed:aws:bot-control:SignalAutomatedBrowser`<br>`awswaf:managed:aws:bot-control:signal:automated_browser` | Non-verified client shows browser automation indicators. |
| `SignalKnownBotDataCenter` | `awswaf:managed:aws:bot-control:SignalKnownBotDataCenter`<br>`awswaf:managed:aws:bot-control:signal:known_bot_data_center` | Non-verified request from a data center typically used by bots. |
| `SignalNonBrowserUserAgent` | `awswaf:managed:aws:bot-control:SignalNonBrowserUserAgent`<br>`awswaf:managed:aws:bot-control:signal:non_browser_user_agent` | User-Agent does not look like a browser (can include API requests). |
| (none documented) | `awswaf:managed:aws:bot-control:signal:non_browser_header` | In the API label list but not in the docs rule listing used; meaning unverified beyond the name. No false-positive pattern claimed. |
| (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:signal:cloud_service_provider:<csp>` | Request from a cloud provider (`aws`, `gcp`, `azure`, `oracle`) (AWS docs). Server-side integrations in clouds are a false-positive pattern (general). |

Targeted (`TGT_*`) and identity rows:

| Rule | Label(s) | What it detects | Common false-positive pattern |
|---|---|---|---|
| `TGT_VolumetricIpTokenAbsent` | `awswaf:managed:aws:bot-control:TGT_VolumetricIpTokenAbsent`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:ip:token_absent` | 5 or more requests from one client IP in 5 minutes without a valid token (action Challenge). Can also match a request that has a token if the client was recently missing tokens (AWS docs). See Notes B2. | Scripted or non-browser clients that never run the challenge (general) |
| `TGT_VolumetricSession` | `awswaf:managed:aws:bot-control:TGT_VolumetricSession`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:high`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:medium`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:low` | Abnormally high request volume for one token session in 5 minutes (action CAPTCHA on `:high`; `:medium` and `:low` are label-only). Needs a token (AWS docs). | Heavy but legitimate single sessions (general) |
| `TGT_VolumetricSessionMaximum` (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:maximum`<br>`awswaf:managed:aws:bot-control:TGT_VolumetricSessionMaximum` | Maximum-confidence session volume anomaly (action Block) (AWS docs). | — |
| `TGT_TokenAbsent` (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:TGT_TokenAbsent` | Non-verified request without a valid token (action Count) (AWS docs). Per-request, unlike the volumetric rule. | Scripted clients and first page loads (general) |
| `TGT_SignalAutomatedBrowser` | `awswaf:managed:aws:bot-control:TGT_SignalAutomatedBrowser`<br>`awswaf:managed:aws:bot-control:targeted:signal:automated_browser` | Token shows automated-browser indicators (action CAPTCHA). | Test automation (general) |
| `TGT_SignalBrowserInconsistency` | `awswaf:managed:aws:bot-control:TGT_SignalBrowserInconsistency`<br>`awswaf:managed:aws:bot-control:targeted:signal:browser_inconsistency` | Inconsistent browser interrogation data in the token (action CAPTCHA). | — |
| `TGT_SignalBrowserAutomationExtension` (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:targeted:signal:browser_automation_extension`<br>rule label `awswaf:managed:aws:bot-control:TGT_SignalBrowserAutomationExtension` (docs only) | Browser extension that assists automation (such as Selenium IDE) is present, even if not in use (action CAPTCHA) (AWS docs). | Users who merely have such an extension installed (AWS docs) |
| `TGT_TokenReuseIp` (docs: Low/Medium/High) | `awswaf:managed:aws:bot-control:TGT_TokenReuseIp`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:ip` | One token used from multiple IPs in 5 minutes. The API output had only the unsuffixed labels. Docs (verify with L-1): Low more than 2 IPs (Count), Medium more than 5 (CAPTCHA), High more than 8 (Block), with labels `awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:ip:low`, `awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:ip:medium`, `awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:ip:high` and rule labels `awswaf:managed:aws:bot-control:TGT_TokenReuseIpLow`, `awswaf:managed:aws:bot-control:TGT_TokenReuseIpMedium`, `awswaf:managed:aws:bot-control:TGT_TokenReuseIpHigh`. | Users changing networks, rotating egress (general) |
| `TGT_TokenReuseCountryLow`, `TGT_TokenReuseCountryMedium`, `TGT_TokenReuseCountryHigh` (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:country:low`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:country:medium`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:country:high`<br>rule labels `awswaf:managed:aws:bot-control:TGT_TokenReuseCountryLow`, `awswaf:managed:aws:bot-control:TGT_TokenReuseCountryMedium`, `awswaf:managed:aws:bot-control:TGT_TokenReuseCountryHigh` | One token across more than 1 / 2 / 3 countries in 5 minutes (Count / CAPTCHA / Block) (AWS docs). | Travellers, VPN users (general) |
| `TGT_TokenReuseAsnLow`, `TGT_TokenReuseAsnMedium`, `TGT_TokenReuseAsnHigh` (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:asn:low`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:asn:medium`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:session:token_reuse:asn:high`<br>rule labels `awswaf:managed:aws:bot-control:TGT_TokenReuseAsnLow`, `awswaf:managed:aws:bot-control:TGT_TokenReuseAsnMedium`, `awswaf:managed:aws:bot-control:TGT_TokenReuseAsnHigh` | One token across more than 1 / 2 / 3 ASNs in 5 minutes (Count / CAPTCHA / Block) (AWS docs). | Mobile users switching carriers or Wi-Fi (general) |
| `TGT_ML_CoordinatedActivityLow/Medium/High` | `awswaf:managed:aws:bot-control:TGT_ML_CoordinatedActivityMedium`<br>`awswaf:managed:aws:bot-control:TGT_ML_CoordinatedActivityHigh`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:coordinated_activity:low`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:coordinated_activity:medium`<br>`awswaf:managed:aws:bot-control:targeted:aggregate:coordinated_activity:high` | ML: behavior consistent with distributed coordinated bots; Low action Challenge, Medium and High CAPTCHA. The Low rule label (`awswaf:managed:aws:bot-control:TGT_ML_CoordinatedActivityLow`) is docs only. | One or two matches can be false positives; many matches suggest a real coordinated attack (AWS docs) |
| (bot identity) | `awswaf:managed:aws:bot-control:bot:verified` | Self-identifying bot that Bot Control verified; labelled, not blocked (AWS docs). | — |
| (bot identity) | `awswaf:managed:aws:bot-control:bot:unverified` | Self-identifying bot that cannot be independently verified; signatures can be falsified (AWS docs). | — |
| (bot identity) | `awswaf:managed:aws:bot-control:bot:user_triggered:verified`<br>`awswaf:managed:aws:bot-control:bot:developer_platform:verified` | Verified-style bots that users invoke directly, or developer-platform scripting bots; treated like unverified (AWS docs). | — |
| (bot identity) | `awswaf:managed:aws:bot-control:bot:organization:google`<br>`awswaf:managed:aws:bot-control:bot:organization:microsoft` | Publisher of the bot. Pattern: `awswaf:managed:aws:bot-control:bot:organization:<organization>`. | — |
| (bot identity) | `awswaf:managed:aws:bot-control:bot:name:<name>`; `awswaf:managed:aws:bot-control:bot:name:<rfc_name>` | Pattern: bot name, or specific bot by RFC product token from the WBA signature. 198 `bot:name:*` labels in the API output; take exact names from L-1 or the logs. | — |
| (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:bot:web_bot_auth:<status>` | Web Bot Authentication result: `verified`, `invalid`, `expired`, `unknown_bot`. When `verified`, the Category and `TGT_TokenAbsent` rules do not match (AWS docs). | — |
| (docs only; verify with L-1) | `awswaf:managed:aws:bot-control:bot:account:<hash>`; `awswaf:managed:aws:bot-control:bot:vendor:<vendor_name>` | Bedrock AgentCore bots only: opaque hash of the owning AWS account; vendor of a verified bot (AWS docs). | — |

Notes B1: Category and Signal false positives are your own monitors, partner integrations, API clients and mobile apps that self-identify or use non-browser User-Agents (general).
Notes B2: the label `awswaf:managed:aws:bot-control:targeted:aggregate:volumetric:ip:token_absent` was seen on a subset of requests from a scripted client, not on all of them (observed).
