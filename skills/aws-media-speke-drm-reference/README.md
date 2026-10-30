# SPEKE / DRM Reference for AWS Elemental Media Services: AWS DevOps Agent Skill

DRM and content-protection reference covering SPEKE v1/v2, CPIX authoring, multi-key presets and the key-rotation-vs-multi-key trade-off, DRM system IDs, commonEncryptionScheme selection, player CENC/CBCS compatibility, provider selection, and layer-by-layer DRM troubleshooting using public AWS APIs and the operator's own logs.

> **Non-production disclaimer.** This skill is sample code. It is not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions it uses against your organization's security policies.

## Agent Types

On-demand (Chat). Select the relevant agent types in the Operator Web App at upload time, or **Generic** to make the skill available to all agent types.

## Usage

Upload the skill to your Agent Space through the DevOps Agent Operator Web App: zip this directory with `SKILL.md` at the root and select the agent types listed above (see [Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)). The skill triggers on symptom descriptions and questions in its domain. There is no need to name it. Example: "Why does key rotation fail on MediaPackage v2 with SPEKE?"

## Prerequisites

This skill is knowledge-only and requires no AWS API permissions of its own. When its guidance leads the agent to inspect MediaPackage encryption settings, those reads use the permissions of `aws-mediapackage-investigate`.

The troubleshooting runbook also describes optional diagnostics against the SPEKE key provider's API Gateway REST API and its ACM certificate. If you want the agent to run those directly, set `EnableMediaSpekeDrmDiagnostics=true` (default `false`) in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml). `apigateway:GET` is scoped to REST API resources only, so API key values and client certificates stay out of reach.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SpekeDrmApiGatewayReadOnly",
      "Effect": "Allow",
      "Action": [
        "apigateway:GET"
      ],
      "Resource": [
        "arn:aws:apigateway:*::/restapis",
        "arn:aws:apigateway:*::/restapis/*"
      ]
    },
    {
      "Sid": "SpekeDrmCertificateMetadata",
      "Effect": "Allow",
      "Action": [
        "acm:DescribeCertificate",
        "acm:ListCertificates"
      ],
      "Resource": "*"
    }
  ]
}
```

## Reference Files

- `references/cpix-authoring.md`
- `references/player-compatibility.md`
- `references/presets-keys-security.md`
- `references/providers.md`
- `references/troubleshooting.md`
- `references/lookup-tables.md`: metric, status and field tables, loaded by the step that uses them

## Evaluation

`evals/evals.json` holds the functional eval definitions and `evals/eval_queries.json` the trigger queries for the skill evaluation tool. Recorded results live under `evals/structure/`, `evals/best-practices/` and `evals/functional/`.

## What this adds over default agent behavior

A baseline agent knows DRM only at the acronym level. This skill carries the SPEKE v1/v2 contract details that decide real incidents: the DRM system UUID registry (Widevine, PlayReady, FairPlay), why enabling `keyRotationIntervalSeconds` with certain SPEKE v2 configurations fails with `UnprocessableEntityException`, the cbcs-versus-cenc selection matrix for multi-DRM CMAF, key-count limits (up to 5 video + 3 audio keys), and PlayReady SL3000 audio-key downgrade behavior.
