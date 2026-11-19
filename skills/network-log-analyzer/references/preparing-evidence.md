# Preparing Evidence for Upload

Use this when the user has to hand the agent their own evidence: an exported flow log slice,
or a packet capture converted to text. The aim is a small, focused, **pre-aggregated** text
file. Two reasons. Chat attachments are size-limited. And a language model is good at
interpreting summaries but unreliable at counting thousands of raw lines.

## Attachment constraints (AWS DevOps Agent chat)

From [On Demand DevOps Tasks: Sending file attachments](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-on-demand-devops-tasks.html):

- **Accepted types** include `txt`, `log`, `csv`, `json`, `md`, `yaml`, `xml`, and others.
  Files outside the listed categories are rejected. That means **`.pcap`, `.pcapng` and
  `.gz` can't be attached**: convert or decompress them first.
- **3.75 MB maximum per file**, and up to 20 attachments per message.
- The message text plus attachment content must fit in the model's per-message context window.
  In practice, aim for **well under 1 MB of text** and a few thousand lines at most.
- Attachments are stored in the Agent Space, and **chats are shared with everyone who has
  access to that Agent Space**. Treat anything you attach as visible to the whole team.

## Rules for any evidence file

1. **Scope the time:** the incident window, plus a few minutes either side. State it in UTC.
2. **Scope the hosts:** the source and destination of the failing flow, plus any middlebox in
   between.
3. **Summarize first, then add raw detail.** Send the aggregate (counts and statistics), plus
   only the raw lines for the failing flows.
4. **Headers, not payloads.** Never attach full packet payloads, `-z follow` output, or exported
   objects. They can contain credentials, tokens, and personal data.
5. **Say how it was produced.** Include the command line, the capture point, and the flow log
   format, either in the message or as the file's first lines.

---

## VPC Flow Logs

If the agent can query CloudWatch Logs in the account directly, prefer that over uploads. The
queries are in `flow-log-queries.md`. Otherwise, export as follows.

### 1. Record the format

```
aws ec2 describe-flow-logs --filter Name=resource-id,Values=<vpc|subnet|eni> \
  --query "FlowLogs[].{id:FlowLogId,fmt:LogFormat,dest:LogDestination}"
```

Paste the `LogFormat` into the chat. Without it, custom-format records can't be interpreted.

### 2a. From CloudWatch Logs: aggregate in Logs Insights, then export the result as CSV

Run the queries from `flow-log-queries.md` scoped to the window and the hosts, for example
"rejected traffic by flow" and "everything between two hosts". In the console, export the
results to CSV and attach that. These outputs are already aggregated, so they stay small.

For the raw records of one conversation (both directions):

```
aws logs filter-log-events --log-group-name <group> \
  --start-time <epoch-ms> --end-time <epoch-ms> \
  --filter-pattern '"10.0.2.20"' --output json > flows-10.0.2.20.json
```

Check the file size before attaching it. If it's over about 1 MB, narrow the time window or
the filter pattern.

### 2b. From S3: decompress, filter, and trim

S3 objects are gzip text with a header line. `.gz` can't be attached, so decompress it and keep
only the matching lines plus the header:

```
aws s3 cp s3://<bucket>/<prefix>/AWSLogs/<acct>/vpcflowlogs/<region>/<yyyy>/<mm>/<dd>/ ./fl --recursive --exclude "*" --include "*<eni-or-time>*"
# Linux/macOS
zcat fl/*.gz | awk 'NR==1 || /10\.0\.2\.20/' > flows-10.0.2.20.log
# Windows PowerShell (header + matching lines)
Get-ChildItem fl\*.gz | ForEach-Object { $s=[IO.Compression.GzipStream]::new([IO.File]::OpenRead($_.FullName),[IO.Compression.CompressionMode]::Decompress); [IO.StreamReader]::new($s).ReadToEnd() } | Out-File all.log
Select-String -Path all.log -Pattern '^version|10\.0\.2\.20' | ForEach-Object Line | Out-File flows-10.0.2.20.log
```

If Athena is set up, run the SQL from `flow-log-queries.md` instead and export the result as
CSV.

### 3. What to send

| File | Contents |
|---|---|
| `format.txt` | `LogFormat` and the flow log ID |
| `rejects.csv` | Logs Insights or Athena "rejected flows" aggregate for the window |
| `flows-<host>.log` or `.json` | Raw records for the failing conversation, both ENIs if possible |

---

## Packet captures

The agent can't read binary captures. Convert them to text with Wireshark's own analysis, so
Wireshark does the counting and the agent interprets the result. Run these where the capture
file is. tshark ships with Wireshark. Tested with tshark 4.6.9.

**Shell notes.**
- The commands below use Linux/macOS line continuations (`\`). In PowerShell, put each command
  on one line, or end lines with a backtick instead.
- **Windows PowerShell 5.1 writes `>` redirects as UTF-16**, which doubles file size. Run the
  commands from `cmd`, use PowerShell 7 (`pwsh`, which writes UTF-8), or replace `> file` with
  `| Out-File -Encoding utf8 file`.
- The fields below were chosen to stay plain ASCII. `tcp.flags.str` and the Info column contain
  Unicode symbols (dots and arrows) that can turn into garbled characters after a redirect, so
  they're avoided.

### 1. Overview (always send)

```
tshark -r cap.pcapng -q -z io,phs              > 01-hierarchy.txt
tshark -r cap.pcapng -q -z conv,tcp            > 02-conv-tcp.txt
tshark -r cap.pcapng -q -z expert,note         > 03-expert.txt
```

### 2. Problem packets, header fields only (always send)

```
tshark -r cap.pcapng -Y "(tcp.analysis.flags && !tcp.analysis.window_update && !tcp.analysis.keep_alive && !tcp.analysis.keep_alive_ack) || tcp.flags.reset==1 || (tcp.flags.syn==1 && tcp.flags.ack==0) || icmp.type==3 || icmp.type==11 || icmpv6.type==2 || dns.flags.rcode!=0" \
  -T fields -E header=y -E separator=, -E quote=d \
  -e frame.number -e frame.time_relative -e ip.src -e ip.dst -e ipv6.src -e ipv6.dst \
  -e tcp.stream -e tcp.srcport -e tcp.dstport -e tcp.flags -e tcp.seq -e tcp.ack -e tcp.len \
  -e tcp.window_size -e _ws.expert.message -e tcp.analysis.rto -e tcp.analysis.ack_rtt \
  -e ip.len -e ip.flags.df -e ip.dsfield.ecn -e icmp.type -e icmp.code -e icmp.mtu -e dns.qry.name -e dns.flags.rcode \
  > 04-problems.csv
```

How to read the columns (verified on tshark 4.6.9):
- `_ws.expert.message` holds Wireshark's expert text for the packet, for example
  `TCP window update`, `Previous segment(s) not captured (common at capture start)`, or
  `Connection reset (RST)`. A packet can have several, separated by commas. Don't use
  `tcp.analysis.flags` as a column: it prints only `1` for "some flag was set", not which one.
- `tcp.flags` is the flags field in hex: `0x0002` SYN, `0x0012` SYN-ACK, `0x0010` ACK, `0x0018`
  PSH-ACK, `0x0011` FIN-ACK, `0x0004` RST, `0x0014` RST-ACK.
- The filter leaves out window updates and keep-alives. They're normal, and on a healthy
  transfer they can make up nearly every flagged packet.

To get counts per flag type, run the filters from `wireshark-analysis.md` section 6
individually, for example:

```
tshark -r cap.pcapng -Y "tcp.analysis.retransmission" | find /c /v ""      # Windows
tshark -r cap.pcapng -Y "tcp.analysis.retransmission" | wc -l              # Linux/macOS
```

### 3. Handshakes and capture point (send for any TCP issue)

```
tshark -r cap.pcapng -Y "tcp.flags.syn==1" -T fields -E header=y -E separator=, \
  -e frame.number -e frame.time_relative -e ip.src -e ip.dst -e tcp.stream -e tcp.flags \
  -e tcp.options.mss_val -e tcp.options.wscale.shift -e tcp.analysis.initial_rtt > 05-handshakes.csv
```

SYN to SYN-ACK and SYN-ACK to ACK timings locate the capture point (see
`wireshark-analysis.md` section 1, step 4).

### 4. One failing stream in full (optional, headers only)

```
tshark -r cap.pcapng -Y "tcp.stream==<N>" -T fields -E header=y -E separator=, \
  -e frame.number -e frame.time_relative -e ip.src -e tcp.srcport -e ip.dst -e tcp.dstport \
  -e tcp.flags -e tcp.seq -e tcp.ack -e tcp.len -e tcp.window_size -e ip.dsfield.ecn -e _ws.expert.message \
  > 06-stream-<N>.csv
```

### 5. Timeline (optional, for intermittent problems)

```
tshark -r cap.pcapng -q -z io,stat,1,"tcp","tcp.analysis.retransmission","tcp.flags.reset==1" > 07-io-1s.txt
# ECN signals per second (CE marks, ECE echoes, CWR responses), for "slow but no loss" cases
tshark -r cap.pcapng -q -z io,stat,1,"ip.dsfield.ecn==3","tcp.flags.ece==1 and tcp.flags.syn==0","tcp.flags.cwr==1 and tcp.flags.syn==0" > 08-ecn-1s.txt
# For captures longer than a few minutes, use 10 or 60 instead of 1 to keep the file small
# Receive-window range per sender (interval 0 = whole capture). Repeat with the other ip.src.
# The field MUST also appear in the filter part (documented tshark quirk). Verified on 4.6.9.
tshark -r cap.pcapng -q -z "io,stat,0,MIN(tcp.window_size)tcp.window_size and ip.src==<host>,MAX(tcp.window_size)tcp.window_size and ip.src==<host>" > 09-window-<host>.txt
```

`io,stat` needs `.` as the system decimal separator. If it's set to `,`, the per-filter columns
are missing (documented in tshark(1)).

### Without tshark

If only tcpdump is available, send the text output for the relevant hosts, kept short:

```
tcpdump -nn -tt -r cap.pcap 'host 10.0.2.20 and (tcp[tcpflags] & (tcp-syn|tcp-rst|tcp-fin) != 0 or icmp)' > cap-key.txt
tcpdump -nn -tt -r cap.pcap 'host 10.0.2.20' | head -2000 > cap-head.txt
```

With text-only tcpdump output, retransmission and duplicate-ACK detection is manual, so
counts are approximate. Say so in the findings.

For a better tcpdump capture (tcpdump(1)):
- Write to a file with `-w` and convert it afterwards with `-r`, instead of printing live text.
  Printing slows capture processing on a busy host.
- Use a bigger buffer (`-B <KiB>`) and a header-sized snaplen, for example `-s 128`. Truncated
  packets show as `[|proto]` in the text output.
- Send the summary lines tcpdump prints when it stops, especially "packets dropped by kernel".
- Add `-S` for absolute sequence numbers. Without it, tcpdump prints numbers relative to the
  first packet it saw for each direction, so a mid-stream capture can show artifacts such as
  `ack 0`.
- Say whether the text was cut down from a longer capture, and how.

### What to send

| File | Always? |
|---|---|
| `01-hierarchy.txt`, `02-conv-tcp.txt`, `03-expert.txt` | Yes |
| `04-problems.csv` | Yes |
| `05-handshakes.csv` | For TCP issues |
| `06-stream-<N>.csv`, `07-io-1s.txt` | When needed |

Also state: the **capture point** (client, server, appliance, or mirror target), the
**capture filter**, the **snaplen**, and whether **offload** (TSO/GRO) was on, if known.

---

## How the agent should treat uploaded evidence

- Label findings from attachments as **Observed (from uploaded file X)**. Name the file and
  the rows or frames.
- Don't recount large raw files by hand. Rely on Wireshark's `-z` statistics and Logs Insights
  or Athena aggregates for counts, and use raw rows only as examples.
- If a needed piece is missing (format, capture point, the other side of the flow), ask for it
  with the exact command above instead of guessing.
- Note the coverage limits of the evidence: the time window, hosts filtered out, one-sided
  captures, and truncated output.
