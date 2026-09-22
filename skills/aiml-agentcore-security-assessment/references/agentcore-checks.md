# Amazon Bedrock AgentCore Security Checks

This reference lists the Amazon Bedrock AgentCore security checks. Each check is
read-only (list/describe/get only) and reports `Passed`, `Failed`, or `N/A`.
Amazon Bedrock AgentCore is not available in every Region; emit regional checks
as `N/A` where the service is unavailable.

Use the **`bedrock-agentcore`** IAM action prefix (the `-control` suffix is only
the SDK client name).

Every check carries a **Verifiability** classification the report engine must
honor (see `SKILL.md` → "Verify vs. prescribe"):

- **Verifiable** — a read-only call returns the exact configuration; deterministic.
- **Heuristic** — readable but inferred; apply the stated rule, cite the evidence,
  and emit `N/A` (not `Passed`) when evidence is ambiguous or the read is denied.
- **Prescribe-only** — not provable read-only under the DevOps Agent; emit `N/A`
  with remediation in `Resolution`. **Never `Passed`/`Failed`.**

**Classification summary:** Verifiable — AC-01, 05, 06, 07, 08, 09, 11, 12, 13,
14, 15, 16, 17 (13). Heuristic — AC-02, AC-10 (2). Prescribe-only — AC-03 (1).
Global (emit once per account, `Region: "Global"`): AC-02, AC-03, AC-09.

> **AC-04 (Observability) is intentionally excluded.** AgentCore observability is
> owned by the `agentcore-observability-setup` skill. Do not evaluate or emit
> AC-04 here; if a user asks about AgentCore tracing/telemetry, point them to that
> skill.

---

### AC-01: Runtime Amazon VPC Configuration
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListAgentRuntimes`, `bedrock-agentcore:GetAgentRuntime`, `ec2:DescribeSubnets`, `ec2:DescribeRouteTables`
- **Evaluate:** `Failed` when an agent runtime lacks a private VPC configuration (public subnets or no VPC); `Passed` when runtimes use private subnets with correct routing; `N/A` when no runtimes exist or AgentCore is unavailable in the region.
- **Resolution:** Configure agent runtimes to run in a VPC using private subnets with correct route tables.
- **Reference:** https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/security/agentcore-vpc.html

### AC-02: AWS IAM Full Access
- **Severity:** High
- **Scope:** Global
- **Verifiability:** Heuristic
- **Read-only APIs:** `iam:ListRoles`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:GetRolePolicy`
- **Evaluate:** `Failed` when an IAM role attaches `BedrockAgentCoreFullAccess` or a wildcard `bedrock-agentcore:*` grant (cite role + policy); `Passed` when inspected roles use scoped AgentCore permissions; `N/A` when no AgentCore roles are found or reads are denied.
- **Resolution:** Replace full-access and wildcard AgentCore grants with least-privilege scoped policies.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/security-iam-awsmanpol.html

### AC-03: Stale Access
- **Severity:** Low
- **Scope:** Global
- **Verifiability:** Prescribe-only
- **Read-only APIs:** *(none reachable)* — determination requires `iam:GenerateServiceLastAccessedDetails` then `iam:GetServiceLastAccessedDetails`. `GenerateServiceLastAccessedDetails` is a `Generate*` verb blocked by the DevOps Agent read-only guardrail.
- **Evaluate:** **Always `N/A`** under the DevOps Agent, with `Finding_Details` stating the platform read-only guardrail blocks the required analysis call. **Never emit `Passed` or `Failed`.** Do not call `GenerateServiceLastAccessedDetails`.
- **Resolution:** Out of band (e.g. IAM console → Access Advisor), review last-accessed data for AgentCore-permissioned principals and remove permissions unused for 60+ days.
- **Reference:** https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_last-accessed.html

### AC-05: Amazon ECR Repository Encryption
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `ecr:DescribeRepositories`
- **Evaluate:** `Failed` when an ECR repository backing AgentCore relies on default AES256 rather than AWS KMS encryption; `Passed` when repositories use KMS encryption; `N/A` when no repositories exist or AgentCore is unavailable in the region.
- **Resolution:** Configure ECR repositories to use AWS KMS encryption at rest.
- **Reference:** https://docs.aws.amazon.com/AmazonECR/latest/userguide/encryption-at-rest.html

### AC-06: Browser Tool Recording
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListAgentRuntimes`, `bedrock-agentcore:GetAgentRuntime`
- **Evaluate:** `Failed` when a runtime lacks storage configuration for browser-tool session recordings and artifacts; `Passed` when storage is configured; `N/A` when no runtimes exist or AgentCore is unavailable in the region.
- **Resolution:** Configure S3 storage for browser-tool session recordings and artifacts.
- **Reference:** https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/builtin-tools/quickstart-browser.html

### AC-07: Memory Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListMemories`, `bedrock-agentcore:GetMemory`
- **Evaluate:** `Failed` when agent memory is not encrypted with an AWS KMS key; `Passed` when memory uses KMS encryption; `N/A` when no memories exist or AgentCore is unavailable in the region.
- **Resolution:** Configure agent memory to use AWS KMS encryption.
- **Reference:** https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/memory/quickstart.html

### AC-08: Amazon VPC Endpoints
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListAgentRuntimes`, `ec2:DescribeVpcs`, `ec2:DescribeVpcEndpoints`
- **Evaluate:** `Failed` when VPC-attached runtimes lack VPC endpoints for AgentCore services; `Passed` when the required endpoints exist; `N/A` when no runtimes or VPCs exist or AgentCore is unavailable in the region.
- **Resolution:** Create Amazon VPC endpoints for the AgentCore services used by runtimes.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc.html

### AC-09: Service-Linked Role
- **Severity:** Medium
- **Scope:** Global
- **Verifiability:** Verifiable
- **Read-only APIs:** `iam:GetRole`
- **Evaluate:** `Failed` when the AgentCore service-linked role does not exist; `Passed` when it is present; `N/A` when AgentCore is unavailable.
- **Resolution:** Create the AgentCore service-linked role for the account.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-vpc.html

### AC-10: Resource-Based Policies
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `bedrock-agentcore:ListAgentRuntimes`, `bedrock-agentcore:ListGateways`, `bedrock-agentcore:GetResourcePolicy`, `bedrock-agentcore:GetGateway`
- **Evaluate:** `Failed` when a runtime or gateway resource-based policy is overly permissive (wildcard `Principal` or `Action` without scoping conditions — cite the resource + statement); `Passed` when policies are appropriately scoped; `N/A` when no runtimes or gateways exist, AgentCore is unavailable, or reads are denied.
- **Resolution:** Restrict runtime and gateway resource-based policies to least-privilege principals.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/security_iam_service-with-iam.html

### AC-11: Policy Engine Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListPolicyEngines`, `bedrock-agentcore:GetPolicyEngine`
- **Evaluate:** `Failed` when a policy engine is not encrypted with an AWS KMS key; `Passed` when it uses KMS encryption; `N/A` when no policy engines exist or AgentCore is unavailable in the region.
- **Resolution:** Configure policy engines to use AWS KMS encryption.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-encryption.html

### AC-12: Gateway Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListGateways`, `bedrock-agentcore:GetGateway`
- **Evaluate:** `Failed` when a gateway is not encrypted with an AWS KMS key; `Passed` when it uses KMS encryption; `N/A` when no gateways exist or AgentCore is unavailable in the region.
- **Resolution:** Configure gateways to use AWS KMS encryption at rest.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/data-encryption.html

### AC-13: Gateway Configuration
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListGateways`, `bedrock-agentcore:GetGateway`
- **Evaluate:** `Failed` when a gateway lacks a secure baseline configuration (no inbound authorization configured at all); `Passed` when the gateway has a secure configuration; `N/A` when no gateways exist or AgentCore is unavailable in the region. (Authorizer *strength* is assessed by AC-14.)
- **Resolution:** Enable inbound authorization and a secure configuration on AgentCore gateways.
- **Reference:** https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/gateway/quickstart.html

### AC-14: Gateway Inbound Authorization
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListGateways`, `bedrock-agentcore:GetGateway`
- **Evaluate:** `Failed` for gateways with a missing, unknown, or `NONE` authorizer. `Passed` for `AWS_IAM` and `CUSTOM_JWT`. `AUTHENTICATE_ONLY` passes only when a policy engine is attached in `ENFORCE` mode; otherwise `Failed`. `N/A` when AgentCore is unavailable or no gateways exist.
- **Resolution:** Configure `AWS_IAM` or `CUSTOM_JWT` inbound authorization on every AgentCore gateway.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-security.html

### AC-15: Gateway Tool Policy Enforcement
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListGateways`, `bedrock-agentcore:GetGateway`
- **Evaluate:** `Failed` for gateways without a policy engine or whose policy engine mode is not `ENFORCE`. `Passed` when a policy engine is attached in `ENFORCE` mode. `N/A` when AgentCore is unavailable or no gateways exist.
- **Resolution:** Attach an AgentCore policy engine in `ENFORCE` mode to gateways to authorize tool invocations.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-security.html

### AC-16: Gateway Error Detail Exposure
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListGateways`, `bedrock-agentcore:GetGateway`
- **Evaluate:** `Failed` for gateways configured to return `DEBUG`-level exception detail; `Passed` otherwise; `N/A` when AgentCore is unavailable or no gateways exist.
- **Resolution:** Set gateway exception detail below `DEBUG` so internal error detail is not exposed to callers.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-security.html

### AC-17: Gateway WAF Protection
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agentcore:ListGateways`, `bedrock-agentcore:GetGateway`
- **Evaluate:** `Failed` for gateways without an associated AWS WAF web ACL (`webAclArn`); `Passed` when a web ACL is associated; `N/A` when AgentCore is unavailable or no gateways exist.
- **Resolution:** Associate an AWS WAF web ACL with public AgentCore gateways to rate-limit and filter inbound requests.
- **Reference:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-security.html
