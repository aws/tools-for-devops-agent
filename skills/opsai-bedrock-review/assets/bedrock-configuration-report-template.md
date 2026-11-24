# Bedrock Configuration & Access Report

> Derived operational guidance from a read-only review of the account under review. SLAs are not
> AWS-published commitments. All findings carry an LLM-INV check-id and an AWS-doc citation.

## Scope

- **Account under review:** <alias or "the account under review" — never a raw 12-digit ID>
- **Region(s) reviewed:**
- **Credentials:** <read-only / least-privilege>
- **Review window (for metric-based signals):**
- **Checks run:** LLM-INV-001 .. LLM-INV-015
- **Not covered (disclosed):** <regions, resources, denied APIs, region-unsupported features>

## Summary

| Severity | Count |
|---|---|
| CRITICAL | |
| HIGH | |
| MEDIUM | |
| LOW | |
| INFO | |

## Access Verdict

- **Can the caller invoke the models it needs?** <yes / no / partial>
- **If denied:** <IAM implicitDeny (LLM-INV-013, customer-fixable) | SCP explicitDeny (LLM-INV-015, escalate to org admin) | model access / marketplace subscription not granted (LLM-INV-014)>
- **SCP note:** <policy name + deny statement if applicable — do NOT prescribe an IAM fix for an SCP deny>

## Findings

For each finding:

### <check-id> — <short title>

- **Severity:** <from catalog>
- **Pillar:** <from catalog>
- **Observed evidence:** <the concrete value read; ARNs masked at the account segment; distinguish "measured zero" from "no datapoints">
- **Why it matters:**
- **Remediation (customer runs it — this review is read-only):** <exact CLI / IaC change>
- **AWS doc:** <citation URL from catalog>

## Disclosed Assumptions & Gaps

- <APIs that returned AccessDenied and the fallback used (e.g. `SimulatePrincipalPolicy` not called → evaluated from policy documents, not simulated), and what that leaves unconfirmed>
- <Organizations membership: not in an Organization (LLM-INV-015 not applicable) / member account, SCPs not readable / readable>
- <features unsupported in the reviewed region>
- <anything inferred vs observed>
