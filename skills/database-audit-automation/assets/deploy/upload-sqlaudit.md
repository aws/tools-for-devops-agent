# upload-sqlaudit.sh — Upload Existing `.sqlaudit` Files for Processing

Save this as `upload-sqlaudit.sh`, `chmod +x upload-sqlaudit.sh`, and run it with a file or directory. You run this in your environment; the DevOps Agent does not execute it. Requires the parser stack (`assets/templates/sqlaudit-parser-stack.yaml`) to be deployed.

```bash
#!/bin/bash
# Upload SQL Server .sqlaudit files to S3 for processing
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="db-audit-ai-audit-logs-${AWS_ACCOUNT_ID}"
REGION="us-east-1"

if [ $# -eq 0 ]; then
    echo "Usage: ./upload-sqlaudit.sh <path-to-sqlaudit-file-or-directory>"
    echo ""
    echo "Examples:"
    echo "  ./upload-sqlaudit.sh Audit-20230716-141753.sqlaudit"
    echo "  ./upload-sqlaudit.sh /path/to/audit/files/"
    exit 1
fi

INPUT="$1"

if [ -f "$INPUT" ]; then
    # Single file
    FILENAME=$(basename "$INPUT")
    echo "Uploading: $FILENAME"
    aws s3 cp "$INPUT" "s3://$BUCKET/raw/sqlserver/$FILENAME" --region $REGION
    echo "Uploaded to s3://$BUCKET/raw/sqlserver/$FILENAME"
    echo ""
    echo "File will be automatically processed by Lambda."
    echo "Parsed JSON will be available at: s3://$BUCKET/processed/sqlserver/${FILENAME%.sqlaudit}.json"
elif [ -d "$INPUT" ]; then
    # Directory
    echo "Uploading all .sqlaudit files from: $INPUT"
    aws s3 sync "$INPUT" "s3://$BUCKET/raw/sqlserver/" \
        --exclude "*" \
        --include "*.sqlaudit" \
        --region $REGION
    echo "All files uploaded"
    echo ""
    echo "Files will be automatically processed by Lambda."
else
    echo "Error: $INPUT is not a valid file or directory"
    exit 1
fi

echo ""
echo "To view processed files:"
echo "  aws s3 ls s3://$BUCKET/processed/sqlserver/ --region $REGION"
echo ""
echo "To download a processed file:"
echo "  aws s3 cp s3://$BUCKET/processed/sqlserver/filename.json . --region $REGION"
```
