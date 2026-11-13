# Opt-in policy grant

Two reads this skill needs are not in the default `AIDevOpsAgentAccessPolicy` (v15). They are
bundled as one opt-in parameter in the shared
`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml` template, added
following the same convention as the other skills' opt-in parameters in that file.

## What the grant adds

| Action | Why it is needed | Behavior without it |
| --- | --- | --- |
| `bedrock:GetIngestionJob` | The only call that returns `failureReasons`, and the only way to name a file dropped at intake (an oversized or unsupported file is absent from both `ListKnowledgeBaseDocuments` and the ingestion logs) | Drops inferred from job `statistics` (`scanned - indexed - failed - skipped`); file identities reported **Not checked** |
| `s3:ListBucket`, `s3:GetBucketLocation` (scoped to the source buckets) | Staleness and file checks over the data source inclusion prefix | Staleness and file checks reported **Not checked** |

The default managed policy already allows `s3:ListBucket` only for the `AWSLogs/*` prefix,
which is why listing a data source bucket needs this grant.

## Statements to add (scope to your data source buckets)

```yaml
- Effect: Allow
  Action:
    - bedrock:GetIngestionJob
  Resource: "*"   # scope to your knowledge base / ingestion-job ARNs
- Effect: Allow
  Action:
    - s3:ListBucket
    - s3:GetBucketLocation
  Resource:
    - arn:aws:s3:::<your-data-source-bucket>
```

Place these behind the template's opt-in parameter (a `Condition` that gates the statements on
the parameter being enabled), matching how the existing opt-in parameters are structured in
`devops-agent-skill-policies.yaml`. All actions are read-only.
