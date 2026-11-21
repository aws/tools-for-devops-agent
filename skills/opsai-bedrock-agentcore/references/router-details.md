# Router details

The full first-read method for the Router rows in `SKILL.md` that need more than one line. Read the
section the row names.

## 1. It is denied even though the role looks right (for example an admin role)

How the caller got its credentials: an assumed-role session can carry a **session policy** passed on `AssumeRole` (`Policy` / `PolicyArns`, visible in the CloudTrail `AssumeRole` event, not in IAM), and the role can have a **permissions boundary** (`iam:GetRole` `PermissionsBoundary`); then effective SCPs via `organizations:ListPoliciesForTarget` / `DescribePolicy`

Load: [Session policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html#policies_session), `references/checks-agentcore.md` (LLM-AC-002)

## 2. An SCP denies `InvokeModel` only when the call goes through an application inference profile, while direct model calls succeed

The SCP `Deny` statement itself (`DescribePolicy`): whether a broad `Resource` wildcard also matches the profile ARN, and whether its `Condition` uses a negated operator (`StringNotEquals`, `StringNotLike`, `ArnNotLike`) on a model-identifying key that is absent or holds a different value for profile requests. A negated operator on an absent key evaluates true, so the deny fires; do not explain it as the SCP failing to cover profile ARNs. Fix: split the deny into narrowly scoped statements per resource type (foundation models, system and application profiles, regions) and test both an approved and a blocked call afterwards

Load: [Condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html), `references/checks-agentcore.md` (LLM-AC-002)

## 3. A call through a gateway returns 403 / `insufficient_scope` or another token error

The gateway's `authorizerConfiguration.customJWTAuthorizer`: `allowedScopes` is checked only if configured (at least one token scope must match), and the same holds for `allowedClients`. If those lists are empty, the gateway is not enforcing scopes or clients, so do not name its scope check as the cause: the likely sources are the target's own authorization (the MCP server or API behind it) or a stale or different token. Ask the operator to mint a fresh token and decode it (`iss`, `aud`, `client_id`, `scope`, `exp`) against the authorizer config, label the cause a hypothesis until that test separates them, and say a support case may be needed to confirm

Load: [Inbound JWT authorizer](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/inbound-jwt-authorizer.html), `references/checks-agentcore.md` (LLM-AC-004)

## 4. A principal in another account cannot invoke, stop sessions on, or use a runtime, gateway or memory; or 429s and active sessions pile up while a cross-account caller stops sessions

For **each action** the caller uses (`InvokeAgentRuntime`, `StopRuntimeSession`, `InvokeGateway`, Memory actions): the caller's identity policy in its own account and the resource-based policy on the resource (`get-resource-policy`; for a runtime both the runtime and the endpoint ARN), plus the error the caller's code got from the call. A missing allow is the cause until read otherwise; do not invent a session-ownership or account-scoping mechanism

Load: `references/checks-agentcore.md` (LLM-AC-014), `references/api-quirks.md` §19

## 5. Agent output changes between turns with the same prompt and config, for example citation or formatting style flips (legacy, Classic)

Treat it as orchestration nondeterminism until a trace shows otherwise: compare `InvokeAgent` traces (`enableTrace`) of a good and a bad turn before naming a mechanism, and say the cause is unconfirmed without them. First lever: pin `temperature` to 0 in the ORCHESTRATION prompt override's `inferenceConfiguration`. Do not blame the knowledge base's citation metadata or the foundation model unless the trace points there

Load: [Advanced prompts](https://docs.aws.amazon.com/bedrock/latest/userguide/advanced-prompts.html), `references/checks-agents.md` (LLM-AGT-005)
