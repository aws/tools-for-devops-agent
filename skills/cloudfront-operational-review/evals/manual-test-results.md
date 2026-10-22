# Test Results — cloudfront-operational-review

This skill was evaluated with the AWS DevOps Agent **skill-eval** tool
(`devops-agent skill-eval`: `structure`, `best-practices`, `functional`) and additionally
validated by hand in a DevOps Agent Space. Account IDs and distribution IDs are redacted.

## Automated skill-eval results

| Test type | Result |
|-----------|--------|
| `structure` | ✅ PASSED — 12/12 static checks (100%) |
| `best-practices` | ✅ PASSED — 17/17 checks, all 3 iterations, 100% consistency (Bedrock-judged) |
| `functional` | ✅ Trigger 3/3 on every positive eval, negative control never fires; with-skill meets or beats the no-skill baseline on every graded run |

**Functional detail** — run v8, same skill content as committed. 3 iterations per eval,
each run with and without the skill, 0 failed runs. The `det-*` evals pass captured API
responses in the prompt and tell the agent not to call AWS, so their inputs are fixed and
repeatable.

| Eval | Trigger | Expected output (with → without) | Skill-specific assertion (with → without) |
|------|---------|----------------------------------|-------------------------------------------|
| `cloudfront-review-best-practices` (broad review) | 3/3 | 1/3 → 0/3 (graded: 1/1 → 0/3) ¹ | — |
| `cloudfront-security-review` (WAF/TLS/origin access) | 3/3 | 2/3 → 3/3 (graded: 2/2 → 3/3) ¹ | — |
| `det-waf-and-alarm-coverage` (WAF on/off, metric-math and composite alarms, additional metrics off) | 3/3 | 3/3 → 2/3 | metric-math alarm counted: 3/3 → 1/3 |
| `det-standard-logging-v2` (v2 delivery, legacy block disabled) | 3/3 | 3/3 → 3/3 | — |
| `det-origin-evidence` (S3 website vs OAC, partial `AccessDenied`, VPC origin evidence unavailable) | 3/3 | 3/3 → 2/3 | denied checks labeled UNKNOWN: 3/3 → 0/3 |
| `det-flat-rate-cost` (flat-rate vs pay-as-you-go, no resource-level cost data) | 3/3 | 3/3 → 3/3 | cost kept account-level: 3/3 → 1/3 |
| `unrelated-question` (ALB-vs-NLB control) | 3/3 correctly does **not** fire | n/a | n/a |

¹ Three with-skill runs (broad review iterations 1–2, security review iteration 3) wrote the
complete review and then ended the turn with the agent's `ask_user` follow-up prompt
("Want me to open an investigation into that error burst…?"). A turn that ends that way emits
no `FinalResponse` event. The tool grades only `FinalResponse`, so it scored those runs as
failed without judging their content. The tool's assertion grader treats the same
condition as errored, not failed. No-skill runs hit the same thing in earlier eval rounds.
Every with-skill live run that produced a `FinalResponse` passed.

- **Trigger timing.** The stock tool opens the chat about one second after uploading the
  skill, which can be before the agent's skill catalog includes it. Earlier runs scored
  1–2/3 on trigger with an unchanged description for that reason: in follow-up questions
  the agent said in 9 of 10 non-loading chats that the skill wasn't in its list, and a
  fresh chat in the same spaces later loaded it 6/6. v8 used a local patch to the tool that
  waits 90 s after upload before opening the chat. In a probe, the skill was in the
  catalog within 30 s of upload in 3/3 spaces. The timing issue has been reported to the
  tool maintainers.
- **Where the skill adds value.** A capable base agent already makes many of these decisions
  when the evidence is handed to it, so several deterministic assertions pass without the
  skill too. The skill consistently adds explicit UNKNOWN labeling for denied checks,
  counts metric-math alarms as coverage, keeps cost at account level when there's no
  resource-level data, and produces a prioritized review that the no-skill agent didn't
  (broad review content: 0/3 without the skill).
- `det-waf-and-alarm-coverage` sometimes answers without tools because all its data is in the
  prompt.
- **Cost/runtime:** a with-skill live review runs the full methodology, so it costs more than
  a bare answer. Broad review: about 5–8 min / $2.50–$4.05 with the skill vs about 1 min /
  $0.50–$0.70 without. Security review: about 2.5 min / $1.20–$1.40 vs under 1 min / $0.30–$0.50.

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
