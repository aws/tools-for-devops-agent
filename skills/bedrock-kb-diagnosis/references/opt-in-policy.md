# Opt-in policy grant

Detecting a dropped file needs no extra permission: the skill compares the latest `COMPLETE`
job's `numberOfDocumentsScanned` with the count of documents `ListKnowledgeBaseDocuments`
returns (all statuses, all pages), both already granted by `AIDevOpsAgentAccessPolicy` (v15).
Two capabilities beyond the managed policy are opt-in, added as one parameter in the shared
`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml` template.

## What the grant adds

| Action | Scope | Why it is needed | Behavior without it |
| --- | --- | --- | --- |
| `bedrock:GetIngestionJob` | this account's knowledge bases | Names an unsupported dropped file and returns job-level `failureReasons` | An unsupported drop is detected but not named |
| `s3:ListBucket` | the buckets in `BedrockKbSourceBucketArns` | Source staleness and file checks; sizing an oversized dropped file to name it | Staleness/file checks reported **Not checked**; an oversized drop is detected but not named |

`s3:GetBucketLocation` is already in the managed policy, so it is not added here. The managed
policy allows `s3:ListBucket` only for the `AWSLogs/*` prefix, which is why listing a source
bucket needs this grant.

## Template wiring (matches the deployed pattern)

- Parameter `BedrockKbSourceBucketArns` (`CommaDelimitedList`, default `''`) and condition
  `HasBedrockKbSourceBuckets: !Not [!Equals [!Join ['', !Ref BedrockKbSourceBucketArns], '']]`,
  mirroring `AllowedRegions` / `HasRegionRestriction`.
- `GetIngestionJob` scoped to `arn:${AWS::Partition}:bedrock:*:${AWS::AccountId}:knowledge-base/*`.
- The `s3:ListBucket` statement sits behind `!If [HasBedrockKbSourceBuckets, {...}, !Ref AWS::NoValue]`
  with `Resource: !Ref BedrockKbSourceBucketArns`, so with no bucket set the statement is omitted
  and the stack still deploys; with buckets set, only those are listable.

```yaml
- Sid: BedrockGetIngestionJob
  Effect: Allow
  Action:
    - bedrock:GetIngestionJob
  Resource: !Sub 'arn:${AWS::Partition}:bedrock:*:${AWS::AccountId}:knowledge-base/*'
- !If
  - HasBedrockKbSourceBuckets
  - Sid: SourceBucketListing
    Effect: Allow
    Action:
      - s3:ListBucket
    Resource: !Ref BedrockKbSourceBucketArns
  - !Ref AWS::NoValue
```

All actions are read-only.
