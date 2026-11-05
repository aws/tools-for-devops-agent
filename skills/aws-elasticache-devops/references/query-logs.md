# Query the delivered logs

Slow log and engine log, when delivery is configured. Node-based caches only: log
delivery is not available for serverless caches.

## Find the log group

`LogDeliveryConfigurations` (from [discover-deployment.md](discover-deployment.md)) lists
each configuration with its `LogType` (`slow-log` or `engine-log`), `DestinationType`
(`cloudwatch-logs` or `kinesis-firehose`), `LogFormat` (`json` or `text`), `Status`, and for
CloudWatch Logs the group in `DestinationDetails.CloudWatchLogsDetails.LogGroup`. If no
configuration exists for a log type, say that log is not delivered and name the gap.

## Slow log

Only commands slower than `slowlog-log-slower-than` (default 10,000 µs) are logged.
A fixed number of entries is retrieved from the engine periodically; depending on
`slowlog-max-len`, additional entries might not be delivered.

Each entry has `CacheClusterId`, `CacheNodeId`, `Id`, `Timestamp`, `Duration (us)`,
`Command`, `ClientAddress` and `ClientName`. Durations are in **microseconds**, and each
one is time the engine's main thread spent on that command. Delivered logs **replace the
key and arguments** with `... (N more arguments)`, so name the command, the node and the
client address, and recommend `SLOWLOG GET` to the operator for the key.

Logs Insights query on the slow log group over the window (JSON format):

```
fields Command, `Duration (us)`, ClientAddress, CacheClusterId
| parse Command /^(?<cmd>\S+)/
| stats count(*) as n, max(`Duration (us)`) as max_us, avg(`Duration (us)`) as avg_us by cmd, CacheClusterId
| sort max_us desc | limit 20
```

What it does, line by line:
- `fields` selects four fields of each slow log entry.
- `parse` extracts the command name (the first word of `Command`) into `cmd`.
- `stats` groups the entries by command name and node, and for each group returns the
  number of slow entries (`n`), the longest duration (`max_us`) and the average duration
  (`avg_us`), in microseconds.
- `sort` and `limit` return the 20 groups with the longest maximum duration.

One row per command and node: which commands were slow, how often, how slow, and on
which node. It does not return keys (they are replaced in the log), and it only counts
entries over the threshold.

## Engine log

The engine log is a curated subset of engine events, not all internal engine logs:
significant operational events such as replication, snapshots, cluster health and
scripting. Private information is redacted: no user data, passwords, authentication
tokens, key names or values appear in it.

Each entry has `CacheClusterId`, `CacheNodeId`, `LogLevel` (`VERBOSE`, `NOTICE` or
`WARNING`), `Role` (`M` primary, `S` replica, `C` a writer child process working on
RDB/AOF, `X` sentinel), `Time` (UTC) and `Message`.

Use it to see what the engine did, and when, around the onset: an example from the
documentation is a message that a Lua script is still running after 1000 microseconds.

Logs Insights query on the engine log group over the window (JSON format):

```
fields @timestamp, CacheNodeId, Role, LogLevel, Message
| sort @timestamp asc | limit 100
```

It lists the first 100 engine log entries of the window in time order, with the node,
its role, the level and the message. Narrow the window to the minutes around the onset.
