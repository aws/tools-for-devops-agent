# Best-Practices Checklist — Amazon CloudFront Operational Review

The canonical list of checks. Each check gives:

- **Pass:** the condition for ✅ Pass
- **Base severity:** the severity of a ❌ Fail or ⚠️ Warning
- **Pass 1 / Pass 2:** whether the check is scored in the inventory pass (P1, data from
  `ListDistributions` + `GetDistributionConfig` + account-level lists) or only for the deep-dive
  set (P2, per-distribution reads)
- **N/A:** when the check does not apply
- **Source:** the AWS documentation the check rests on

Verdicts: ✅ Pass · ⚠️ Warning · ❌ Fail · 🔎 Inspect (depends on something the API cannot
show; say what to confirm) · ➖ N/A · "not evaluated — <reason>". Severity meanings are in
`references/severity-and-scoring.md`. LOW findings count as passes in the readiness score.

Field paths are the public API's PascalCase (`DistributionConfig.ViewerCertificate`, not
`distributionConfig.viewerCertificate`). A camelCase path silently returns nothing.

Evaluate behavior-level checks on the `DefaultCacheBehavior` **and** on every item in
`CacheBehaviors.Items`. Report the path pattern of each failing behavior.

## Documented defaults

| Setting | Default | Source |
|---|---|---|
| Connection attempts | 3 | [Origin settings](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html) |
| Connection timeout | 10 s | same |
| Response (origin read) timeout | 30 s | same |
| Response completion timeout | 60 s | same |
| Quota ranges | connection timeout 1–10 s, response timeout 1–120 s, keep-alive 1–300 s (higher by quota request) | [Quotas](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html) |

---

## Security

### SEC-01 — Viewer HTTP allowed (P1)
- **Fail:** `ViewerProtocolPolicy == allow-all` on any behavior.
- **Base severity:** CRITICAL. Content can be served over plaintext HTTP.
- **Fix:** `redirect-to-https` (keeps old links working) or `https-only`.
- **Source:** [Require HTTPS between viewers and CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-https-viewers-to-cloudfront.html)

### SEC-02 — Origin HTTP only (P1)
- **Fail:** A custom origin with `CustomOriginConfig.OriginProtocolPolicy == http-only`.
- **Base severity:** CRITICAL.
- **Exception:** An **S3 website endpoint** origin supports HTTP only, so `http-only` is
  unavoidable there. Mark it 🔎 Inspect (MEDIUM). Recommend an S3 REST origin with origin
  access control if the website features (index and error documents, redirects) are not
  needed.
- **N/A:** S3 REST, VPC-origin-free S3 classes that use `S3OriginConfig`.

### SEC-03 — Origin protocol follows the viewer (P1)
- **Fail:** `OriginProtocolPolicy == match-viewer`.
- **Base severity:** HIGH. Escalate to CRITICAL when any behavior targeting that origin
  has `ViewerProtocolPolicy == allow-all`, since HTTP viewer requests then go to the origin
  over HTTP.

### SEC-04 — Weak origin TLS protocols (P1)
- **Fail:** `CustomOriginConfig.OriginSslProtocols.Items` includes `SSLv3` → CRITICAL.
  It includes `TLSv1` or `TLSv1.1` → HIGH.
- **Note:** The API takes the full list of protocols CloudFront may use with the origin,
  not a minimum. Recommend `TLSv1.2` only.
- **Source:** [Supported protocols and ciphers between CloudFront and the origin](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/secure-connections-supported-ciphers-cloudfront-to-origin.html)

### SEC-05 — Viewer security policy (P1)
- **Pass:** `ViewerCertificate.MinimumProtocolVersion` is `TLSv1.2_2021`, `TLSv1.2_2025`, or
  `TLSv1.3_2025`.
- **Fail:** Any older value (`SSLv3`, `TLSv1`, `TLSv1_2016`, `TLSv1.1_2016`, `TLSv1.2_2018`,
  `TLSv1.2_2019`) → HIGH.
- **Default certificate:** With `CloudFrontDefaultCertificate == true` (the
  `*.cloudfront.net` domain), CloudFront automatically sets the security policy to `TLSv1`
  and it cannot be changed. Mark it 🔎 Inspect (MEDIUM). To control the policy, serve
  through an alternate domain name with an ACM certificate.
- **Source:** [Supported protocols and ciphers between viewers and CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/secure-connections-supported-viewer-protocols-ciphers.html), [Distribution settings — security policy](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesGeneral.html)

### SEC-06 — Certificate validity and coverage (P2)
- Read `acm.DescribeCertificate` (us-east-1) for `ViewerCertificate.ACMCertificateArn`.
- **CRITICAL:** `Status` is not `ISSUED`, or `NotAfter` is in the past.
- **HIGH:** `NotAfter` within 30 days and the certificate is `IMPORTED`, or its
  `RenewalSummary.RenewalStatus == FAILED`.
- **INFO:** `NotAfter` within 30 days on an ACM-issued certificate whose managed renewal is
  `PENDING_AUTO_RENEWAL` or `PENDING_VALIDATION`. Note that DNS validation records must
  still resolve for renewal to complete.
- **HIGH:** An entry in `Aliases.Items` is not covered by the certificate's `DomainName` or
  `SubjectAlternativeNames` (a wildcard covers one label only).
- **N/A:** Default certificate.

### SEC-07 — IAM-stored certificate (P1)
- **Condition:** `ViewerCertificate.IAMCertificateId` set.
- **Base severity:** LOW. Recommend ACM, which renews issued certificates automatically.

### SEC-08 — No AWS WAF web ACL (P1, refined in P2)
- **Fail:** `WebACLId` empty.
- **Base severity:** HIGH for a **dynamic** distribution, MEDIUM for a **static** one (the
  profile is defined in SKILL.md Step 2).
- **P2 refinement:** Read the web ACL with `wafv2.GetWebACL` (`Scope=CLOUDFRONT`). A web ACL
  with zero rules gives no protection; treat it as absent. If it has rules but no
  AWS-managed rule group and no rate-based rule, raise LOW. Record rule types only. **Do not
  evaluate rule correctness or tuning.**
- **Source:** [Use AWS WAF protections](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-web-awswaf.html)

### SEC-09 — Legacy origin access identity (P1)
- **Fail:** An S3 origin uses `S3OriginConfig.OriginAccessIdentity` (non-empty) instead of
  `OriginAccessControlId`.
- **Base severity:** MEDIUM. AWS recommends origin access control. OAC supports S3 server-side
  encryption with KMS, all Regions, and dynamic requests to S3, which OAI does not.
- **N/A:** Every non-S3 origin class.
- **Source:** [Restrict access to an Amazon S3 origin](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)

### SEC-10 — S3 REST origin with no origin access restriction (P1)
- **Fail:** An S3 REST origin has neither `OriginAccessControlId` nor an
  `OriginAccessIdentity`.
- **Base severity:** HIGH. CloudFront then fetches as an anonymous principal, so the bucket
  (or its objects) must be publicly readable for the distribution to work. Viewers can bypass
  CloudFront and WAF.
- **Note:** This skill does not read the bucket policy. Say "the bucket is likely public"
  and recommend confirming with S3 Block Public Access.

### SEC-11 — Other OAC-eligible origins without OAC (P1)
- **Fail:** A Lambda function URL, MediaStore, MediaPackage v2, or S3 Multi-Region Access
  Point origin without `OriginAccessControlId`.
- **Base severity:** MEDIUM.
- **Source:** [Restrict access to an AWS origin](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-origin.html)

### SEC-12 — Custom origin reachable without CloudFront (P1)
- **Condition:** A custom origin (ALB, EC2, API, on-premises) that is not a VPC origin.
- **Verdict:** 🔎 Inspect, INFO. The API cannot show the origin's security group. Recommend
  confirming the origin accepts only CloudFront traffic: the CloudFront managed prefix list
  in its security group and/or a secret custom header the origin validates. If
  `CustomHeaders.Quantity == 0`, say no secret header is configured.
- **Source:** [Restrict access to Application Load Balancers](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/restrict-access-to-load-balancer.html)

### SEC-13 — Legacy signed URLs with key pairs (P1)
- **Fail:** `TrustedSigners.Enabled == true` on any behavior.
- **Base severity:** HIGH. CloudFront key pairs need the AWS account root user to manage.
  AWS recommends trusted key groups (`TrustedKeyGroups`).
- **Source:** [Specify signers for signed URLs and signed cookies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-trusted-signers.html)

### SEC-14 — Security response headers (P1 presence, P2 values)
- **P1:** No behavior has a `ResponseHeadersPolicyId` → MEDIUM on an HTTPS-serving
  distribution.
- **P2:** In the policy's `SecurityHeadersConfig`: `StrictTransportSecurity` absent →
  MEDIUM. HSTS `AccessControlMaxAgeSec` < 31,536,000 → LOW. `ContentTypeOptions` or
  `FrameOptions` absent → LOW. Report `ContentSecurityPolicy` presence as INFO (its content
  is application-specific).
- **Note:** The origin may set these headers itself. Say the API cannot see origin-set headers.

### SEC-15 — Geo restriction and field-level encryption (P1, INFO)
- Record `Restrictions.GeoRestriction.RestrictionType` and any `FieldLevelEncryptionId`.
- **Verdict:** 🔎 Inspect. Whether either is needed depends on regulatory and data
  requirements the API cannot show. Never Pass or Fail.

---

## Reliability

### REL-01 — No origin failover (P1)
- **Condition:** The default behavior targets a single origin (not an origin group) on a
  **dynamic** distribution.
- **Base severity:** MEDIUM. Static S3 distributions → LOW.
- **Source:** [Origin failover](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/high_availability_origin_failover.html)

### REL-02 — Origin group failover criteria (P1)
- **Condition:** An origin group's `FailoverCriteria.StatusCodes` lacks any of 500, 502,
  503, 504.
- **Verdict:** 🔎 Inspect, LOW. Confirm the omission is intended.

### REL-03 — Origin timeouts at default (P1)
- **Condition:** `ConnectionAttempts`, `ConnectionTimeout`, `OriginReadTimeout`,
  `ResponseCompletionTimeout` (where set) and `OriginKeepaliveTimeout`.
- **Verdict:** 🔎 Inspect, INFO. Report the value and whether it is the default. **Never
  Pass.** The right value depends on origin behaviour. Note that each connection attempt
  multiplies time-to-failover: attempts × connection timeout before CloudFront fails over or
  returns an error.
- **N/A:** S3 REST origins (connection and keep-alive settings). Keep-alive applies to custom
  and VPC origins only.

### REL-04 — No custom error responses (P1)
- **Condition:** `CustomErrorResponses.Quantity == 0`.
- **Base severity:** LOW. Also record `ErrorCachingMinTTL` where responses exist. A long
  error-caching TTL extends an outage at the edge.

### REL-05 — 5xx error rate (P2)
- From `references/metrics-thresholds.md`. Above 1 % → HIGH. Report 502/503/504 split only
  when additional metrics are on.

### REL-06 — 4xx error rate (P2)
- Above 10 % → MEDIUM. Report 401/403/404 split only when additional metrics are on.
- **Note:** A high 403 rate often comes from WAF blocks or origin access. Hand
  request-level diagnosis to a reactive investigation; do not diagnose it here.

### REL-07 — Continuous deployment (P1, INFO)
- Record `ContinuousDeploymentPolicyId` and its staging distribution, if present. No verdict.

---

## Performance Efficiency

### PERF-01 — Cache hit rate (P2, needs additional metrics)
- **Static distribution:** `CacheHitRate` below 60 % → HIGH. Below 80 % → MEDIUM.
- **Dynamic distribution:** 🔎 Inspect, INFO. A low rate is expected for uncacheable API
  traffic. Report it with the cache policy TTLs.
- **Not evaluated:** additional metrics disabled (see OPS-04).

### PERF-02 — Legacy cache settings (P1)
- **Fail:** A behavior uses `ForwardedValues` instead of `CachePolicyId`.
- **Base severity:** MEDIUM. Legacy settings tie the cache key to forwarded values, which
  usually lowers the hit rate.
- **Source:** [Control the cache key with a policy](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/controlling-the-cache-key.html)

### PERF-03 — Compression (P1, refined in P2)
- **Fail:** `Compress == false` on a behavior → MEDIUM.
- **P2:** The behavior's cache policy has `EnableAcceptEncodingGzip` and
  `EnableAcceptEncodingBrotli` both false → MEDIUM. CloudFront compresses only when
  `Compress` is true **and** the cache policy includes `Accept-Encoding`.
- **Source:** [Serve compressed files](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/ServingCompressedFiles.html)

### PERF-04 — Origin latency (P2, needs additional metrics)
- `OriginLatency` p90 above 2,000 ms → HIGH. Above 500 ms → MEDIUM.

### PERF-05 — HTTP version (P1)
- **Fail:** `HttpVersion == http1.1` → LOW. Recommend `http2and3`.

### PERF-06 — Origin Shield (P1, INFO)
- Record `OriginShield.Enabled` per origin. 🔎 Inspect. It helps when viewers span many
  Regions or the origin is sensitive to load, and it adds cost. No pass or fail.
- **Source:** [Origin Shield](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/origin-shield.html)

---

## Operational Excellence

### OPS-01 — Access logging (P1, from GetDistributionConfig and logs)
- **Fail:** No standard logging (v2) delivery for the distribution
  (`logs.DescribeDeliverySources` in us-east-1 with no source whose `resourceArns` contains
  the distribution ARN) **and** `DistributionConfig.Logging.Enabled` false → HIGH.
- **Warning:** Legacy logging only → MEDIUM. Standard logging (v2) adds CloudWatch Logs and
  Firehose destinations, field selection, and output formats.
- **Not evaluated:** `GetDistributionConfig` failed, or the `logs` call was denied. **Never
  judge logging from the distribution summary**, which has no `Logging` field.
- **Source:** [Standard logging (v2)](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/standard-logging.html)

### OPS-02 — No alarms (P2)
- **Fail:** No CloudWatch alarm in us-east-1 on `AWS/CloudFront` with this `DistributionId`
  for `5xxErrorRate` (or `TotalErrorRate`) → MEDIUM.
- **INFO:** Where additional metrics are on, note missing alarms on `CacheHitRate` or
  `OriginLatency`.

### OPS-03 — Distribution has no tags (P2)
- **Fail:** `ListTagsForResource` returns no tags → LOW.

### OPS-04 — Additional metrics disabled (P1)
- **Condition:** `GetMonitoringSubscription` shows `Disabled` or `NoSuchMonitoringSubscription`.
- **Base severity:** LOW. Without it, cache hit rate, origin latency, and per-code error rates
  are unavailable. Note that it is billed per distribution, and list it under Visibility
  Limits.
- **Source:** [Turn on additional CloudFront distribution metrics](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/viewing-cloudfront-metrics.html)

### OPS-05 — Empty comment (P1)
- **Fail:** `DistributionConfig.Comment` empty → LOW.

---

## Cost Optimization

### COST-01 — Dedicated-IP custom SSL (P1)
- **Fail:** `ViewerCertificate.SSLSupportMethod == vip`.
- **Base severity:** MEDIUM. Dedicated-IP custom SSL carries a monthly charge. SNI
  (`sni-only`) serves all modern clients. Cite the
  [CloudFront pricing page](https://aws.amazon.com/cloudfront/pricing/) rather than stating a
  figure.

### COST-02 — Disabled distributions (P1)
- **Condition:** `Enabled == false`.
- **Verdict:** LOW hygiene. A disabled distribution does not serve requests. Recommend
  deleting it if it is no longer needed. Escalate to MEDIUM if it also uses `vip` (COST-01),
  which keeps billing.

### COST-03 — Real-time log sampling at 100 % (P1)
- **Condition:** A real-time log configuration attached to a behavior has `SamplingRate == 100`.
- **Verdict:** 🔎 Inspect, LOW. Full sampling multiplies stream volume. Confirm it is needed.

### COST-04 — Price class (P1, INFO)
- Record `PriceClass`. 🔎 Inspect against the audience geography, which the API does not
  show. No pass or fail.

### COST-05 — Compression savings (cross-reference)
- Where PERF-03 fails, express the data-transfer opportunity as a **range from $0 to about
  70 % of monthly data-transfer-out cost**. Already-compressed and binary content gains
  nothing, so never give a single-point estimate.

### COST-06 — Spend breakdown (P2, Cost Explorer, degrades)
- Report the 3-month CloudFront cost by usage type as INFO, labelled "from Cost Explorer".
- **Not evaluated:** denied or empty in a linked account. The configuration-driven checks
  above still run.
