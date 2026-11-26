# Changelog

## 1.0.1
- README heading is now "OpsAI Capacity and Cost" instead of the folder name; added an explanatory README introduction, which the catalog card shows, and a rewritten `metadata.summary`; the `llms.txt` entry matches.
- `metadata.author` is now the `aws/aws-support` team.

## 1.0.0
- Description: covers how-to questions (one run skipped the skill for `quota-lookup-by-code`).
- Evals: the 12-digit account-ID regex ignores the documentation example IDs `123456789012` and `111122223333`.
- `related-skills.md` is a markdown link and is listed under References with its load condition (best-practices BP-05).
- Evals: check-id assertions are dropped from the four questions that name no account resource.

- PR #268 review item 1 (IAM reads and action names):
  - IAM: `EnableOpsaiCapacityCost` also grants the `bedrock-agentcore` runtime and gateway reads used by the AgentCore fallback in `references/related-skills.md`; the access-key fallback lists IAM users only (`iam:ListAccessKeys` is not called).
- Initial release in this repository.
- Explains and reduces Amazon Bedrock spend and checks capacity: pricing tiers, Provisioned Throughput, quotas and token drift.
- Renamed from the earlier capacity and cost skill.
- Works on its own: sibling skills are optional, with a fallback check per area in `references/related-skills.md`.
