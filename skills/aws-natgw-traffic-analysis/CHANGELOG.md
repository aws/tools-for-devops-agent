# Changelog

## 1.0.0 — 2026-10-19

Initial release.

- Locates the NAT Gateway's flow logs (ENI, subnet, or VPC level) and reads them by destination: CloudWatch Logs Insights, an existing Athena table over S3, or a user-supplied summary. Covers missing flow logs, log formats without required fields, and missing opt-in S3/Athena permissions.
- Picks the analysis window from the user's period or 14 days of NAT Gateway CloudWatch byte metrics, and states the window used.
- Categorizes NAT Gateway destinations into AWS service, customer-owned public IP, RFC1918-initiated, and third-party/CDN, using ip-ranges.amazonaws.com and the S3/DynamoDB managed prefix lists (local region first, then other regions), and checks the account's own Elastic IPs before labeling anything third-party. AWS traffic without a dedicated service code is labeled "AWS (service unidentified)"; only S3 and DynamoDB are attributed to the byte.
- Checks Gateway Endpoint route-table coverage and cross-region S3, Interface Endpoint usage (private DNS, VPC DNS attributes, AZ coverage, CloudTrail confirmation, the ECR image-pull pattern), and peering bypassed via public IPs.
- Gates any Cross-Region S3 Interface Endpoint recommendation on a CopyObject/UploadPartCopy check.
- 14 hard rules for non-obvious NAT Gateway and endpoint behaviors.
- Read-only: reports GB and percent only. No dollar figures, estimates, or per-GB prices, even when asked or when the account's rates are available; gives the formula and inputs instead. No mutating calls.
