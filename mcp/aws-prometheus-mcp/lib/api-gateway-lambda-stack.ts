import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as fs from 'fs';
import * as path from 'path';
import { Construct } from 'constructs';

interface APIGatewayLambdaStackProps extends cdk.StackProps {
  mcpFunction: lambda.Function;
  userPool: cognito.UserPool;
  m2mClient: cognito.UserPoolClient;
  cognitoDomain: cognito.UserPoolDomain;
}

export class APIGatewayLambdaStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: APIGatewayLambdaStackProps) {
    super(scope, id, props);

    const { mcpFunction, userPool, m2mClient, cognitoDomain } = props;

    // JWT Authorizer Lambda
    const jwtAuthorizer = new lambda.Function(this, 'JWTAuthorizer', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'jwt-authorizer.lambda_handler',
      // Dependencies (PyJWT, cryptography) are installed at synth time via pip bundling.
      code: lambda.Code.fromAsset('lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
          ],
        },
      }),
      timeout: cdk.Duration.seconds(30),
      environment: {
        USER_POOL_ID: userPool.userPoolId,
        COGNITO_ISSUER: `https://cognito-idp.${this.region}.amazonaws.com/${userPool.userPoolId}`,
        REQUIRED_SCOPES: 'prometheus-mcp-server/read',
      },
      description: 'JWT Authorizer with signature verification for MCP API',
    });

    // API Gateway
    this.api = new apigateway.RestApi(this, 'MCPAPI', {
      restApiName: 'Prometheus MCP Lambda API',
      description: 'Machine-to-Machine API for Prometheus MCP Server via Lambda',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
      },
    });

    // Lambda Authorizer
    const authorizer = new apigateway.TokenAuthorizer(this, 'MCPAuthorizer', {
      handler: jwtAuthorizer,
      identitySource: 'method.request.header.Authorization',
      authorizerName: 'MCPJWTAuthorizer',
    });

    // Lambda Integration
    const integration = new apigateway.LambdaIntegration(mcpFunction, {
      proxy: true,
    });

    // MCP endpoint with JWT authorization
    this.api.root.addResource('mcp').addMethod('POST', integration, {
      authorizer,
      authorizationType: apigateway.AuthorizationType.CUSTOM,
    });

    // Health check endpoint (no auth required)
    const healthIntegration = new apigateway.LambdaIntegration(mcpFunction);
    this.api.root.addResource('health').addMethod('GET', healthIntegration);

    // Outputs
    new cdk.CfnOutput(this, 'APIEndpoint', {
      value: this.api.url,
      description: 'API Gateway endpoint for M2M access',
    });

    new cdk.CfnOutput(this, 'MCPEndpoint', {
      value: `${this.api.url}mcp`,
      description: 'MCP endpoint for machine clients',
    });

    new cdk.CfnOutput(this, 'HealthEndpoint', {
      value: `${this.api.url}health`,
      description: 'Health check endpoint',
    });

    // Generate MCP configuration file
    const mcpConfig = {
      name: "Prometheus MCP Lambda Server",
      endpoint: `${this.api.url}mcp`,
      description: "Production-ready Prometheus MCP server deployed as AWS Lambda with API Gateway and Cognito JWT authentication. Provides 5 MCP tools for querying AWS Managed Prometheus: GetAvailableWorkspaces, ExecuteQuery, ExecuteRangeQuery, ListMetrics, and GetServerInfo. Supports natural language queries via Strands Agent integration with 748 available metrics from Kubernetes cluster monitoring.",
      authorization_flow: "OAuth Client Credentials",
      authorization_configuration: {
        client_id: m2mClient.userPoolClientId,
        client_secret: "REPLACE_WITH_ACTUAL_SECRET", // CDK cannot retrieve generated secrets
        exchange_url: `https://${cognitoDomain.domainName}.auth.${this.region}.amazoncognito.com/oauth2/token`,
        exchange_parameters: [
          {
            key: "grant_type",
            value: "client_credentials"
          },
          {
            key: "scope",
            value: process.env.OAUTH_SCOPE || "prometheus-mcp-server/read prometheus-mcp-server/write"
          }
        ]
      },
      tools: [
        {
          name: "GetAvailableWorkspaces",
          description: "List available Prometheus workspaces in the specified AWS region"
        },
        {
          name: "ExecuteQuery", 
          description: "Execute PromQL instant queries against Amazon Managed Prometheus"
        },
        {
          name: "ExecuteRangeQuery",
          description: "Execute PromQL range queries over time periods for trend analysis"
        },
        {
          name: "ListMetrics",
          description: "Get sorted list of all available metric names in Prometheus server"
        },
        {
          name: "GetServerInfo",
          description: "Get Prometheus server configuration and connection information"
        }
      ],
      deployment_info: {
        git_tag: "v0.5.0-lambda-5tools-complete",
        region: this.region,
        lambda_function_name: mcpFunction.functionName,
        lambda_function_arn: mcpFunction.functionArn,
        user_pool_id: userPool.userPoolId,
        cognito_domain: cognitoDomain.domainName,
        api_gateway_id: this.api.restApiId,
        deployment_timestamp: new Date().toISOString()
      }
    };

    // Write config file to current working directory
    const configPath = 'mcp-server-config.json';
    fs.writeFileSync(configPath, JSON.stringify(mcpConfig, null, 2));

    // Output config file location
    new cdk.CfnOutput(this, 'ConfigFile', {
      value: configPath,
      description: 'MCP server configuration file location',
    });

    new cdk.CfnOutput(this, 'ClientCredentialsNote', {
      value: 'Run: aws cognito-idp describe-user-pool-client --user-pool-id ' + userPool.userPoolId + ' --client-id ' + m2mClient.userPoolClientId + ' --region ' + this.region,
      description: 'Command to retrieve client secret (replace REPLACE_WITH_ACTUAL_SECRET in config)',
    });
  }
}
