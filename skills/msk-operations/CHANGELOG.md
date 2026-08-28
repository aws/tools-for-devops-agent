# Changelog

## 1.0.2

- Tighten `SKILL.md` frontmatter description for stronger MSK-anchor
  activation and explicit exclusions (CloudFormation / CDK / Terraform /
  other AWS services) to prevent spurious triggering.
- Rewrite the rolling-restart / Kafka-version-upgrade trigger query in
  `evals/eval_queries.json` into realistic operator language.
- Commit Agent Skill Eval outputs (`evals/benchmark.json`,
  `evals/report.json`, `evals/trigger_report.json`). Unified skill report
  passes with Overall Grade B (0.82) — Audit 80/100, Functional 0.75
  (passed, cost PARETO_BETTER at -74.7%), Trigger 1.00.

## 1.0.1

- Add explicit read-only boundary to `SKILL.md` Critical Warnings — mutating
  MSK / CloudWatch commands are recommendations for the operator, not agent
  actions.
- Reframe mutating command references (`update-broker-storage`,
  `create-configuration`, `reboot-broker`) with operator-actor language.
- Guard the `reboot-broker` game-day exercise in
  `references/maintenance-operations.md` with a `UnderReplicatedPartitions = 0`
  precondition and scheduled-window framing.
- Rename README agent-type label "On-demand" → "Chat tasks" to match the
  frontmatter value and the rest of the repo.
- Note `kafka:GetBootstrapBrokers` as the single IAM action not covered by
  `AIDevOpsAgentAccessPolicy`; granted via the new `EnableMskOperations`
  block in `cloudformation/devops-agent-skill-policies.yaml`.

## 1.0.0

- Initial version
