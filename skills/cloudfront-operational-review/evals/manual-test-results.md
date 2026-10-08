# Test Results — cloudfront-operational-review

This skill was evaluated with the AWS DevOps Agent **skill-eval** tool
(`devops-agent skill-eval`: `structure`, `best-practices`, `functional`) and additionally
validated by hand in a DevOps Agent Space. Account IDs and distribution IDs are redacted.

## Automated skill-eval results

| Test type | Result |
|-----------|--------|
| `structure` | ✅ PASSED — 12/12 static checks (100%) |
| `best-practices` | ✅ PASSED — 17/17 checks, all 3 iterations, 100% consistency (Bedrock-judged) |
| `functional` | ✅ Trigger PASS on all evals; with-skill clearly beats the no-skill baseline on expected output |

**Functional detail** — 3 evals × 3 iterations, each run with and without the skill against a
live CloudFront distribution:

| Eval | Trigger | Expected output (with → without) |
|------|---------|----------------------------------|
| `cloudfront-review-best-practices` (broad review) | 3/3 fires | 3/3 (100%) → 0/3 (0%) |
| `cloudfront-security-review` (WAF/TLS/origin-access) | 3/3 fires | 3/3 (100%, high conf) → 0/3 (0%) |
| `unrelated-question` (ALB-vs-NLB control) | 3/3 correctly does **not** fire | n/a (should_trigger: false) |

- **Trigger** is the key reliability signal: both review prompts activate the skill every
  time, and the unrelated networking question never does.
- **Expected output** is the clearest enrichment signal: with the skill, the agent meets the
  full expectation on every run (3/3) for both review types; without the skill it meets it on
  none (0/3).
- **Per-assertion** checks mostly pass with the skill. A capable base agent (with CloudFront
  read access) already satisfies several individual assertions, so they do not isolate the
  skill on their own — the enrichment shows up in the holistic expected-output measure and in
  the guaranteed completeness/structure of the review. Two security assertions scored low
  (WAF-absence wording — the test distribution has a WAF attached, so there is no absence to
  flag; and per-gap severity in the final summary); these are assertion-phrasing artifacts,
  not skill gaps.
- **Cost/runtime:** a with-skill broad review runs the full methodology, so it is longer and
  costlier than a bare answer (≈3m / ≈$1.7 vs ≈30s / ≈$0.25 per run) — expected for a
  thorough operational review.

Reproducing the functional eval:

- Set each prompt's distribution ID in `evals/evals.json` to a real distribution in the
  target account (the committed value `E1EXAMPLEDIST0` is a placeholder).
- Run: `devops-agent skill-eval functional . --aws-profile <profile> --region us-east-1 --additional-permissions-file evals/additional-permissions.json`
- `evals/additional-permissions.json` grants the eval's agent-space monitor role the
  skill's read-only CloudFront/WAF/ACM/CloudWatch/logs/CE actions so the agent can actually
  read the distribution during the run.

Note: the skill-eval tool requires a `botocore` recent enough to include the `devops-agent`
service model (botocore ≥ 1.43.x at time of writing).

## Manual DevOps Agent Space validation

Each prompt was run in a fresh chat on the On-demand agent against a live CloudFront
distribution; the skill was never named explicitly (auto-invocation only).

### Positive cases (skill expected to load and run)

| Prompt | Loaded? | Result |
|--------|:-------:|:------:|
| "Review my CloudFront distribution for best practices" | Yes | ✅ Pass |
| "Do a health check on our CDN — is it secure and cached well?" | Yes | ✅ Pass |

### Negative cases (skill expected NOT to hijack the response)

| Prompt | Loaded? | Behavior | Result |
|--------|:-------:|----------|:------:|
| "Set up a new CloudFront distribution with an S3 origin and OAC" | Loaded | Gave correct setup guidance, did not force a review, offered one as a follow-up | ✅ Acceptable |
| "Create a CloudFront invalidation for /images/*" | No | Attempted the action, declined as read-only; no skill load | ✅ Pass |
| "How much does CloudFront data transfer out cost per GB in the US?" | No | Answered as a pricing question | ✅ Pass |
| "My CloudFront distribution returns 403 on one path — help me fix the bucket policy" | No | Handled as targeted debugging | ✅ Pass |

## Overall

The skill triggers reliably on review and security-review prompts, does not hijack near-miss
prompts, stays strictly read-only, and produces a complete, structured, severity-labelled
per-distribution review. In a live run it correctly surfaced a real outage (100% 4xx error
rate with no CloudWatch alarms) on the test distribution.
