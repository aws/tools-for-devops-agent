#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { CognitoStack } from '../lib/cognito-stack';
import { LambdaStack } from '../lib/lambda-stack';
import { APIGatewayLambdaStack } from '../lib/api-gateway-lambda-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

// 1. Cognito Stack - Authentication (NEW NAMES)
const cognitoStack = new CognitoStack(app, 'PrometheusLambdaMCPCognitoStack', {
  env,
  description: 'Cognito User Pool and OAuth configuration for Lambda MCP (New)',
});

// 2. Lambda Stack - MCP Server (NEW NAMES)
const lambdaStack = new LambdaStack(app, 'PrometheusLambdaMCPStack', {
  env,
  description: 'Lambda MCP Server with 5 Prometheus tools (New)',
});

// 3. API Gateway Stack - HTTP Interface (NEW NAMES)
const apiGatewayStack = new APIGatewayLambdaStack(app, 'PrometheusLambdaMCPAPIGatewayStack', {
  env,
  description: 'API Gateway with JWT authentication for Lambda MCP (New)',
  mcpFunction: lambdaStack.mcpFunction,
  userPool: cognitoStack.userPool,
  m2mClient: cognitoStack.m2mClient,
  cognitoDomain: cognitoStack.userPoolDomain,
});

// Dependencies
apiGatewayStack.addDependency(cognitoStack);
apiGatewayStack.addDependency(lambdaStack);

app.synth();
