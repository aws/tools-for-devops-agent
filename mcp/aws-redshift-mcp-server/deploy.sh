#!/bin/bash
# End-to-end deploy script for the Redshift MCP Lambda (zip-package, no ECR).
#
# What this does:
#   1. Builds the .zip deployment package (build_zip.sh -- a plain
#      `pip install --platform manylinux2014_aarch64` on the host, no
#      container runtime needed).
#   2. Creates the IAM execution role (first run only) or reuses it.
#   3. Creates or updates the Lambda function from the .zip.
#   4. Creates (or reuses) an API Gateway REST API with an AWS_IAM
#      (SigV4) authorized POST /mcp method, integrated with the Lambda
#      function via caller-identity passthrough, and deploys it to a
#      "Prod" stage.
#   5. Prints the invoke URL.
#
# Prerequisites:
#   - AWS CLI v2, configured with credentials that can create IAM roles,
#     Lambda functions, and API Gateway REST APIs.
#   - Python 3.9+ with pip, and the `zip` command -- both are preinstalled
#     on macOS and most Linux distributions. No Docker or Finch required:
#     every dependency (uv, mcp-proxy, and transitive deps) publishes
#     prebuilt manylinux/arm64 wheels, so `pip install --platform` alone
#     produces a Lambda-compatible package.
#
# Usage:
#   ./deploy.sh [function-name] [aws-region] [caller-role-arn]
#
# Defaults: function-name=redshift-mcp-proxy-zip, aws-region=us-east-1
# caller-role-arn is optional -- if provided, that IAM role is granted
# execute-api:Invoke on the API Gateway endpoint AND lambda:InvokeFunction
# on the Lambda function automatically (step 5), so no separate manual
# grant is needed afterward. Run the script again (or run the printed
# `put-role-policy` command directly) to grant additional caller roles.

set -euo pipefail

FUNCTION_NAME="${1:-redshift-mcp-proxy-zip}"
REGION="${2:-us-east-1}"
CALLER_ROLE_ARN="${3:-}"
ROLE_NAME="redshift-mcp-lambda-execution-role"
API_NAME="${FUNCTION_NAME}-api"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIP_PATH="${SCRIPT_DIR}/redshift-mcp-proxy-lambda.zip"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
LWA_LAYER_ARN="arn:aws:lambda:${REGION}:753240598075:layer:LambdaAdapterLayerArm64:28"

echo "== Account: ${ACCOUNT_ID}  Region: ${REGION}  Function: ${FUNCTION_NAME} =="

echo
echo "== Step 1: Build the .zip deployment package =="
"${SCRIPT_DIR}/build_zip.sh"
if [[ ! -f "${ZIP_PATH}" ]]; then
  echo "ERROR: build did not produce ${ZIP_PATH}" >&2
  exit 1
fi
echo "Package built: ${ZIP_PATH} ($(du -h "${ZIP_PATH}" | cut -f1))"

echo
echo "== Step 2: IAM execution role =="
if aws iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  echo "Role ${ROLE_NAME} already exists, reusing it."
else
  echo "Creating role ${ROLE_NAME}..."
  aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document "file://${SCRIPT_DIR}/lambda-trust-policy.json" \
    --tags Key=Project,Value=redshift-mcp Key=ManagedBy,Value=redshift-mcp-deploy-script >/dev/null
  aws iam put-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-name RedshiftMcpAccess \
    --policy-document "file://${SCRIPT_DIR}/redshift-access-policy.json"
  aws iam attach-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "Waiting for IAM role propagation..."
  sleep 10
fi
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo
echo "== Step 3: Create or update the Lambda function =="
if aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${REGION}" >/dev/null 2>&1; then
  echo "Function ${FUNCTION_NAME} exists, updating code..."
  aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --region "${REGION}" \
    --zip-file "fileb://${ZIP_PATH}" >/dev/null
  aws lambda wait function-updated --function-name "${FUNCTION_NAME}" --region "${REGION}"
else
  echo "Creating function ${FUNCTION_NAME}..."
  aws lambda create-function \
    --function-name "${FUNCTION_NAME}" \
    --region "${REGION}" \
    --runtime python3.13 \
    --handler run.sh \
    --zip-file "fileb://${ZIP_PATH}" \
    --role "${ROLE_ARN}" \
    --layers "${LWA_LAYER_ARN}" \
    --timeout 60 \
    --memory-size 512 \
    --architectures arm64 \
    --environment 'Variables={AWS_LAMBDA_EXEC_WRAPPER=/opt/bootstrap,AWS_LWA_PORT=8000,AWS_LWA_READINESS_CHECK_PATH=/mcp,FASTMCP_LOG_LEVEL=INFO}' \
    --tags Project=redshift-mcp,ManagedBy=redshift-mcp-deploy-script >/dev/null
  aws lambda wait function-active --function-name "${FUNCTION_NAME}" --region "${REGION}"
fi
FUNCTION_ARN="$(aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${REGION}" --query 'Configuration.FunctionArn' --output text)"

echo
echo "== Step 4: API Gateway REST API (AWS_IAM auth, POST /mcp) =="
API_ID="$(aws apigateway get-rest-apis --region "${REGION}" --query "items[?name=='${API_NAME}'].id" --output text)"
if [[ -n "${API_ID}" ]]; then
  echo "API ${API_NAME} already exists (${API_ID}), reusing it."
else
  echo "Creating REST API ${API_NAME}..."
  API_ID="$(aws apigateway create-rest-api \
    --name "${API_NAME}" \
    --region "${REGION}" \
    --tags Project=redshift-mcp,ManagedBy=redshift-mcp-deploy-script \
    --query 'id' --output text)"
fi

ROOT_RESOURCE_ID="$(aws apigateway get-resources --rest-api-id "${API_ID}" --region "${REGION}" --query "items[?path=='/'].id" --output text)"
MCP_RESOURCE_ID="$(aws apigateway get-resources --rest-api-id "${API_ID}" --region "${REGION}" --query "items[?pathPart=='mcp'].id" --output text)"
if [[ -z "${MCP_RESOURCE_ID}" ]]; then
  echo "Creating /mcp resource..."
  MCP_RESOURCE_ID="$(aws apigateway create-resource \
    --rest-api-id "${API_ID}" \
    --region "${REGION}" \
    --parent-id "${ROOT_RESOURCE_ID}" \
    --path-part mcp \
    --query 'id' --output text)"
fi

echo "Configuring POST /mcp method (AWS_IAM authorization)..."
aws apigateway put-method \
  --rest-api-id "${API_ID}" \
  --region "${REGION}" \
  --resource-id "${MCP_RESOURCE_ID}" \
  --http-method POST \
  --authorization-type AWS_IAM >/dev/null

# --credentials "arn:aws:iam::*:user/*" tells API Gateway to invoke the
# Lambda function AS THE CALLER'S OWN IAM IDENTITY (caller-identity
# passthrough) rather than via a service-linked role. This means each
# caller role needs lambda:InvokeFunction granted directly on the
# function, in addition to execute-api:Invoke on this method (see Step 5)
# -- there is no separate `lambda add-permission` step for API Gateway's
# own service principal.
aws apigateway put-integration \
  --rest-api-id "${API_ID}" \
  --region "${REGION}" \
  --resource-id "${MCP_RESOURCE_ID}" \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --credentials "arn:aws:iam::*:user/*" \
  --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${FUNCTION_ARN}/invocations" >/dev/null

echo "Deploying to stage 'Prod'..."
aws apigateway create-deployment \
  --rest-api-id "${API_ID}" \
  --region "${REGION}" \
  --stage-name Prod >/dev/null

API_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/Prod/mcp"

if [[ -n "${CALLER_ROLE_ARN}" ]]; then
  echo
  echo "== Step 5: Grant invoke access to caller role =="
  CALLER_ROLE_NAME="$(basename "${CALLER_ROLE_ARN}")"
  aws iam put-role-policy \
    --role-name "${CALLER_ROLE_NAME}" \
    --policy-name InvokeRedshiftMcpApi \
    --policy-document "{
      \"Version\": \"2012-10-17\",
      \"Statement\": [
        {
          \"Effect\": \"Allow\",
          \"Action\": \"execute-api:Invoke\",
          \"Resource\": \"arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/POST/mcp\"
        },
        {
          \"Effect\": \"Allow\",
          \"Action\": \"lambda:InvokeFunction\",
          \"Resource\": \"${FUNCTION_ARN}\"
        }
      ]
    }" >/dev/null
  echo "Granted execute-api:Invoke and lambda:InvokeFunction to ${CALLER_ROLE_ARN}"
fi

echo
echo "== Done =="
echo "MCP endpoint (register this with AWS DevOps Agent, Service Name = execute-api):"
echo "  ${API_URL}"
echo
if [[ -z "${CALLER_ROLE_ARN}" ]]; then
  echo "Grant invoke access to a caller role with:"
  echo "  aws iam put-role-policy --role-name <role-name> \\"
  echo "    --policy-name InvokeRedshiftMcpApi --policy-document '{"
  echo "      \"Version\": \"2012-10-17\","
  echo "      \"Statement\": ["
  echo "        {\"Effect\": \"Allow\", \"Action\": \"execute-api:Invoke\", \"Resource\": \"arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/POST/mcp\"},"
  echo "        {\"Effect\": \"Allow\", \"Action\": \"lambda:InvokeFunction\", \"Resource\": \"${FUNCTION_ARN}\"}"
  echo "      ]"
  echo "    }'"
  echo
  echo "Or re-run this script with a third argument:"
  echo "  ./deploy.sh ${FUNCTION_NAME} ${REGION} arn:aws:iam::<account-id>:role/<role-name>"
fi

echo
echo "== Database grants required (run once per cluster/workgroup, as a database superuser) =="
echo "Amazon Redshift maps this Lambda's execution role (${ROLE_NAME}) to the database"
echo "user IAMR:${ROLE_NAME} (IAM roles use the IAMR: prefix, IAM users use IAM:)."
echo "By default that database user can only see its own queries -- run this so it can"
echo "see all users' queries in the monitoring views this skill relies on:"
echo
echo "  GRANT ROLE sys:monitor TO \"IAMR:${ROLE_NAME}\";"
echo
echo "SVV_TABLE_INFO (used for table-health checks) is superuser-visible by default and"
echo "isn't covered by sys:monitor, so it needs its own grant too:"
echo
echo "  GRANT SELECT ON SVV_TABLE_INFO TO \"IAMR:${ROLE_NAME}\";"
