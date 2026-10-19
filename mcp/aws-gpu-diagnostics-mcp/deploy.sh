#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:?Set AWS_REGION to the target Region.}"
: "${TRUSTED_INSTANCE_PROFILE_ARNS:?Set the EC2 instance profile ARNs that this MCP may collect from.}"
: "${TRUSTED_INSTANCE_ROLE_ARNS:?Set the IAM role ARNs attached to those instance profiles.}"
if [[ "${REQUIRE_HUMAN_APPROVAL:-false}" == "true" ]]; then
  : "${APPROVAL_APPROVER_ARNS:?Set IAM principal ARNs allowed to approve collection.}"
fi

export ALLOWED_REGIONS="${ALLOWED_REGIONS:-$AWS_REGION}"

npm install
npm run build
npx cdk synth --region "$AWS_REGION"
npx cdk deploy AwsGpuDiagnosticsMcpStack --region "$AWS_REGION" --require-approval broadening
