---
name: aws-natgw-traffic-analysis
description: 'Use this skill when a user wants to understand what traffic is going through an AWS NAT Gateway, why it takes that path, or how to reduce NAT Gateway cost - for example "why is my NAT Gateway bill so high", "what is going through my NAT Gateway", traffic leaving through NAT instead of over peering or a VPC endpoint, EKS, ECS, or other private-subnet workloads sending heavy AWS API, container image, or S3 traffic through NAT, S3 traffic still hitting NAT even though a Gateway Endpoint exists, whether Gateway or Interface Endpoints are actually being used, customer-owned or BYOIP public IPs appearing as NAT destinations, estimating how much fixing NAT traffic would save, which flow logs to use for NAT analysis, or before recommending a Cross-Region S3 Interface Endpoint. Also use it when the user shares or points to NAT Gateway VPC Flow Logs, or asks which resource or service is behind a NAT Gateway destination IP. Read-only and advisory: reports traffic in GB and percent and never changes resources.'
metadata:
  version: "1.0.0"
  author: abitnar1
  summary: "Traces AWS NAT Gateway traffic from flow logs to find endpoint, peering, and cross-region paths that bypass NAT. Read-only, GB and percent only."
  aws-devops-agent-skills.agent-types: "CHAT"
  aws-devops-agent-skills.aws-services: "Amazon VPC, Amazon S3, Amazon EC2, AWS CloudTrail, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Networking, Cost Optimization"
---

## Overview

This skill analyzes NAT Gateway traffic — *where it is actually going and why it takes that path* — to surface network architecture issues (endpoints that exist but aren't used, internal services talking over public IPs, unintended cross-region data paths) and the cost reduction that follows from fixing them. NAT Gateway bills on GB processed, and the flow log destination IP is the only reliable way to know whether that traffic is addressable (routable around NAT for free or near-free) or genuinely has to leave the VPC.

It is **read-only**: it produces traffic categorization, endpoint-coverage findings, and read-only validation commands (`describe-*`, `get-*`, `list-*`) — never mutating actions. It does not modify route tables, create endpoints, or change peering.

## Verification & Anti-Hallucination Directives (Mandatory)

- **Answer first, then ask.** When the user describes a situation, answer from that description: give the explanation and the likely causes, state your assumptions, then list the data or read-only commands that would confirm it. Do not end your turn with only a question. Stop to ask before answering only when the request cannot be answered at all without more input.
- Do not generate any fact, categorization, or cost estimate that is not grounded in the provided flow log data, the user's description, or a verified API response. If you lack a verified source, state "unable to verify" rather than inventing a category or IP owner.
- State assumptions explicitly before presenting findings — especially the data source (NAT Gateway ENI vs. instance ENI), the analysis window and how it was chosen, and its representativeness.
- Cross-check every "AWS Service" tag in the flow log data against `ip-ranges.amazonaws.com` before trusting it. The tag reflects IP-to-service mapping at export time and can be stale.
- Do not name a specific AWS API service (for example STS, ECR, CloudWatch Logs) from an IP range alone — most of them share the generic `AMAZON` range (Hard Rule 12).
- Do not report dollar figures — no savings totals, monthly or yearly estimates, ranges, or per-GB prices. This holds even when the user asks for dollars and even when you can retrieve the account's own rates (for example from Cost Explorer): a rate from one service, region, or billing window applied to flow-log GB from another produces a confident wrong number. Report traffic volume in GB and % of total, then give the user the formula and inputs to price it themselves (GB × their NAT Gateway processing rate, minus the GB × their rate for the replacement path).
- Never present a Gateway/Interface Endpoint recommendation as risk-free without checking the CopyObject/UploadPartCopy interaction first (see Hard Rule 3 below).

## When to use this skill

Activate when the user asks about:

- Why NAT Gateway spend is high, or NAT GW flagged as a top cost line item
- EKS/ECS/container workloads in private subnets making heavy AWS API calls or image pulls through NAT
- Whether a Gateway Endpoint (S3/DynamoDB) or Interface Endpoints would reduce NAT traffic, and why an existing endpoint isn't intercepting traffic it "should"
- Customer-owned public IPs (including BYOIP) appearing as NAT destinations, when private connectivity (peering/PrivateLink) may already exist
- Cross-region S3 access patterns and whether a Cross-Region Interface Endpoint is safe to recommend
- RDS or other AWS-managed services appearing as public-IP NAT destinations, or which resource sits behind a NAT destination IP

## What this skill does NOT do

This skill is **read-only and advisory**. It will not:

- **Create, modify, or delete any AWS resource.** It does not add Gateway/Interface Endpoints, create VPC Peering, modify route tables, or write Infrastructure-as-Code to be deployed. Every fix described is a *recommendation* to review and implement yourself.
- **Calculate or present cost in dollars.** It reports GB and percentages; converting to cost requires the account's actual rate card and billing period, which this skill cannot verify.
- **Identify the specific pod, container, or EC2 instance generating traffic.** NAT Gateway flow logs show the NAT Gateway's own IP as the source — never the origin inside the VPC.
- **Price traffic or reconcile it against the bill.** NAT Gateway charges can be attributed to each gateway, but turning flow-log GB into dollars needs the account's own rates and a billing window that matches the flow-log window exactly, which this skill cannot verify. Flow-log GB is the source of truth for what the traffic is.
- **Guarantee a recommendation is risk-free.** In particular, a Cross-Region S3 Interface Endpoint with private DNS can silently break cross-region `CopyObject`/`UploadPartCopy` VPC-wide — this must always be checked (Hard Rule 3) before recommending it.

## How to investigate NAT Gateway cost

Work through these steps in order and do not skip one — each depends on the one before it. If the user only describes a situation and has no data yet, apply the steps to their description and answer (see "Answer first, then ask").

- [ ] Step 1: **Confirm the data source and locate the flow logs.** Flow logs must be from the **NAT Gateway's own ENI**, not an instance ENI. Instance-ENI flow logs capture all traffic including endpoint-routed traffic and cannot determine what actually crossed NAT. If the user has instance-ENI logs, explain why they can't answer the question and what to collect instead, rather than analyzing them. If the user supplied a file or summary, confirm it came from the NAT Gateway ENI; if the source isn't stated, say the analysis assumes NAT Gateway ENI flow logs and why that matters. If the user supplied nothing, find the flow logs yourself — read [the flow log location guide](references/flow-log-location.md) before querying any flow logs. In short:
  - Get the NAT Gateway's ENI ID with `describe-nat-gateways`.
  - Call `describe-flow-logs` filtered on that ENI, then on its subnet and its VPC. VPC-level and subnet-level flow logs also capture the NAT Gateway ENI and are the common setup.
  - Branch on the destination: CloudWatch Logs → Logs Insights; S3 → an existing Athena table, or ask the user (the default agent role can't read the bucket); no flow logs → say so, give the enable command as a recommendation, and do only what CloudWatch metrics allow.
  - Check the log format includes `dstaddr` and `bytes`, and filter every query to `interface-id` = the NAT Gateway ENI.
- [ ] Step 2: **Verify the region and set the analysis window.** Do not assume region from a filename or report. Confirm via `describeVpcEndpoints`, `describeVpcPeeringConnections`, or `describeNatGateways` against the VPC ID, or state the region as an assumption. Then choose the time window **before** querying any flow logs — never default to the last few minutes or the last hour, because many workloads (batch jobs, nightly ETL, backups) only push NAT traffic at certain times:
  - If the user names a period (a billing month, "last week", the date of a spike), use it.
  - Otherwise, pull the NAT Gateway's CloudWatch metrics (`BytesOutToDestination` and `BytesInFromDestination`, statistic Sum, hourly) for the last 14 days to see when traffic actually flows, then analyze at least the last 7 days of flow logs, or the busiest days within them.
  - Check how far back flow log data exists (log group retention, the S3 objects or Athena partitions available, or when the flow log was created); if it covers less than the chosen window, say so and analyze what exists.
  - State the window you used in the findings.
- [ ] Step 3: **Categorize every destination IP** into: AWS Service, customer-owned public IP, RFC1918 (treat as the flow's initiator, never as a destination), or third-party/CDN. Read [the traffic categorization procedure](references/traffic-categorization.md) before categorizing — it covers the `src|dst` pipe-delimited aggregation artifact, the RFC1918 attribution rule, the "AWS (service unidentified)" label, and how to map IPs with API calls when `ip-ranges.amazonaws.com` can't be fetched. Two checks are mandatory here:
  - Map AWS destinations with the S3 and DynamoDB AWS-managed prefix lists (`com.amazonaws.<region>.s3`, `com.amazonaws.<region>.dynamodb`) — local region first, then other regions for IPs that don't match locally — and name the region of every S3 or DynamoDB destination.
  - Before labeling any destination third-party, check whether it is one of the account's own Elastic IPs (`describe-addresses`) or another resource in the account.
- [ ] Step 4: **Check Gateway Endpoint coverage** for S3 and DynamoDB — existence, route table association completeness, and same-region-only scope. Read [the endpoint coverage and cross-region guide](references/endpoint-coverage-and-cross-region.md) when S3 or DynamoDB traffic appears in the AWS Service bucket.
- [ ] Step 5: **If S3 traffic remains despite an endpoint existing**, check whether it's cross-region: compare the destination IPs against the endpoint region's S3 managed prefix list (`get-managed-prefix-list-entries`), then check the IPs that don't match against the S3 prefix lists of other regions, starting with regions where the account has buckets or other resources. IPs found in another region's list are cross-region and are expected to bypass the endpoint (Hard Rule 1) — name that region in the findings. Use the prefix-list detection steps in [the endpoint coverage and cross-region guide](references/endpoint-coverage-and-cross-region.md).
- [ ] Step 6: **Check Interface Endpoint coverage for all other AWS service traffic.** Identify which AWS APIs cross NAT from CloudTrail (`sourceIPAddress` = the NAT Gateway's public IP, grouped by `eventSource`), then check each one for an Interface Endpoint with private DNS on, a subnet in every workload AZ, and both VPC DNS attributes enabled. Read [the Interface Endpoint guide](references/interface-endpoints.md) when AWS service traffic other than S3 or DynamoDB is significant, or when the user runs EKS/ECS in private subnets.
- [ ] Step 7: **If customer-owned public IPs are significant**, trace ASN ownership, peering status, and route table coverage to determine if the traffic could move to a private path. Read [the customer IP tracing guide](references/customer-ip-tracing.md) when customer-owned or BYOIP addresses appear as destinations, or when the user asks which resource is behind a destination IP.
- [ ] Step 8: **Before recommending any cross-region S3 fix**, check for CopyObject/UploadPartCopy activity — see Hard Rule 3 and the CopyObject decision tree in [the endpoint coverage and cross-region guide](references/endpoint-coverage-and-cross-region.md). This gates whether a Cross-Region Interface Endpoint is safe to suggest at all.
- [ ] Step 9: **Draft findings in GB and % only**, with a data-window disclaimer and a "what we cannot determine" limitations block. Read [the output format and limitations rules](references/output-and-limitations.md) before writing the findings.
- [ ] Step 10: **Validate your own output before presenting it.** Check each item below; if any fails, fix the draft and re-check:
  - Category GB values add up to the total GB, and percentages sum to roughly 100%.
  - Every destination IP sits in exactly one category, and every "AWS Service" attribution was checked against `ip-ranges.amazonaws.com` or the AWS-managed prefix lists.
  - Every S3 and DynamoDB destination names its region, and no destination is labeled third-party without checking the account's own Elastic IPs first.
  - No destination was attributed to a service from the flow log `pkt-src-aws-service` / `pkt-dst-aws-service` fields (Hard Rule 13).
  - The findings state where the flow logs came from (log group, S3 location, or user-supplied file) and that queries were filtered to the NAT Gateway ENI.
  - No specific API service is named from an IP range alone (Hard Rule 12).
  - No cross-region flow is blamed on a missing or misconfigured Gateway Endpoint (Hard Rule 1).
  - Any Interface Endpoint recommendation states the per-AZ hourly tradeoff, and any cross-region S3 recommendation has passed the Step 8 CopyObject/UploadPartCopy check.
  - The draft contains no dollar figures (no totals, estimates, ranges, or per-GB prices) — even if the user asked for dollars or you retrieved rates — and both the data-window disclaimer and the limitations block are present.
  - The analysis window is stated, and it was chosen from the user's period or the NAT Gateway's CloudWatch traffic pattern — not a default short window.
  - The response answers the user's question before asking for anything.

## Key hard rules

These are non-obvious, field-verified behaviors — violating them produces wrong or actively harmful recommendations.

1. **Gateway Endpoints (S3/DynamoDB) are same-region only.** They cannot intercept cross-region traffic. Confirm by checking the destination IPs against the endpoint region's managed prefix list: if they aren't in it, the endpoint is irrelevant to that traffic and the bypass is expected behavior, not a misconfiguration — don't recommend "check your endpoint" for cross-region flows.
2. **A Gateway Endpoint doesn't block anything — it either intercepts or it doesn't.** Same-region traffic matching the prefix list is intercepted; everything else takes the default route. The one exception: `CopyObject` with a cross-region source bucket will fail if it gets intercepted by an endpoint it wasn't meant to hit.
3. **A Cross-Region S3 Interface Endpoint with private DNS blocks cross-region `CopyObject`/`UploadPartCopy` for the entire VPC — all subnets, public and private.** Private DNS is VPC-wide; there is no subnet-level isolation. Always check for CopyObject/UploadPartCopy activity before recommending this fix. If present, recommend CRR + local reads or MRAP instead.
4. **`CopyObject`'s payload never traverses NAT Gateway — only the control-plane API call does.** Don't count CopyObject data volume toward NAT Gateway savings potential.
5. **Flow logs from NAT Gateway ENIs confirm actual NAT traversal.** Flow logs from instance ENIs capture all traffic — including endpoint-routed traffic — and cannot be used to determine what crossed NAT.
6. **Cross-Region Replication (CRR) inbound traffic never traverses the customer's NAT Gateway.** `PutObjectForRepl`/`PutObjectReplTime` are S3-to-S3 service-side operations.
7. **NAT Gateway flow logs cannot reveal the source pod, container, or instance** — only the NAT Gateway's own IP appears as source. You can identify the VPC; you cannot identify what inside it generated the traffic.
8. **Peering existing does not mean peering is being used.** If an application calls a public IP instead of a private one, traffic still routes to `0.0.0.0/0` → NAT Gateway regardless of any peering connection. Also check for a missing route in a specific route table (a VPC's main route table is not automatically applied everywhere).
9. **Absence of evidence is not evidence of absence.** An API error or empty result can mean wrong region, wrong account, or insufficient permissions — never state a resource is "confirmed missing" from a failed or empty query.
10. **A Cross-Region Interface Endpoint costs more per GB than a same-region one** — PrivateLink processing *and* inter-region data transfer both apply to the same bytes. Say this when comparing options; do not quote per-GB prices.
11. **An Interface Endpoint existing does not mean it is being used.** Traffic still crosses NAT if private DNS is off on the endpoint, if either VPC DNS attribute (`enableDnsSupport`, `enableDnsHostnames`) is off, or if the endpoint has no subnet in the AZ the workload runs in. For ECR image pulls, the layer bytes come from S3, so they stay on NAT without an S3 Gateway Endpoint even when ECR Interface Endpoints exist.
12. **`ip-ranges.amazonaws.com` cannot identify most AWS API services.** It has service codes for only a few services (such as S3, DynamoDB, EC2, CloudFront, Route 53); most API endpoints appear only under `AMAZON`. Label that traffic "AWS (service unidentified)" and identify the service from CloudTrail.
13. **Don't attribute traffic from the flow log `pkt-src-aws-service` / `pkt-dst-aws-service` fields.** They come from the same published ranges, so they are only reliable where the S3 and DynamoDB managed prefix lists already confirm the service. Ranges overlap, and many services appear only as `AMAZON`. Record the field as context at most; attribute S3 and DynamoDB from the prefix lists, and every other AWS service from CloudTrail.
14. **Only S3 and DynamoDB can be attributed to the byte.** The managed prefix lists tie each S3/DynamoDB destination to a service and region. Every other AWS service is identified from a CloudTrail sample of API calls, which gives call counts, not bytes. An Interface Endpoint recommendation for those services is therefore a candidate whose payoff this skill cannot quantify — say so, and present the per-AZ hourly tradeoff.

## Reference material

Load each file only when its step comes up:

- [Flow log location](references/flow-log-location.md) — load at Step 1, when the user hasn't supplied flow log data. Finding the NAT Gateway's flow logs at the ENI, subnet, or VPC level, and querying them by destination (CloudWatch Logs Insights, an existing Athena table over S3, or the user), plus what to do when no flow logs exist or the log format lacks required fields.
- [Traffic categorization](references/traffic-categorization.md) — load at Step 3. The four-bucket categorization procedure, the `src|dst` pipe-delimited aggregation artifact, RFC1918 attribution rules, AWS-Service-tag verification against `ip-ranges.amazonaws.com`, and the "AWS (service unidentified)" label.
- [Endpoint coverage and cross-region](references/endpoint-coverage-and-cross-region.md) — load at Steps 4, 5, and 8. Gateway Endpoint verification steps, prefix-list cross-region detection, and the full CopyObject/UploadPartCopy decision tree for cross-region S3 fixes.
- [Interface Endpoints](references/interface-endpoints.md) — load at Step 6, when non-S3/DynamoDB AWS service traffic is significant or the workload is EKS/ECS in private subnets. CloudTrail-based service identification, Interface Endpoint coverage checks, the ECR image-pull pattern, and how to present the per-AZ hourly cost tradeoff without dollar figures.
- [Customer IP tracing](references/customer-ip-tracing.md) — load at Step 7, when customer-owned or BYOIP addresses are significant or the user asks what is behind a destination IP. ASN ownership tracing (a lookup the customer runs), EIP-to-ENI-to-VPC tracing, peering and route-table verification, and the RDS-via-public-endpoint identification pattern (including its known limitation: the RDS instance name cannot be recovered from the ENI lookup alone).
- [Output and limitations](references/output-and-limitations.md) — load at Step 9, before drafting findings. Output format rules (GB/% only, no dollar figures), the mandatory data-window disclaimer, and the standard limitations block.

## Output expectations

- Present traffic by category as a table: category, GB, % of total.
- State the data window and a representativeness disclaimer (e.g., weekday/weekend traffic can vary 2-3×).
- For each addressable finding, describe the fix as a comparison of options with tradeoffs (Gateway Endpoint vs. Interface Endpoint vs. peering vs. CRR vs. MRAP) — never a single silver-bullet recommendation without noting what it doesn't cover.
- Report volumes in GB and percentages only. Do not calculate or present dollar savings.
- Include a "what we cannot determine" limitations block in every output (see `references/output-and-limitations.md` for the required content).
- Include read-only AWS CLI/API validation commands (`describe-*`, `get-*`) so the user can confirm findings themselves.
- Recommend validating any fix in a non-production environment before applying it to production traffic.
