# Wireshark / tshark Expert Analysis

How to analyze a capture the way an experienced Wireshark analyst does: method first, then
Wireshark's own TCP analysis, filters, and statistics. Behavior and field names come from the
Wireshark sources listed below (field names checked against the 4.6.x display-filter
reference). Items marked **[Not verified this session]** are standard practice that I couldn't
confirm against a fetched source. Confirm them on the installed version before relying on them.

## Sources (retrieved and used)

- [User's Guide 7.5: TCP Analysis](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvTCPAnalysis.html): flag definitions, precedence, completeness
- [User's Guide 7.4: Expert Information](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvExpert.html)
- [User's Guide 6.4: Building Display Filter Expressions](https://www.wireshark.org/docs/wsug_html_chunked/ChWorkBuildDisplayFilterSection.html)
- [User's Guide 11.5: Decode As](https://www.wireshark.org/docs/wsug_html_chunked/ChCustProtocolDissectionSection.html)
- [tshark(1) man page](https://www.wireshark.org/docs/man-pages/tshark.html)
- Display filter reference: [tcp](https://www.wireshark.org/docs/dfref/t/tcp.html), [ip](https://www.wireshark.org/docs/dfref/i/ip.html), [icmp](https://www.wireshark.org/docs/dfref/i/icmp.html), [dns](https://www.wireshark.org/docs/dfref/d/dns.html), [tls](https://www.wireshark.org/docs/dfref/t/tls.html), [vxlan](https://www.wireshark.org/docs/dfref/v/vxlan.html), [geneve](https://www.wireshark.org/docs/dfref/g/geneve.html)
- [pcap-filter(7)](https://www.tcpdump.org/manpages/pcap-filter.7.html) and [tcpdump(1)](https://www.tcpdump.org/manpages/tcpdump.1.html) for capture filters

---

## 1. Method: how an expert works a capture

1. **Pin down the capture point before reading a single packet.** Wireshark itself warns that
   interpretations "may be different whether the capture was performed server side, client side
   or anywhere in the middle". Ask where it was taken, or infer it (step 4).
2. **Treat Expert Info as a hint, not a verdict.** Per the User's Guide: "Expert information is
   the starting point for investigation, not the stopping point... absence of expert information
   doesn't necessarily mean everything is OK."
3. **Get the overview first** (`-q` suppresses per-packet output):
   ```
   tshark -r cap.pcapng -q -z io,phs              # protocol hierarchy
   tshark -r cap.pcapng -q -z conv,tcp            # TCP conversations (bytes, duration)
   tshark -r cap.pcapng -q -z endpoints,ip
   tshark -r cap.pcapng -q -z expert,note         # expert items of severity note and above
   ```
4. **Locate the capture point with the iRTT split** [heuristic, standard practice]. In a
   complete handshake, SYN to SYN-ACK is the round trip from the capture point to the server,
   and SYN-ACK to ACK is the round trip to the client. Whichever leg is tiny is the side the
   capture sits next to. `tcp.analysis.initial_rtt` gives the total. Compute the split from
   the `frame.time_relative` values of the SYN, SYN-ACK and ACK.
   **No handshake in the capture?** Estimate it instead [Heuristic]:
   - **Round trip to the receiver:** the time from a data segment to the ACK that covers it, at
     the capture point.
   - **Round trip to the sender:** how old the `TSecr` a sender echoes is, compared with the
     peer's current `TSval`. Check the timestamp tick rate against frame times first (it's often
     1 ms per tick). This is approximate: the echo can lag by a tick or two.
   - **Hop count:** received TTL below a common starting value (64, 128 or 255) estimates hops.
     A host's *own* outbound packets carry the starting TTL, and with offload they also show
     `tcp.options.mss.exceeded` or `tcp.checksum.partial`. If neither side shows those, the
     capture probably wasn't taken on either host.
5. **Isolate the failing stream** (`tcp.stream == N`). Then read it in time order with
   `tcp.time_delta` (time since the previous frame in this TCP stream) to find the stall.
6. **Explain every flagged packet in context.** One retransmission doesn't make a diagnosis; a
   pattern does, such as RTO-style retransmits after silence, or loss limited to large segments.
7. **Prove it from the other side when you can.** A two-sided capture turns "probably dropped"
   into "left A, never reached B".

## 2. Wireshark TCP analysis flags (the core vocabulary)

Wireshark tracks each TCP session and flags problems under "SEQ/ACK analysis". The analysis
runs once per packet, in packet-list order, when the file is opened. The "Analyze TCP sequence
numbers" preference toggles it. Filter on any flag with `tcp.analysis.<name>`, or on all of
them with `tcp.analysis.flags`.

Definitions are paraphrased from the User's Guide. "Next expected seq" means the last-seen seq
plus the segment length.

| Filter | Set when (Wireshark definition, abridged) | What it usually means |
|---|---|---|
| `tcp.analysis.retransmission` | Not a keep-alive; length > 0 or SYN/FIN; next expected seq > this seq | The sender resent data it had already sent. After a pause, it's an RTO: loss with no dup-ACK recovery. SYN retransmissions mean no reply to the SYN. |
| `tcp.analysis.fast_retransmission` | As above, plus at least 2 dup ACKs in reverse (or more than 2 MSS jumped), seq = next expected ack, last ACK seen < 20 ms ago. **Supersedes** Out-Of-Order and Retransmission. | Loss detected by the receiver via dup ACKs. Recovery is quicker than RTO. |
| `tcp.analysis.spurious_retransmission` | Length > 0, no SYN/FIN, not keep-alive, data already ACKed by the reverse direction. **Supersedes** Fast Retransmission, Out-Of-Order and Retransmission. | Unnecessary resend: the sender didn't see the ACK in time (ACK loss or delay, or RTO too short). |
| `tcp.analysis.out_of_order` | Next expected seq > this seq, the segment's next seq differs from it, and it arrived within the iRTT (default 3 ms if no iRTT). **Supersedes** Retransmission. | Reordering, for example across parallel paths. Ambiguous with fast retransmission; see the preferences in section 3. |
| `tcp.analysis.lost_segment` | This seq > next expected seq ("Previous segment not captured") | A hole before this packet. It's loss upstream of the capture point **or** the capture missed it. "Common at capture start". |
| `tcp.analysis.ack_lost_segment` | This ACK > next expected ack for the reverse direction ("ACKed unseen segment") | The receiver ACKed data the capture never saw. **The capture missed packets.** This is not evidence of network loss. |
| `tcp.analysis.duplicate_ack` | Length 0; window non-zero and unchanged (or valid SACK); connection established; no SYN/FIN/RST | The receiver is still waiting for a missing segment. `tcp.analysis.duplicate_ack_num` is the count. |
| `tcp.analysis.keep_alive` | Length 0 or 1; seq = next expected - 1; no SYN/FIN/RST. **Supersedes** all retransmission types and Out-Of-Order. | A keepalive probe. Normal, and useful evidence of idle periods. |
| `tcp.analysis.keep_alive_ack` | Length 0; window unchanged; seq/ack unchanged; the previous reverse packet was a keep-alive. **Supersedes** Dup ACK and ZeroWindowProbeAck. | The peer is alive |
| `tcp.analysis.zero_window` | Receive window 0, no SYN/FIN/RST | **The receiver is full.** In most cases it's a performance or capacity problem on the receiving end. Resuming can take a long time. |
| `tcp.analysis.zero_window_probe` | seq = next expected, length 1, last reverse window was 0 | The sender probing a closed window |
| `tcp.analysis.zero_window_probe_ack` | Length 0, window 0, seq/ack unchanged, the previous reverse packet was a probe. **Supersedes** Dup ACK. | The window is still closed |
| `tcp.analysis.window_full` | Segment size exceeds the reverse direction's window | The sender is limited by the receiver's window, which is often too small for the bandwidth-delay product |
| `tcp.analysis.window_update` | Length 0; window non-zero and changed; seq/ack unchanged; no SYN/FIN/RST | The receiver opened its window. After a zero window, this marks the recovery point. |
| `tcp.analysis.reused_ports` | SYN (not SYN+ACK) for an existing conversation with a different ISN | Port reuse. It's only a problem if a middlebox (NAT, conntrack) still holds the old state. |

**Counting: flags can overlap.** "Supersedes" in the User's Guide describes how Wireshark
classifies a packet, but it does **not** mean a packet carries only one filter flag. Verified on
tshark 4.6.9: a spurious retransmission carries **both** `tcp.analysis.spurious_retransmission`
and `tcp.analysis.retransmission`, with two expert items on the same frame. So:
- `tcp.analysis.retransmission` counts include spurious ones. For "real" (RTO-style) resends,
  use `tcp.analysis.retransmission && !tcp.analysis.spurious_retransmission`.
- For "all resends", filter on `tcp.analysis.retransmission || tcp.analysis.fast_retransmission`.
  Don't add the spurious count on top, or you'll double-count.
- **Out-of-order segments do not** also carry `tcp.analysis.retransmission`. That was verified
  on 22 out-of-order segments in 4 Wireshark test captures (tshark 4.6.9); each had only its
  own expert message.
- Whether **fast retransmissions** also carry `tcp.analysis.retransmission` hasn't been checked
  against a real capture (none of the public test captures contained one). Count each filter
  separately and say so if it matters.

Related, verified fields:
- `tcp.analysis.initial_rtt` (iRTT), `tcp.analysis.ack_rtt` (RTT to ACK the segment),
  `tcp.analysis.rto` / `tcp.analysis.rto_frame` (time since the original segment, for
  retransmissions)
- `tcp.analysis.bytes_in_flight` (watch it plateau at the receiver window, which means
  window-limited)
- `tcp.analysis.acks_frame`, `tcp.analysis.duplicate_ack_frame`, `tcp.analysis.duplicate_ack_num`
- `tcp.time_delta`, `tcp.time_relative` (per-stream timing), `tcp.stream`, `tcp.len`, `tcp.nxtseq`
- `tcp.window_size` (calculated, scaled), `tcp.window_size_value` (raw),
  `tcp.window_size_scalefactor`
- `tcp.options.mss_val`, `tcp.options.wscale.shift`, `tcp.options.wscale.multiplier`.
  The window scale is a power of two: shift *n* multiplies the raw window by 2^*n* (maximum
  shift 14). It's sent only in the SYNs and is fixed for the connection (RFC 7323), so
  without the handshake the real window is unknown. A raw value only gives a lower bound,
  from the bytes in flight.
- `tcp.reset_cause`, `tcp.connection.syn`, `tcp.connection.synack`, `tcp.connection.rst`,
  `tcp.connection.fin`

## 3. Conversation completeness and ambiguity controls

> **tshark needs two-pass (`-2`) for completeness.** Verified on tshark 4.6.9: in a normal
> single pass, the value builds up packet by packet (0, 1, 3, 7, 15, 31), so early packets of a
> healthy connection show `1` and a filter like `tcp.completeness == 1` matches the first SYN of
> *every* connection. With `-2`, every packet carries the final value for its conversation. For
> example, a plain RST-only stream shows 40 (DATA + RST). Always write
> `tshark -2 -r cap.pcapng -Y "tcp.completeness == 1"`.

`tcp.completeness` is a per-conversation bitmask: **1 SYN, 2 SYN-ACK, 4 ACK, 8 DATA, 16 FIN,
32 RST**.

| Filter | Finds |
|---|---|
| `tcp.completeness == 1` (tshark: with `-2`) | SYN only: no answer at all |
| `tcp.completeness == 7` | Handshake only, no data, no close |
| `tcp.completeness == 31 or tcp.completeness == 47 or tcp.completeness == 63` | Complete with data, closed by FIN, RST or both (Wireshark's own example) |
| `tcp.flags.reset == 1 && tcp.completeness.syn-ack == 0` (tshark: with `-2`) | Refused before any SYN-ACK |
| `(tcp.completeness.fin==1 \|\| tcp.completeness.rst==1) && tcp.completeness.str contains "DASS"` | "Complete, WITH_DATA" (Wireshark example) |

`tcp.stream.client.contiguity_count` and `tcp.stream.server.contiguity_count` (4.6+) show 1 for
a contiguous stream, 0 for no segments, and 2 or more when data is missing. Use them to decide
whether a stream is good enough for data extraction.

Ambiguity is built in. Wireshark offers a preference "Fast Retransmission supersedes
Out-of-Order interpretation", and an "Enable Distal Disambiguation Algorithm" preference. When
the iRTT is known, the distal algorithm calls a resend a fast retransmission if its gap is 0.8x
to 2.4x the iRTT and there were enough dup ACKs, an RTO-retransmission if it's over 2.4x, and
out-of-order otherwise. Say which interpretation you're using when the counts are borderline.
Assume Wireshark's defaults unless the user says they changed these preferences.

## 3a. ECN: congestion without loss

Source: [RFC 3168](https://www.rfc-editor.org/rfc/rfc3168.html). Fields verified in the
Wireshark tcp and ip display filter references.

| Signal | Filter | Meaning |
|---|---|---|
| ECE and CWR both set on a SYN (`tcp.flags` 0x00c2) | `tcp.flags.syn==1 && tcp.flags.ece==1 && tcp.flags.cwr==1` | **Negotiation only** ("ECN-setup SYN"): the host is ECN-capable. Not congestion. |
| ECE set, CWR clear on the SYN-ACK | `tcp.flags.syn==1 && tcp.flags.ack==1 && tcp.flags.ece==1` | The peer agrees to use ECN |
| CE codepoint in the IP header | `ip.dsfield.ecn == 3` | A router marked congestion **instead of dropping** the packet |
| ECE on ACKs | `tcp.flags.ece==1 && tcp.flags.syn==0` | The receiver echoing a CE mark it received |
| CWR on data | `tcp.flags.cwr==1 && tcp.flags.syn==0` | The sender confirming it reduced its congestion window |

How to read it:
- The sender treats ECE "as if a packet had been dropped" (RFC 3168), so throughput can fall with
  **zero retransmissions**. Don't report loss.
- Look for the CE marks themselves (`ip.dsfield.ecn == 3`). The capture point needs to be where
  they're visible, on the receiver side of the marking router. If ECE keeps repeating after CWR
  with no CE seen, report it as an [Heuristic] observation of endpoint behavior, not proven
  congestion.
- Count with aggregates, not by hand. The ECN columns are in the `preparing-evidence.md` exports.
  If a figure (count, range, rate) was read from CSV rows instead of a tshark aggregate, say so
  and mark it approximate.

## 4. Artifacts that fool non-experts

- **Offload: TSO, GSO, GRO, LRO.** Captures taken on the sending or receiving host show
  super-segments larger than the MSS. Wireshark has a dedicated flag:
  `tcp.options.mss.exceeded`, described as "This packet's length exceeds MSS (common with TSO or
  incomplete conversations)". Never diagnose MTU from packet sizes in such a capture.
- **Checksum offload.** `tcp.checksum.partial` is "Partial (pseudo header) checksum (likely
  caused by "TCP checksum offload")". Bad checksums on locally sent packets are normal on hosts
  with offload. Don't report them as corruption.
- **Capture-side drops.** `tcp.analysis.ack_lost_segment` and gaps that nobody retransmits
  point at the capture, not the network. Re-capture with a larger buffer
  (`tcpdump -B <KiB>`), a tighter filter, or on a less busy host.
  - **In tcpdump text** (no Wireshark flags), a hole is capture-side when: (a) the peer ACKs past
    it, (b) no later segment re-covers that range, and (c) if the sender's IP ID goes up by one
    per segment, the ID gap matches the number of missing segments [Heuristic]. Wireshark's
    `ack_lost_segment` fires only when an ACK goes beyond the highest sequence number seen, so
    it can flag far fewer packets than there are holes.
  - tcpdump prints "packets dropped by kernel" when it stops: packets the OS capture mechanism
    dropped for lack of buffer space (tcpdump(1)). Ask for that line.
  - Ask whether a pasted file is an **edited excerpt**. Deleted lines look exactly like capture
    drops.
- **Start-of-capture noise.** `lost_segment` and `ack_lost_segment` are "common at capture
  start". Ignore them on the first packets of mid-stream conversations.
- **One-sided captures.** "No response" at the client and "never arrived" at the server are
  different conclusions. Only a two-sided capture separates them.
- **Snaplen truncation.** `frame.cap_len < frame.len` means truncated packets. Header analysis
  still works; payload dissection (TLS, DNS, HTTP) may not.

## 5. Display filter language essentials (verified)

- Operators come in English and C-like forms: `eq/==`, `ne/!=`, `===` (all equal),
  `!==` (any not equal), `gt/>`, `lt/<`, `ge/>=`, `le/<=`, `contains`, `matches/~` (PCRE).
  Since 3.6, `!=` means "**all** not equal". So `ip.addr != 10.0.0.5` excludes any packet with
  that address on either side.
- Logic: `and/&&`, `or/||`, `xor/^^`, `not/!`. Group with parentheses.
- CIDR works: `ip.addr == 10.0.0.0/16`, and `ipv6.addr` matches subnets the same way.
- Membership: `tcp.port in {80, 443, 8080}`, ranges `tcp.port in {443, 4430..4434}`,
  `ip.addr in {10.0.0.5 .. 10.0.0.9}`. A range inside `in` tests a single field; plain `>=`
  and `<=` on `tcp.port` match **either** port.
- **Layer operator:** `ip.addr#2 == 10.0.1.10` matches only the inner (second) IP header, which
  is essential for VXLAN and GENEVE captures. Ranges like `tcp.port#[2-4]` also work.
- Slices: `eth.src[0:3] == 00:00:83`, `frame[-4:]`. Bitwise: `tcp.flags & 0x02`.
- Functions: `len()`, `count()` (e.g. `count(ip.addr) > 2` finds tunnels and ICMP errors),
  `lower()`, `upper()`, `string()`, `vals()`, `max()`, `min()`, `abs()`, `double()`.
- Arithmetic needs a space before minus (`A - B`). Group with braces:
  `frame.cap_len < { 14 + ip.hdr_len + tcp.hdr_len }` finds truncated TCP options.
- Field references from the selected packet: `frame.time_relative >= ${frame.time_relative} - 300`.
- Boolean fields are *present* whether 0 or 1. Write `tcp.flags.syn == 1`, not `tcp.flags.syn`.
- Absolute-time literals are parsed in **local time**, even for UTC-displayed fields:
  `frame.time >= "2026-01-15 10:00:00"`.

## 6. Filter cookbook for network troubleshooting (all fields verified)

| Question | Display filter |
|---|---|
| Every TCP problem Wireshark flagged | `tcp.analysis.flags && !tcp.analysis.window_update && !tcp.analysis.keep_alive && !tcp.analysis.keep_alive_ack` |
| All resends | `tcp.analysis.retransmission \|\| tcp.analysis.fast_retransmission \|\| tcp.analysis.spurious_retransmission` |
| RTO-style retransmits after more than 1 s | `tcp.analysis.retransmission && tcp.analysis.rto > 1` |
| Loss vs capture gap | `tcp.analysis.lost_segment` vs `tcp.analysis.ack_lost_segment` |
| Receiver-limited | `tcp.analysis.zero_window \|\| tcp.analysis.window_full \|\| tcp.analysis.zero_window_probe` |
| Stalls inside a stream | `tcp.time_delta > 1 && tcp.stream == N` |
| Slow ACKs (RTT over 200 ms) | `tcp.analysis.ack_rtt > 0.2` |
| Handshakes and their iRTT | `tcp.flags.syn == 1 && tcp.flags.ack == 1` (then add the `tcp.analysis.initial_rtt` column) |
| Unanswered connection attempts | `tcp.completeness == 1` (tshark: `-2`, see section 3) |
| Resets (and why, where known) | `tcp.flags.reset == 1` / `tcp.reset_cause` |
| MSS advertised | `tcp.options.mss_val` / jumbo senders: `tcp.options.mss_val > 1460` |
| Offload artifacts | `tcp.options.mss.exceeded \|\| tcp.checksum.partial` |
| Big packets with DF set | `ip.flags.df == 1 && ip.len > 1500` |
| Fragments | `ip.flags.mf == 1 \|\| ip.frag_offset > 0` |
| PMTUD messages (with the next-hop MTU) | `(icmp.type == 3 && icmp.code == 4) \|\| icmpv6.type == 2` (MTU is in `icmp.mtu`) |
| Any ICMP error | `icmp.type.error` (4.6+) / `icmp.type == 3 \|\| icmp.type == 11` |
| Unanswered pings | `icmp.resp_not_found` / `icmp.no_resp` |
| DNS errors | `dns.flags.rcode != 0` |
| DNS queries with no response | `dns.response_missing` (4.4+), or `dns.flags.response == 0 && !dns.response_in` |
| DNS retransmissions | `dns.retransmit_request \|\| dns.retransmit_response` |
| TLS alerts (handshake failures, bad certs) | `tls.alert_message` / `tls.alert_message.desc` |
| TLS ClientHello and SNI | `tls.handshake.type == 1` / `tls.handshake.extensions_server_name == "api.example.com"` |
| TLS client fingerprint | `tls.handshake.ja4` (4.2+) / `tls.handshake.ja3` |
| Traffic Mirroring session | `vxlan.vni == 1234` (outer UDP 4789) |
| GWLB traffic | `geneve` / `geneve.vni` (outer UDP 6081) |
| Inner host in an encapsulated capture | `ip.addr#2 == 10.0.1.10` |

`dns.flags.response` and `dns.flags.rcode` are standard DNS fields. I didn't re-fetch them this
session, but they appear throughout Wireshark's examples.

## 7. tshark recipes (options verified in tshark(1))

```
# Read with a display filter (single pass)
tshark -r cap.pcapng -Y "tcp.analysis.flags"

# Two-pass, needed for forward-looking fields like "response in frame" (dns.response_in)
tshark -r cap.pcapng -2 -R "dns" -Y "dns.flags.response == 0 && !dns.response_in"

# Extract fields as a table (tab-separated, header row)
tshark -r cap.pcapng -Y "tcp.analysis.retransmission" -T fields -E header=y \
  -e frame.number -e frame.time_relative -e ip.src -e ip.dst -e tcp.stream -e tcp.seq -e tcp.len -e tcp.analysis.rto

# Statistics (add -q to suppress per-packet output)
tshark -r cap.pcapng -q -z conv,tcp
tshark -r cap.pcapng -q -z endpoints,tcp
tshark -r cap.pcapng -q -z io,phs
tshark -r cap.pcapng -q -z expert,warn
tshark -r cap.pcapng -q -z "expert,note,tcp"
tshark -r cap.pcapng -q -z dns,tree
tshark -r cap.pcapng -q -z icmp,srt
tshark -r cap.pcapng -q -z http,tree

# Per-second packets and bytes, and per-second retransmissions, for one host
tshark -r cap.pcapng -q -z io,stat,1,"ip.addr==10.0.2.20","tcp.analysis.retransmission && ip.addr==10.0.2.20"

# Aggregates: the field MUST also appear in the filter part (documented quirk)
tshark -r cap.pcapng -q -z io,stat,1,"MAX(tcp.analysis.ack_rtt)tcp.analysis.ack_rtt"
tshark -r cap.pcapng -q -z io,stat,5,"AVG(tcp.analysis.bytes_in_flight)tcp.analysis.bytes_in_flight"

# Follow one stream's payload
tshark -r cap.pcapng -q -z follow,tcp,ascii,3

# Temporary preference override (not saved), or run with a named profile
tshark -r cap.pcapng -o "<prefname>:<value>" ...
tshark -r cap.pcapng -C <profile> ...

# Export transferred objects (HTTP, etc.)
tshark -r cap.pcapng --export-objects http,./objects
```

- `io,stat` needs `.` as the system decimal separator. With `,` the per-filter statistics
  aren't displayed (documented).
- **Decode As** on the command line uses `-d <layer_type>==<selector>,<decode_as_protocol>`.
  That's the template tshark 4.6.9 prints when the syntax is wrong; it accepts a single `=`
  with a warning. For example `-d udp.port==4790,vxlan`. In the GUI it's Analyze > Decode As.
- Preference names for `-o` vary by version. List them with `tshark -G defaultprefs` (the man
  page documents the `defaultprefs` report) rather than guessing.

## 8. Expert Info

Severities, from lowest to highest: **Chat** (blue, normal workflow such as SYN), **Note** (cyan,
notable, such as HTTP 404), **Warn** (yellow, unusual, such as a connection problem), **Error**
(red, serious, such as malformed). Groups include Sequence (retransmission, non-continuous seq),
Malformed, Protocol, Reassemble, Checksum, Response Code, Security, Undecoded, and others. Start
with `-z expert,warn`, then drill into Sequence items with the TCP flags above.

## 9. Capture filters (BPF, at capture time) vs display filters

Capture filters use pcap-filter syntax, which is not display-filter syntax. Verified examples:

```
host 10.0.2.20 and port 443
tcp[tcpflags] & (tcp-syn|tcp-fin) != 0                   # SYNs and FINs only
tcp[tcpflags] & (tcp-rst|tcp-ack) == (tcp-rst|tcp-ack)   # RST+ACK
icmp[icmptype] != icmp-echo and icmp[icmptype] != icmp-echoreply   # ICMP errors etc.
ip[2:2] > 1500                                           # IPv4 packets over 1500 bytes
```

Named ICMPv6 types include `icmp6-packettoobig` and `icmp6-destinationunreach`. `tcpdump -C <size>`
rotates files; the default unit is millions of bytes, and `k/m/g` suffixes are binary.

## 10. Reporting like an expert

For each finding, give:
- The **flag or field** and its count
- The **frame numbers** and the stream, so others can jump to them
- The **filter** that reproduces it
- The **capture point**, and why it doesn't change the conclusion (or why it does)
- **Alternative interpretations** Wireshark itself acknowledges: out-of-order vs fast
  retransmission, and capture gap vs network loss
- What a capture **on the other side** would prove

When the evidence is tshark text output (`preparing-evidence.md`), take counts from Wireshark's
statistics (`-z expert`, `-z conv`, filter counts), not from tallying CSV rows by hand.
