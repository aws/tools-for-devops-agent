# AWS Support API Reference

Quick reference for the AWS Support API operations used by this skill.

## DescribeCases

Returns a list of support cases filtered by case IDs, date range, or status.

### Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `caseIdList` | List of strings | Specific case IDs to retrieve |
| `afterTime` | String (ISO 8601) | Return cases created after this timestamp |
| `beforeTime` | String (ISO 8601) | Return cases created before this timestamp |
| `includeResolvedCases` | Boolean | Include resolved/closed cases (default: false) |
| `includeCommunications` | Boolean | Include communication thread (default: true) |
| `language` | String | Language code for results (e.g., "en") |
| `maxResults` | Integer | Max cases per page (10–100) |
| `nextToken` | String | Pagination token |

### Response Fields

| Field | Description |
|-------|-------------|
| `caseId` | Unique case identifier |
| `subject` | Case subject line |
| `status` | Current status: `opened`, `pending-customer-action`, `reopened`, `resolved`, `unassigned`, `work-in-progress` |
| `serviceCode` | AWS service code (e.g., `amazon-elastic-compute-cloud`) |
| `categoryCode` | Issue category within the service |
| `severityCode` | Severity: `low`, `normal`, `high`, `urgent`, `critical` |
| `submittedBy` | Email of the case creator |
| `timeCreated` | Case creation timestamp |
| `recentCommunications` | Latest communications (when includeCommunications is true) |
| `language` | Language of the case |

---

## DescribeCommunications

Returns the full communication thread for a specific support case.

### Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `caseId` | String (required) | The case ID to retrieve communications for |
| `afterTime` | String (ISO 8601) | Return communications after this timestamp |
| `beforeTime` | String (ISO 8601) | Return communications before this timestamp |
| `maxResults` | Integer | Max results per page (10–100) |
| `nextToken` | String | Pagination token |

### Response Fields

| Field | Description |
|-------|-------------|
| `communications[].body` | Full text of the communication |
| `communications[].submittedBy` | Who sent the message (customer or AWS) |
| `communications[].timeCreated` | Timestamp of the communication |
| `communications[].attachmentSet` | Any attached files |

---

## Common Service Codes

| Service | Code |
|---------|------|
| EC2 | `amazon-elastic-compute-cloud` |
| RDS | `amazon-relational-database` |
| Lambda | `aws-lambda` |
| ELB | `amazon-elastic-load-balancing` |
| S3 | `amazon-simple-storage-service` |
| CloudFront | `amazon-cloudfront` |
| DynamoDB | `amazon-dynamodb` |
| ECS | `amazon-elastic-container-service` |
| EKS | `amazon-elastic-kubernetes-service` |
| VPC | `amazon-virtual-private-cloud` |
| Route 53 | `amazon-route53` |
| IAM | `aws-iam` |
| CloudWatch | `amazon-cloudwatch` |
| SNS | `amazon-simple-notification-service` |
| SQS | `amazon-simple-queue-service` |

---

## Severity Levels

| Level | Code | Description |
|-------|------|-------------|
| Critical | `critical` | Business at risk, production system down |
| Urgent | `urgent` | Production system impaired |
| High | `high` | Important functions impaired |
| Normal | `normal` | Non-critical functions behaving abnormally |
| Low | `low` | General guidance or feature request |

---

## Important Constraints

- **Data retention**: Case data is available for 12 months after creation.
- **Support plan required**: Business, Enterprise On-Ramp, or Enterprise Support
  plan is required to use the AWS Support API.
- **API endpoint**: The AWS Support API is available only in the `us-east-1`
  region. All API calls must target this region regardless of where the affected
  resources are located.
- **Pagination**: Both operations are paginated. Use `nextToken` to retrieve all
  results when the response is truncated.
- **Rate limiting**: Standard AWS API rate limits apply. Use exponential backoff
  for retries.
