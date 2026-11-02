# Changelog

## [1.0.0] - Unreleased

### Added

- Initial release: troubleshooting from VPC Flow Logs and packet captures.
- Security group vs network ACL attribution from paired flow log records, and TCP handshake
  analysis from `tcp-flags`.
- Time-boxed CloudWatch Logs Insights and Athena queries, including custom flow log formats.
- Interpretation of tshark and tcpdump text output using Wireshark's `tcp.analysis.*`
  definitions and precedence, capture-point location, and capture-artifact handling (capture
  gaps, TSO/GRO offload).
- Playbooks for timeouts, refusals, one-way traffic, path MTU, idle resets, DNS, NAT/EKS source
  IPs, and inspection paths.
- Evidence-preparation guide for chat attachments (header-only exports).
- tshark commands and flag behavior checked on tshark 4.6.9 against public Wireshark sample and
  test captures:
  - spurious retransmissions also carry `tcp.analysis.retransmission`, but out-of-order
    segments don't;
  - `tcp.completeness` filters need two-pass `-2`;
  - Decode As syntax.
- Windows capture via `pktmon`, checked against Microsoft's documentation, including captures of
  drops inside the Windows network stack.
- Flow log queries and decision rules checked against live flow logs in a test VPC (NACL
  response reject, SG initial reject, closed-port RST, NAT gateway legs, NLB idle reset):
  - `tcp-flags` matching uses every OR-ed value that carries the bit (SYN-ACK 18/19/22/23,
    RST 4/5), and a three-query answered/refused/silent check replaces the exact `2`/`18` pair;
  - the NAT "which instance" query limits the source to the VPC CIDR, which excludes the
    internet -> NAT response leg;
  - field-discovery wording now reflects the observed behavior for custom formats.
- SKILL.md restructured for `skill-eval` best practices (structure 100%, best-practices 100%
  in 3 of 3 iterations):
  - a checklist workflow and a Step 5 self-check;
  - decision rules kept in the body, with detailed values in the references;
  - markdown reference links, each with a condition for when to load it;
  - a shorter description.
- `skill-eval` on the final files:
  - structure 100%;
  - best-practices 100% in 3 of 3 iterations;
  - functional (3 iterations, 10 positive and 5 negative evals): expected output 28/30 with
    the skill vs 18/30 without, and assertions 87/105 vs 56/105. The skill triggered on 27/30
    positive runs and 0/15 negative runs. The three misses are `dns-not-in-flow-logs`, a
    boundary case with `aws-vpc-dns-investigation` that the agent answers correctly without
    loading either skill.

  Results are committed with real resource IDs and names redacted.
- Rules added after the first functional run: say when a flow log needs re-creating to add
  `pkt-*` fields, and always recommend keepalives for idle resets.
- Scoped DNS to evidence only, so this skill doesn't compete with `aws-vpc-dns-investigation`:
  - "DNS queries time out" removed from the description, which now excludes name-resolution
    failures (NXDOMAIN, SERVFAIL, wrong answers);
  - playbook 7 reads only DNS packets and flow-log gaps, and hands resolution problems off;
  - a `should_trigger: false` eval for a private hosted zone NXDOMAIN, plus three negative
    trigger queries.
- Flow log references extended:
  - NODATA isn't activity;
  - a checklist for when nothing is logged in either direction;
  - how to tell who sent an RST;
  - common misreadings (3 is not abnormal, exact `= 4` misses resets, ACCEPT both ways doesn't
    clear the network for slowness, bytes per packet isn't an MTU test);
  - parse lines for the 21- and 29-field formats;
  - checking the Athena partition and column names;
  - per-minute spike, reset-over-time, bytes-over-time, and `dedup` queries;
  - a flow log triage order with an explicit return-path step;
  - pointers to Layer 7 sources.
