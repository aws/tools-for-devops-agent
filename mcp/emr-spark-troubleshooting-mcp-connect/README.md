# EMR Spark Troubleshooting MCP — DevOps Agent Integration

One-click CloudFormation deploy that registers the AWS-managed **Apache Spark Troubleshooting Agent for Amazon EMR** (a SageMaker Unified Studio MCP server) with **AWS DevOps Agent**. **No MCP server code is deployed** — the MCP is hosted by AWS. This template creates the SigV4 IAM role AWS DevOps Agent uses to invoke the MCP, and the AWS DevOps Agent Service (capability provider) that wraps the registration.

> [!IMPORTANT]
> This is sample code. Test in a non-production environment first, review IAM permissions against your organization's policies, and validate the deployment before production use.

## What this deploys

| Resource | Why |
|---|---|
| `AWS::IAM::Role` trusted by `aidevops.amazonaws.com` | The SigV4 identity DevOps Agent uses to call the MCP. `SourceAccount` + `SourceArn` conditions confine it to your account. |
| Inline policies on that role | MCP invoke; scoped S3 read on caller-supplied Spark artifacts buckets; conditional per-toggle reads of EMR / EMR Serverless / Glue and their CloudWatch Log groups; optional CloudWatch KMS decrypt. |
| `AWS::DevOpsAgent::Service` (MCPServerSigV4) | Registers the MCP endpoint as a capability provider under SigV4 auth. |

**Not deployed**: agent spaces, capability-provider attachments, S3 buckets, demo workloads. Attaching the registered Service to your Agent Space is a one-time manual step (see [Step 3](#step-3-attach-the-service-to-your-agent-space)).

## Region support

Deploy in a region where **both** AWS DevOps Agent and the SageMaker Unified Studio MCP service are available:

`us-east-1`, `us-west-2`, `ap-northeast-1`, `eu-west-1`, `ap-southeast-1`, `ap-southeast-2`, `ca-central-1`, `sa-east-1`, `eu-central-1`, `eu-west-2`, `ap-south-1`

The template fails fast in any other region via a `Rules` block.

## Prerequisites

- An AWS account
- An **AWS DevOps Agent space** already created in the target region (see the [DevOps Agent Getting Started guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html))
- AWS CLI v2 with credentials that can create IAM roles and DevOps Agent resources
- One or more S3 bucket names where your Spark event logs, driver / executor stdout / stderr, or application code live — you'll pass these as `SparkArtifactsBucketNames`

## Step 1 — Deploy

```bash
aws cloudformation deploy \
  --stack-name spark-troubleshooting-mcp-connect \
  --template-file cloudformation/integration.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      SparkArtifactsBucketNames=my-spark-logs,my-spark-code
```

Deploy takes about 30 seconds.

## Step 2 — Capture the outputs

```bash
aws cloudformation describe-stacks \
  --stack-name spark-troubleshooting-mcp-connect \
  --query 'Stacks[0].Outputs'
```

Note the `ServiceArn` — you'll reference it in Step 3.

## Step 3 — Attach the Service to your Agent Space

The template registers the Service (capability provider), but **does not** attach it to your Agent Space. In the AWS DevOps Agent console:

1. Open your Agent Space.
2. Under **Capability Providers**, choose **Add**.
3. Select the Service named `spark-troubleshooting` (or whatever value you passed for `ServiceName`).
4. Save.

See the [DevOps Agent MCP registration guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html) for details.

## Parameters

| Parameter | Required | Default | Notes |
|---|---|---|---|
| `TroubleshootingRoleName` | | `SparkTroubleshootingRole` | IAM role name |
| `ServiceName` | | `spark-troubleshooting` | Capability provider name; unique per account per region |
| `EnableEMREC2` | | `true` | Attach EMR-on-EC2 read permissions |
| `EnableEMRServerless` | | `true` | Attach EMR Serverless read permissions |
| `EnableGlue` | | `true` | Attach Glue read permissions |
| `SparkArtifactsBucketNames` | ✅ | | Comma-delimited S3 bucket **names** (not ARNs) — where Spark logs / code live |
| `CloudWatchKmsKeyArn` | | `''` | Optional — KMS key ARN if your log groups are CMK-encrypted |

## IAM permissions summary

Inline policies attached to the role (conditional on the toggles above):

| Policy | Scope |
|---|---|
| `MCPInvokeAccess` | `sagemaker-unified-studio-mcp:InvokeMcp`, `CallReadOnlyTool`, `CallPrivilegedTool` (service actions have no ARN form) |
| `SparkArtifactsS3Access` | `s3:GetObject`, `s3:GetObjectVersion`, `s3:ListBucket`, `s3:GetBucketLocation` — scoped to the buckets you name |
| `EMREC2Access` | EMR-on-EC2 describes + persistent-app-UI actions |
| `EMRServerlessAccess` | EMR Serverless describes + CloudWatch Logs read on `/aws/emr-serverless/*` |
| `GlueAccess` | Glue job reads + CloudWatch Logs read on `/aws-glue/*` + Spark web UI actions + `iam:PassRole` scoped to `glue.amazonaws.com` |
| `CloudWatchKmsDecrypt` | `kms:Decrypt`, `DescribeKey` on the KMS key you supply |

The role's trust policy allows only `aidevops.amazonaws.com`, conditioned on `aws:SourceAccount` matching the deployer account and `aws:SourceArn` matching `arn:aws:aidevops:<region>:<account>:service/*` (matches the console-suggested scope).

## Cleanup

If you attached the Service to an Agent Space in Step 3, **detach it first** in the DevOps Agent console — otherwise stack delete fails because the Service is still in use.

```bash
aws cloudformation delete-stack --stack-name spark-troubleshooting-mcp-connect
aws cloudformation wait stack-delete-complete --stack-name spark-troubleshooting-mcp-connect
```

## References

- [Apache Spark Troubleshooting Agent for Amazon EMR — setup](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/spark-troubleshooting-agent-setup.html)
- [Connecting MCP servers to AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html)
- [AWS Big Data Blog — Accelerate Apache Spark debugging on Amazon EMR with AWS DevOps Agent](https://aws.amazon.com/blogs/big-data/accelerate-apache-spark-debugging-on-amazon-emr-with-aws-devops-agent/)
