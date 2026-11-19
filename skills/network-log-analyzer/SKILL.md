---
name: network-log-analyzer
description: 'Use this skill when a user is troubleshooting AWS network connectivity: a connection times out, is refused, or resets; traffic flows only one way; flow logs show REJECT and they need to know whether a security group or network ACL caused it; TCP handshakes fail; transfers are slow or retransmit; large packets hang; idle connections drop; or they want top talkers or the real source behind a NAT gateway or EKS pod. Also use it whenever the user shares or describes VPC Flow Logs or a packet capture (tcpdump, Wireshark, tshark), including traffic that is missing from flow logs or unexpected packet sizes in a capture, even if they don''t name the problem. Not for name-resolution failures such as NXDOMAIN, SERVFAIL, or a name resolving to the wrong address; use the VPC DNS investigation skill for those.'
metadata:
  version: "1.0.0"
  author: midakin
  summary: "Troubleshoots connectivity from VPC Flow Logs and packet captures: SG vs NACL rejects, TCP handshake and retransmission analysis, MTU, idle resets."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "Amazon VPC, Amazon EC2, Amazon CloudWatch, Amazon S3"
  aws-devops-agent-skills.technical-domains: "Networking, Observability"
---

# Network Log Analyzer

Turn network evidence into a diagnosis. There are two kinds of evidence:

- **VPC Flow Logs**: what each ENI allowed or rejected per aggregation interval. Query them in
  CloudWatch Logs or Athena, or read an export the user attaches.
- **Packet captures**: what actually crossed the wire at one point. You can't read binary
  pcap/pcapng, and chat doesn't accept them, so the user converts them to text with tshark or
  tcpdump first.

This skill is **read-only**. It never changes security groups, network ACLs, routes, flow logs,
or mirroring sessions.

## Verification rules (mandatory)

- Base every finding on evidence actually present in query results or attached files. Label
  each one **Observed** (directly in the data), **Inferred** (follows from documented AWS or
  Wireshark behavior), or **[Heuristic]** (analysis judgment).
- State assumptions before answering: the **capture point**, the **flow log format** (which
  fields exist), and the **time window** (UTC).
- Check AWS and Wireshark behavior against the reference files. If you can't verify a claim,
  say "I cannot verify this". Only cite URLs listed in the reference files or retrieved during
  the task.
- When the evidence isn't Wireshark output, anything you say Wireshark *would* flag, and any value
  you derive from a pattern (such as the IP ID of an unseen packet), is **Inferred**, not Observed.

## Workflow

Copy this checklist into your working notes and tick each step. Each step depends on the one
before it.

- [ ] Step 1: Classify the evidence path (A, B, or both)
- [ ] Step 2A or 2B: Collect scoped evidence
- [ ] Step 3: Interpret it with documented behavior
- [ ] Step 4: Confirm with read-only checks
- [ ] Step 5: Self-check the findings, then answer in the output format

## Step 1: Classify the evidence path

Decide which path applies before collecting anything:

- **Path A: flow logs reachable in the account.** CloudWatch Logs or S3 with Athena are
  available to you. Query them directly (Step 2A).
- **Path B: the user has or must provide evidence.** The flow logs aren't queryable from here,
  or the evidence is a packet capture (Step 2B).
- **Both**, when a capture exists alongside flow logs. Flow logs show allow and reject per ENI.
  The capture shows what happened on the wire.

If the symptom, endpoints (IPs, ports, protocol) or time window are missing, ask for them
first. Don't start broad unscoped queries.

## Step 2A: Query flow logs

1. Get the format:
   `aws ec2 describe-flow-logs --filter Name=resource-id,Values=<vpc|subnet|eni>`. Read
   `LogFormat` and `LogDestination`. The default v2 format has no `tcp-flags` or
   `flow-direction`. An existing flow log's format can't be changed: to add fields, the user
   creates a new flow log (suggest it; don't create it).
2. Load [references/flow-log-queries.md](references/flow-log-queries.md) and run its scoped
   queries: rejected flows, both directions between the two hosts, and gaps (`logStatus`).
   **Always time-box them**, because Logs Insights and Athena bill by data scanned. Custom
   formats need `parse @message` in the exact field order.
3. For record-level pairing, pull only the failing conversation's records
   (`filter-log-events` with the host as the filter pattern).

## Step 2B: Get evidence from the user

Load [references/preparing-evidence.md](references/preparing-evidence.md). Paste its exact
commands into your reply, and ask for the files in its "What to send" tables. Never refer the
user to the skill's own files by name, because they can't see them:

- **Flow logs:** `LogFormat`, a rejects aggregate (CSV), and the raw records for the failing
  conversation, from both ENIs if possible.
- **Captures:** the tshark overview, the header-only problem-packet CSV, and the handshake CSV.
  Ask for the **capture point**, the capture filter, the snaplen, and whether offload was on.
- Ask for **headers only, never payloads**. Attachments are visible to everyone in the Agent
  Space.

## Step 3: Interpret with documented behavior

**Flow logs.** Load [references/vpc-flow-logs.md](references/vpc-flow-logs.md) to interpret
any flow log record. It holds the field definitions, flag values, address translation, and
traffic that isn't logged. The core rules:

- Request ACCEPT plus response REJECT on the same ENI points to a **network ACL** (NACLs are
  stateless; SGs are stateful).
- A lone REJECT with no reverse traffic could be **the SG or the NACL**. Flow logs can't tell
  which: check the SG first, then the NACL. Never claim certainty, and don't call either one
  "more likely" without configuration evidence.
- `tcp-flags` are OR-ed per record, so match the bit, not one exact value. Pair each SYN with
  what came back: SYN-ACK means answered, RST means refused, nothing means dropped downstream.
- Some traffic is **not logged**, and SKIPDATA intervals hide flows, so a missing record isn't
  proof that traffic didn't happen.
- Behind a NAT gateway or EKS pod, the real source is in specific legs and fields. Check the
  address translation section before naming a source. If the format lacks the `pkt-*` fields,
  say so: an existing flow log's format can't be changed, so adding them takes a new flow log.

**Captures.** Load [references/wireshark-analysis.md](references/wireshark-analysis.md) to read
any tshark or tcpdump output (flag definitions, precedence, capture point, artifacts). Load
[references/packet-capture-analysis.md](references/packet-capture-analysis.md) for TCP
signatures, MTU values, and ENA counters. The core rules:

- **Fix the capture point first** from the handshake timing split.
- Use Wireshark's `tcp.analysis.*` vocabulary. Flags overlap, so separate spurious
  retransmissions and capture gaps from real loss. Expert Info is a hint, not a verdict.
- Offload (TSO/GRO) makes packet sizes meaningless for MTU diagnosis in that capture.
- SGs and NACLs **drop silently**. An RST or ICMP error comes from a host, firewall, or router.
- **No loss isn't the same as healthy.** A window-limited flow shows no retransmissions.
- **Resets after an idle gap** point to an idle timeout (load balancer or connection
  tracking). Always recommend the fix: TCP keepalives, or connection-pool idle limits, shorter
  than that timeout.

**Symptoms.** Load
[references/troubleshooting-playbooks.md](references/troubleshooting-playbooks.md) when the
symptom is a timeout, refusal, one-way traffic, slow transfer, large packets hanging, idle
resets, DNS packets in a capture, or a NAT/EKS source question. It maps each to evidence, causes, and confirmation,
including the MTU and idle-timeout values to compare against.

## Step 4: Confirm with read-only checks

Validate the suspected cause against configuration using read-only calls only (`describe-*`,
`get-*`, `list-*`, `search-*`). For example: `ec2 describe-security-groups`,
`describe-network-acls`, `describe-route-tables`, `describe-network-interfaces`,
`describe-flow-logs`, `describe-nat-gateways`, `describe-instances`,
`search-transit-gateway-routes`, `elbv2 describe-listener-attributes`,
`cloudwatch get-metric-data`, and `cloudtrail lookup-events` (recent changes). Reachability
Analyzer and Traffic Mirroring create resources: suggest them, but don't create them.

Always write the read-only commands out in your answer, with the IDs or filters to use. Do this
even when you ran them yourself, or when the resource isn't in the account you can reach, so
the user can repeat the check.

For why a route was chosen (TGW, Cloud WAN, Direct Connect path selection), use the
`aws-routing` skill if it's available. Name-resolution problems (NXDOMAIN, SERVFAIL, a name
resolving to the wrong address, private hosted zones, Resolver rules) belong to
`aws-vpc-dns-investigation`: hand off to it when it's available. This skill covers DNS only as
evidence: DNS packets in a capture, and the fact that flow logs never record traffic to the
Amazon DNS server.

## Step 5: Self-check before answering

Check each finding before you present it, and fix it if any check fails:

- [ ] Every Observed finding points at a specific record, query result, or frame you actually
  have. If it doesn't, relabel it Inferred or drop it.
- [ ] Counts come from aggregates (Logs Insights or Athena results, tshark `-z` statistics), not
  hand-tallied rows. If a figure was read from rows, say so and mark it approximate.
- [ ] Every AWS or Wireshark behavior you state matches the reference file you loaded. If it
  isn't there and you didn't retrieve a source, say "I cannot verify this".
- [ ] Each query or display filter you show would reproduce the finding on the user's data.
- [ ] Every command you suggest running is read-only.

## Output requirements

**Compact form (the default for conceptual questions).** If the question has no evidence files
and no account data, answer in under about 200 words: the answer, its evidence label, one
read-only check, and the main coverage gap.

**Full form**, when there's evidence or account data to analyze. Every response must include:

1. **Assumptions:** capture point, flow log format and fields, time window, filters applied.
2. **Findings**, most severe first. Each one has its evidence (ENI and time, or file, frame
   and stream), a Wireshark display filter or query that reproduces it, and a label:
   Observed, Inferred, or [Heuristic]. List what the evidence or the user's description directly
   shows as separate **Observed** findings, before any Inferred or [Heuristic] finding that
   interprets them.
3. **Coverage gaps:** SKIPDATA, traffic that isn't logged, missing fields, one-sided or
   truncated captures, and anything outside the exported slice.
4. **Most likely root cause**, and what evidence would disprove it.
5. **Read-only confirmation commands.**
6. **Recommended fix** (described, never applied), with blast radius and rollback. Describe
   rollback in words. If you show a command, label it **mutating, for the change record, not to
   run now**. Recommend testing in non-production first. Investigations need this too: not
   applying a fix doesn't mean not recommending one.

## What this skill does NOT do

- Modify any AWS resource, or run mutating commands.
- Read binary capture files, or ask for packet payloads.
- Prove a negative from incomplete evidence.

## References

Load each file only when its condition applies:

- [references/vpc-flow-logs.md](references/vpc-flow-logs.md): when interpreting any flow log
  record (fields v2 to v11, SG vs NACL inference, tcp-flags, address translation, unlogged
  traffic)
- [references/flow-log-queries.md](references/flow-log-queries.md): when querying flow logs in
  CloudWatch Logs Insights or Athena
- [references/preparing-evidence.md](references/preparing-evidence.md): when the user has to
  export flow logs or convert a capture to text
- [references/wireshark-analysis.md](references/wireshark-analysis.md): when reading tshark or
  tcpdump output (tcp.analysis definitions and precedence, completeness, artifacts, filters)
- [references/packet-capture-analysis.md](references/packet-capture-analysis.md): when planning
  a capture (EC2, Windows, EKS, Traffic Mirroring) or matching TCP signatures, MTU, ENA counters
- [references/troubleshooting-playbooks.md](references/troubleshooting-playbooks.md): when
  mapping a symptom to evidence, causes, and confirmation
