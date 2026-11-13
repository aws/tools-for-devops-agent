# Media Spec Reference (AV1, SCTE-35, SCTE-104, MediaPackage v2 headers): AWS DevOps Agent Skill

A lookup layer for four streaming-media standards that are referenced far more often than they are remembered correctly: the AV1 codec (profiles/tiers/levels), SCTE-35 (splice commands, the full segmentation_type_id and UPID tables), SCTE-104 (opIDs, request types, result codes), and MediaPackage v2 response headers including CMSD fields. It explains standards; it does not inspect files or streams.

> **Non-production disclaimer.** This skill is sample code. It is not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions it uses against your organization's security policies.

## Agent Types

On-demand (Chat). Select the relevant agent types in the Operator Web App at upload time, or **Generic** to make the skill available to all agent types.

## Usage

Upload the skill to your Agent Space through the DevOps Agent Operator Web App: zip this directory with `SKILL.md` at the root and select the agent types listed above (see [Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)). The skill triggers on symptom descriptions and questions in its domain. There is no need to name it. Example: "What does SCTE-35 segmentation type 0x30 mean?"

## Prerequisites

This skill is knowledge-only and requires no AWS API permissions. The shared IAM template lists it under `EnableMediaSpecReference` so the skill list stays complete; toggling that parameter changes nothing in the stack.

## Reference Files

- `references/av1-reference.md`
- `references/mediapackage-v2-response-headers.md`
- `references/scte104-reference.md`
- `references/scte35-reference.md`

## Evaluation

`evals/evals.json` holds the functional eval definitions and `evals/eval_queries.json` the trigger queries for the skill evaluation tool. Recorded results live under `evals/structure/`, `evals/best-practices/` and `evals/functional/`.

## What this adds over default agent behavior

A baseline agent answers media-standards questions from general knowledge and often hedges or errs on identifiers. This skill provides authoritative lookup tables: SCTE-35 segmentation type IDs (e.g., 0x30 = Provider Advertisement Start) and SCTE-104 operation IDs, codec profile/level hierarchies (AVC, HEVC, AV1 Main ⊂ High ⊂ Professional), container and timing constants, answered exactly, offline, without a web search.
