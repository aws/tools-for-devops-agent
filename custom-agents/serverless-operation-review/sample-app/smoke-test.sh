#!/usr/bin/env bash
#
# Generates telemetry against the serverless-review test bed so the
# metric- and log-based checks in serverless-operation-review have data.
#
# Read-only against everything except the test bed's own resources: it invokes
# the deliberately broken functions, sends messages to the test queue, writes
# items to the test table, and starts one state machine execution.
#
# Usage: ./smoke-test.sh [stack-name] [region] [aws-profile]
#
set -euo pipefail

STACK="${1:-serverless-review-testbed}"
REGION="${2:-us-east-1}"
PROFILE="${3:-default}"

AWS="aws --region ${REGION} --profile ${PROFILE}"

echo "Stack:   ${STACK}"
echo "Region:  ${REGION}"
echo "Profile: ${PROFILE}"
echo

output() {
  $AWS cloudformation describe-stacks \
    --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text
}

echo "Reading stack outputs..."
TIMEOUT_FN=$(output TimeoutFunctionName)
MEMORY_FN=$(output MemoryHogFunctionName)
LEGACY_FN=$(output LegacyRuntimeFunctionName)
PUBLIC_FN=$(output PublicUrlFunctionName)
QUEUE_URL=$(output NoDlqQueueUrl)
TABLE=$(output UnprotectedTableName)
SM_ARN=$(output FragileStateMachineArn)
HEALTHY_FN=$(output HealthyFunctionName)
API_URL=$(output WideOpenApiEndpoint)

# ---------------------------------------------------------------------------
# 1. Timeouts -> "Task timed out" in logs, Errors > 0, Duration at the ceiling
# ---------------------------------------------------------------------------
echo "Invoking ${TIMEOUT_FN} (expect timeouts)..."
for i in 1 2 3; do
  $AWS lambda invoke --function-name "$TIMEOUT_FN" \
    --payload '{}' --cli-binary-format raw-in-base64-out \
    /dev/null >/dev/null 2>&1 || true
done

# ---------------------------------------------------------------------------
# 2. OOM -> "Runtime.OutOfMemory", Max Memory Used at the allocation
# ---------------------------------------------------------------------------
echo "Invoking ${MEMORY_FN} (expect out-of-memory)..."
for i in 1 2 3; do
  $AWS lambda invoke --function-name "$MEMORY_FN" \
    --payload '{}' --cli-binary-format raw-in-base64-out \
    /dev/null >/dev/null 2>&1 || true
done

# ---------------------------------------------------------------------------
# 3. Async failures with no DLQ -> Errors, and events lost on purpose
# ---------------------------------------------------------------------------
echo "Invoking ${LEGACY_FN} asynchronously (expect lost failures, no DLQ)..."
for i in 1 2 3 4 5; do
  $AWS lambda invoke --function-name "$LEGACY_FN" \
    --invocation-type Event --payload '{}' \
    --cli-binary-format raw-in-base64-out \
    /dev/null >/dev/null 2>&1 || true
done

# ---------------------------------------------------------------------------
# 4. Healthy control -> successful invocations, no findings expected
# ---------------------------------------------------------------------------
echo "Invoking ${HEALTHY_FN} (expect success)..."
for i in 1 2 3 4 5; do
  $AWS lambda invoke --function-name "$HEALTHY_FN" \
    --payload '{}' --cli-binary-format raw-in-base64-out \
    /dev/null >/dev/null 2>&1 || true
done

# ---------------------------------------------------------------------------
# 5. Function URL -> confirm the auth mode is what you expect
# ---------------------------------------------------------------------------
echo "Checking the function URL for ${PUBLIC_FN}..."
PUBLIC_URL=$(output PublicFunctionUrl)
AUTH_MODE=$(output FunctionUrlAuthType)
echo "  auth mode: ${AUTH_MODE}"
if command -v curl >/dev/null 2>&1; then
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$PUBLIC_URL" || echo "000")
  echo "  HTTP ${CODE} from ${PUBLIC_URL} (unsigned request)"
  case "$CODE" in
    403) echo "  ✅ 403 expected — the URL requires SigV4, so it is NOT anonymously reachable." ;;
    200) echo "  ⚠️  200 means this stack was deployed with SeedPublicExposureFaults=true."
         echo "      The endpoint is public. Delete the stack when testing is done." ;;
    *)   echo "  (unexpected status; check the function state)" ;;
  esac
fi

# ---------------------------------------------------------------------------
# 6. SQS batch failures -> messages recycle with no DLQ to catch them
# ---------------------------------------------------------------------------
echo "Sending messages to ${QUEUE_URL} (expect repeated batch failures)..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  $AWS sqs send-message --queue-url "$QUEUE_URL" \
    --message-body "{\"seq\":${i}}" >/dev/null
done

# ---------------------------------------------------------------------------
# 7. DynamoDB stream poison pill -> IteratorAge grows, shard blocks
# ---------------------------------------------------------------------------
echo "Writing items to ${TABLE}, including a POISON record..."
for i in 1 2 3; do
  $AWS dynamodb put-item --table-name "$TABLE" \
    --item "{\"pk\":{\"S\":\"ok-${i}\"}}" >/dev/null
done
$AWS dynamodb put-item --table-name "$TABLE" \
  --item '{"pk":{"S":"POISON"}}' >/dev/null
for i in 4 5 6; do
  $AWS dynamodb put-item --table-name "$TABLE" \
    --item "{\"pk\":{\"S\":\"ok-${i}\"}}" >/dev/null
done

# ---------------------------------------------------------------------------
# 8. State machine with no retry/catch/timeout -> failed execution
# ---------------------------------------------------------------------------
echo "Starting an execution of ${SM_ARN} (expect failure, no Catch)..."
$AWS stepfunctions start-execution \
  --state-machine-arn "$SM_ARN" \
  --input '{}' >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
# 9. API Gateway traffic -> stage metrics with no access logs to explain them
#    With the default IAM authorization, unsigned calls return 403. That still
#    produces stage metrics (4XXError), which is enough for the review. Signed
#    calls need SigV4; use awscurl or the console if you want 200s.
# ---------------------------------------------------------------------------
if command -v curl >/dev/null 2>&1; then
  API_AUTH=$(output ApiAuthorizationMode)
  echo "Calling ${API_URL} (auth: ${API_AUTH})..."
  for i in 1 2 3; do
    CODE=$(curl -s -o /dev/null -w '%{http_code}' "$API_URL" || echo "000")
    echo "  HTTP ${CODE}"
  done
  echo "  (403 is expected under IAM authorization and still generates stage metrics)"
fi

cat <<EOF

Done. Telemetry generated.

CloudWatch needs a few minutes to aggregate. Wait at least 5 minutes before
running the review, and note that percentile figures over a 7-day window are
more meaningful the longer the stack has been running.

Next:
  1. Ask the DevOps Agent, without naming the skill:
       "Run a serverless operational review for ${REGION}"
  2. Compare the report against the expected findings table in README.md.
  3. Confirm no environment variable VALUES appear anywhere in the output.
  4. Confirm the healthy control function has no CRITICAL or HIGH findings.

Remember to delete the stack when finished — it holds an over-privileged role,
a deprecated runtime, and a scheduled function that fails every hour:
  aws cloudformation delete-stack --stack-name ${STACK} --region ${REGION} --profile ${PROFILE}
EOF
