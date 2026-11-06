# Evidence sources

Where Neo4j's state, configuration and container output live on each platform, the tool behavior that affects
reading them, and how to tell a source is missing. Shipped log files and Logs Insights queries are in
[log-queries.md](log-queries.md); finding a volume is in [A3](runbooks/A3-disk-storage.md).

## EKS (Neo4j Helm chart)

Each Neo4j server is one Helm release: a StatefulSet named after the release with one pod (`<release>-0`) and a
container `neo4j`. Cluster members are separate releases sharing the `neo4j.name` value. Without Helm, find pods whose
image starts with `neo4j:`.

`use_kubectl` returns only the `NAME` and `AGE` columns of a table, so `get pods` and `get events` show no status,
restarts or reasons: read state from `-o yaml` or `describe`, and never report a status you didn't read there. It
can't pipe or grep, so read the returned text and match it against the runbook signatures. The access policy covers
get and list on pods, pod logs, events, ConfigMaps, workloads, Services and PVCs, not Secrets or `exec`.

| Need | Call | Notes |
| --- | --- | --- |
| Find Neo4j pods | `get pods -n <ns> -l helm.neo4j.com/instance` | `-l app=<neo4j.name>` lists every member of a cluster |
| Pod state and events | `get pod <pod> -n <ns> -o yaml`, `describe pod <pod> -n <ns>` | `lastState.terminated` (`exitCode`, `reason`, `finishedAt`), `restartCount`. Events expire after about an hour |
| Container output | `logs <pod> -n <ns> -c neo4j --since=<window> --timestamps`, or `--tail=300` | neo4j.log and stderr only, unless the operator added Console appenders for the other logs |
| Last crashed container | `logs <pod> -n <ns> -c neo4j --previous --timestamps` | Only the one previous container; earlier restarts are lost unless shipped |
| Configuration | `get configmap <release>-default-config -n <ns> -o yaml`, then `-user-config`, `-k8s-config` | Later ConfigMaps override earlier ones; `<release>-env` holds environment variables. Helm release history and supplied values are in Secrets the agent can't read |
| Workload spec | `get statefulset <release> -n <ns> -o yaml` | Image tag, `resources`, probes, `terminationGracePeriodSeconds`, volume claim templates, Secret mount names |
| Cluster traffic | `get svc <release>-internals -n <ns> -o yaml` | Discovery and Raft between members |
| Backup and load jobs | `get cronjob,job -n <ns>`, `logs job/<job> -n <ns> --timestamps` | The job output is the only record of a backup or load |

## ECS

| Need | Call | Notes |
| --- | --- | --- |
| Stopped tasks | `ecs list-tasks --cluster <c> --service-name <s> --desired-status STOPPED`, then `ecs describe-tasks` | Read `containers[].reason` and `exitCode`; the task's `stoppedReason` is often only `Essential container in task exited`. Stopped tasks stay visible for at least an hour |
| Task definition | `ecs describe-task-definition --task-definition <arn>` | `environment` (`NEO4J_*`), `secrets` (names only), `memory`, `ulimits`, `user`, `stopTimeout`, `mountPoints`, `logConfiguration`, `healthCheck` |

Environment variable names map to settings: `NEO4J_` prefix, `.` → `_`, `_` → `__`. `NEO4J_AUTH` holds credentials;
never quote its value.

## EC2 (package or tarball install)

neo4j.conf, the Neo4j logs and the service state are readable only if the CloudWatch agent ships the logs, or if an
operator already ran the evidence command in [operator-queries.md](operator-queries.md). The agent can't run SSM
commands itself.

| Need | Call | Notes |
| --- | --- | --- |
| Serial console | `ec2 get-console-output --instance-id <id> --latest` | Needs `ec2:GetConsoleOutput` added to the agent role. Kernel memory errors (`__vm_enough_memory ... comm: java`), boot and filesystem errors |
| SSM agent | `ssm describe-instance-information --filters Key=InstanceIds,Values=<id>` | `PingStatus` `ConnectionLost` on a host that was online can mean it ran out of memory |
| Installed version | `ssm list-inventory-entries --instance-id <id> --type-name AWS:Application --filters Key=Name,Values=neo4j,Type=BeginWith` | Needs SSM Inventory |
| Operator-run evidence | `ssm list-commands --instance-id <id>`, then `ssm get-command-invocation --command-id <cid> --instance-id <id>` | Commands can't be filtered by comment: look for `neo4j-support-evidence` in the list. Inline output is cut at 24,000 characters |
| Memory and disk fill | `CWAgent` `mem_used_percent` and `disk_used_percent` | Only if the CloudWatch agent runs; `AWS/EC2` has neither |

## Changes in the window

Use `lookup_cloudtrail_events`; `use_aws` refuses CloudTrail calls. Look for `RegisterTaskDefinition`,
`UpdateService`, `ModifyVolume`, `AuthorizeSecurityGroupIngress`, `RevokeSecurityGroupIngress` and EKS updates.
CloudTrail doesn't record changes inside a Kubernetes cluster, such as a ConfigMap edit.

## Recognizing a missing source

| Source | It's missing when | Say in the report |
| --- | --- | --- |
| EKS access | `use_kubectl` returns forbidden or unauthorized | EKS access entry for the Agent Space role is missing or namespace-scoped |
| A ConfigMap's content | The read succeeds but the platform content guardrail removes the output; it can happen on one run and not the next | Settings in that ConfigMap weren't seen; ask the operator to export it, and use the startup diagnostics in container output for heap and page cache |
| Cluster-scoped objects | Nodes, PVs or StorageClasses forbidden, namespace objects fine | Access is namespace-scoped; volume type and node checks not done |
| Container output on ECS | No `logConfiguration` | Only task state was available |
| History before the last restart | `--previous` covers one restart; no application log group | Earlier crashes can't be examined |
| debug.log | No log group or stream holds `"category":"` JSON lines or `[o.n.` text lines | Database state, recovery, GC and cluster detail unavailable |
| query.log | No lines with ` page hits, ` and `transaction id:` | Query-level analysis unavailable |
| security.log | No `42NFF`, `logged in` or `failed to log in` lines outside container output | Authentication detail unavailable |
| Container Insights | No metrics for the cluster in `ContainerInsights` or `ECS/ContainerInsights` | Memory and restart trends unavailable |
| EC2 console | `get-console-output` access denied | Add `ec2:GetConsoleOutput` to the agent role to see kernel memory errors |
| EC2 files | No CloudWatch agent log groups and no SSM command output | Ask for the evidence command |
