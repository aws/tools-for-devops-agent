# Run Command reference

## Calls (all read-only)

| Call | What it gives | Notes |
|---|---|---|
| `ssm:ListCommands` (`CommandId`) | Document, version, `Parameters` (the script text for the AWS-managed shell documents; other documents keep it in their content: `ssm:GetDocument` at that version), `Targets`, `InstanceIds`, `MaxConcurrency`, `MaxErrors`, `TargetCount`, `CompletedCount`, `ErrorCount`, `DeliveryTimedOutCount`, `OutputS3BucketName`, `OutputS3KeyPrefix`, `CloudWatchOutputConfig`, `TimeoutSeconds` | `TargetCount` counts only nodes that resolved to an invocation |
| `ssm:ListCommandInvocations` (`CommandId`, `Details=true`) | Per node: `Status`, `StatusDetails`, `CommandPlugins[].ResponseCode`, plugin `Output` | Plugin `Output` is cut at about 2,500 characters (marker `---Error truncated----` or `---Output truncated---`) |
| `ssm:GetCommandInvocation` (`CommandId`, `InstanceId`, `PluginName` required for a document with more than one step: take it from `CommandPlugins[].Name`) | `StandardOutputContent`, `StandardErrorContent`, `ResponseCode`, `Status`, `StatusDetails`, `StandardOutputUrl`, `StandardErrorUrl`, `CloudWatchOutputConfig`, `ExecutionStartDateTime`, `ExecutionEndDateTime` | stdout: first 24,000 characters, then `--output truncated--`; stderr: documented first 8,000 characters (seen returned whole at 16,390, so detect a marker, not a length) |
| `logs:DescribeLogStreams`, `logs:GetLogEvents` / `logs:FilterLogEvents` | Stream names, and the full output when CloudWatch output was on | Read the end of the stream (`startFromHead=false`, or the latest events) |

Per node, record `Status`, `StatusDetails` and each plugin's `ResponseCode`
(`CommandPlugins[].Name`). For a document with more than one step, pass `PluginName` to
`GetCommandInvocation` and call once per plugin of each failed or suspect node; without
it the call fails with `InvalidPluginName`. Read `StandardOutputContent`,
`StandardErrorContent`, `ResponseCode`, `StandardOutputUrl` and `StandardErrorUrl`.

## Output locations

- **CloudWatch Logs**: log group `CloudWatchOutputConfig.CloudWatchLogGroupName`, default
  `/aws/ssm/<document name>`. Streams `<command ID>/<instance ID>/<step>/stdout` and
  `/stderr`. The step segment differs by document schema: for schema 2.x documents it is
  the step `name`; for schema 1.2 documents (the AWS-managed shell documents) it is the
  plugin name with `:` replaced by `-`. Find the streams by listing with prefix
  `<command ID>/<instance ID>/` first.
- **On the node**: the agent keeps each run's output under
  `/var/lib/amazon/ssm/<instance ID>/document/orchestration/<command ID>/` (Windows:
  `C:\ProgramData\Amazon\SSM\InstanceData\<instance ID>\document\orchestration\<command ID>\`).
  Each step has its own subfolder with `stdout` and `stderr` files. Not observable to the
  agent; the operator can read them (for example
  `sudo find <that folder> -name stdout -o -name stderr | xargs sudo tail -n 100`). The
  agent prunes old run folders, so an old run may be gone.
- **S3**: `StandardOutputUrl` and `StandardErrorUrl` in `GetCommandInvocation`, under
  `OutputS3BucketName/OutputS3KeyPrefix/<command ID>/<instance ID>/...`. `s3:GetObject` is
  not in `AIDevOpsAgentAccessPolicy`: when it is denied, the content is not observable.
  Ask the operator for the end of the object first, with the command
  (`aws s3 cp s3://<bucket>/<key> - | tail -n 100`) or the on-node copy above, and to
  redact any secrets before sharing it. Never ask
  for S3 read for the agent's own role as the fix.

## Reading cut output

1. Look for a cut marker in each field before reading a cause from it.
2. The visible end is the API's cut. The script may have run long after it. A progress
   line such as "chunk 334 of 800" at the cut means nothing about where it stopped.
3. Warnings repeated many times on stderr (deprecated settings, "ignored") are usually
   noise; the exit code comes from the last command.
4. Map the exit code to the last command of the script (in `ListCommands` `Parameters`)
   for a labelled inference, for example curl exit 6 = could not resolve host, curl exit 7
   = could not connect, curl exit 22 = HTTP error with `-f`.

## Status and StatusDetails

Match `StatusDetails` values without regard to spaces or case: the API and the
documentation write some of them differently (for example `DeliveryTimedOut` and
"Delivery Timed Out").

| StatusDetails | Meaning | Counts toward MaxErrors | What it tells you |
|---|---|---|---|
| `Pending`, `InProgress`, `Delayed` | Not finished; `Delayed` = the node did not answer, the system retries | - | Wait or check the node |
| `Success` | Last command exited 0 | No | Check earlier errors (exit code rule) and precondition skips |
| `Failed` | Non-zero exit | Yes | Script error: quote it |
| `ExecutionTimedOut` | Ran past the execution timeout | Yes | T4 |
| `DeliveryTimedOut` | Not delivered before the delivery timeout | No | Managed-node problem (T2) |
| `Undeliverable` | Node not found, not managed, or no permission | No | Managed-node problem (T2) |
| `Terminated` | The command passed `MaxErrors`; this invocation was stopped or never started | - | Never ran (`ResponseCode -1`). Not broken. `Status` may show `Failed`: go by `StatusDetails` |
| `Canceled` | Someone canceled it | - | Check CloudTrail `CancelCommand` |
| `Invalid Platform` | Document does not support the node's platform | No | T5 |
| `Access Denied` | The caller lacked permission for that node | No | T1 |

`ResponseCode -1` means the plugin never started on the node.

## Target resolution

- `InstanceIds`: one invocation per listed node; a node that is not managed shows
  `Undeliverable`.
- `Targets` (tag, resource group): only managed nodes that match get an invocation. A
  tagged node that is not managed gets **no invocation at all** and no error. Compare the
  tagged instances (`ec2:DescribeInstances` with `tag:<key>` filter) with the invocation
  list to find them.
- `MaxConcurrency` sets how many run at once; once errors pass `MaxErrors`, the rest are
  `Terminated`. Which nodes ran first is not set by the operator.

## Exit code rule

A shell script's status is the exit code of its last command. Earlier failures are hidden
unless the script stops on errors or checks each exit code. Propose that change as a diff,
together with the fix for the failing input:

- Linux: `set -e`, or an explicit check after the command that matters
  (`dnf install -y pkg || exit 1`). Add `-u` only when the script sets every variable it
  uses: Run Command shells can run without `HOME` and other variables set. Add `-o pipefail` only when the script runs in bash:
  the shell documents run the script with `sh`, which is dash on Debian and Ubuntu and
  rejects `-o pipefail`.
- Windows PowerShell: `$ErrorActionPreference = 'Stop'`, and a check of `$LASTEXITCODE`
  after native commands.
