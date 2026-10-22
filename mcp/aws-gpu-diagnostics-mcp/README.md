# AWS GPU Diagnostics MCP

> **Proof of concept:** Validate this server in a non-production account before production use. It collects operating-system and GPU diagnostic evidence from EC2 instances and uploads it to an encrypted S3 bucket.

This MCP server extends AWS DevOps Agent with a controlled path to collect node-local NVIDIA GPU diagnostics. It is designed to complement the `aiml-gpu-training-cluster-investigation` skill: the skill performs the initial read-only investigation, and this MCP server obtains host evidence only when that evidence is needed.

The fixed collector is adapted from the AWS Samples [GPU Diagnostics Collector](https://github.com/aws-samples/sample-gpu-diagnostics-collector); this MCP integration adds target validation, SSM orchestration, bounded artifact access, and DevOps Agent tool schemas.

## Design

The server uses the MCP Streamable HTTP transport through an AWS Bedrock AgentCore Gateway and a Lambda target to expose five tools. A collection request validates its target EC2 instance profile, then starts SSM Automation to run the fixed collector. SSM approval is optional and enabled only when `REQUIRE_HUMAN_APPROVAL=true`.

```text
DevOps Agent -> AgentCore Gateway -> Lambda MCP target
                                      |
                                      v
                              SSM Automation
                                      |
                                      v
                         EC2 GPU node runs fixed collector
                                      |
                                      v
                         KMS-encrypted S3 diagnostic bundle
```

The agent cannot supply arbitrary shell commands or choose an arbitrary S3 destination. The Lambda generates the collection prefix, and the Automation document independently restricts it to the server-generated `collections/<instance-id>/<collection-id>` shape before substituting it into the fixed command.

## Tools

| Tool | Purpose |
| --- | --- |
| `collect_gpu_diagnostics` | Request standard or extended diagnostics from one trusted EC2 instance. |
| `collection_status` | Poll SSM approval and collection status. |
| `validate_gpu_bundle` | Verify a completed manifest and its expected artifacts. |
| `get_gpu_findings` | Retrieve structured Xid, ECC, NVLink, and Fabric Manager findings. |
| `read_gpu_artifact` | Read a capped byte range from a text artifact. |

## Security controls

- Native SSM `aws:approve` gating is available when `REQUIRE_HUMAN_APPROVAL=true`.
- A target must be running, in an allowed Region, and attached to an explicitly trusted instance profile.
- The SSM Automation role permits commands only on instances tagged `DevOpsGpuDiagnostics=true`.
- The Lambda can start only this stack's Automation document and can pass only its Automation role to Systems Manager.
- The node can read only `collector/*` and can write diagnostic output only under `collections/*`; it cannot overwrite the collector.
- Lambda validation and Automation `allowedPattern` constraints independently restrict the instance ID and generated S3 collection prefix before either value is substituted into the fixed shell command.
- `collection_status` accepts only executions created from this stack's GPU diagnostics Automation document.
- Artifacts use SSE-KMS, blocked public access, versioning, and a seven-day lifecycle.
- The MCP artifact reader accepts only server-shaped artifact keys and caps responses at 256 KiB.
- Node-generated artifact text is untrusted data. Control characters are removed from structured findings and streamed text artifacts, but operators and agents must treat the remaining log content as evidence, not instructions.

## Prerequisites

- Node.js 18+, npm, AWS CDK, and AWS CLI.
- A GPU instance with SSM Agent installed and an instance profile that includes `AmazonSSMManagedInstanceCore`.
- A dedicated non-production target tagged `DevOpsGpuDiagnostics=true`.
- The full ARN of that instance profile and the full ARN of its role.
- The trusted node role must be permitted to use the created S3 bucket and KMS key; the stack's bucket and key resource policies grant this scope.

## Deploy

```bash
cd mcp/aws-gpu-diagnostics-mcp
export AWS_REGION=us-west-2
export AWS_PROFILE=optimus-123456789012
export TRUSTED_INSTANCE_PROFILE_ARNS=arn:aws:iam::123456789012:instance-profile/gpu-diagnostics-node
export TRUSTED_INSTANCE_ROLE_ARNS=arn:aws:iam::123456789012:role/gpu-diagnostics-node
./deploy.sh
```

The stack outputs `GatewayUrl`, `CognitoClientId`, `OAuthTokenUrl`, `ArtifactsBucketName`, and `CollectionDocumentName`.

## Connect to AWS DevOps Agent

Run `./get-config.sh` after deployment to print the non-secret Agent Space configuration. Use `SHOW_SECRET=true ./get-config.sh` only while entering the OAuth client secret into the AWS DevOps Agent console; do not store or commit that value.

In the Agent Space, register the printed MCP server URL as a customer-configured MCP server using OAuth client credentials and the `gpu-diagnostics/invoke` scope. The gateway exposes namespaced tool names, so use these exact classifications when prompted:

| Tool | Classification |
| --- | --- |
| `GpuDiagnostics___collect_gpu_diagnostics` | `MUTATIVE` |
| `GpuDiagnostics___collection_status` | `READ_ONLY` |
| `GpuDiagnostics___validate_gpu_bundle` | `READ_ONLY` |
| `GpuDiagnostics___get_gpu_findings` | `READ_ONLY` |
| `GpuDiagnostics___read_gpu_artifact` | `READ_ONLY` |

The `MUTATIVE` classification ensures DevOps Agent requests chat approval before starting an SSM collection. Set `REQUIRE_HUMAN_APPROVAL=true` with `APPROVAL_APPROVER_ARNS` only when a second, native SSM approval gate is desired.

This integration is intended for interactive troubleshooting only. Do not configure the MCP tools for scheduled or unattended collection. `REQUIRE_HUMAN_APPROVAL` remains off by default because DevOps Agent already requires in-chat approval for the `MUTATIVE` collection tool; enable it with `APPROVAL_APPROVER_ARNS` only when a second SSM approval is required.

## P6 validation plan

1. Launch a non-production P6 instance from a current NVIDIA GPU AMI with the trusted profile and `DevOpsGpuDiagnostics=true` tag.
2. Deploy the stack with that profile and role in the trust lists.
3. Use `collect_gpu_diagnostics` with `profile=standard`; poll `collection_status`.
4. Validate `manifest.json` through `validate_gpu_bundle`, then inspect the normal no-fault result through `get_gpu_findings`.
5. Repeat with `profile=extended` and verify EFA and PCIe artifacts are present when the instance configuration supports them.
6. Exercise denied approval, untrusted-profile rejection, non-GPU or stopped target rejection, and artifact-key validation before considering a merge.

Do not merge generated deployment outputs, Cognito secrets, account IDs, instance IDs, or collected diagnostic artifacts.

## Capacity Block validation

Use `scripts/run_reserved_gpu_validation.py` against an active Capacity Block. It launches a
tagged host into the targeted reservation, waits for SSM, and invokes the deployed MCP handler.
The `run` action completes the collection and validates the artifact bundle and findings.
Use `resume` only if a prior invocation stopped before the collection completed.
The runner sets `InstanceMarketOptions.MarketType` to `capacity-block`, which EC2 requires when
launching into a Capacity Block reservation.
This is a manually invoked pre-merge test harness, not a supported scheduled or unattended
operation mode for the MCP integration.

```bash
export AWS_PROFILE=optimus-123456789012
python3 scripts/run_reserved_gpu_validation.py run \
  --region us-east-1 \
  --reservation-id cr-0123456789abcdef0 \
  --image-id ami-0123456789abcdef0 \
  --subnet-id subnet-0123456789abcdef0 \
  --security-group-id sg-0123456789abcdef0 \
  --instance-profile-name gpu-diagnostics-node

# If a prior invocation stopped before the collection completed:
python3 scripts/run_reserved_gpu_validation.py resume \
  --region us-east-1 \
  --reservation-id cr-0123456789abcdef0 \
  --image-id ami-0123456789abcdef0 \
  --subnet-id subnet-0123456789abcdef0 \
  --security-group-id sg-0123456789abcdef0 \
  --instance-profile-name gpu-diagnostics-node
```

Run `run` only after the reservation state is `active`. The script does not terminate the
instance; terminate it after validation so no post-reservation On-Demand charges accrue.
