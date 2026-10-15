# Changelog

## 1.0.0 (pre-release)

- Agent type: Incident RCA only. Both modes run as investigations, including a user-requested threat hunt with no alarm; the investigation records (symptoms, causes, one root cause, linked observations, gaps) are the deliverable, and Mode B also writes a threat-hunt report artifact from `assets/threat-hunt-report-template.md`
- Mode A, access-denied triage: WAF rule-out (Block, Challenge, CAPTCHA, Anti-DDoS, Shield Advanced automatic mitigation), rule and label attribution, false-positive verdicts, narrowly scoped advisory fixes
- Mode B, threat hunting: fast path and funnel, detected-but-not-blocked findings, attacker-residue check, a required Known automation section with per-client lines for Count and rate rules and for sensitive-endpoint bursts (Q-13b), path-scoped rate-rule fixes
- Backends: CloudWatch Logs Insights and Amazon Athena query libraries, with a metrics and sampled-requests fallback when logs are unavailable
- AWS DevOps Agent orchestration: one log-analysis subagent for querying, one change subagent for CloudTrail (minimum prompt: us-east-1 plus the origin Region, per-name lookups, then a capped catch-all write-event sweep around symptom onset, reported as "incomplete (sweep capped)" when capped), and the skill preloaded on every mitigation handoff, origin-side ones included
- Output rules: counts copied from the subagent table, "none found" scoped per category and never evidence, no "flood" or "abusive" wording for known automation, payloads reported as class and count only, closing "Ruled out:" line
- Read-only and advisory: no changes are applied, and no recommendation removes or loosens WAF protection as a side effect
