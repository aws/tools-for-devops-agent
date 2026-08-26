# Read-Only IAM Tiers

The skill degrades gracefully across three read-only permission tiers. It detects which tier is
present, runs the matching checks, and reports the exact policy to attach to unlock the rest.

**Who applies these:** the customer attaches a scoped inline policy to the DevOps Agent role in
their own account. The shared managed access policy is cross-tenant and must **not** be modified
per-skill, so Tier 2 and Tier 3 are customer-applied and opt-in. All permissions are read-only; the
skill never mutates IAM.

---

## Tier 1 — Standard (telemetry-arrival verification, host-agnostic)

Typically already available to the DevOps Agent role.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AgentCoreObsTier1",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:FilterLogEvents",
        "logs:GetLogEvents",
        "logs:StartQuery",
        "logs:GetQueryResults",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "cloudwatch:DescribeAlarms"
      ],
      "Resource": "*"
    }
  ]
}
```

## Tier 2 — Runtime config verification

Unlocks Transaction Search state, runtime tracing/env, Memory/Gateway delivery, X-Ray resource policy.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AgentCoreObsTier2",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:GetAgentRuntime",
        "bedrock-agentcore:ListAgentRuntimes",
        "xray:GetTraceSegmentDestination",
        "logs:DescribeDeliveries",
        "logs:DescribeDeliverySources",
        "logs:DescribeDeliveryDestinations",
        "logs:DescribeResourcePolicies"
      ],
      "Resource": "*"
    }
  ]
}
```

> `bedrock-agentcore` control-plane action names may vary by resource (runtime, memory, gateway).
> Verify exact action names against the current AgentCore API reference before applying; keep them
> read-only (`Get*` / `List*` / `Describe*` only).

## Tier 3 — Non-runtime host config verification

Unlocks host-side config checks for Lambda / ECS / EKS.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AgentCoreObsTier3",
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunctionConfiguration",
        "ecs:DescribeTaskDefinition",
        "ecs:DescribeServices",
        "ecs:ListTasks",
        "eks:DescribeCluster"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Provider connectivity

| Provider | Needed for | Tier |
|---|---|---|
| CloudWatch Logs + Metrics | telemetry-arrival verification (required baseline) | 1 |
| AWS X-Ray | Transaction Search state, traces delivery | 2 |
| AgentCore control plane | runtime auto-detection, runtime config | 2 |
| Lambda / ECS / EKS | non-runtime host config | 3 |

Source-repository file read (GitHub/GitLab) is **not** a dependency — code-level instrumentation
checks are prescriptive.

## Scoping note

`Resource: "*"` is shown for brevity because these are read/describe actions. Where the customer
prefers tighter scoping, restrict `logs:*` to the AgentCore log-group ARNs
(`/aws/bedrock-agentcore/*`, `/aws/vendedlogs/bedrock-agentcore/*`) and the resource actions to the
relevant function/cluster/task-definition ARNs.
