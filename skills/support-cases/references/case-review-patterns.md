# Support Case Review Patterns

Common patterns and heuristics for identifying relevant historical support cases
during incident investigations.

## Pattern 1: Recurring Infrastructure Failures

**Indicators:**
- Multiple cases with the same `serviceCode` and `categoryCode` within 90 days.
- Similar error messages appearing in case subjects or communications.
- Cases filed by different team members for the same underlying issue.

**Investigation approach:**
1. Search cases by service code for the past 90 days.
2. Group cases by `categoryCode` and look for clusters.
3. Review resolutions — if workarounds were applied instead of permanent fixes,
   the issue is likely recurring.

**Example keywords to search in subjects:**
- "timeout", "connection refused", "throttling"
- "5xx", "502", "503", "504"
- "capacity", "scaling", "limit"

---

## Pattern 2: Post-Deployment Issues

**Indicators:**
- Incident started shortly after a deployment (within 1–4 hours).
- Past cases reference deployment-related root causes.
- Symptoms match a known regression pattern.

**Investigation approach:**
1. Identify the deployment timestamp from CI/CD pipeline.
2. Search cases created within 24 hours after similar past deployments.
3. Look for cases mentioning "rollback", "deployment", "release", or "config change".

---

## Pattern 3: AWS Service Events

**Indicators:**
- Multiple accounts or services affected simultaneously.
- Past cases reference AWS Health Dashboard events.
- AWS Support responses mention "service team investigation" or "known issue".

**Investigation approach:**
1. Check AWS Health Dashboard for active events.
2. Search past cases in the same time window as known AWS service events.
3. Look for communications where AWS confirms a service-side issue.

**Key phrases in AWS responses indicating service events:**
- "Our service team has identified..."
- "This is a known issue affecting..."
- "We are actively working on..."
- "The issue has been resolved on our end..."

---

## Pattern 4: Capacity and Scaling Issues

**Indicators:**
- Errors related to limits, quotas, or throttling.
- Incidents correlate with traffic spikes or batch processing windows.
- Past cases resulted in limit increases or scaling adjustments.

**Investigation approach:**
1. Search cases with keywords: "limit", "quota", "throttle", "capacity".
2. Check if limit increases from past cases are still sufficient.
3. Review if auto-scaling configurations recommended in past cases were implemented.

---

## Pattern 5: Network and Connectivity Issues

**Indicators:**
- Timeout errors, DNS resolution failures, or connectivity drops.
- Issues affecting specific Availability Zones or regions.
- Past cases involving security group, NACL, or route table changes.

**Investigation approach:**
1. Search cases by VPC, ELB, or Route 53 service codes.
2. Look for cases mentioning the same Availability Zone or subnet.
3. Check if network configuration changes recommended in past cases were applied.

---

## Correlation Heuristics

When comparing the current incident to historical cases, use these heuristics
to assess relevance:

### Strong correlation signals
- Identical error codes or exception types.
- Same resource ID or ARN appears in both incidents.
- Same time-of-day pattern (e.g., both occur during peak traffic hours).
- Same sequence of events leading to the failure.

### Moderate correlation signals
- Same AWS service but different resource.
- Similar but not identical error messages.
- Same architectural pattern (e.g., both involve cross-AZ communication).
- Same category of root cause (e.g., both are configuration drift issues).

### Weak correlation signals
- Different services but same failure mode (e.g., both are timeout-related).
- Same team or application owner filed both cases.
- Similar time window but different symptoms.

---

## Anti-Patterns to Avoid

- **Over-matching**: Don't assume every past case for the same service is
  relevant. Focus on matching symptoms and error patterns, not just service names.
- **Ignoring resolved status**: Resolved cases are often the most valuable
  because they contain root cause analysis and proven fixes.
- **Skipping communications**: The case subject alone rarely contains enough
  detail. Always review the full communication thread for relevant cases.
- **Single-case bias**: Don't anchor on the first matching case. Review multiple
  cases to identify patterns rather than one-off issues.
- **Stale recommendations**: Verify that remediation steps from old cases still
  apply to the current infrastructure configuration.
