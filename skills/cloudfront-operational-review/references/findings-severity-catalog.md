# CloudFront Findings & Severity Catalog

Organized by AWS Well-Architected pillar. Maps to `SKILL.md` Step 11. Each row gives the
check, the condition, the **evidence required** before the severity applies, and the
severity. Severities are starting points — escalate for tier-1 or regulated (PCI, HIPAA)
workloads.

If the required evidence cannot be collected (`AccessDenied`, unreadable bucket, origin in
another account), report the check as **UNKNOWN — manual verification required**, naming the
API and error. The configuration-absent codes listed in `SKILL.md` Known API quirks (for
example, `NoSuchBucketPolicy`) mean the feature is not configured: record a negative result,
not UNKNOWN. `NoSuchBucket` on an origin bucket is a missing origin (see Reliability). Do not
substitute a CloudFront-config
inference for missing origin evidence.

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | 24–48 hours |
| HIGH | Significant gap that could lead to incidents | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |
| UNKNOWN | Evidence could not be collected | Manual verification |

## Security

| Check | Condition | Evidence required | Severity |
|---|---|---|---|
| WAF web ACL attached | `WebACLId` empty on an internet-facing distribution | `GetDistributionConfig.WebACLId` | HIGH (CRITICAL for auth'd/sensitive apps) |
| S3 REST origin: bucket policy classified as public | REST origin (`S3OriginConfig`) with no OAC/OAI, `GetBucketPolicyStatus.IsPublic=true`, and `RestrictPublicBuckets` is not true at bucket or account level | `s3.GetBucketPolicyStatus`, `s3.GetPublicAccessBlock`, `s3control.GetPublicAccessBlock` (bucket owner account) | CRITICAL — word it "bucket policy classified as public; effective access is public unless an organization-level Block Public Access policy applies" |
| S3 REST origin: bucket ACL grants public access | No OAC/OAI, ACLs enabled (`ObjectOwnership` not `BucketOwnerEnforced`), a `GetBucketAcl` grant to `AllUsers` or `AuthenticatedUsers`, and `IgnorePublicAcls` is not true at bucket or account level | `s3.GetBucketOwnershipControls`, `s3.GetBucketAcl`, the Block Public Access calls | CRITICAL — name what the grant permits (`READ` = public object listing, `WRITE` = public write, `WRITE_ACP` or `FULL_CONTROL` = anyone can change the ACL); same organization-level caveat |
| S3 REST origin without OAC/OAI, no public path | Policy not public (or `RestrictPublicBuckets=true`) **and** public ACLs cannot apply (ACLs disabled, or `IgnorePublicAcls=true` at bucket or account level) — CloudFront cannot authenticate, so requests likely fail with 403 | All of the above | HIGH (availability) — confirm with 403ErrorRate or logs |
| S3 REST origin without OAC/OAI, object ACLs unchecked | Policy not public (or `RestrictPublicBuckets=true`), no public bucket-ACL grant, ACLs enabled, and `IgnorePublicAcls` not true at bucket or account level — objects can still be public through object ACLs | All of the above, plus 403ErrorRate (additional metrics) or the log 403 share (Step 8) | HIGH (availability) when the 403 evidence shows requests failing; otherwise UNKNOWN — "object ACLs not checked" |
| S3 REST origin, evidence incomplete | Any bucket, ACL, or account-level call returns `AccessDenied`, or the bucket is owned by another account, and the readable evidence does not already settle the check | Error from the call, or `s3.ListBuckets` | UNKNOWN — name the API and error |
| S3 website endpoint origin | Custom origin with an `s3-website` domain | Origin type | INFO — OAC/OAI cannot be used with website endpoints by design; the bucket must allow public reads. Recommend a REST origin with OAC only if website features (redirects, index documents) are not needed |
| Origin Access Control | REST origin using legacy OAI instead of OAC | Origin config | MEDIUM |
| OAC signing disabled | OAC attached with `SigningBehavior=never` | `ListOriginAccessControls` | MEDIUM |
| TLS minimum protocol | `MinimumProtocolVersion` ≤ `TLSv1.1_2016` on a custom certificate | Viewer certificate | HIGH |
| TLS minimum protocol | `MinimumProtocolVersion` = `TLSv1.2_2018/2019` (not 2021) | Viewer certificate | LOW |
| Viewer protocol policy | `allow-all` (plain HTTP permitted) | Cache behaviors | HIGH |
| Custom SSL certificate | Custom CNAME served on the default `*.cloudfront.net` certificate | Aliases + viewer certificate | MEDIUM |
| Field-level encryption | Sensitive form fields (PII/PCI) without FLE | User-confirmed data classification | MEDIUM, else INFO |
| Signed URLs / cookies | Private content without `TrustedKeyGroups` | User-confirmed private content | MEDIUM, else INFO |
| Geo restriction | Geo/regulatory-locked content with `RestrictionType=none` | User-confirmed requirement | LOW–MEDIUM, else INFO |
| Security response headers | No response headers policy (HSTS, X-Content-Type-Options) | Cache behaviors | LOW |
| Lambda@Edge / Functions | Untracked edge functions altering security behavior | Function associations | INFO–LOW |

Block Public Access applies the most restrictive of bucket, account, and organization settings
([S3 Block Public Access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html)).

## Reliability

| Check | Condition | Evidence required | Severity |
|---|---|---|---|
| Origin failover absent | Critical distribution, single origin, no origin group | Origins + origin groups | MEDIUM (HIGH for tier-1) |
| Failover status codes | Origin group omits 500/502/503/504 from `FailoverCriteria.StatusCodes` | Origin group config | MEDIUM |
| Failover vs allowed methods | Behavior targeting an origin group allows POST/PUT/PATCH/DELETE — those requests never fail over | `AllowedMethods` on the behavior | MEDIUM for write-heavy/API behaviors; INFO otherwise. Never report failover as a full reliability pass for such behaviors |
| OPTIONS failover | `AllowedMethods` includes OPTIONS but `CachedMethods` excludes it — OPTIONS will not fail over | `CachedMethods` | LOW |
| Origin error trend | Custom-origin 502/503/504 rising over 7 days | Additional metrics or logs | HIGH |
| 5xx error rate | `5xxErrorRate` 7-day avg > 1% | Default metric | HIGH |
| 5xx error rate | `5xxErrorRate` 7-day avg > 5% | Default metric | CRITICAL |
| S3 origin bucket missing | Any bucket call for an origin bucket returns `NoSuchBucket` | Error from the S3 call | HIGH — origin requests fail, and another account can re-register the bucket name |
| VPC origin backing health | Backing ALB/NLB has unhealthy targets, or load balancer is not `active` | `elbv2.DescribeLoadBalancers`, `DescribeTargetHealth` in the backing region | HIGH |
| VPC origin single-AZ | Backing load balancer spans one Availability Zone | `DescribeLoadBalancers.AvailabilityZones` | MEDIUM |
| VPC origin EC2 health | Backing instance state is not `running`, or `InstanceStatus`/`SystemStatus` is impaired | `ec2.DescribeInstanceStatus` (`IncludeAllInstances=true`) | HIGH |
| VPC origin evidence unavailable | Backing resource could not be described | Error from ELB/EC2 calls | UNKNOWN — `GetVpcOrigin` alone identifies the resource but not its health |
| Connection settings | `ConnectionAttempts=1` with no failover | Origin config | MEDIUM |
| Origin timeouts | Default timeouts unsuited to a slow origin (p95 OriginLatency near `OriginReadTimeout`) | Origin config + p95 OriginLatency | MEDIUM |
| Distribution status | Stuck `InProgress` well beyond the deploy window | `GetDistribution.Status` | MEDIUM |

## Performance

| Check | Condition | Evidence required | Severity |
|---|---|---|---|
| Cache hit ratio | `CacheHitRate` 7-day avg < 90% on a distribution where at least one behavior caches; label mixed distributions per metrics-thresholds Notes | Additional metric, or labeled log-derived approximation | MEDIUM |
| Cache hit ratio | `CacheHitRate` 7-day avg < 80% on a distribution where at least one behavior caches; label mixed distributions per metrics-thresholds Notes | Same | HIGH |
| Cache hit ratio, uncached by design | No behavior caches (`MaxTTL` 0) | Cache policies | INFO |
| Cache hit ratio unavailable | Additional metrics off and no queryable logs | Monitoring subscription + Step 8 outcome | UNKNOWN |
| Compression | `Compress=false` on text/JSON/HTML behaviors | Cache behaviors | MEDIUM |
| HTTP version | `HttpVersion` not `http2and3` (no HTTP/3) | Distribution config | LOW |
| HTTP version | HTTP/1.1 only | Distribution config | MEDIUM |
| Origin Shield | High-traffic distribution without Origin Shield | Origins + Requests | LOW–MEDIUM |
| Origin latency | p95 `OriginLatency` > 500 ms | Additional metric (p95) | MEDIUM |
| Origin latency | p95 `OriginLatency` > 1500 ms | Additional metric (p95) | HIGH |
| Cache key hygiene | Cache policy forwards unnecessary headers/cookies/query strings | Cache policies | MEDIUM |

## Cost Optimization

Report account-level cost plus per-distribution usage drivers. Do not compute a per-distribution
dollar figure unless resource-level billing data (`GetCostAndUsageWithResources` or the usage
report's `Resource` column) provides it.

| Check | Condition | Evidence required | Severity |
|---|---|---|---|
| Price class | `PriceClass_All` for a region-limited audience (pay-as-you-go only) | Price class + user-confirmed audience | MEDIUM |
| Cache hit ratio → cost | Low cache hit ratio raising origin fetch and data transfer (behaviors that cache only) | Cache hit ratio | MEDIUM |
| Unused distribution | `Enabled=false` or `Requests` 7-day sum ≈ 0 | Default metric | MEDIUM |
| Additional metrics on idle | Monitoring subscription on a near-zero-traffic distribution | Monitoring subscription + Requests | LOW |
| Cost-allocation tags | Missing `Environment`, `Owner`, `CostCenter`, `Application` | Tags | LOW |
| Flat-rate plan fit | Distribution in a flat-rate plan with usage far above or below the tier allowance | `pricingplanmanager.ListSubscriptions` + Requests/BytesDownloaded | INFO–LOW. Do not present per-GB or per-request savings for flat-rate distributions |

## Operational Excellence

| Check | Condition | Evidence required | Severity |
|---|---|---|---|
| CloudWatch alarms | No metric, metric-math, or composite alarm covers `5xxErrorRate` / `TotalErrorRate` | `DescribeAlarms` (Metric + Composite) | MEDIUM |
| CloudWatch alarms | No alarm covers p95 `OriginLatency` / `CacheHitRate` — **only when additional metrics are enabled** | `DescribeAlarms` + monitoring subscription | MEDIUM |
| Standard logging | Legacy `Logging.Enabled=false` **and** no v2 delivery source/delivery for the distribution | `GetDistributionConfig.Logging` + `logs.DescribeDeliverySources` / `DescribeDeliveries` | MEDIUM |
| Standard logging, v2 unreadable | Legacy logging off and delivery-source calls return `AccessDenied` | Error from logs calls | UNKNOWN |
| Log signals unavailable | Destination is S3 or Firehose, legacy logging only, output not JSON, or the Logs Insights query is denied | `DescribeDeliveries` / `DescribeDeliveryDestinations`, or the query error | UNKNOWN — name the reason; rely on CloudWatch metrics |
| Additional metrics | `GetMonitoringSubscription` disabled | Monitoring subscription | LOW–MEDIUM |
| Real-time logs | Absent for a high-value distribution needing sub-minute visibility (Kinesis Data Streams) | `RealtimeLogConfigArn` + `ListRealtimeLogConfigs` | LOW |
| Default root object | Not set on a website distribution | Distribution config | LOW |
| Operational tags | Missing `Environment`, `Owner`, `Runbook`, `OnCall` | Tags | LOW |

## Best-Practices Checklist (quick pass/fail)

### Security
- [ ] WAF web ACL attached to internet-facing distributions (`WebACLId`)
- [ ] `MinimumProtocolVersion` ≥ `TLSv1.2_2021`
- [ ] `ViewerProtocolPolicy` = `redirect-to-https` or `https-only`
- [ ] S3 REST origins use **OAC** with signing enabled; bucket policy not public, no public ACL, Block Public Access on (bucket or account)
- [ ] S3 website origins identified as such (OAC not applicable)
- [ ] Custom domains use an ACM certificate (not the default cert)
- [ ] Response headers policy adds HSTS + security headers

### Reliability
- [ ] Origin groups configured for critical distributions, with 5xx failover codes
- [ ] Failover-dependent behaviors serve GET/HEAD/OPTIONS (POST/PUT never fail over)
- [ ] VPC origin backing target healthy and multi-AZ (verified with ELB/EC2 APIs)
- [ ] `5xxErrorRate` within error budget (< 1%)

### Performance
- [ ] `CacheHitRate` ≥ 95%
- [ ] Compression enabled on compressible content types
- [ ] `HttpVersion` = `http2and3`
- [ ] p95 `OriginLatency` within the origin's expected range

### Cost Optimization
- [ ] Price class matches audience geography (pay-as-you-go)
- [ ] Flat-rate plan tier matches observed usage
- [ ] No enabled-but-idle distributions
- [ ] Cost-allocation tags applied

### Operational Excellence
- [ ] Alarms (metric, metric-math, or composite) on `5xxErrorRate` and `TotalErrorRate`
- [ ] Standard logging enabled (legacy or v2)
- [ ] Monitoring subscription enabled where cache/latency visibility is needed
- [ ] Operational tags present
