import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

interface LambdaStackProps extends cdk.StackProps {
  // No dependencies needed for Lambda
}

export class LambdaStack extends cdk.Stack {
  public readonly mcpFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: LambdaStackProps) {
    super(scope, id, props);

    // IAM role for Lambda function
    const lambdaRole = new iam.Role(this, 'MCPLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
      inlinePolicies: {
        PrometheusAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'aps:QueryMetrics',
                'aps:GetSeries',
                'aps:GetLabels',
                'aps:GetMetricMetadata',
                'aps:ListWorkspaces',
                'aps:DescribeWorkspace',
              ],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // Lambda function
    this.mcpFunction = new lambda.Function(this, 'MCPFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_function_v2.handler',  // Updated to use new MCP SDK handler
      // Dependencies are installed at synth time via pip bundling (see requirements.txt).
      // They are intentionally NOT vendored into the repository.
      code: lambda.Code.fromAsset('lambda-mcp-wrapper/lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
          ],
        },
      }),
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      role: lambdaRole,
      environment: {
        LOG_LEVEL: 'INFO',
      },
      description: 'Prometheus MCP Server Lambda Function (MCP SDK)',
    });

    // Outputs
    new cdk.CfnOutput(this, 'FunctionName', {
      value: this.mcpFunction.functionName,
      description: 'Lambda function name',
    });

    new cdk.CfnOutput(this, 'FunctionArn', {
      value: this.mcpFunction.functionArn,
      description: 'Lambda function ARN',
    });
  }
}
