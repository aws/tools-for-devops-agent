# Test Results — cloudfront-operational-review

This skill was evaluated with the AWS DevOps Agent **skill-eval** tool
(`devops-agent skill-eval`: `structure`, `best-practices`, `functional`) and additionally
validated by hand in a DevOps Agent Space. Account IDs and distribution IDs are redacted.

## Automated skill-eval results

| Test type | Result |
|-----------|--------|
| `structure` | ✅ PASSED — 12/12 static checks (100%) on this revision |
| `best-practices` | ✅ PASSED — 17/17 checks, all 3 iterations, 100% consistency (Bedrock-judged) on this revision |
| `functional` | v9 (this revision, five `det-*` evals): trigger 15/15, expected output 15/15 with vs 11/15 without, with 90 s post-upload delay (patched tool). v8 (previous revision, all evals): trigger 18/18 on positive evals and 0/3 on the negative control, with 90 s post-upload delay (patched tool). |

## v9 results: targeted `det-*` rerun (this revision)

Run v9, on this revision. Only the five `det-*` evals ran, including the new
`det-origin-header-redaction`. Each ran 3 iterations with the skill and 3 without, with 90 s
post-upload delay (patched tool), and 0 runs failed. The live prompts and the
`unrelated-question` control were not rerun; their figures are from v8 below. Every cell is
n=3. Trigger applies only to with-skill runs. Assertions that scored 3/3 → 3/3 are omitted.

| Eval | Trigger | Expected output (with → without) | Skill-specific assertions (with → without) |
|------|---------|----------------------------------|--------------------------------------------|
| `det-waf-and-alarm-coverage` | 3/3 | 3/3 → 2/3 | metric-math and composite counted as coverage: 3/3 → 0/3 ²; missing WAF rated HIGH: 3/3 → 0/3 |
| `det-standard-logging-v2` | 3/3 | 3/3 → 3/3 | — (all 3 assertions 3/3 → 3/3) |
| `det-origin-evidence` | 3/3 | 3/3 → 3/3 | `reports` labeled UNKNOWN (anchored regex): 3/3 → 1/3; VPC origin labeled UNKNOWN (anchored regex): 3/3 → 1/3; `site` website endpoint rated INFO: 3/3 → 0/3; both denied checks rated UNKNOWN: 3/3 → 0/3 |
| `det-flat-rate-cost` | 3/3 | 3/3 → 3/3 | no per-GB or per-request savings for the flat-rate distribution: 3/3 → 2/3; no per-distribution dollars: 3/3 → 3/3 |
| `det-origin-header-redaction` | 3/3 | 3/3 → 0/3 ⁴ | header value and WAF match string absent (regex): 3/3 → 1/3 |

- The severity assertions failed without the skill on substance, not wording. In
  `det-origin-evidence` the no-skill agent rated `site` Medium or Medium–High in 2 of 3 runs,
  and rated `reports` High in 2 and "highest priority" in the third, although its exposure
  could not be checked. In `det-waf-and-alarm-coverage` no no-skill run gave the missing web
  ACL a severity.
- The anchored regexes matched origin-specific lines in every with-skill run, for example a
  "`reports` bucket public-access status | UNKNOWN" row, and did not match report-template
  text. The no-skill matches were "`reports` bucket policy / public access block state —
  unknown" and an "| api | … | Gap, unknown" table cell.
- In `det-waf-and-alarm-coverage`, all three no-skill runs again doubted the composite alarm,
  because its child alarms appear only in the fixture's `Note`. The tool's pairwise quality
  judge preferred the no-skill output on this eval in 2 of 2 evaluated pairs, for the same
  reason. See "How to read the two graders".
- Small samples vary between runs. "No per-distribution dollars" without the skill went from
  1/3 in v8 to 3/3 in v9, and the alarm-coverage assertion from 1/3 to 0/3.

⁴ Two no-skill runs reproduced both values verbatim. The third did not, and the regex passed
it. The expected-output judge still failed that run, reading a sentence that called the values
"static, plaintext" as a reproduction. The regex count, 3/3 → 1/3, is the accurate measure.

## v8 results (previous revision)

Run v8, on the revision before this one. 3 iterations per eval, each run with and without the
skill, 0 failed runs. The `det-*` evals pass captured API responses in the prompt and tell the
agent not to call AWS, so their inputs are fixed and repeatable. All trigger figures are with
90 s post-upload delay (patched tool).

| Eval | Trigger | Expected output (with → without) | Skill-specific assertion (with → without) |
|------|---------|----------------------------------|-------------------------------------------|
| `cloudfront-review-best-practices` (broad review) | 3/3 | with: 1 pass, 2 ungraded ¹ → without: 0/3 | — |
| `cloudfront-security-review` (WAF/TLS/origin access) | 3/3 | with: 2 pass, 1 ungraded ¹ → without: 3/3 | — |
| `det-waf-and-alarm-coverage` (WAF on/off, metric-math and composite alarms, additional metrics off) | 3/3 | 3/3 → 2/3 | metric-math and composite counted as coverage: 3/3 → 1/3 ² |
| `det-standard-logging-v2` (v2 delivery, legacy block disabled) | 3/3 | 3/3 → 3/3 | — |
| `det-origin-evidence` (S3 website vs OAC, partial `AccessDenied`, VPC origin evidence unavailable) | 3/3 | 3/3 → 2/3 | v8 token-count regex: 3/3 → 0/3. Re-scored on the same outputs with this revision's anchored patterns: `reports` labeled UNKNOWN 3/3 → 1/3; VPC origin labeled UNKNOWN 3/3 → 0/3 ³ |
| `det-flat-rate-cost` (flat-rate vs pay-as-you-go, no resource-level cost data) | 3/3 | 3/3 → 3/3 | no per-distribution dollars: 3/3 → 1/3 ² |
| `unrelated-question` (ALB-vs-NLB control) | 0/3 (correctly not loaded) | n/a | n/a |

¹ Three with-skill runs (broad review iterations 1–2, security review iteration 3) wrote the
complete review and then ended the turn with an `ask_user` follow-up question. A turn that
ends that way emits no `FinalResponse` event, and the tool grades only `FinalResponse`, so
those runs were not judged. No no-skill run in v8 ended that way. Step 12 now tells the agent
to end the turn with the report and list follow-ups as a closing line.

² See "How to read the two graders".

³ The v8 regex `(?i)unknown|manual verification` with `min_count: 2` also matched the report
template's own text ("UNKNOWN <n>", "Limitations and Unknowns"), so it partly measured template
use. This revision anchors each pattern to the denied origin's identifiers and requires the
label on the same line.

### How to read the two graders

The tool grades each run twice. The expected-output judge gives one holistic verdict against
`expected_output` and credits the right conclusion in any wording. The assertions are graded
one by one and are stricter. The no-skill agent often reached the right conclusion in hedged
prose, which the judge accepted and the assertions did not. Examples from v8, n=3 per cell:

- `det-origin-evidence`: no-skill responses described the denied checks as "unverified" or
  "can't be confirmed" without labeling them; the judge passed 2 of 3. The failed no-skill run
  rated `site` HIGH and called `reports` "almost certainly" public.
- `det-waf-and-alarm-coverage`: the two failing no-skill runs doubted the composite alarm
  because its child alarms appear only in the fixture's `Note`, not in `MetricAlarms`. That doubt
  is defensible, so this result shows the skill accepting the `Note` as evidence more than a
  gap in coverage logic.
- `det-flat-rate-cost`: two no-skill runs attributed most of the account total to the
  pay-as-you-go distribution while labeling it an inference. The judge accepted the hedge; the
  assertion did not.
- Broad review: every no-skill failure was "no CloudWatch metric findings" (it reviewed
  configuration only). No-skill passed 14/15 broad-review assertions, so the measured difference
  there is the metrics pass.
- Security review: the with-skill runs reported the live distribution's web ACL as attached
  (INFO), and the v8 assertion expected an absence to be called out, so they failed it 0/2.
  This revision rewords that assertion to "reports whether a web ACL is associated".

### Notes

- **Trigger timing.** The stock tool opens the chat about one second after uploading the
  skill, which can be before the agent's skill catalog includes it. Earlier stock-tool runs
  scored 1–2/3 on trigger for several evals with an unchanged description: in follow-up
  questions the agent said in 9 of 10 non-loading chats that the skill wasn't in its list, and
  a fresh chat in the same spaces later loaded it 6/6. v8 and v9 used a local patch that waits
  until the skill is listed in the space and then 90 s more before opening the chat. In a probe, the skill was in the catalog within 30 s of upload in 3/3 spaces.
  The stock tool may report lower trigger rates. The timing issue has been reported to the tool
  maintainers.
- `det-waf-and-alarm-coverage` sometimes answers without tools because all its data is in the
  prompt.
- **Cost/runtime:** a with-skill live review runs the full methodology, so it costs more than
  a bare answer. Broad review: about 5–8 min / $2.50–$4.05 with the skill vs about 1 min /
  $0.50–$0.70 without. Security review: about 2.5 min / $1.20–$1.40 vs under 1 min / $0.30–$0.50.

Reproducing the functional eval:

- Set each live prompt's distribution ID in `evals/evals.json` to a real distribution in the
  target account (the committed value `E1EXAMPLEDIST0` is a placeholder).
- Run: `devops-agent skill-eval functional . --aws-profile <profile> --region us-east-1 --additional-permissions-file evals/additional-permissions.json`
- `evals/additional-permissions.json` grants the eval's agent-space monitor role the
  skill's read-only CloudFront/WAF/ACM/CloudWatch/logs/S3/CE actions so the agent can actually
  read the distribution during the run.

Note: the skill-eval tool requires a `botocore` recent enough to include the `devops-agent`
service model (botocore ≥ 1.43.x at time of writing).

## Manual DevOps Agent Space validation

Each prompt was run in a fresh chat in DevOps Agent Chat (skill uploaded for the Chat tasks
agent type) against a live CloudFront distribution; the skill was never named explicitly
(auto-invocation only).

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

Manual: the skill loaded on 2/2 positive prompts; on 4 near-miss prompts it loaded once and
gave setup guidance without forcing a review. In a live run the
review reported a 100% 4xx error rate with no CloudWatch alarms on the test distribution.
