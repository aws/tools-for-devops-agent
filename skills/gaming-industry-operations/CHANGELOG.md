# Changelog

All notable changes to the `gaming-industry-operations` skill are documented here.

## [1.0.0] - 2026-11-05

### Added

- Initial release. Games-industry operations skill grounded in the AWS
  Well-Architected Games Industry Lens (publication date December 9, 2025).
- **Workflow A — games workload review (Chat):** read-only, graded assessment of a
  game workload against all **78 lens best practices** across the six pillars
  (12 GAMEOPS, 25 GAMESEC, 6 GAMEREL, 24 GAMEPERF, 7 GAMECOST, 4 GAMESUS) with
  PASS / FAIL / N/A verdicts, the lens's own risk levels, Critical promotion rules
  tied to the player critical path and upcoming events, a severity-ordered action
  plan, and a launch / in-game event readiness checklist when a date is known.
- **Workflow B — games-aware incident triage and RCA:** player-impact framing,
  failure-domain separation (AWS impairment vs studio change vs demand/external) and
  a symptom → cause → evidence map for login storms, matchmaking failures and
  placement capacity, mid-match disconnects (Spot interruptions, unprotected
  scale-in, EC2 network allowances), regional lag, launch meltdowns, cheating and
  account-takeover waves, and post-event cost spikes. Emits a fixed "Games context"
  block and cites the lens best practice for prevention.
- `references/games-lens-best-practices.md` — every lens check by ID with risk
  level, read-only verification calls, PASS criteria and companion skills.
- `references/architecture-scenarios.md` — lens vocabulary, the five scenario
  families (real-time game hosting incl. GameLift serverless and multi-Region/hybrid
  references, container and serverless backends, cloud game development CI/CD and
  workstations, game analytics pipeline), messaging patterns and hosting trade-offs.
- `references/incident-symptom-map.md` — seven symptom families with candidate
  causes ordered by frequency, the CloudWatch metrics and API reads that confirm or
  rule them out, and an evidence-collection order for games RCAs.
- `references/discovery.md` — ordered read-only discovery (D0–D5) and applicability
  gates (no dedicated game servers, denied reads, third-party tooling, CGD-only).
- `references/report-format.md` — the review report contract (§1–§7) and the
  incident "Games context" block.
- `evals/evals.json` — positive scenarios for full review, launch readiness,
  matchmaking audit, security-pillar scope, incident RCA (disconnects, login storm,
  matchmaking capacity) and a narrow fast-path question, plus negative cases for a
  streaming/OTT review, a non-game Well-Architected review and game-client code.

### Design decisions

- **Canonical-checklist fidelity.** The agent grades the lens's published IDs, never
  a synthesized subset, and prints all 78 rows in the scorecards so a scoped review
  shows what was not examined.
- **Evidence-first with "present but unprepared = FAIL".** A fleet or table that
  exists but cannot reach the stated peak is a capacity risk, not a blank.
- **Reuse-first.** Quotas, Health, EKS/ECS, RDS and S3 depth come from companion
  skills when installed; otherwise reduced-depth discovery with the gap named.
- **No custom IAM policy.** All reads used (`gamelift:Describe*/List*`,
  `globalaccelerator`, `cognito-idp`, `cognito-identity`, `shield`, `wafv2`,
  `cloudfront`, `dynamodb`, `autoscaling`, `cloudwatch`, `ce`, …) are already granted
  by the `AIDevOpsAgentAccessPolicy` managed policy; reads that may be denied
  (Organizations, Control Tower, Compute Optimizer) degrade to N/A with reason.
