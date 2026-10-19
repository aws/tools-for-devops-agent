import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import * as path from 'path';

export interface GpuDiagnosticsMcpStackProps extends cdk.StackProps {
  allowedRegions?: string[];
  trustedInstanceProfileArns?: string[];
  trustedInstanceRoleArns?: string[];
  approvalApproverArns?: string[];
  requireHumanApproval?: boolean;
}

const TOOL_SCHEMAS = [
  {
    Name: 'collect_gpu_diagnostics',
    Description: 'Request GPU diagnostics from one EC2 GPU instance. This starts SSM Automation. Call collection_status with the returned executionId; do not submit the collection again.',
    InputSchema: {
      Type: 'object',
      Properties: {
        instanceId: { Type: 'string', Description: 'Target EC2 instance ID.' },
        region: { Type: 'string', Description: 'Target AWS Region.' },
        profile: {
          Type: 'string',
          Description: 'Collection profile: standard or extended.',
        },
      },
      Required: ['instanceId', 'region'],
    },
  },
  {
    Name: 'collection_status',
    Description: 'Return the approval state and execution status of a GPU diagnostics collection.',
    InputSchema: {
      Type: 'object',
      Properties: {
        executionId: { Type: 'string', Description: 'SSM Automation execution ID.' },
        region: { Type: 'string', Description: 'Target AWS Region.' },
      },
      Required: ['executionId', 'region'],
    },
  },
  {
    Name: 'validate_gpu_bundle',
    Description: 'Validate the manifest and expected files in a completed GPU diagnostics bundle.',
    InputSchema: {
      Type: 'object',
      Properties: {
        collectionId: { Type: 'string', Description: 'Collection ID returned by collect_gpu_diagnostics.' },
        instanceId: { Type: 'string', Description: 'Target EC2 instance ID.' },
      },
      Required: ['collectionId', 'instanceId'],
    },
  },
  {
    Name: 'get_gpu_findings',
    Description: 'Read structured, evidence-backed GPU findings from a completed collection.',
    InputSchema: {
      Type: 'object',
      Properties: {
        collectionId: { Type: 'string', Description: 'Collection ID returned by collect_gpu_diagnostics.' },
        instanceId: { Type: 'string', Description: 'Target EC2 instance ID.' },
        severity: { Type: 'string', Description: 'Optional minimum severity filter.' },
      },
      Required: ['collectionId', 'instanceId'],
    },
  },
  {
    Name: 'read_gpu_artifact',
    Description: 'Read a bounded byte range from a text diagnostic artifact. Use artifact keys returned by validate_gpu_bundle or get_gpu_findings.',
    InputSchema: {
      Type: 'object',
      Properties: {
        artifactKey: { Type: 'string', Description: 'Exact artifact key returned by this MCP server.' },
        startByte: { Type: 'integer', Description: 'Optional byte offset. Defaults to the beginning.' },
        maxBytes: { Type: 'integer', Description: 'Maximum bytes to return, capped at 262144.' },
      },
      Required: ['artifactKey'],
    },
  },
];

export class GpuDiagnosticsMcpStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: GpuDiagnosticsMcpStackProps) {
    super(scope, id, {
      ...props,
      description: 'Approval-gated GPU diagnostics MCP server for AWS DevOps Agent.',
    });

    if (props.requireHumanApproval && !props.approvalApproverArns?.length) {
      throw new Error('APPROVAL_APPROVER_ARNS is required when REQUIRE_HUMAN_APPROVAL is true.');
    }
    if (!props.trustedInstanceProfileArns?.length || !props.trustedInstanceRoleArns?.length) {
      throw new Error('TRUSTED_INSTANCE_PROFILE_ARNS and TRUSTED_INSTANCE_ROLE_ARNS are required.');
    }

    const allowedRegions = props.allowedRegions?.length ? props.allowedRegions : [this.region];
    const encryptionKey = new kms.Key(this, 'ArtifactsKey', {
      enableKeyRotation: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    const artifactsBucket = new s3.Bucket(this, 'ArtifactsBucket', {
      encryption: s3.BucketEncryption.KMS,
      encryptionKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      lifecycleRules: [{ expiration: cdk.Duration.days(7), noncurrentVersionExpiration: cdk.Duration.days(1) }],
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      autoDeleteObjects: false,
    });

    for (const roleArn of props.trustedInstanceRoleArns) {
      const principal = new iam.ArnPrincipal(roleArn);
      artifactsBucket.addToResourcePolicy(new iam.PolicyStatement({
        principals: [principal],
        actions: ['s3:GetObject', 's3:PutObject', 's3:AbortMultipartUpload', 's3:ListMultipartUploadParts'],
        resources: [artifactsBucket.arnForObjects('collector/*'), artifactsBucket.arnForObjects('collections/*')],
      }));
      artifactsBucket.addToResourcePolicy(new iam.PolicyStatement({
        principals: [principal],
        actions: ['s3:ListBucketMultipartUploads'],
        resources: [artifactsBucket.bucketArn],
      }));
      encryptionKey.addToResourcePolicy(new iam.PolicyStatement({
        principals: [principal],
        actions: ['kms:Decrypt', 'kms:Encrypt', 'kms:GenerateDataKey'],
        resources: ['*'],
      }));
    }

    new s3deploy.BucketDeployment(this, 'CollectorDeployment', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '..', 'collector'))],
      destinationBucket: artifactsBucket,
      destinationKeyPrefix: 'collector',
      retainOnDelete: false,
    });

    const automationRole = new iam.Role(this, 'AutomationRole', {
      assumedBy: new iam.ServicePrincipal('ssm.amazonaws.com'),
    });
    automationRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ssm:SendCommand'],
      resources: [`arn:${this.partition}:ssm:${this.region}::document/AWS-RunShellScript`],
    }));
    automationRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ssm:SendCommand'],
      resources: allowedRegions.map(
        region => `arn:${this.partition}:ec2:${region}:${this.account}:instance/*`
      ),
      conditions: {
        StringEquals: { 'aws:ResourceTag/DevOpsGpuDiagnostics': 'true' },
      },
    }));
    automationRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'ssm:DescribeInstanceInformation',
        'ssm:GetCommandInvocation',
        'ssm:ListCommandInvocations',
        'ssm:ListCommands',
      ],
      resources: ['*'],
    }));

    const document = new ssm.CfnDocument(this, 'GpuCollectionDocument', {
      documentType: 'Automation',
      name: `${this.stackName}-gpu-collection-${props.requireHumanApproval ? 'approval' : 'automated'}-v2`,
      content: {
        schemaVersion: '0.3',
        description: props.requireHumanApproval
          ? 'Approval-gated GPU diagnostics collector.'
          : 'Automated GPU diagnostics collector.',
        assumeRole: automationRole.roleArn,
        parameters: {
          InstanceId: { type: 'String' },
          CollectionPrefix: { type: 'String' },
          Profile: { type: 'String', allowedValues: ['standard', 'extended'], default: 'standard' },
        },
        mainSteps: [
          ...(props.requireHumanApproval ? [{
            name: 'HumanApproval',
            action: 'aws:approve',
            timeoutSeconds: 900,
            inputs: {
              Approvers: props.approvalApproverArns,
              Message: 'Approve GPU diagnostics collection on {{ InstanceId }}. The collection reads host GPU and kernel state and uploads encrypted artifacts to the diagnostics bucket.',
              MinRequiredApprovals: 1,
            },
          }] : []),
          {
            name: 'CollectDiagnostics',
            action: 'aws:runCommand',
            inputs: {
              DocumentName: 'AWS-RunShellScript',
              InstanceIds: ['{{ InstanceId }}'],
              Parameters: {
                commands: [
                  `bash -c 'set -euo pipefail; aws s3 cp s3://${artifactsBucket.bucketName}/collector/gpu-diag-collect.sh /tmp/gpu-diag-collect.sh --region ${this.region}; chmod 700 /tmp/gpu-diag-collect.sh; /tmp/gpu-diag-collect.sh --bucket ${artifactsBucket.bucketName} --prefix "{{ CollectionPrefix }}" --region ${this.region} --profile "{{ Profile }}"'`,
                ],
              },
            },
          },
        ],
      },
    });

    const functionRole = new iam.Role(this, 'FunctionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')],
    });
    functionRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ec2:DescribeInstances', 'ssm:StartAutomationExecution', 'ssm:GetAutomationExecution'],
      resources: ['*'],
      conditions: { StringEquals: { 'aws:RequestedRegion': allowedRegions } },
    }));
    artifactsBucket.grantRead(functionRole);

    const handlerLogGroup = new logs.LogGroup(this, 'McpHandlerLogGroup', {
      logGroupName: `/aws/lambda/${this.stackName}-gpu-mcp-handler`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    const handler = new lambda.Function(this, 'McpHandler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda')),
      role: functionRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      environment: {
        ARTIFACTS_BUCKET: artifactsBucket.bucketName,
        COLLECTION_DOCUMENT: document.ref,
        ALLOWED_REGIONS: allowedRegions.join(','),
        TRUSTED_INSTANCE_PROFILE_ARNS: props.trustedInstanceProfileArns.join(','),
        REQUIRE_HUMAN_APPROVAL: String(props.requireHumanApproval),
        STACK_NAME: this.stackName,
      },
      logGroup: handlerLogGroup,
    });

    const gatewayRole = new iam.Role(this, 'GatewayRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
    });
    gatewayRole.addToPolicy(new iam.PolicyStatement({
      actions: ['lambda:InvokeFunction'],
      resources: [handler.functionArn],
    }));
    handler.addPermission('AgentCoreInvoke', {
      principal: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceAccount: this.account,
    });

    const userPool = new cognito.UserPool(this, 'UserPool', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    const resourceServer = new cognito.UserPoolResourceServer(this, 'ResourceServer', {
      userPool,
      identifier: 'gpu-diagnostics',
      scopes: [{ scopeName: 'invoke', scopeDescription: 'Invoke GPU diagnostics MCP tools.' }],
    });
    const client = new cognito.UserPoolClient(this, 'Client', {
      userPool,
      generateSecret: true,
      oAuth: {
        flows: { clientCredentials: true },
        scopes: [cognito.OAuthScope.custom('gpu-diagnostics/invoke')],
      },
    });
    client.node.addDependency(resourceServer);
    const userPoolDomainPrefix = `${this.stackName.toLowerCase()}-${this.account}`;
    const userPoolDomain = new cognito.UserPoolDomain(this, 'UserPoolDomain', {
      userPool,
      cognitoDomain: { domainPrefix: userPoolDomainPrefix },
    });

    const gateway = new cdk.CfnResource(this, 'AgentCoreGateway', {
      type: 'AWS::BedrockAgentCore::Gateway',
      properties: {
        Name: `${this.stackName}-gateway`,
        Description: 'GPU diagnostics MCP server',
        ProtocolType: 'MCP',
        AuthorizerType: 'CUSTOM_JWT',
        AuthorizerConfiguration: {
          CustomJWTAuthorizer: {
            AllowedClients: [client.userPoolClientId],
            DiscoveryUrl: `https://cognito-idp.${this.region}.amazonaws.com/${userPool.userPoolId}/.well-known/openid-configuration`,
          },
        },
        RoleArn: gatewayRole.roleArn,
      },
    });
    gateway.node.addDependency(userPoolDomain);
    const target = new cdk.CfnResource(this, 'GatewayTarget', {
      type: 'AWS::BedrockAgentCore::GatewayTarget',
      properties: {
        GatewayIdentifier: gateway.ref,
        Name: 'GpuDiagnostics',
        Description: 'Approval-gated GPU diagnostics collection and analysis',
        TargetConfiguration: {
          Mcp: {
            Lambda: {
              LambdaArn: handler.functionArn,
              ToolSchema: { InlinePayload: TOOL_SCHEMAS },
            },
          },
        },
        CredentialProviderConfigurations: [{ CredentialProviderType: 'GATEWAY_IAM_ROLE' }],
      },
    });
    target.node.addDependency(gateway);

    new cdk.CfnOutput(this, 'GatewayUrl', {
      value: gateway.getAtt('GatewayUrl').toString(),
      description: 'Register this URL with AWS DevOps Agent.',
    });
    new cdk.CfnOutput(this, 'ArtifactsBucketName', { value: artifactsBucket.bucketName });
    new cdk.CfnOutput(this, 'CollectionDocumentName', { value: document.ref });
    new cdk.CfnOutput(this, 'CognitoClientId', { value: client.userPoolClientId });
    new cdk.CfnOutput(this, 'OAuthTokenUrl', {
      value: `https://${userPoolDomainPrefix}.auth.${this.region}.amazoncognito.com/oauth2/token`,
    });
  }
}
