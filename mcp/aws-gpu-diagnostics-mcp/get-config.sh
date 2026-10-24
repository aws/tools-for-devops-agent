#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${1:-AwsGpuDiagnosticsMcpStack}"
REGION="${AWS_REGION:?Set AWS_REGION to the Region where the stack is deployed.}"
SHOW_SECRET="${SHOW_SECRET:-false}"

outputs="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)"

output_value() {
  local key="$1"
  python3 -c '
import json
import sys

key = sys.argv[1]
for output in json.load(sys.stdin):
    if output["OutputKey"] == key:
        print(output["OutputValue"])
        break
else:
    raise SystemExit(f"Missing CloudFormation output: {key}")
' "$key" <<<"$outputs"
}

gateway_url="$(output_value GatewayUrl)"
client_id="$(output_value CognitoClientId)"
token_url="$(output_value OAuthTokenUrl)"

echo "AWS DevOps Agent MCP configuration"
echo "MCP server URL: $gateway_url"
echo "OAuth client ID: $client_id"
echo "OAuth token URL: $token_url"
echo "OAuth scope: gpu-diagnostics/invoke"
echo "Tool classification:"
echo "  MUTATIVE: GpuDiagnostics___collect_gpu_diagnostics"
echo "  READ_ONLY: GpuDiagnostics___collection_status"
echo "  READ_ONLY: GpuDiagnostics___validate_gpu_bundle"
echo "  READ_ONLY: GpuDiagnostics___get_gpu_findings"
echo "  READ_ONLY: GpuDiagnostics___read_gpu_artifact"

if [[ "$SHOW_SECRET" == "true" ]]; then
  user_pool_id="$(aws cloudformation list-stack-resources \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'StackResourceSummaries[?ResourceType==`AWS::Cognito::UserPool`].PhysicalResourceId | [0]' \
    --output text)"
  client_secret="$(aws cognito-idp describe-user-pool-client \
    --user-pool-id "$user_pool_id" \
    --client-id "$client_id" \
    --region "$REGION" \
    --query 'UserPoolClient.ClientSecret' \
    --output text)"
  echo "OAuth client secret: $client_secret"
else
  echo "OAuth client secret: hidden (use SHOW_SECRET=true only when entering it in DevOps Agent)"
fi
