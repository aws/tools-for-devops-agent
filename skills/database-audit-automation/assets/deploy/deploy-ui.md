# deploy-ui.sh — Deploy the Optional Dashboard

Save this as `deploy-ui.sh` alongside the `web-ui/` assets, `chmod +x deploy-ui.sh`, and run it. You run this in your environment; the DevOps Agent does not execute it. Template: `assets/templates/ui-infrastructure.yaml`.

```bash
#!/bin/bash
# Deploy Web UI for Database Audit AI Solution
set -e

STACK_NAME="db-audit-ai-ui-stack"
REGION="us-east-1"

echo "=== Deploying Web UI ==="
echo ""

# Deploy UI infrastructure
echo "Deploying API Gateway and Lambda functions..."
aws cloudformation deploy \
    --template-file ui-infrastructure.yaml \
    --stack-name $STACK_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION
echo "Infrastructure deployed"
echo ""

# Get outputs
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text)
WEB_BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`WebUIBucket`].OutputValue' --output text)
WEB_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`WebUIUrl`].OutputValue' --output text)
echo "API Endpoint: $API_ENDPOINT"
echo "Web Bucket: $WEB_BUCKET"
echo "Web URL: $WEB_URL"
echo ""

# Update index.html with API endpoint
echo "Updating web UI with API endpoint..."
sed "s|API_ENDPOINT_PLACEHOLDER|${API_ENDPOINT}/prod|g" web-ui/index.html > web-ui/index-updated.html

# Upload to S3
echo "Uploading web UI to S3..."
aws s3 cp web-ui/index-updated.html s3://$WEB_BUCKET/index.html --content-type "text/html" --region $REGION
echo "Web UI uploaded"
echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Access your dashboard at:"
echo "   $WEB_URL"
echo ""
echo "Note: It may take a few seconds for the site to become available."
```
