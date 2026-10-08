#!/bin/bash

# Script to update MCP config file with actual Cognito client secret and real URLs
# CloudShell version - uses default credentials and region
# Usage: ./update-mcp-config-cloudshell.sh

set -e

CONFIG_FILE="mcp-server-config.json"
COGNITO_STACK_NAME="PrometheusLambdaMCPCognitoStack"
API_STACK_NAME="PrometheusLambdaMCPAPIGatewayStack"

echo "🔍 Updating MCP configuration with actual client secret and URLs..."

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config file $CONFIG_FILE not found. Run CDK deploy first."
    exit 1
fi

# Get values from Cognito stack
CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$COGNITO_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='M2MClientId'].OutputValue" \
    --output text)

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$COGNITO_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
    --output text)

COGNITO_DOMAIN=$(aws cloudformation describe-stacks \
    --stack-name "$COGNITO_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='CognitoDomain'].OutputValue" \
    --output text)

# Get values from API Gateway stack
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name "$API_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='MCPEndpoint'].OutputValue" \
    --output text)

if [ "$CLIENT_ID" = "None" ] || [ -z "$CLIENT_ID" ]; then
    echo "❌ Could not retrieve Client ID from CloudFormation outputs"
    exit 1
fi

if [ "$USER_POOL_ID" = "None" ] || [ -z "$USER_POOL_ID" ]; then
    echo "❌ Could not retrieve User Pool ID from CloudFormation outputs"
    exit 1
fi

if [ "$API_ENDPOINT" = "None" ] || [ -z "$API_ENDPOINT" ]; then
    echo "❌ Could not retrieve API Endpoint from CloudFormation outputs"
    exit 1
fi

# Extract region from User Pool ID (format: region_poolid)
REGION=$(echo "$USER_POOL_ID" | cut -d'_' -f1)

echo "📋 Found User Pool: $USER_POOL_ID"
echo "📋 Found Client ID: $CLIENT_ID"
echo "📋 Found API Endpoint: $API_ENDPOINT"
echo "📋 Found Cognito Domain: $COGNITO_DOMAIN"
echo "📋 Detected Region: $REGION"

# Get client secret from Cognito
echo "🔐 Retrieving client secret..."
CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
    --user-pool-id "$USER_POOL_ID" \
    --client-id "$CLIENT_ID" \
    --query 'UserPoolClient.ClientSecret' \
    --output text)

if [ "$CLIENT_SECRET" = "None" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "❌ Could not retrieve client secret"
    exit 1
fi

# Build token endpoint URL
TOKEN_ENDPOINT="https://${COGNITO_DOMAIN}.auth.${REGION}.amazoncognito.com/oauth2/token"

# Update the config file with all real values
echo "📝 Updating configuration file..."
jq --arg client_id "$CLIENT_ID" \
   --arg client_secret "$CLIENT_SECRET" \
   --arg endpoint "$API_ENDPOINT" \
   --arg token_url "$TOKEN_ENDPOINT" \
   '.authorization_configuration.client_id = $client_id | 
    .authorization_configuration.client_secret = $client_secret |
    .endpoint = $endpoint |
    .authorization_configuration.exchange_url = $token_url |
    .authorization_configuration.exchange_parameters[1].value = "prometheus-mcp-server/read"' \
    "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"

echo "✅ Successfully updated $CONFIG_FILE with actual values"
echo "🔍 Verification:"
echo "Client ID: $CLIENT_ID"
echo "Client Secret: ${CLIENT_SECRET:0:8}..."
echo "MCP Endpoint: $API_ENDPOINT"
echo "Token Endpoint: $TOKEN_ENDPOINT"
