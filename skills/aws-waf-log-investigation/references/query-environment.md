# Query environment under DevOps Agent

## Why Athena fails with "Access denied when writing output"

When DevOps Agent assumes its Agent Space role, it attaches a session policy (the permission
guardrail). Effective permissions are the intersection of the role's policies and that session
policy. The session policy is `AIDevOpsAgentAccessPolicy` + `ReadOnlyAccess` + a short list of
extras that includes `athena:StartQueryExecution`, `athena:StopQueryExecution` and `kms:Decrypt`.
`s3:PutObject` is not in it.

Athena writes the result CSV to the output location using the caller's credentials. So a normal
workgroup fails every query at the last step, whatever bucket you point it at and whatever the
role allows. Symptoms:

- `StartQueryExecution` succeeds, the query scans data, then ends FAILED with
  "Access denied when writing output to url: s3://...".
- Reads of the data bucket and Glue tables work.
- Switching result buckets gives the same error.

Athena wraps the S3 error, so the text never says "because no session policy allows". The same
denial on the Glue path does say it, for example on `glue:CreateTable`.

## What works

A workgroup with **Athena managed query results**. Athena stores results itself and you read
them with `GetQueryResults`. Rules:

- Discover it: `ListWorkGroups`, then `GetWorkGroup` on each, and use one whose configuration has
  `ManagedQueryResultsConfiguration.Enabled = true`.
- Call `StartQueryExecution` with `WorkGroup=<that name>` and no `ResultConfiguration`. Passing
  an `OutputLocation` is rejected with "ManagedQueryResultsConfiguration and ResultConfiguration
  cannot be set together", with or without `EnforceWorkGroupConfiguration`.
- The role needs `athena:StartQueryExecution`, `GetQueryExecution`, `GetQueryResults` (and
  `GetQueryResultsStream`, `BatchGetQueryExecution`, `StopQueryExecution`) on that workgroup,
  plus `s3:GetObject` / `s3:ListBucket` on the log bucket. The default
  `AIDevOpsAgentAccessPolicy` does not grant `StartQueryExecution` or `GetQueryResults`; the
  user has to add them.
- Results are kept 24 hours. Query result reuse is not supported, so a repeated query rescans.
- If the log bucket is KMS-encrypted, the role also needs `kms:Decrypt` on that key.

If the user has no such workgroup, give them this to run (it does not change existing
workgroups):

```
aws athena create-work-group --region <log-bucket-region> --name devops-agent \
  --configuration '{"ManagedQueryResultsConfiguration":{"Enabled":true}}'
```

Do not suggest enabling managed results on `primary` without asking: other tools that pass an
explicit output location or use result reuse would start failing there.

## What does not work, and what to tell the user

| Need | Why it fails | Tell the user |
|---|---|---|
| Create the Athena table over WAF logs | `glue:CreateTable` is outside the guardrail, even if the role grants it | Create it yourself; AWS documents a WAF log table with partition projection |
| CTAS, INSERT, UNLOAD | Writes to S3 | Not available; use SELECT and summarise |
| Change WAF rules | Mutating action | Write the change as a plan with backup, LockToken and rollback; a human applies it |

## Finding the right table

1. `wafv2:GetLoggingConfiguration` for the WebACL gives `LogDestinationConfigs`.
   - `arn:aws:s3:::aws-waf-logs-...`: logs go straight to that bucket under
     `AWSLogs/<account>/WAFLogs/<region>/<webacl>/...`.
   - `arn:aws:firehose:...`: `firehose:DescribeDeliveryStream` gives the bucket and prefix.
   - `arn:aws:logs:...:log-group:aws-waf-logs-...`: use Logs Insights, no table needed.
2. Find the bucket's Region (`s3:GetBucketLocation`; `null` means us-east-1). Glue and Athena
   calls go to that Region.
3. List Glue databases and tables there. Pick the table whose `StorageDescriptor.Location`
   covers the logging path. If its location is the bucket root or a shared prefix, more than one
   WebACL may be in it: add a `webaclid` filter (see log-data-facts.md).
4. Read its partition projection parameters (`projection.*`, `storage.location.template`). The
   format and range decide your partition predicate.

If two tables match, prefer the one whose projection format matches the newest objects in the
bucket. A table whose projection range does not cover the window returns zero rows with no
error.

## Cost and speed

Athena charges by bytes scanned. On minute-partitioned logs, scan cost tracks the window width.
On hourly partitions you pay for whole hours, so narrowing below an hour saves nothing. The number
of queries usually matters more than the width of each: plan a few well-chosen aggregations
rather than many small ones. Large windows over minute partitions also slow query planning,
because Athena expands the declared projection range.
