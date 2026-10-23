# Traffic Categorization

For each VPC's flow log data, categorize destination IPs into one of four buckets.

## The four buckets

1. **AWS Service IPs** — Look up via `ip-ranges.amazonaws.com` to confirm the IP is AWS-owned and to get its region. Only a few services have their own service code in that file (for example `S3`, `DYNAMODB`, `EC2`, `CLOUDFRONT`, `ROUTE53`); most AWS API endpoints (container registry, credential, key, logging, monitoring, and Systems Manager APIs, among others) appear only under the generic `AMAZON` code. Label those destinations **"AWS (service unidentified)"** and identify the service through CloudTrail as described in [the Interface Endpoint guide](interface-endpoints.md) — never infer a specific API service from the IP range alone.
2. **Customer-owned public IPs** — First check the account's own Elastic IPs with `describe-addresses` (see [the customer IP tracing guide](customer-ip-tracing.md)). For an IP not found there, give the customer an ASN lookup to run (`dig TXT <reversed-ip>.origin.asn.cymru.com`) — the agent has no shell to run it. Check whether the ASN is an AWS-owned ASN (AS16509 or AS14618 — meaning the IP is hosted *in* AWS, likely BYOIP or an AWS-managed service with a public endpoint) versus the customer's own non-AWS infrastructure.
3. **RFC1918 (10.x, 172.16–31.x, 192.168.x)** — Always the flow's *initiator*, never a destination. See "NAT egress attribution" below for the exact handling.
4. **Third-party IPs** — CDNs (Fastly = 146.75.x/16, Cloudflare, Akamai) and other SaaS/partner infrastructure not owned by AWS or the customer.

## NAT egress attribution — classify on the destination (public) IP

Every flow has a source (initiator) and a destination. Classify egress category using the **destination** IP only; the RFC1918 address is the initiator and must never be classified as a destination category.

- **Aggregated summary format:** source and destination may be bundled into a single pipe-delimited `src|dst` field (a known export artifact). Split on the pipe and use the destination side for categorization.
- **Raw VPC Flow Logs format:** use the `dstaddr` column as the destination; `srcaddr` is the initiator — do not swap them.

In both formats: do not classify the RFC1918 address as "RFC1918 egress" (it isn't egress, it's the source), and do not double-count a `src|dst` pair as two separate flows.

## AWS Service tag verification (mandatory)

If the flow log CSV includes an "AWS Service" column, **do not trust it without verification**. The tag reflects IP-to-service mapping at the time of export and can be stale or wrong. The same applies to the flow log `pkt-src-aws-service` and `pkt-dst-aws-service` fields: they draw on the same published ranges, and many AWS services appear only as `AMAZON`. Never attribute traffic to a service from them (Hard Rule 13).

Always cross-reference every tagged destination IP against `ip-ranges.amazonaws.com` and the regional prefix list for that service before including it in a finding. If the tag and the IP-range lookup disagree, surface the discrepancy explicitly:

> "Tagged as [X] in flow log but IP resolves to [Y] via ip-ranges.amazonaws.com. Requires verification before acting on this finding."

## CDN/third-party matching discipline

Only match exact, known CDN ranges (e.g., Fastly's published /16 blocks). If a match is made on a broader range than a CDN's actual published block, note the match criteria explicitly in the output rather than presenting it as a confirmed match. Always cross-reference against `ip-ranges.amazonaws.com` first to rule out the IP being AWS-owned before attributing it to a third party.

## Mapping IPs with API calls (use this when `ip-ranges.amazonaws.com` can't be fetched)

An agent working through AWS APIs may not be able to download `ip-ranges.json`. The AWS-managed prefix lists give the same answer for the services that matter most here, through calls that always work against the account:

1. Look up the prefix list IDs in a region:
   ```
   aws ec2 describe-managed-prefix-lists --region <region> \
     --filters Name=prefix-list-name,Values=com.amazonaws.<region>.s3,com.amazonaws.<region>.dynamodb
   ```
2. Get the CIDRs:
   ```
   aws ec2 get-managed-prefix-list-entries --region <region> --prefix-list-id <pl-id>
   ```
3. Check every AWS-looking destination IP against the **local** region's S3 and DynamoDB lists first. For IPs that don't match, repeat in other regions — start with regions where the account has S3 buckets (`s3api list-buckets` plus `get-bucket-location`) or other resources. A match in another region's S3 list means **cross-region S3**; name that region in the findings.
4. IPs that match neither list stay "AWS (service unidentified)" until CloudTrail identifies them (see [the Interface Endpoint guide](interface-endpoints.md)).

## Check the account's own addresses before calling anything third-party

Before labeling a destination third-party, check whether it belongs to the account itself:

```
aws ec2 describe-addresses --region <region> --filters Name=public-ip,Values=<ip>
```

An Elastic IP owned by the account (for example on an instance in a peered VPC) is a **customer-owned public IP**, not third-party traffic — trace it with [the customer IP tracing guide](customer-ip-tracing.md). Elastic IPs are drawn from AWS address space, so an IP that "doesn't look like AWS" can still be the account's own instance.

## Output for this step

A table of traffic by category with GB and % of total, feeding into the endpoint-coverage and customer-IP-tracing steps.
