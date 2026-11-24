# Collection Reference
The exact **read-only** API calls this skill uses to collect state, and the fields each contributes, by family. All calls are describe/list/get; none mutate state. Use ReadOnly or least-privilege credentials (production safety).

Naming: the API column names **IAM actions**. Bedrock Agents Classic calls use the `bedrock:` prefix (the CLI and SDK client is `aws bedrock-agent`, which is not an IAM prefix). AgentCore control-plane calls use the `bedrock-agentcore:` prefix (the CLI client is `aws bedrock-agentcore-control`). The data-plane clients `bedrock-runtime`, `bedrock-agent-runtime` and `bedrock-agentcore` are **not** used for collection (they invoke models, agents and runtimes).

**Permissions.** The AWS managed policy `AIDevOpsAgentAccessPolicy` grants the Bedrock Agents Classic, IAM policy, Organizations, EC2, Lambda, CloudWatch and Logs reads below. It grants no `bedrock-agentcore:` action and not `bedrock:GetPrompt`. The `EnableOpsaiBedrockAgentCore` parameter of [devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml) adds them. Without it (or when a call returns AccessDenied) an AgentCore read is a disclosed permission gap, never an absent runtime and never a finding: the checks that depend on it (LLM-AC-001, 003, 004, 008, 009, 012, 013, 014) are reported as not evaluated, and LLM-AC-005, 006, 007, 010 and 011 still run from the `AWS/Bedrock-AgentCore` metrics and the Logs reads. A denied `bedrock:GetPrompt` leaves the `bedrock:ListPrompts` summaries (prompt names, versions, update times) for LLM-AGT-003, with the prompt configuration not evaluated. `iam:SimulatePrincipalPolicy` is in neither and is never called: the agent runtime refuses it even when granted, so the permission checks read the policy documents instead (fallback below). `s3:GetObject` is never called (it returns customer data): a gateway target schema in S3 is checked by its location and owner fields only.

---
## AgentCore (AC)
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock-agentcore:ListAgentRuntimes` / `bedrock-agentcore:GetAgentRuntime` | runtime status, version, `roleArn`, `networkConfiguration`, `protocolConfiguration`, lifecycle settings | LLM-AC-001, 003, 009 |
| `bedrock-agentcore:ListAgentRuntimeEndpoints` / `bedrock-agentcore:ListAgentRuntimeVersions` | which version each endpoint (DEFAULT or named) serves | LLM-AC-009, 014 |
| `bedrock-agentcore:ListGateways` / `bedrock-agentcore:GetGateway` | gateway status, `authorizerConfiguration` (inbound JWT), role ARN | LLM-AC-004, 008 |
| `bedrock-agentcore:ListGatewayTargets` / `bedrock-agentcore:GetGatewayTarget` | target type, endpoint, `credentialProviderConfigurations`, schema location (`S3Configuration.bucketOwnerAccountId`) | LLM-AC-004, 008, api-quirks §15 |
| `bedrock-agentcore:ListMemories` / `bedrock-agentcore:GetMemory` | memory status, strategies and namespaces, event expiry | LLM-AC-012 |
| `bedrock-agentcore:ListBrowsers` / `ListBrowserSessions` / `GetBrowserSession`, `bedrock-agentcore:ListCodeInterpreters` / `ListCodeInterpreterSessions` / `GetCodeInterpreterSession` | session status, age, timeout, `viewPort`, recording configuration | LLM-AC-013 |
| `bedrock-agentcore:GetResourcePolicy` | resource-based policy on a runtime, endpoint, gateway or memory | LLM-AC-014 |
| `ec2:DescribeVpcEndpoints` | VPC endpoints in the runtime's VPC (`ecr.dkr`, `ecr.api`, S3 gateway, `logs`, plus each service the agent code calls) | LLM-AC-003 |
| `cloudwatch:GetMetricData` on namespace `AWS/Bedrock-AgentCore` | runtime, gateway, memory and built-in tool `Invocations`, `Latency`, errors and throttles | LLM-AC-011, 012, 013 |
| `logs:DescribeLogGroups` / `logs:StartQuery` on `/aws/bedrock-agentcore/runtimes/*` | runtime log lines per request (a 429 with no runtime log line was rejected before the container ran) | LLM-AC-007, 011 |
| AgentCore Observability (spans in the `aws/spans` log group, read with `logs:StartQuery`) | telemetry enabled, span coverage per stage, session IDs | LLM-AC-005, 006, 010 |

## Agents & action groups (AGT), Bedrock Agents Classic
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListAgents` | agent ids, status | LLM-AGT-004, 011 |
| `bedrock:GetAgent` | `guardrailConfiguration`, `foundationModel`, `memoryConfiguration`, prompt override config | LLM-AGT-001, 003, 008, 009 |
| `bedrock:ListAgentActionGroups` / `bedrock:GetAgentActionGroup` | action group executor (Lambda ARN), API schema, parent action group signatures (code interpreter) | LLM-AGT-002, 006 |
| `bedrock:ListAgentAliases` / `bedrock:GetAgentAlias` | alias ids, routing config, version pinning | LLM-AGT-007 |
| `lambda:GetPolicy` / `iam:GetRolePolicy` for the action-group Lambda | execution-role permission scope | LLM-AGT-002 |
| `bedrock:ListPrompts` / `bedrock:GetPrompt` | prompt versions in Prompt Management (`GetPrompt` is not in the managed policy) | LLM-AGT-003 |
| `cloudwatch:GetMetricData` on `AWS/Bedrock/Agents` | `InvocationCount` and related agent metrics over the window | LLM-AGT-004 |

## Access control (AC permission checks)
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `iam:ListRolePolicies` / `iam:GetRolePolicy`, `iam:ListAttachedRolePolicies` / `iam:GetPolicy` / `iam:GetPolicyVersion`, `iam:GetRole` (permissions boundary) | the runtime role's identity policies, read action by action | LLM-AC-001 |
| `organizations:ListPoliciesForTarget` / `organizations:DescribePolicy` | SCPs that apply to the account | LLM-AC-002 |
| `cloudtrail:LookupEvents` (`EventName=AssumeRole`) | how the denied caller got its credentials (session policy) | LLM-AC-002 |

**Fallback for `iam:SimulatePrincipalPolicy`** (never called: the DevOps Agent runtime refuses it even when granted): read the role's inline and attached policies, its permissions boundary (`iam:GetRole`, then `iam:GetPolicy` / `iam:GetPolicyVersion`) and the SCPs above, evaluate each required action against them statically, and label the verdict "evaluated from policy documents, not simulated". Say what static reading cannot see: session policies, resource-based policies that were not read, and SCPs when the account cannot read Organizations.
