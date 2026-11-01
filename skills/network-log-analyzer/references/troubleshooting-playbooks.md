# Troubleshooting Playbooks - Symptom to Evidence to Cause

Each playbook lists what to look for in flow logs (FL) and packet captures (PCAP), the likely
causes, and **read-only** commands to confirm them. Facts come from `vpc-flow-logs.md` and
`packet-capture-analysis.md` (documented, with sources). Steps marked [Heuristic] are analysis
judgment.

Read-only command set used below:

```
aws ec2 describe-network-interfaces --network-interface-ids <eni>
aws ec2 describe-security-groups --group-ids <sg>
aws ec2 describe-network-acls --filters Name=association.subnet-id,Values=<subnet>
aws ec2 describe-route-tables --filters Name=association.subnet-id,Values=<subnet>
aws ec2 describe-flow-logs --filter Name=resource-id,Values=<vpc|subnet|eni>
aws ec2 search-transit-gateway-routes --transit-gateway-route-table-id <rt> --filters Name=type,Values=static,propagated
```

Reachability Analyzer (`create-network-insights-path` + `start-network-insights-analysis`)
evaluates SG, NACL and route configuration without sending traffic. It creates analysis
resources, so get the user's go-ahead first and suggest it rather than running it.

## Flow log triage order

Work through these in order for the failing 5-tuple, on **both** endpoints' interfaces:

1. **Anything logged at all?** If not, rule out the logging itself first (`vpc-flow-logs.md`,
   "Nothing logged in either direction"), then look upstream.
2. **REJECT?** Pair the directions. Request ACCEPT plus response REJECT means a NACL. A lone
   REJECT means the SG or the NACL (check both). A `reject-reason` of BPA or EC means neither.
3. **ACCEPT one way, nothing back?** Check the return path before anything else: the other
   interface's records, the return route (route tables and TGW route tables for the source
   CIDR), and any stateful appliance that may see only one direction. Return-path routing is
   the check people most often skip.
4. **Resets?** Match the RST bit, find the sender (playbooks 2 and 6).
5. **Volume?** Spikes, top talkers, or a flow that stopped (`flow-log-queries.md`).
6. **All ACCEPT, both directions, still failing or slow?** The SG and NACL are cleared, not the
   network. Get a packet capture and the ENA counters (playbook 4) before handing off to the
   application team.

---

## 1. "Connection times out" (TCP)

**FL:** On the client ENI, look for SYN records (`tcp-flags` 2 or 3; flags are OR-ed per record).
Then check what came back. SYN-ACK (18/19/22/23) means answered, RST (4/5) means refused, and
nothing means a timeout. A refused connection also logs a bare 2 on the client.
- Client ENI shows SYN ACCEPT, no reverse record: the drop is past the client ENI. Check the
  server ENI's logs.
- Server ENI shows SYN REJECT, or nothing at all: the server SG or NACL inbound (REJECT), or a
  routing problem before the server (nothing logged).
- Server ENI shows SYN ACCEPT and SYN-ACK (18/19) ACCEPT, but the client never sees it: the return
  path is broken (route back via a different path, or a stateful firewall seeing only one
  direction).
- Response REJECTed on either ENI: a NACL is missing the ephemeral return range.

**PCAP:** "never got a SYN-ACK" at the client. Look for "SYN-ACK did not reach the client" at
the server.

**Causes:** SG inbound, NACL in or out (ephemeral ports), route table missing or wrong next hop,
TGW route table association or propagation, inspection appliance with asymmetric routing,
target down.

**Confirm:** describe-security-groups (inbound on the server, outbound on the client),
describe-network-acls (both subnets, both directions), describe-route-tables (both subnets),
TGW routes for both CIDRs.

## 2. "Connection refused"

**FL:** SYN (2) answered by RST (4), both ACCEPT.
**PCAP:** RST/ACK in response to SYN ("refused with RST").
**Cause:** reachable, but nothing is listening on that IP:port, or a host firewall REJECT rule,
or a middlebox sending RST. **Not** a security group or NACL: those drop silently.
**Confirm:** on the host, run `ss -lntp` (Linux) or `Get-NetTCPConnection -State Listen` (Windows).
Check the bind address (127.0.0.1 vs 0.0.0.0) and the host firewall.

## 3. "Works one way, not the other" / ping fails one direction

**FL:** Request ACCEPT plus response REJECT on the same ENI is the documented NACL signature
(pair the two directions of the 5-tuple on the same ENI).
**Cause:** NACL outbound (or inbound) lacks a rule for the return traffic. For TCP/UDP that's
usually ephemeral ports 1024-65535. For ping, it's ICMP echo-reply.
**Confirm:** describe-network-acls for the subnet. Read the rules in order: the lowest number
wins, and there's an implicit deny at `*`.

**No REJECT anywhere, but the reply never arrives:** the return path is asymmetric. Check the
route back to the source CIDR from the server's subnet (and its TGW route table), and whether a
stateful firewall or appliance sees only one direction. Remember that a NACL is evaluated on
each subnet the packet crosses: the client's and the server's.

## 4. Intermittent drops / slow transfers

**PCAP:** retransmission rate, dup-ACK runs, sequence gaps, zero windows.
- Zero windows: the receiver application is slow. Not the network.
- Retransmissions plus gaps: loss. Check the ENA counters on **both** instances:
  `bw_*_allowance_exceeded`, `pps_allowance_exceeded`, `conntrack_allowance_exceeded`.
- Only large segments retransmitted: go to playbook 5.
- **No loss and no zero window, but slow: suspect a window limit, not "healthy".** Bursts at
  line rate followed by idle gaps that repeat about once per round trip mean the sender is
  ACK-clocked and limited by its congestion window, its send buffer, or the receive window.
  Throughput tops out at about **window / RTT**. RFC 7323: without window scaling the window
  maxes out at 64 KiB, and on paths where bandwidth × delay is larger, the receive window
  limits throughput. Without the handshake the scale is unknown, so the receive window can't be
  ruled out. Missing zero-window flags don't mean there's no window pressure. With well under
  one RTT of data, also allow for an app- or rate-limited sender (for example a rate-capped
  test tool). [Inferred]
  - Confirm (the user runs these; they're read-only or test-only):
    - `ss -ti` on the sender: `-i` shows internal TCP information, including `rtt`, `wscale`,
      `mss` and `rto` (ss(8)).
    - `ping` or `mtr` for RTT and hop count.
    - A throughput test repeated with parallel streams or a bigger window. With iperf2:
      `-P <n>` runs parallel client threads, `-w <size>` sets the TCP window (socket buffer)
      size, and `-e` reports cwnd and RTT per interval (iperf2 man page). Its default port
      is 5001, which tcpdump shows as `commplex-link`.
    - If parallel streams or a bigger window raises throughput, the limit is per-flow
      windowing, not the path.

**FL:** look for SKIPDATA and for REJECTs on the same 5-tuple in the middle of the transfer
(`accepted-then-rejected`, which can mean a conntrack timeout or exhaustion). Use the per-minute
top-flows and bytes-over-time queries to line a spike up with the slow window. ACCEPT in both
directions with normal volume does **not** clear the network for slowness: flow logs can't show
loss, retransmissions or latency.

**Causes:** instance bandwidth or PPS allowance, conntrack exhaustion (many short or idle
connections, asymmetric routing), an appliance at capacity, cross-AZ path through a congested
middlebox. [Heuristic: correlate timestamps across all three sources before concluding.]

## 5. Path MTU black hole ("small requests work, large responses hang")

**PCAP:** large (>1500) segments retransmitted while small ones succeed. MSS 8961 in the SYN
(9001 MTU sender). No ICMP "fragmentation needed" or "packet too big" seen, or seen at the
router but not the sender.
**Documented limits:**
- **Site-to-Site VPN: maximum MTU 1446 and MSS 1406,** or less depending on the encryption
  algorithm and NAT-T (for example AES-CBC with NAT-T: MTU 1422, MSS 1382). Jumbo frames aren't
  supported, and **Site-to-Site VPN does not support Path MTU Discovery** (VPN quotas page and
  customer gateway best practices).
- 1500 over an internet gateway, and between Regions unless a transit gateway is used. 8500
  over inter-Region VPC peering (EC2 MTU page). The EC2 page also lists VPN under its 1500 limit;
  the VPN-specific 1446 figure is the stricter one, so use it.

**Causes:** a sender's segments exceed the path MTU with DF set, and the ICMP signal never
reaches the sender. That's either because ICMP type 3 code 4 / ICMPv6 type 2 is blocked by an
SG, NACL or appliance, or, over Site-to-Site VPN, because PMTUD isn't supported at all.

**Fix options (recommend; don't apply).** Order them by path:
- **Over Site-to-Site VPN** (AWS customer gateway best practices): clamp TCP MSS on the customer
  gateway to the value for the algorithm in use, fragment packets *before* encryption, and reset
  the DF flag on the customer gateway if it supports that. A per-route or instance MTU of 1446
  or lower is the host-side alternative. Don't rely on allowing ICMP fragmentation-needed, since
  there's no PMTUD over the VPN.
- **Over an IGW or inter-Region path:** allow ICMP fragmentation-needed / packet-too-big back to
  the sender (SG and NACL), clamp MSS on the appliance, or set a per-route or instance MTU of
  1500 for that path.

## 6. Resets on idle or long-lived connections

**PCAP:** RST after an idle gap of about 350 s or more. Check `frame.time_relative` (or
`tcp.time_delta`) of the RST against the previous packet in the stream.
**Documented:**
- NLB TCP listeners have an idle timeout set by the listener attribute
  `tcp.idle_timeout.seconds`: 60 to 6000 s, **default 350 s** (ELB ListenerAttribute API).
  Read the current value with `aws elbv2 describe-listener-attributes --listener-arn <arn>`.
- A 350 s default SG conntrack TCP established timeout on Nitro v6 instances. NAT gateways also
  track connections.

**Confirm with NLB metrics** (CloudWatch `AWS/NetworkELB`, statistic Sum):
`TCP_ELB_Reset_Count` (RSTs generated by the load balancer, which points at its idle timeout),
compared with `TCP_Target_Reset_Count` and `TCP_Client_Reset_Count` (RSTs from targets or
clients, forwarded by the load balancer). Use `cloudwatch get-metric-data`, which is read-only.
**Fix:** TCP keepalives under 5 minutes (AWS recommendation), connection-pool max-idle under the
timeout, or set the ENI idle connection-tracking timeout `TcpEstablishedTimeout` (60 to
432000 s). It can be set at launch or changed on an existing, non-requester-managed ENI
("Modify network interface attributes"). That's a mutating change: recommend it, don't run it.

## 7. DNS failures

**FL:** usually shows nothing. Traffic to the Amazon DNS server is **not logged**. A custom DNS
server's traffic is logged.
**PCAP:** unanswered queries, NXDOMAIN or SERVFAIL, slow answers.
- NXDOMAIN for a private name: private hosted zone not associated with the VPC, or a Resolver
  forwarding rule shadowing it.
- Unanswered queries to VPC+2: check `linklocal_allowance_exceeded` (per-ENI PPS cap to the
  Amazon DNS server). Add local caching if it's increasing.
- Timeouts to on-prem resolvers: outbound Resolver endpoint SG, routes, DX/VPN path.

If an `aws-vpc-dns-investigation` skill and its MCP server are available, hand off to it for
live resolver probing and pre-change simulation.

## 8. Traffic through NAT gateway, NLB, or EKS: "whose traffic is this?"

**FL:** on a zonal NAT gateway ENI, the original instance is `srcaddr` on the
**instance -> NAT** leg (`dstaddr` = NAT private IP, `pkt-dstaddr` = the internet destination).
That works even in the default v2 format. On the NAT -> internet leg, `srcaddr` and
`pkt-srcaddr` are both the NAT IP, so they can't identify the instance. See `vpc-flow-logs.md`
for the full pattern and `flow-log-queries.md` for the query. EKS pods appear in the `pkt-*`
fields. Records
from AWS-managed ENIs can show `account-id` = `unknown`. With client IP preservation, `pkt-*`
may show the client IP.
**Confirm:** describe-network-interfaces to map the ENI to its owner (`InterfaceType`,
`RequesterId`, `Description`).

## 9. Suspected scanning or unexpected sources

**FL:** one source REJECTed across many distinct dst:port (`possible_scans`), or REJECTs from
outside the expected CIDRs.
**Action:** report only; don't block. Recommend that the user verify the source (internal
scanner, health checker, misconfigured client) and consider GuardDuty findings.

## 10. Inspection / appliance paths (GWLB, Network Firewall)

**PCAP on the appliance:** GENEVE 6081 outer header (GWLB). VXLAN 4789 inner header if the
traffic is mirrored. Wireshark decodes both; filter inner headers with `ip.addr#2`.
**Look for:** one direction only reaching the appliance (asymmetric routing, which breaks
stateful inspection), or SYN in and nothing out (appliance policy drop).
**Confirm:** route tables in the consumer, endpoint and appliance subnets. Return routes must
send traffic back through the same GWLB endpoint or AZ. For routing-path questions, use the
`aws-routing` skill.

---

## Reporting checklist

1. **Evidence source** for every finding: FL (which ENI, time window), PCAP (capture point),
   AWS config (which describe call). Label each one Observed, Inferred, or [Heuristic].
2. **Coverage gaps:** SKIPDATA intervals, traffic types flow logs don't record, one-sided
   captures, truncated snaplen, missing `tcp-flags` or `flow-direction` fields.
3. **Most likely cause**, plus what would disprove it.
4. **Read-only confirmation steps** (commands above).
5. **Recommended change** (described, never applied), with blast radius and a rollback plan.
   Describe rollback in words. If you show a command, label it **mutating, for the change
   record, not to run now**.
