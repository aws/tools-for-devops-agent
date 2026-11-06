# Packet Capture Analysis - tcpdump, Wireshark, tshark on AWS

Use this when the user has, or needs, a packet capture. Flow logs show what was allowed or
rejected per interval. A capture shows what actually happened on the wire at one point. The
capture point matters: always ask **where** it was taken.

## References

- [EC2 network MTU](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/network_mtu.html)
- [Security group connection tracking](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-connection-tracking.html)
- [ENA network performance metrics](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html)
- [Traffic Mirroring packet format](https://docs.aws.amazon.com/vpc/latest/mirroring/traffic-mirroring-packet-formats.html)
- [Gateway Load Balancer overview (GENEVE 6081)](https://docs.aws.amazon.com/elasticloadbalancing/latest/gateway/introduction.html)

## Getting a useful capture

Ask for both ends if possible: client side and server side, time-synced. One-sided captures
can't tell "never arrived" from "arrived and was dropped by the host".

Linux EC2 (`-s 0` captures full packets; `-C`/`-W` gives a rotating ring buffer):

```
sudo tcpdump -i any -s 0 -nn -w /tmp/cap.pcap host 10.0.2.20 and port 443
sudo tcpdump -i eth0 -s 0 -nn -C 100 -W 10 -w /tmp/ring.pcap 'tcp[tcpflags] & (tcp-syn|tcp-rst) != 0'
```

- `-i any` writes Linux cooked (SLL/SLL2) frames. Wireshark and tshark read both.
- Prefer a BPF filter over capturing everything on busy hosts.

Windows EC2 (built-in Packet Monitor; Microsoft `pktmon` docs):
- `pktmon start --capture`, reproduce the problem, then `pktmon stop`. The log goes to
  `PktMon.etl`: circular, 512 MB by default.
- `--pkt-size` sets the bytes kept per packet. The **default of 128** already gives a
  headers-only capture; `0` keeps whole packets, so avoid it unless payloads are needed.
- Convert with `pktmon etl2pcap PktMon.etl --out cap.pcapng` for Wireshark or tshark.
- **Drops inside the Windows stack:** capture with `--type drop`, or convert with
  `pktmon etl2pcap PktMon.etl --drop-only --out drops.pcapng`. The pcapng output doesn't
  mark which packets were dropped, so make a separate drop-only file.
- Or use Wireshark/dumpcap if they're installed.

On busy hosts, increase the capture buffer to avoid capture-side drops (`tcpdump -B <KiB>`).
Drops show up later as `tcp.analysis.ack_lost_segment` ("ACKed unseen"), which isn't network
loss.

Containers and EKS: capture inside the pod network namespace (`kubectl debug` with a tooling
image, or `nsenter -t <pid> -n tcpdump ...` on the node). Pod IPs appear here. In flow logs they
appear only in `pkt-srcaddr`/`pkt-dstaddr`.

Where you can't run tcpdump (appliances, or to avoid touching the host), use **VPC Traffic
Mirroring** to send a copy of ENI traffic to a target. Documented packet format:

- Mirrored packets are **VXLAN-encapsulated, destination UDP port 4789**. The outer source is
  the mirror source ENI's primary IP. The outer destination is the target (an appliance, NLB, or
  GWLB endpoint).
- The VNI is caller-chosen and not authenticated. Don't treat it as a trust boundary.
- Through a Gateway Load Balancer target, there is an **outer GENEVE (UDP 6081)** around the
  **inner VXLAN**. Wireshark decodes both by default on those ports.
- Remember: flow logs record the mirror target's traffic, not the mirrored source traffic.

## Getting the capture to the agent

The agent can't read binary pcap/pcapng files, and chat doesn't accept them as attachments.
Ask the user to convert the capture to text with tshark (or tcpdump) using the exact commands
in `preparing-evidence.md`. Then analyze the text output: Wireshark's statistics, expert info,
and the header-only problem-packet CSV.

## Wireshark / tshark

See **`wireshark-analysis.md`** for the expert method. It covers Wireshark's TCP analysis flag
definitions and their precedence, `tcp.completeness`, offload artifacts, the display filter
language, a verified filter cookbook, and tshark statistics recipes.

Report findings with Wireshark's own `tcp.analysis.*` names and a display filter, so the user
can reproduce each one in Wireshark.

For encapsulated captures (VXLAN 4789 from Traffic Mirroring, GENEVE 6081 from GWLB), filter
inner headers with the layer operator, for example `ip.addr#2 == 10.0.1.10`.

Installing Wireshark on Windows: `winget install WiresharkFoundation.Wireshark` (package ID
confirmed with `winget search`; tshark ships with it).

## Reading TCP failure signatures

Packet sizes in a host capture can be misleading. With TSO/GRO offload, the capture shows
super-segments larger than the MSS (Wireshark flags these as `tcp.options.mss.exceeded`, "common
with TSO"). Rule out offload before calling an MTU problem.

| Signature at the capture point | Likely meaning |
|---|---|
| SYN, SYN retransmits (about 1 s, 2 s, 4 s ...), no reply | Silent drop between here and the server: SG, NACL, firewall, a route blackhole, or a server that's down. Security groups and NACLs **drop** and never send RST or ICMP. |
| SYN then RST/ACK from the server | Reachable, port closed or host firewall REJECT. An SG would not produce this. |
| SYN in, SYN-ACK out, SYN retransmitted (server-side capture) | SYN-ACK lost on the return path: asymmetric routing through a stateful device, a NACL on ephemeral ports, or wrong return route. |
| Large segments retransmitted, small ones succeed | Path MTU black hole (see MTU below). |
| Many retransmissions, with dup-ACK runs of 3 or more | Loss on the path. Check ENA `*_allowance_exceeded` counters on both instances. |
| Zero window from one side | The receiving application isn't reading. An endpoint issue, not the network. |
| RST after a long idle gap | An idle timeout on a tracked flow. NLB TCP listeners default to **350 s** (listener attribute `tcp.idle_timeout.seconds`, 60 to 6000 s). The default SG connection-tracking TCP established timeout on Nitro v6 instances is **350 s** (432000 s on other instance types). Confirm an NLB-generated reset with `TCP_ELB_Reset_Count`. Fix with TCP keepalives under 5 minutes, connection-pool idle limits under the timeout, or a timeout change (recommended, not applied). |
| ICMP admin-prohibited | A router or firewall actively rejecting traffic (not an SG) |
| TTL-expired ICMP for normal traffic | Routing loop |

## MTU facts (documented)

- All EC2 instance types support 1500 MTU. Current-generation types support jumbo frames
  (9001 MTU).
- **1500 bytes**: traffic over an internet gateway, and between Regions unless a transit
  gateway is used (EC2 MTU page).
- **Site-to-Site VPN: maximum MTU 1446 and MSS 1406,** lower by encryption algorithm and NAT-T.
  Jumbo frames aren't supported, and **Path MTU Discovery isn't supported** (VPN quotas page and
  customer gateway best practices). The EC2 page lists VPN under 1500, but the VPN-specific
  figure is the stricter one.
- **8500 bytes**: inter-Region VPC peering.
- Direct Connect private and transit VIFs support jumbo frames. See the DX MTU docs for
  per-VIF values.
- Oversized packets are fragmented, or **dropped if DF is set**. PMTUD relies on ICMP "fragmentation
  needed" (IPv4 type 3 code 4) and ICMPv6 "packet too big". If SGs/NACLs or appliances block
  those, you get a black hole.
- Egress fragments over **1024 PPS per ENI** are dropped (visible as `pps_allowance_exceeded`,
  ENA Linux driver 2.13.3+ can change this with fragment proxy mode).

MSS in the SYN reveals the sender's interface MTU: MSS 8961 means MTU 9001, MSS 1460 means
MTU 1500 (IPv4, no options).

## Instance-level drops that look like network loss

Check these on both instances when retransmissions are high (`ethtool -S eth0` on Linux, "ENA
Packets Shaping" perf counters on Windows):

- `bw_in_allowance_exceeded` / `bw_out_allowance_exceeded`: aggregate bandwidth over the
  instance maximum
- `pps_allowance_exceeded`: bidirectional PPS over the instance maximum
- `conntrack_allowance_exceeded`: tracked-connection limit hit, so new connections drop
  (`conntrack_allowance_available` shows headroom)
- `linklocal_allowance_exceeded`: PPS to the Amazon DNS server, IMDS, or Time Sync over the
  per-ENI maximum. This explains intermittent DNS timeouts to the VPC resolver that flow logs
  can't show. It doesn't affect custom DNS resolvers.

Connections that are automatically tracked even when SG rules wouldn't require it include
traffic through NAT gateways, NLBs, Network Firewall endpoints, interface VPC endpoints,
Global Accelerator, egress-only IGWs, and Lambda Hyperplane ENIs.

## Privacy and handling

Captures contain payloads (credentials, tokens, PII). Ask only for header-field exports
(`preparing-evidence.md`), never payloads or followed streams. Chat attachments are visible to
everyone in the Agent Space. Quote only the minimum needed in reports.
