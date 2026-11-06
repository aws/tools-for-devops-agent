# Flow Log Query Library - CloudWatch Logs Insights and Athena

Read-only queries. Always time-box them: Logs Insights and Athena both bill by data scanned.
Start with the narrowest time window that covers the incident.

## CloudWatch Logs Insights

The default format is auto-discovered (camelCase): `@timestamp, accountId, interfaceId,
srcAddr, dstAddr, srcPort, dstPort, protocol, packets, bytes, startTime, endTime, action,
logStatus, version`. Field discovery applies only to Standard-class log groups.

Run from the CLI (read-only; `start-query` creates only a query job):

```
aws logs start-query --log-group-name <group> --start-time <epoch> --end-time <epoch> --query-string '<query>'
aws logs get-query-results --query-id <id>
```

The CloudWatch MCP server exposes the same capability as `execute_log_insights_query`.

### Rejected traffic by flow

```
fields @timestamp, interfaceId, srcAddr, dstAddr, dstPort, protocol
| filter action = "REJECT"
| stats count(*) as records, sum(packets) as pkts by interfaceId, srcAddr, dstAddr, dstPort, protocol
| sort pkts desc
| limit 50
```

### Everything between two hosts (both directions), to pair request and response

```
fields @timestamp, interfaceId, srcAddr, srcPort, dstAddr, dstPort, protocol, action, packets
| filter (srcAddr = "10.0.1.10" and dstAddr = "10.0.2.20") or (srcAddr = "10.0.2.20" and dstAddr = "10.0.1.10")
| sort @timestamp asc
| limit 200
```

An ACCEPT one way plus a REJECT the other way on the same ENI points at a NACL. See
`vpc-flow-logs.md`.

### Rejected inbound from outside a CIDR (who is knocking)

```
filter action = "REJECT" and not isIpv4InSubnet(srcAddr, "10.0.0.0/8")
| stats sum(packets) as pkts, count_distinct(dstPort) as ports by srcAddr
| sort pkts desc
| limit 25
```

### Top talkers by bytes

```
filter action = "ACCEPT"
| stats sum(bytes) as totalBytes by srcAddr, dstAddr
| sort totalBytes desc
| limit 20
```

### Which instance is behind a zonal NAT gateway

On the NAT gateway ENI, the instance -> NAT leg has the instance as `srcAddr` and the NAT private
IP as `dstAddr`. The internet -> NAT response leg **also** has `dstAddr` = NAT private IP, with
an internet host as `srcAddr`, and it usually carries most of the bytes. So also limit the source
to the VPC CIDR. This works with the default format:

```
filter interfaceId = "eni-<nat-gateway-eni>" and dstAddr = "<nat-private-ip>"
  and isIpv4InSubnet(srcAddr, "<vpc-cidr>")
| stats sum(bytes) as bytesToNat, sum(packets) as pkts by srcAddr, dstPort
| sort bytesToNat desc
| limit 25
```

Without the CIDR filter, a test VPC's top results were all internet hosts (the response leg),
not the instance. [Observed in a test VPC.]

Don't group the NAT -> internet leg by `pkt-srcaddr`: on that leg it's the NAT IP, not the
instance. To see the final destination per instance, add `pkt-dstaddr` to a custom format and
group the instance -> NAT leg by `srcaddr` and `pkt-dstaddr`.

### Traffic over time to a port (spot when it stopped)

```
filter dstPort = 443 and dstAddr = "10.0.2.20"
| stats sum(packets) as pkts by bin(1m), action
```

### Bytes over time for one interface (spot a spike or a stop)

```
filter interfaceId = "eni-<id>" and logStatus = "OK"
| stats sum(bytes) as totalBytes, sum(packets) as pkts by bin(5m)
```

### Unique conversations on one interface

```
fields @timestamp, srcAddr, srcPort, dstAddr, dstPort, protocol, action, bytes
| filter interfaceId = "eni-<id>"
| sort @timestamp desc
| dedup srcAddr, srcPort, dstAddr, dstPort, protocol
| limit 200
```

`dedup` keeps the first record in sort order per combination, and only `limit` may follow it
(documented).

### Gaps in logging

```
filter logStatus != "OK"
| stats count(*) by logStatus, interfaceId
```

### Custom formats: parse first

The discovered field list covers only the default fields. Fields such as `tcp-flags`,
`flow-direction` and `pkt-srcaddr` are never discovered, so parse `@message` in the exact field
order from `describe-flow-logs`. In a test VPC whose custom format began with the 14 default
fields in default order, the default field names (`action`, `srcAddr`, ...) still returned
correct values. AWS doesn't document this for custom formats, so don't rely on it if the format
reorders or omits the default fields. [Observed in a test VPC; not documented.] For example,
with the recommended version 5 format:

```
parse @message "* * * * * * * * * * * * * * * * * * * * * * * * * *" as version, account, eni, src, dst, sport, dport, proto, pkts, byts, start, end, act, status, vpc, subnet, instance, tcpflags, type, pktsrc, pktdst, az, direction, path, srcsvc, dstsvc
| filter act = "REJECT"
| stats count(*) by eni, direction, src, dst, dport
```

Two other common orders. Match the one `describe-flow-logs` returns, field for field:

21 fields, with `tcp-flags` last:

```
parse @message "* * * * * * * * * * * * * * * * * * * * *" as version, account, eni, src, dst, sport, dport, proto, pkts, byts, start, end, act, status, vpc, subnet, instance, type, pktsrc, pktdst, tcpflags
```

29 fields, with `tcp-flags` after `pkt-dstaddr` and `reject-reason` last:

```
parse @message "* * * * * * * * * * * * * * * * * * * * * * * * * * * * *" as version, account, eni, src, dst, sport, dport, proto, pkts, byts, start, end, act, status, vpc, subnet, instance, type, pktsrc, pktdst, tcpflags, az, subloctype, sublocid, srcsvc, dstsvc, direction, path, rejectreason
```

`tcpFlags` is not a discovered field, so `filter tcpFlags = 4` without a `parse` matches
nothing. [Discovered field list: documented]

Resets by sender (who sent the RSTs). Use whichever parse line matches the format:

```
parse @message "* * * * * * * * * * * * * * * * * * * * * * * * * *" as version, account, eni, src, dst, sport, dport, proto, pkts, byts, start, end, act, status, vpc, subnet, instance, tcpflags, type, pktsrc, pktdst, az, direction, path, srcsvc, dstsvc
| filter proto = "6" and tcpflags in ["4", "5", "6", "7", "22", "23"]
| stats count(*) as rstRecords by eni, direction, src, dst
| sort rstRecords desc
| limit 25
```

Unanswered SYNs: run three queries and compare. Logs Insights can't self-join, so do the exact
pairing with Athena (below). Flags are OR-ed per record, so match every value that carries the
bit: an exact `tcpflags = "18"` misses a short exchange logged as 19 (SYN-ACK+FIN).

First, the SYNs sent per server and port:

```
parse @message "* * * * * * * * * * * * * * * * * * * * * * * * * *" as version, account, eni, src, dst, sport, dport, proto, pkts, byts, start, end, act, status, vpc, subnet, instance, tcpflags, type, pktsrc, pktdst, az, direction, path, srcsvc, dstsvc
| filter proto = "6" and tcpflags in ["2", "3", "6", "7"]
| stats count(*) as syns by eni, dst, dport
| sort syns desc
```

Then the SYN-ACKs returned from those servers:

```
parse @message "* * * * * * * * * * * * * * * * * * * * * * * * * *" as version, account, eni, src, dst, sport, dport, proto, pkts, byts, start, end, act, status, vpc, subnet, instance, tcpflags, type, pktsrc, pktdst, az, direction, path, srcsvc, dstsvc
| filter proto = "6" and tcpflags in ["18", "19", "22", "23"]
| stats count(*) as synacks by eni, src, sport
```

Then the resets:

```
parse @message "* * * * * * * * * * * * * * * * * * * * * * * * * *" as version, account, eni, src, dst, sport, dport, proto, pkts, byts, start, end, act, status, vpc, subnet, instance, tcpflags, type, pktsrc, pktdst, az, direction, path, srcsvc, dstsvc
| filter proto = "6" and tcpflags in ["4", "5"]
| stats count(*) as rsts by eni, src, sport
```

Read them together per server and port: SYNs and SYN-ACKs mean it's answering. SYNs and RSTs but
no SYN-ACKs mean it's refused (port closed). SYNs with neither mean it's silent (SG, NACL,
routing, or the host is down); check the server ENI for REJECT. In a test VPC this separated a
healthy port, a closed port (RST) and an SG-blocked port correctly. [Observed in a test VPC.]

## Athena (flow logs delivered to S3)

Create the table with the DDL from the
[Athena docs](https://docs.aws.amazon.com/athena/latest/ug/vpc-flow-logs-create-table-statement.html).
Column order must match your flow log format. Columns are snake_case. Always filter on the
partition, and keep the range narrow.

**Check the table before writing a query.** Run `SHOW CREATE TABLE <table>` (read-only). The
AWS DDL partitions on `` `date` `` (type date) and names the time columns `start` and
`` `end` ``. Tables built with partition projection often use a string partition instead, for
example `dt` in `yyyy/MM/dd` form (`WHERE dt = '2026/01/15'`), and teams sometimes rename
columns. Use the names the table actually has. The queries below follow the AWS DDL.
[The Athena queries in this file were not run against a live table; their logic matches the
Logs Insights versions validated in a test VPC.]

### Biggest flows per minute in an incident window (packet spikes)

```sql
SELECT date_trunc('minute', from_unixtime("start")) AS minute_bucket,
       srcaddr, srcport, dstaddr, dstport,
       SUM(packets) AS total_packets, SUM(bytes) AS total_bytes
FROM vpc_flow_logs
WHERE date = DATE('2026-01-15')
  AND "start" >= to_unixtime(TIMESTAMP '2026-01-15 05:30:00')
  AND "end" <= to_unixtime(TIMESTAMP '2026-01-15 05:50:00')
GROUP BY 1, 2, 3, 4, 5
ORDER BY total_packets DESC
LIMIT 50;
```

### Resets over time (match the RST bit, not the value 4)

```sql
SELECT date_trunc('minute', from_unixtime("start")) AS minute_bucket,
       interface_id, flow_direction, srcaddr, dstaddr, dstport, COUNT(*) AS rst_records
FROM vpc_flow_logs
WHERE date = DATE('2026-01-15') AND protocol = 6
  AND bitwise_and(tcp_flags, 4) = 4
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY rst_records DESC
LIMIT 50;
```

### Average bytes per packet (small-packet floods; not an MTU test)

```sql
SELECT srcaddr, dstaddr, protocol,
       SUM(bytes) AS total_bytes, SUM(packets) AS total_packets,
       SUM(bytes) / NULLIF(SUM(packets), 0) AS avg_bytes_per_packet
FROM vpc_flow_logs
WHERE date = DATE('2026-01-15') AND action = 'ACCEPT'
GROUP BY 1, 2, 3
ORDER BY total_bytes DESC
LIMIT 50;
```

A low average is normal on the ACK side of a bulk transfer. Don't read it as an MTU problem.
[Heuristic]

### Rejected flows on a day

```sql
SELECT interface_id, srcaddr, dstaddr, dstport, protocol, flow_direction,
       SUM(packets) AS pkts, COUNT(*) AS records
FROM vpc_flow_logs
WHERE date = DATE('2026-01-15') AND action = 'REJECT'
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY pkts DESC
LIMIT 50;
```

### Response rejected while request accepted (NACL signature)

```sql
WITH f AS (
  SELECT interface_id, srcaddr, dstaddr, srcport, dstport, protocol, action
  FROM vpc_flow_logs
  WHERE date = DATE('2026-01-15')
)
SELECT req.interface_id, req.srcaddr AS client, req.dstaddr AS server, req.dstport,
       resp.srcport AS resp_sport, resp.dstport AS resp_dport
FROM f req
JOIN f resp
  ON resp.interface_id = req.interface_id
 AND resp.srcaddr = req.dstaddr AND resp.dstaddr = req.srcaddr
 AND resp.srcport = req.dstport AND resp.dstport = req.srcport
 AND resp.protocol = req.protocol
WHERE req.action = 'ACCEPT' AND resp.action = 'REJECT'
LIMIT 100;
```

### Unanswered SYNs (needs tcp_flags)

```sql
WITH f AS (
  SELECT interface_id, srcaddr, dstaddr, srcport, dstport, tcp_flags
  FROM vpc_flow_logs
  WHERE date = DATE('2026-01-15') AND protocol = 6
)
SELECT s.interface_id, s.srcaddr, s.dstaddr, s.dstport, COUNT(*) AS syn_records
FROM f s
LEFT JOIN f r
  ON r.interface_id = s.interface_id AND r.srcaddr = s.dstaddr AND r.dstaddr = s.srcaddr
 AND r.srcport = s.dstport AND r.dstport = s.srcport AND bitwise_and(r.tcp_flags, 18) = 18
WHERE bitwise_and(s.tcp_flags, 2) = 2 AND bitwise_and(s.tcp_flags, 16) = 0
  AND r.interface_id IS NULL
GROUP BY 1, 2, 3, 4
ORDER BY syn_records DESC
LIMIT 50;
```

This also lists refused connections (RST back, no SYN-ACK). Separate them with the RST query
above. [Logic matches the Logs Insights version validated in a test VPC; this Athena SQL was not
run.]

### Cross-AZ bytes (cost and latency check; needs az_id and next-hop fields or a subnet map)

```sql
SELECT az_id, flow_direction, traffic_path, SUM(bytes) AS bytes
FROM vpc_flow_logs
WHERE date BETWEEN DATE('2026-01-14') AND DATE('2026-01-15')
GROUP BY 1, 2, 3
ORDER BY bytes DESC;
```

## Raw records for one conversation

To examine request/response pairing record by record, pull only the records for the failing
hosts and window:

```
aws logs filter-log-events --log-group-name <group> --start-time <ms> --end-time <ms> \
  --filter-pattern '"10.0.2.20"' --output json
```

Interpret them with the field order from `describe-flow-logs` (`LogFormat`). For S3-delivered
logs, the header line in each object gives the field order. When the user has to export records
themselves, follow `preparing-evidence.md`.
