# VPC Flow Logs - Semantics, Fields, and Limits

Use this when interpreting flow log records. Every behavior below comes from the AWS
documentation pages listed under References. Anything marked **[Heuristic]** is an analysis
technique, not documented AWS behavior. Say so when you rely on it.

## References

- [Flow log records (fields)](https://docs.aws.amazon.com/vpc/latest/userguide/flow-log-records.html)
- [Flow log record examples](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-records-examples.html)
- [Flow log limitations](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-limitations.html)
- [Athena table for flow logs](https://docs.aws.amazon.com/athena/latest/ug/vpc-flow-logs-create-table-statement.html)
- [CloudWatch Logs Insights discovered fields](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_AnalyzeLogData-discoverable-fields.html)

## What a record is

- A record summarizes a flow (a 5-tuple on one network interface) over an aggregation interval.
  It is not a packet. `start` and `end` are Unix seconds, and either can be up to 60 seconds off
  from when packets actually crossed the interface.
- On Nitro-based instances the aggregation interval is always 1 minute or less, regardless of the
  configured maximum.
- Each direction of a conversation is a separate record. A healthy TCP session on one ENI usually
  appears as two records with srcaddr/dstaddr and srcport/dstport swapped.
- The format is fixed when the flow log is created. To add fields (for example `tcp-flags`), you
  have to create a new flow log.

## Default format (version 2)

```
version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
```

## Fields worth adding for troubleshooting (custom format)

| Field | Version | Why it matters |
|---|---|---|
| `vpc-id`, `subnet-id`, `instance-id` | 3 | Locate the ENI without a lookup. `instance-id` is `-` for requester-managed ENIs (NAT GW). |
| `tcp-flags` | 3 | Handshake analysis. FIN=1, SYN=2, RST=4, SYN-ACK=18. ACK/PSH are not logged (0). Flags are OR-ed over the interval, so 3 = SYN+FIN and 19 = SYN-ACK+FIN. |
| `type` | 3 | IPv4 / IPv6 / EFA |
| `pkt-srcaddr`, `pkt-dstaddr` | 3 | Original packet IPs behind a NAT gateway, EKS pod IPs vs. node ENI IPs, secondary IPs. May show the preserved client IP when an intermediate layer has client IP preservation. |
| `region`, `az-id`, `sublocation-type`, `sublocation-id` | 4 | Cross-AZ analysis, Local Zones, Outposts, Wavelength |
| `pkt-src-aws-service`, `pkt-dst-aws-service` | 5 | AWS service IP range names (S3, DYNAMODB, EC2, ROUTE53_RESOLVER, ...) |
| `flow-direction` | 5 | `ingress` / `egress` relative to the ENI. Needed for direction-aware SG and NACL verdicts. |
| `traffic-path` | 5 | Egress path: 1 same-VPC resource, 2 IGW or gateway endpoint, 3 VGW, 4 intra-Region peering, 5 inter-Region peering, 6 Local Zone/Wavelength, 7 gateway endpoint, 8 IGW |
| `ecs-*` | 7 | ECS cluster, service, task, and container (awsvpc network mode only) |
| `reject-reason` | 8 | `BPA` (VPC Block Public Access), `EC` (VPC Encryption Controls). `-` for any other reason, including SG and NACL. |
| `resource-id` | 9 | Regional NAT gateway ID |
| `encryption-status` | 10 | 0 not encrypted, 1 Nitro, 2 application (port-443 assumption for endpoints), 3 both |
| `interface-type`, `next-hop-*` | 11 | ENI type (nat_gateway, network_load_balancer, transit_gateway, vpc_endpoint, ...) and next-hop interface, subnet, AZ and VPC. Not available for IGW, cross-Region traffic, or some ingress (TGW, NLB). With a middlebox, the next hop is the middlebox ENI. |

A recommended troubleshooting format (version 5 fields, so it works everywhere):

```
${version} ${account-id} ${interface-id} ${srcaddr} ${dstaddr} ${srcport} ${dstport} ${protocol} ${packets} ${bytes} ${start} ${end} ${action} ${log-status} ${vpc-id} ${subnet-id} ${instance-id} ${tcp-flags} ${type} ${pkt-srcaddr} ${pkt-dstaddr} ${az-id} ${flow-direction} ${traffic-path} ${pkt-src-aws-service} ${pkt-dst-aws-service}
```

Organizations publish different "recommended" formats, and the field order varies: `tcp-flags`
may come after `instance-id`, after `type`, or at the end. Never assume an order. Read
`LogFormat` from `describe-flow-logs` and parse in that order. A format without
`flow-direction` still works for pairing: match `srcaddr`/`dstaddr` against the interface's IP.

## action and log-status

- `ACCEPT`: allowed by both the security group and the network ACL.
- `REJECT`: not allowed by the security group or the network ACL, **or packets arrived after the
  connection was closed** (documented). A REJECT does not always mean a rule is wrong.
- `NODATA`: no traffic on the ENI during the interval.
- `SKIPDATA`: some records were skipped (internal capacity or error). A missing flow in a
  SKIPDATA interval is not evidence that the traffic didn't happen.
- Judge whether an interface is in use by `OK` records only. NODATA records are written for
  idle intervals, so a recently written log stream doesn't mean traffic is flowing. In a test
  VPC, an NLB interface and a NAT gateway interface logged hundreds of NODATA records within
  two hours. [Observed in a test VPC]

## Nothing logged in either direction

Before concluding "no traffic", rule out the logging itself:

1. The flow log exists for this resource and is active: `describe-flow-logs` shows
   `FlowLogStatus` ACTIVE and `DeliverLogsStatus` SUCCESS.
2. You're querying the right destination (log group or S3 prefix) and the right interface. Each
   network interface gets its own log stream in CloudWatch Logs; filter on `interfaceId`.
3. `TrafficType` is ALL. A REJECT-only flow log never shows accepted traffic, and the reverse.
4. The time window covers the incident, allowing for `start` and `end` being up to 60 s off.
5. The traffic isn't one of the types that are never logged (below).

Only then treat the absence as "the packets never reached this interface". That points
upstream: routing, a TGW or firewall path, or the client never sending.

## Security group vs network ACL (the core inference)

Documented behavior: security groups are **stateful**, so responses to allowed traffic are
allowed regardless of rules. Network ACLs are **stateless**, so responses are evaluated against
NACL rules.

| Pattern on the same ENI | Meaning |
|---|---|
| Request `ACCEPT` + response `ACCEPT` | Allowed both ways |
| Request `ACCEPT` + response `REJECT` | The NACL denied the response. The SG can't do this, because it's stateful. The usual cause is a missing NACL rule for the ephemeral port range. |
| Single `REJECT`, no reverse record | The SG or NACL denied the initial traffic. Flow logs can't distinguish which: check the SG first, then the NACL. |
| Same 5-tuple both `ACCEPT` and `REJECT` | Late packets after close, a connection-tracking idle timeout, or a rule change mid-window. [Heuristic: separating these needs timing or a capture.] |
| `reject-reason` = `BPA` / `EC` | Block Public Access / Encryption Controls, not SG or NACL |

The documented example is a ping from 203.0.113.12 to 172.31.16.139. The SG allows inbound ICMP
and the NACL allows inbound but not outbound ICMP. That produces an inbound ICMP ACCEPT followed
by an outbound ICMP REJECT.

Remember that SG and NACL evaluation happens on both ends. A flow ACCEPTed at the client ENI
can still be REJECTed at the server ENI. Compare both ENIs' logs.

## TCP flags patterns (needs `tcp-flags`)

Flags are OR-ed per record (documented), so match on the bit, not one exact value:

- **SYN sent:** 2, 3 (SYN+FIN), 6 (SYN+RST) or 7.
- **SYN-ACK sent:** 18, 19 (SYN-ACK+FIN), 22 (SYN-ACK+RST) or 23.
- **RST sent:** 4 or 5 (RST+FIN), without the SYN-ACK bit.

Matching only `2` and `18` misreads short and long connections. In a test VPC, a short HTTP
exchange logged 3 from the client and 19 from the server: no record was exactly 2 or 18. A
long-lived connection logged 2 and 18 in its first interval and 0 afterwards (ACK-only traffic).
[Observed in a test VPC, 1-minute aggregation; consistent with the documented OR-ing.]

| Initiator record | Reverse record | Interpretation [Heuristic built on documented flag values; each row observed in a test VPC] |
|---|---|---|
| SYN bit | SYN-ACK bit (18/19/22/23) | Handshake completed: the server answered |
| SYN bit | RST only (4/5) | Host reachable, port closed or host firewall refused. The client still logs a bare 2. |
| SYN bit, ACCEPT | none | SYN left this ENI and nothing came back. The drop is downstream: route, TGW or firewall, the remote SG/NACL, a target that's down, or asymmetric return via another ENI. |
| SYN bit, ACCEPT | REJECT | Return traffic blocked on this ENI (NACL) |
| 1 or 4 only, REJECT | | Late FIN or RST after close: usually noise |

A bare 2 on the client is not "unanswered" on its own: a refused connection (RST back) and the
first interval of a long-lived connection both log 2. Check the reverse records.

**Who sent the RST.** Flags belong to the packets of that record's direction, so the sender is
the record's `srcaddr` (or `pkt-srcaddr` behind translation). An `ingress` record from the
client carrying RST means this interface *received* the reset from the client side; it didn't
send one. Assign root cause to the sender. In a test VPC, NLB idle resets showed on the client
interface as records with `srcaddr` = the NLB IP and `tcp-flags` 4. [Observed in a test VPC]

## Common misreadings

- **"3 (SYN+FIN) is abnormal."** It isn't. It's a short connection whose SYN and FIN fell in
  one interval (documented). Every healthy HTTP request in a test VPC logged 3. [Observed]
- **Exact `tcp-flags = 4` finds all resets.** It misses RST+FIN (5), SYN+RST (6) and SYN-ACK+RST
  (22). Match the bit.
- **"ACCEPT in both directions means the network is fine."** It means the SG and NACL allowed
  it. Flow logs don't show loss, retransmissions, latency, MTU black holes, or
  `*_allowance_exceeded` drops. For slowness, get a capture or the ENA counters before handing
  off to the application team.
- **"ACCEPT with no reply means an application problem."** First check the other end's
  interface. In a test VPC, an SG-blocked port showed ACCEPT with no reply on the client, and
  the REJECT appeared only on the server. A closed port isn't silent: it answers with RST.
  [Observed in a test VPC]
- **"Low bytes per packet means MTU trouble."** An MTU black hole drops *large* packets. A low
  `bytes / packets` average is normal on the ACK side of a bulk transfer and for chatty
  protocols. Use it to spot small-packet floods, not to diagnose MTU. [Heuristic]
- **`count(*)` is a request count.** It counts flow log records (per 5-tuple, per interval,
  per interface), not requests or connections.
- **`pkt-srcaddr` always shows the real client.** On the NAT -> internet leg it's the NAT
  itself. See address translation below.

## Address fields and translation

- For traffic to a secondary private IPv4, or to an IP that isn't the ENI's, `dstaddr` shows the
  ENI's **primary** private IPv4. Use `pkt-dstaddr` for the real destination.
- For egress from an ENI where the source isn't the ENI's own IP, `srcaddr` shows the primary
  private IP. Use `pkt-srcaddr`.
- **Zonal NAT gateway: finding the original instance** (verified against the AWS "Traffic
  through a zonal NAT gateway" example). The NAT ENI logs two legs:
  - **Instance -> NAT:** `srcaddr` = the **instance**, `dstaddr` = the NAT private IP,
    `pkt-dstaddr` = the internet destination. The default v2 format already shows the instance
    here: filter the NAT ENI on `dstaddr` = NAT private IP.
  - **NAT -> internet:** `srcaddr` **and** `pkt-srcaddr` are both the NAT private IP. The instance
    does **not** appear on this leg, so grouping it by `pkt-srcaddr` just returns the NAT again.
  - To tie the legs together, match the instance -> NAT record's `pkt-dstaddr` and time window to
    the NAT -> internet record's `dstaddr`. Don't match on source port, because the NAT rewrites it.
  - On the response leg (NAT -> instance), `pkt-srcaddr` is the internet host.
  - Regional NAT gateways log differently (`resource-id`, with `srcaddr` = instance and `dstaddr` =
    internet host). See the AWS "Traffic through a regional NAT gateway" example.
- EKS pods: `pkt-srcaddr`/`pkt-dstaddr` carry the pod IP when it differs from the node ENI IP.
- `account-id` can be `unknown` for AWS-service-created ENIs (VPC endpoint, NLB).

## Traffic that is NOT logged (documented)

- Traffic to the Amazon DNS server. Traffic to your own DNS server **is** logged.
- Windows license activation traffic
- 169.254.169.254 (instance metadata) and 169.254.169.123 (Amazon Time Sync)
- DHCP and ARP
- Mirrored **source** traffic. You see only the mirror target's traffic.
- Traffic to the reserved IP of the default VPC router
- Traffic between an endpoint network interface and a Network Load Balancer network interface.
  Read this literally: it covers only that ENI pair, as on a PrivateLink path from an interface
  endpoint to an NLB. It's not a general rule that NLB traffic goes unlogged.
- Traffic on a short-lived regional NAT gateway deleted a few minutes after creation

When the symptom involves one of these (for example DNS to the Route 53 Resolver), flow logs
can't prove or disprove anything. Use a packet capture, Route 53 Resolver query logs, or the ENA
`linklocal_allowance_exceeded` counter instead.

Flow logs also carry no application-layer data: no hostnames, URLs or payloads. For that, use
Route 53 Resolver query logs (DNS names), AWS Network Firewall logs (for traffic it inspects),
VPC Traffic Mirroring or a packet capture (packets), and application tracing such as AWS X-Ray
(request latency).

## Other limits

- You can't enable flow logs for a peer VPC in another account.
- With VPC Block Public Access, BPA flow logs omit skipped records and bytes.
- There's a maximum of 250 flow log subscriptions per resource per account.
- Next-hop fields aren't computed when the next-hop ENI belongs to another account (except
  `next-hop-az-id`).

## Where the logs live

| Destination | How to query | Field names |
|---|---|---|
| CloudWatch Logs | Logs Insights | Default format auto-discovered as camelCase (`srcAddr`, `dstAddr`, `srcPort`, `dstPort`, `action`, `logStatus`, `interfaceId`, ...). Custom formats need `parse @message`. Field discovery works only for the Standard log class. |
| S3 (text/Parquet) | Athena | Columns are snake_case (`srcaddr`, `interface_id`, `tcp_flags`, `flow_direction`). Column order must match the flow log format. |
| Firehose | Downstream tooling | |
| Uploaded file | Read directly (see `preparing-evidence.md`) | Hyphenated names in the S3 header line, as in the AWS docs |

Get the exact format with:
`aws ec2 describe-flow-logs --query "FlowLogs[].{id:FlowLogId,res:ResourceId,fmt:LogFormat,dest:LogDestination}"`
