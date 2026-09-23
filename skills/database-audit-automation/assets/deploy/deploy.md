# deploy.sh — Deploy the Database Audit AI Solution

Save this as `deploy.sh`, edit `EMAIL_FOR_ALERTS` and `REGION`, `chmod +x deploy.sh`, and run it. You run this in your environment; the DevOps Agent does not execute it.

```bash
#!/bin/bash
# Database Audit AI Solution - Deployment Script
# This script deploys the infrastructure and configures RDS audit logging
set -e

STACK_NAME="db-audit-ai-stack"
REGION="us-east-1"
EMAIL_FOR_ALERTS="your-email@example.com"  # Change this

echo "=== Database Audit AI Solution Deployment ==="
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI not found. Please install it first."
    exit 1
fi

# Check Bedrock model access
echo "Checking Bedrock model access..."
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?modelId==`anthropic.claude-3-sonnet-20240229-v1:0`]' > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Warning: Bedrock access may not be enabled. Request model access in the AWS Console."
    echo "Go to: https://console.aws.amazon.com/bedrock/ -> Model access"
fi

# Deploy CloudFormation stack (template: assets/templates/infrastructure.yaml)
echo ""
echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
    --template-file infrastructure.yaml \
    --stack-name $STACK_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION \
    --parameter-overrides ProjectName=db-audit-ai

if [ $? -eq 0 ]; then
    echo "Stack deployed successfully"
else
    echo "Stack deployment failed"
    exit 1
fi

# Get outputs
echo ""
echo "Retrieving stack outputs..."
AUDIT_BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`AuditLogsBucket`].OutputValue' --output text)
REPORTS_BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`ReportsBucket`].OutputValue' --output text)
SNS_TOPIC=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`AnomalyAlertTopic`].OutputValue' --output text)
echo "Audit Logs Bucket: $AUDIT_BUCKET"
echo "Reports Bucket: $REPORTS_BUCKET"
echo "SNS Topic: $SNS_TOPIC"

# Subscribe email to SNS topic
if [ "$EMAIL_FOR_ALERTS" != "your-email@example.com" ]; then
    echo ""
    echo "Subscribing $EMAIL_FOR_ALERTS to anomaly alerts..."
    aws sns subscribe \
        --topic-arn $SNS_TOPIC \
        --protocol email \
        --notification-endpoint $EMAIL_FOR_ALERTS \
        --region $REGION
    echo "Please check your email and confirm the subscription"
fi

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next Steps:"
echo "1. Enable audit logging on your RDS SQL Server instances"
echo "2. Enable pgAudit on your Aurora PostgreSQL clusters"
echo "3. Configure CloudWatch Logs export (see the audit-setup files under assets/sql/)"
echo ""
echo "To test the report generator manually:"
echo "aws lambda invoke --function-name db-audit-ai-report-generator --region $REGION output.json"
echo ""
echo "To test anomaly detection manually:"
echo "aws lambda invoke --function-name db-audit-ai-anomaly-detector --region $REGION output.json"
```
