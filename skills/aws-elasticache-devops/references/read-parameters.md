# Read the parameters

Node-based caches only. Serverless caches have no parameter groups: their settings are
fixed. Their `maxmemory-policy` is `volatile-lru`, so a serverless cache evicts only keys
that have a TTL; with none, writes at the limit fail with `OOM`. The policy is in the
serverless parameter table
([configuration and limits](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/RedisConfiguration.html#RedisConfiguration.Serverless));
the behavior at a storage maximum is described in "Setting scaling limits to manage
costs" on the [scaling page](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/Scaling-serverless.html).

## Call

```
use_aws(service_name="elasticache", operation_name="describe_cache_parameters",
        parameters={"CacheParameterGroupName": "<pg>", "Source": "user"})
```

`Source: user` returns the parameters the customer changed. Parameters missing from the
result have their default value; a default group (`default.*`) uses
`maxmemory-policy = volatile-lru`.

## Which parameters to read

Read every parameter that is relevant to the cause under investigation, not a fixed
list. The parameters this skill names, with their documented defaults
([Valkey and Redis OSS parameters](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/ParameterGroups.Engine.html)):

| Parameter | Default | Read it when |
|---|---|---|
| `maxmemory-policy` | `volatile-lru` | Writes fail with `OOM`, keys are evicted |
| `reserved-memory-percent` | 25 | Memory pressure or swap: the percent of a node's memory reserved for non-data use |
| `timeout` | 0 | Connections pile up: 0 never disconnects an idle client; values 1 to 19 are invalid; 20 or more is the idle time in seconds |
| `maxclients` | 65000 (20000 on `t3.micro` and `t4g.micro`, 46000 on `t3.small` and `t3.medium`); not modifiable | Connection errors or timeouts: the maximum number of clients connected at one time. It also counts replica and cluster bus connections (OTel: `valkey.clients.max`) |
| `slowlog-log-slower-than` | 10000 | Slow log entries: the minimum execution time, in microseconds, for a command to be logged |
| `slowlog-max-len` | 128 | Slow log entries: the maximum length of the slow log |
| `activedefrag` | no | Fragmentation |
| `lua-time-limit` | 5000 | `BUSY` replies: the maximum execution time of a Lua script, in milliseconds |
| `repl-backlog-size` | 10485760 in Valkey 8.0 parameter groups | Replication lag: the size, in bytes, of the primary's backlog buffer. A replica that reconnects tries a partial sync from it, and a full sync if that fails |
| `client-output-buffer-limit-*` | see the parameter reference | A client is disconnected when its output buffer reaches the limit (normal clients: no limit by default) |

Any other parameter the customer changed shows up in the `Source: user` result: read it
too if it is relevant to the cause.
