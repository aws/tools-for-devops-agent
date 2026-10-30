# Origin Classification — Amazon CloudFront Operational Review

Classify every origin in Step 2, before any origin finding is evaluated. The class decides
which origin-access mechanism a finding may recommend. Source:
[Restrict access to an AWS origin](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-origin.html).

| Origin shape | Class | Origin access mechanism |
|---|---|---|
| `S3OriginConfig` with an S3 REST endpoint | S3 | OAC (recommended) or legacy OAI |
| Domain `*.s3-website*.amazonaws.com` | S3 website endpoint (custom origin) | Not OAC-eligible. Custom headers or bucket policy |
| S3 Multi-Region Access Point domain | S3 MRAP | OAC |
| Lambda function URL domain (`*.lambda-url.*.on.aws`) | Lambda URL | OAC |
| MediaStore / MediaPackage v2 domain | Media | OAC |
| `VpcOriginConfig` present | VPC origin | VPC origin (private by construction) |
| Any other `CustomOriginConfig` (ALB, EC2, API, on-premises) | Custom | 🔎 Inspect (SEC-12): secret custom header and/or CloudFront managed prefix list security group |

Origin access control applies **only** to the OAC-eligible classes (S3, S3 MRAP, Lambda URL,
Media). Never recommend OAC for a custom, website-endpoint, or VPC origin.

## Distribution profile

Classify each distribution as:

- **static:** every origin is S3, S3 MRAP, or Media, and every behavior allows only
  `GET`/`HEAD`/`OPTIONS`.
- **dynamic:** anything else.

WAF severity depends on this profile (see the WAF checks in
`references/best-practices-checklist.md`).
