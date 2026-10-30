---
name: cloudfront-operation-review
description: 'Read-only Amazon CloudFront operational review aligned with the AWS Well-Architected Framework. Use this skill when a user asks to review, audit, or assess CloudFront distributions for viewer and origin TLS posture, plaintext HTTP exposure, origin access control versus legacy origin access identity, AWS WAF association, certificate expiry, origin failover, cache-key and compression configuration, cache hit rate, error rates, logging, alarm coverage, or price class and dedicated-IP cost. Triggers on requests like "CloudFront operational review", "review my CloudFront distributions", "CDN health check", "CloudFront security audit", "CloudFront best practices", or "ORR for CloudFront". Also answers how the review judges a check (OAC eligibility, logging sources, additional metrics, Inspect verdicts). Not for diagnosing a single failing request or a specific 403 error.'
metadata:
  author: bajavani
  version: "1.0.0"
  summary: "Read-only CloudFront operational review: TLS, WAF, origin access, caching, logging, alarms and cost, scored by Well-Architected pillar."
  aws-devops-agent-skills.agent-types: "CHAT"
  aws-devops-agent-skills.aws-services: "Amazon CloudFront, AWS WAF, AWS Certificate Manager, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Networking, Security, Observability, Cost Optimization"
---

# Amazon CloudFront Operational Review

Conduct a read-only operational review of Amazon CloudFront distributions aligned with the
[AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
and the [Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html).

The skill reads control-plane configuration and CloudWatch metrics only. It sends no request
through any distribution, contacts no origin, creates no invalidation, and reads no edge
function code.

## When to Use

Activate this skill when the user asks to:
- Review, audit, or assess CloudFront distributions for best practices
- Check CloudFront TLS, WAF, origin access, logging, or alarm posture
- Evaluate cache efficiency, error rates, origin failover, or CloudFront cost levers
- Perform a CloudFront operational readiness review (ORR) or a recurring health check

Do **not** use this skill to diagnose one failing request, a specific 403/5xx incident, or
an origin connectivity failure that is happening now. Those are reactive investigations.
This skill is the proactive posture baseline run before an incident exists.

## Review Checklist

Work through these steps in order. Each depends on the outputs of the ones before it.

- [ ] Step 1: Identify target scope (accounts, distributions, pillars, window)
- [ ] Step 2: Pass 1. Discover distributions and the account's shared edge resources
- [ ] Step 3: Pass 1. Score configuration checks and rank distributions
- [ ] Step 4: Pass 2. Deep-dive reads for the ranked set (load the thresholds reference)
- [ ] Step 5: Evaluate the remaining checks (load the checklist reference)
- [ ] Step 6: Generate the report (load the report template)
- [ ] Step 7: Track findings over time (recurring reviews)

## Step 1: Identify Target Scope

Ask which accounts to review, and whether to focus on specific distribution IDs or all of
them. Validate a supplied distribution ID against `^E[A-Z0-9]{12,13}$`, anchored at both
ends. Accept a pillar subset and map free-text names to this canonical set
(case-insensitive): `security`; `reliability` (high availability, resiliency, failover);
`performance` (perf, caching, latency); `operational-excellence` (ops, observability,
logging, monitoring); `cost` (cost optimization, finops). If a term matches none of these,
ask the user to choose from the list.

Defaults: all distributions, all five pillars, a 7-day metric window.

**Unattended / scheduled runs.** If there is no interactive user turn, do not wait for
input. Proceed with the full default scope immediately.

**Account scoping.** Operate only within the accounts the Agent Space is configured to
access. Do not assume roles. Report an unassociated account as "not accessible from this
Agent Space".

## Step 2: Pass 1 — Discover

CloudFront is a global service. **Make every CloudFront, ACM-for-CloudFront, and CloudWatch
call in `us-east-1`, and do not iterate regions.**

```
cloudfront.ListDistributions                  # paginate on Marker / NextMarker until null (≤100 per page)
cloudfront.GetDistributionConfig              # per distribution: Logging and ContinuousDeploymentPolicyId are not in the summary
cloudfront.ListOriginAccessControls
cloudfront.ListCloudFrontOriginAccessIdentities
cloudfront.ListCachePolicies                  # Type=custom, plus managed policies referenced by behaviors
cloudfront.ListOriginRequestPolicies
cloudfront.ListResponseHeadersPolicies
cloudfront.ListRealtimeLogConfigs
cloudfront.ListContinuousDeploymentPolicies
cloudfront.ListKeyGroups
cloudfront.ListFunctions                      # metadata only
cloudfront.GetMonitoringSubscription          # per distribution: are additional metrics on?
logs.DescribeDeliverySources                  # us-east-1: standard logging (v2) sources for distributions
```

`ListDistributions` returns, per distribution, its origins, cache behaviors, viewer
certificate, `WebACLId`, restrictions, HTTP version, price class and custom error
responses. **It does not return `Logging`.** A logging verdict is only valid after
`GetDistributionConfig` has run for that distribution. If that call fails, mark the logging
check "not evaluated" for that distribution. Never report logging as missing from the
summary alone.

**Staging and tenant distributions.** Record `Staging == true` distributions as continuous
deployment staging copies, review them with their primary, and do not double-count their
findings. For `ConnectionMode == tenant-only` (multi-tenant) distributions, note that
per-tenant settings are out of scope for v1.

**Classify every origin and distribution** before any origin finding is evaluated. Load:
```
read_skill_resource(skill_id="cloudfront-operation-review", path="references/origin-classification.md")
```
[references/origin-classification.md](references/origin-classification.md) maps each origin
shape to its class and access mechanism, and defines the static / dynamic distribution
profile that WAF severity depends on. **If this call fails**, note it at the top of the
report and apply this summary: OAC applies only to S3 REST, S3 Multi-Region Access Point,
Lambda function URL, and MediaStore / MediaPackage v2 origins. Never recommend OAC for a
custom, S3 website-endpoint, or VPC origin; a custom origin (ALB, EC2, API, on-premises) is
🔎 Inspect (SEC-12).

## Step 3: Pass 1 — Score and Rank

Load the checklist now (it is needed for scoring):
```
read_skill_resource(skill_id="cloudfront-operation-review", path="references/best-practices-checklist.md")
```
[references/best-practices-checklist.md](references/best-practices-checklist.md) is the
canonical list of checks, with IDs, pass conditions, base severities and sources.

**If this call fails**, state at the top of the report: "⚠️ best-practices checklist
(`references/best-practices-checklist.md`) could not be loaded; findings are based on the
summary rules in SKILL.md only". Then apply the Core Rules below.

Evaluate every check whose data Pass 1 already holds (the checklist marks each check
**P1** or **P2**). Then rank distributions by their worst finding, then by finding count.

**Pass 2 set:** all distributions if the account has fewer than 10. Otherwise the 10
worst-ranked, plus any distribution the user named. State the set and the rule used in the
report, and list the distributions that received Pass 1 only.

## Step 4: Pass 2 — Deep-Dive Reads

Load the thresholds reference:
```
read_skill_resource(skill_id="cloudfront-operation-review", path="references/metrics-thresholds.md")
```
[references/metrics-thresholds.md](references/metrics-thresholds.md) holds every metric name,
dimension, statistic and band. **If this call fails**, note it at the top of the report and
use best-effort guidance.

For each Pass 2 distribution:

```
cloudwatch.GetMetricData        # us-east-1, namespace AWS/CloudFront, dimensions DistributionId AND Region=Global
cloudwatch.DescribeAlarms       # us-east-1; match AWS/CloudFront alarms on the DistributionId
wafv2.GetWebACL                 # Scope=CLOUDFRONT, us-east-1, for the WebACLId (an ARN)
acm.DescribeCertificate         # us-east-1, for ViewerCertificate.ACMCertificateArn
cloudfront.GetResponseHeadersPolicy / GetCachePolicy / GetOriginRequestPolicy   # policies referenced by behaviors
cloudfront.ListTagsForResource
logs.DescribeDeliveries         # for a matched standard logging (v2) delivery source
```

**Both dimensions are required.** A CloudFront metric query without `Region=Global` returns
nothing. An empty result from a query missing that dimension is a query error, not a "no
traffic" finding.

**Additional metrics are opt-in.** `CacheHitRate`, `OriginLatency` and per-status-code error
rates exist only when `GetMonitoringSubscription` shows
`MonitoringSubscription.RealtimeMetricsSubscriptionConfig.RealtimeMetricsSubscriptionStatus == Enabled`.
A `NoSuchMonitoringSubscription` error means the subscription was never created and is the
same as disabled. If they are disabled, mark the dependent
checks "not evaluated — additional metrics not enabled" and raise OPS-04 instead. Never
read a missing cache hit rate as 0 %.

**Cost (optional, degrades).** If the user asked for cost, or the cost pillar is in scope,
call `ce.GetCostAndUsage` for service "Amazon CloudFront", 3 months, `MONTHLY`,
`UnblendedCost`, grouped by `USAGE_TYPE`. Cost Explorer may return nothing meaningful from a
linked account. On `AccessDenied` or an empty result, mark the Cost Explorer findings "not
evaluated — cost data unavailable from this account" and still run every
configuration-driven cost check. Never report "no spend found" from a denied call.

**Permission handling.** On `AccessDenied` for any Pass 2 call, mark only the dependent
checks "not evaluated — `<action>` denied", continue, and list the denial under Visibility
Limits.

## Step 5: Evaluate the Remaining Checks

Work the checklist for every Pass 2 check. Mark each one ✅ Pass, ⚠️ Warning, ❌ Fail,
🔎 Inspect, or ➖ N/A, and raise a finding for every Warning and Fail. Apply the reference
rather than memory, so two runs over unchanged configuration agree.

### Core Rules (apply even if the checklist cannot be loaded)

1. **Prove it or don't assert it.** A distribution is reported non-compliant only when the
   API shows it. Where correctness depends on application requirements the API cannot see
   (origin timeouts, keep-alive, geo restriction, field-level encryption), the verdict is
   🔎 **Inspect**, never Pass and never Fail.
2. **Origin type gates origin findings.** Resolve the origin class (Step 2) before emitting
   any origin-access finding. OAC findings apply only to OAC-eligible origins.
3. **Defaults are reported as defaults.** An unchanged timeout reads "using default (<value>)
   — confirm against application behaviour". It never reads "not configured" or "pass".
   Timeout checks are N/A for S3 REST origins.
4. **Missing signal is a visibility limit.** Opt-in metrics that are off, a denied call, or a
   field not returned all produce "not evaluated — <reason>", listed under Visibility Limits.
5. **LOW findings never reduce the readiness score.** Surface them in the findings, but
   score them as passes, so best-practice suggestions cannot make a healthy distribution look
   defective.

### Severity and Readiness Score

Load before rating findings:
```
read_skill_resource(skill_id="cloudfront-operation-review", path="references/severity-and-scoring.md")
```
[references/severity-and-scoring.md](references/severity-and-scoring.md) defines CRITICAL,
HIGH, MEDIUM, LOW and INFO with their SLAs, and the readiness score formula. **If this call
fails**, note it at the top of the report and apply this summary: score = passes ÷ (passes +
warnings + fails) × 100, LOW counts as a pass, and Inspect, N/A and not-evaluated checks are
excluded and reported as a count beside the score.

### Recommendations

One recommendation per Warning or Fail, in the form **Current → Risk → Fix**, citing the
CloudFront documentation page for the fix. Use only documented commands
(`aws cloudfront get-distribution-config`, `aws cloudfront update-distribution`,
`aws cloudfront create-monitoring-subscription`, `aws cloudwatch put-metric-alarm`) with
placeholder IDs. Never invent flags. Remind the reader that `update-distribution` needs the
full config plus the current `ETag`. Do not give effort or time estimates.

## Step 6: Generate the Report

Load the template with:
```
read_skill_resource(skill_id="cloudfront-operation-review", path="assets/report-template.md")
```
[assets/report-template.md](assets/report-template.md) defines the sections, tables and
artifact naming (`cloudfront-review-<distribution-or-account>-<YYYY-MM-DD>.md`). If the call
fails, note it and still produce: header, executive summary with scores, distribution
inventory, findings by pillar, metrics summary, visibility limits, and prioritized
recommendations.

**Re-run behaviour.** Refresh an existing report for the same scope rather than creating a
duplicate.

**Validate before delivering.** Re-check the draft: every finding cites a check ID and the
API field that shows it; no OAC finding targets a non-eligible origin; every score matches
the formula and lists its excluded count; every "not evaluated" item appears under
Visibility Limits. Fix any mismatch, then re-check.

**End with the report.** Deliver the report as the final response. Put next steps in its
prioritized recommendations; do not call a follow-up question tool after it.

## Step 7: Track Findings Over Time (recurring reviews)

If a prior report exists for the same scope, lead with **Change Since Last Review**: New,
Resolved, and Persistent (with severity changes) findings, matched on distribution ID +
check ID. Persistent CRITICAL/HIGH findings warrant escalation. With no prior report, note
"baseline review — no prior run to compare". Never suppress a current finding because it
appeared before.

## Data Source Boundaries

Read-only calls only, all in the `AIDevOpsAgentAccessPolicy` managed policy: `cloudfront`
List/Get/Describe, `wafv2:GetWebACL`, `acm:DescribeCertificate`, `cloudwatch:GetMetricData`,
`cloudwatch:DescribeAlarms`, `logs:DescribeDeliverySources`, `logs:DescribeDeliveries`,
`ce:GetCostAndUsage`.

It does **not**:
- Send requests through a distribution, contact an origin, or create invalidations.
- Read CloudFront Functions or Lambda@Edge code (`DescribeFunction` metadata only).
- Evaluate WAF rule correctness or tuning. It reads the web ACL only to answer whether a
  distribution is protected, and by which rule types.
- Verify S3 bucket policies behind an origin, DNS alias records, or Lambda@Edge concurrency.
  These are deferred (see README Limitations).
- Assess sustainability. There is no API data source for a CloudFront carbon figure, so the
  pillar is omitted rather than estimated.

**Runtime inputs vs. eval fixtures.** At review time the skill reads only live AWS APIs and
its own `references/` and `assets/` files. Anything under `evals/` is for the evaluation
harness only.
