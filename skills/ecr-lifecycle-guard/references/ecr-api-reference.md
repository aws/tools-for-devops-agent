# API Reference for ECR Lifecycle Guard

Load this file at Step 1 of the execution flow, before the first API call. It
lists every operation the skill may call, the fields it reads, how each call is
paginated, how errors are classified, and the operations it must never call.
Everything is control plane and read only. Data is read with the agent's native
AWS tooling under the Agent Space role. No credentials are requested from the
user.

## 1. API allowlist

"Managed policy" means `AIDevOpsAgentAccessPolicy` v11 (edited 2026-09-24),
checked 2026-10-26 at
https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html.

| Service | Operation | IAM action | Managed policy | Pagination | Fields read | Purpose |
|---|---|---|---|---|---|---|
| STS | GetCallerIdentity | none required | n/a | none | `Account` | Account id for the report and registry URI matching |
| EC2 | DescribeRegions | `ec2:DescribeRegions` | Yes (`ec2:Describe*`) | none | `Regions[].RegionName` | Only when the user asks for all Regions; `AllRegions=false` |
| ECR | DescribeRepositories | `ecr:DescribeRepositories` | Yes (`ecr:Describe*`) | `nextToken`, `maxResults` up to 1000 | `repositoryName`, `repositoryUri`, `registryId` | Multi repo mode inventory |
| ECR | DescribeImages | `ecr:DescribeImages` | Yes (`ecr:Describe*`) | `nextToken`, `maxResults` up to 1000 | `imageDigest`, `imageTags`, `imagePushedAt`, `lastRecordedPullTime`, `imageStatus`, `imageManifestMediaType`, `artifactMediaType`, `subjectManifestDigest`, `lastActivatedAt`, `lastArchivedAt` | Image set, tag to digest map, pull recency |
| ECR | GetLifecyclePolicy | `ecr:GetLifecyclePolicy` | Yes | none | `lifecyclePolicyText`, `lastEvaluatedAt` | The attached policy |
| ECR | StartLifecyclePolicyPreview | `ecr:StartLifecyclePolicyPreview` | **No** | none | `status` | Ask ECR to evaluate the attached policy, or a draft passed in `lifecyclePolicyText` |
| ECR | GetLifecyclePolicyPreview | `ecr:GetLifecyclePolicyPreview` | **No** | `nextToken`, `maxResults` 1 to 100 | `status`, `previewResults[]` (`imageDigest`, `imageTags`, `imagePushedAt`, `appliedRulePriority`, `action.type`, `storageClass`), `summary.expiringImageTotalCount`, `lifecyclePolicyText` | Authoritative expiring set |
| ECS | ListClusters | `ecs:ListClusters` | Yes (`ecs:List*`) | `nextToken` | `clusterArns[]` | Running task and service scan |
| ECS | ListTasks | `ecs:ListTasks` | Yes | `nextToken`, 100 per page | `taskArns[]` | Per cluster, `desiredStatus=RUNNING` |
| ECS | DescribeTasks | `ecs:DescribeTasks` | Yes (`ecs:Describe*`) | 100 task ARNs per call | `tasks[].containers[].image`, `tasks[].containers[].imageDigest`, `tasks[].taskDefinitionArn` | Strongest in use evidence (running container digest) |
| ECS | ListServices | `ecs:ListServices` | Yes | `nextToken`, 100 per page | `serviceArns[]` | Per cluster |
| ECS | DescribeServices | `ecs:DescribeServices` | Yes | 10 service ARNs per call | `services[].taskDefinition`, `services[].deployments[].taskDefinition` | Task definitions a service will launch |
| ECS | ListTaskDefinitions | `ecs:ListTaskDefinitions` | Yes | `nextToken`, `maxResults` up to 100 | `taskDefinitionArns[]` | `status=ACTIVE`, `sort=DESC` |
| ECS | ListTaskDefinitionFamilies | `ecs:ListTaskDefinitionFamilies` | Yes | `nextToken` | `families[]` | Bounded fallback, see section 5 |
| ECS | DescribeTaskDefinition | `ecs:DescribeTaskDefinition` | Yes | one per call | `taskDefinition.containerDefinitions[].image` | Image URIs a task definition references |
| Batch | DescribeJobDefinitions | `batch:DescribeJobDefinitions` | **No** | `nextToken`, `maxResults` up to 100 | `jobDefinitions[].containerProperties.image`, `nodeProperties.nodeRangeProperties[].container.image`, `ecsProperties.taskProperties[].containers[].image`, `eksProperties.podProperties.containers[].image` | `status=ACTIVE`; often AccessDenied under the managed policy |
| Lambda | ListFunctions | `lambda:ListFunctions` | Yes (`lambda:List*`) | `Marker`, `MaxItems` up to 50 | `Functions[].FunctionName`, `Functions[].PackageType` | Select `PackageType=Image` |
| Lambda | GetFunction | `lambda:GetFunction` | **No** | one per call | `Code.ImageUri`, `Code.ResolvedImageUri` | Image URI and resolved digest of container image functions |
| App Runner | ListServices | `apprunner:ListServices` | Yes (`apprunner:List*`) | `NextToken`, `MaxResults` up to 20 | `ServiceSummaryList[].ServiceArn`, `Status` | Service inventory |
| App Runner | DescribeService | `apprunner:DescribeService` | Yes (`apprunner:Describe*`) | one per call | `Service.SourceConfiguration.ImageRepository.ImageIdentifier`, `Service.Status` | ECR image a service runs |
| EKS | ListClusters | `eks:ListClusters` | Yes (`eks:List*`) | `nextToken` | `clusters[]` | Presence only; pod image references are data plane and out of scope |
| CloudTrail | LookupEvents | `cloudtrail:LookupEvents` | Yes | `NextToken`, `MaxResults` up to 50 | `Events[].EventName`, `Events[].EventTime`, `CloudTrailEvent` (JSON string with `eventTime`, `userIdentity`, `requestParameters.imageIds`, `repositoryName`) | Optional tier (c) pull evidence and `PutImage` push principal; see section 6 |

`lambda:GetFunctionConfiguration` is in the managed policy and returns
`PackageType` but not the image URI, so it cannot replace `GetFunction`.

## 2. Hard denials

The skill never calls any of the following, in any mode, for any reason,
including a direct request from the user. If asked, it explains that it reports
and never remediates, and hands the operator the exact change to make.

- `ecr:PutLifecyclePolicy`, `ecr:DeleteLifecyclePolicy`
- `ecr:BatchDeleteImage`, `ecr:PutImage`, `ecr:PutImageTagMutability`,
  `ecr:DeleteRepository`, `ecr:CreateRepository`, `ecr:PutReplicationConfiguration`,
  `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` (pulling an image would create
  a `lastRecordedPullTime` and corrupt the evidence)
- Any `ecs:*`, `batch:*`, `lambda:*`, `apprunner:*`, `eks:*` operation that is
  not `List*`, `Describe*` or `Get*`
- Any operation not in the allowlist above

`StartLifecyclePolicyPreview` is the one operation the agent may flag as
mutating. It is not in this list because it computes a result and changes no
repository content. See section 3.

## 3. Preview procedure

1. Call `StartLifecyclePolicyPreview` with `repositoryName`. Omit
   `lifecyclePolicyText` to preview the attached policy. Pass it only when the
   user supplied a draft policy in chat. If the repository has no policy and no
   text was passed, ECR returns `LifecyclePolicyNotFoundException`.
2. Possible outcomes of the start call:
   - Success with `status: IN_PROGRESS`: continue to polling.
   - `LifecyclePolicyPreviewInProgressException` ("The previous lifecycle policy
     preview request has not completed. Wait and try again."): a preview is
     already running for this repository. Do not retry the start call. Wait 5
     seconds and go to polling. Only one preview runs per repository at a time.
   - `AccessDeniedException`: record source status `AccessDenied` for the
     preview and go to the simulation fallback.
   - Tool policy cancellation (`Cancelled mutative operation: ecr
     StartLifecyclePolicyPreview. This operation requires an operator approval
     to execute.` or similar): this is the agent's guardrail, not IAM. Explain
     once, in one short paragraph, that the preview computes which images the
     policy would act on and deletes, archives or changes nothing, and ask the
     operator to approve it. If approved, repeat step 1. If declined, not
     answered, or cancelled again, record `ToolingFailure` and go to the
     simulation fallback. Ask once per run, not once per repository.
3. Poll `GetLifecyclePolicyPreview` every 5 seconds for up to 60 seconds:
   - `COMPLETE`: read every page (`nextToken`) of `previewResults`, and
     `summary.expiringImageTotalCount`. The count must equal the number of
     results collected. Label the expiring set `AUTHORITATIVE`.
   - `IN_PROGRESS`: keep polling.
   - `EXPIRED` or `FAILED`: start one new preview (step 1) and poll again. If
     the second attempt also ends `EXPIRED` or `FAILED`, record `ToolingFailure`
     and fall back to simulation.
   - `LifecyclePolicyPreviewNotFoundException` ("There is no dry run for this
     repository."): no preview exists; go to step 1 if you have not started one,
     otherwise record `ToolingFailure`.
   - Still `IN_PROGRESS` after 60 seconds: record `ToolingFailure`, fall back to
     simulation, and tell the operator the preview can be read later with
     `GetLifecyclePolicyPreview`.
4. The preview evaluates against the images present at that moment. State the
   preview time in the report. ECR keeps preview results for a limited time and
   reports `EXPIRED` once they are gone; the exact retention period is not
   stated in the public documentation (see section 8).
5. `GetLifecyclePolicyPreview` also accepts `imageIds` and `filter.tagStatus`.
   Do not use them for the main read; always read the unfiltered, paginated
   result so the count is complete.

Access level, from the AWS service reference for ECR
(https://servicereference.us-east-1.amazonaws.com/v1/ecr/ecr.json, read
2026-10-26): `StartLifecyclePolicyPreview` is classified `IsWrite: true`;
`GetLifecyclePolicyPreview` is `IsWrite: false`. This is why a read only
guardrail may block the start call even though it changes no image, tag, or
policy. The API reference for `StartLifecyclePolicyPreview` describes it as a
way to "see the results before associating the lifecycle policy with the
repository".

## 4. Error classification

| Response | Source status | Effect |
|---|---|---|
| `AccessDeniedException` on any call | `AccessDenied` | The source is "not checked". Every expiring image without a confirmed reference becomes `Expiring-Unknown` if the source is an in use source. Never read a denial as "no references". |
| `Cancelled mutative operation ...` (tool policy) | `ToolingFailure` | Same effect as `AccessDenied`. Report it as a guardrail cancellation, not as an IAM gap, so the operator fixes the right thing. |
| `LifecyclePolicyNotFoundException` on `GetLifecyclePolicy` | n/a | No policy attached. Check P1 reports INFO, expiring set is empty, rating `Healthy`. If the user supplied a draft, evaluate the draft instead. |
| `LifecyclePolicyPreviewInProgressException` | n/a | Wait 5 seconds, poll `GetLifecyclePolicyPreview`. |
| `LifecyclePolicyPreviewNotFoundException` | n/a | Start a preview first. |
| `RepositoryNotFoundException` | n/a | Stop for that repository and say the name was not found in this Region and registry. Do not guess a Region. |
| `ThrottlingException`, `TooManyRequestsException` | retry | Back off 2 seconds, then 5 seconds. After two failures record `ToolingFailure` for that source. |
| Empty list from a successful call (for example `ListTaskDefinitions` returns no ARNs) | `OK` | Empty success is data. The source was checked and holds no references. |
| `ServerException` (HTTP 500) | retry once, then `ToolingFailure` | Never treat as empty. |

## 5. In use inventory and URI matching

Build the inventory once per Region and reuse it for every repository in that
Region. A reference is a string that names an ECR image. Parse it as:

```
<registryId>.dkr.ecr.<region>.amazonaws.com/<repositoryName>:<tag>
<registryId>.dkr.ecr.<region>.amazonaws.com/<repositoryName>@sha256:<digest>
<registryId>.dkr.ecr.<region>.amazonaws.com/<repositoryName>:<tag>@sha256:<digest>
```

Matching rules:

- A digest reference matches an expiring image when the digest is equal.
- A tag reference matches when `<registryId>`, `<region>` and `<repositoryName>`
  equal the repository under review and the tag resolves, through the tag to
  digest map built from `DescribeImages`, to an expiring digest. A tag that no
  longer exists in the repository is reported as a dangling reference (the
  consumer is already broken) and is not a match.
- `tasks[].containers[].imageDigest` from `DescribeTasks` matches directly by
  digest and is the strongest evidence, because it names what is running now.
- Lambda `Code.ResolvedImageUri` carries a digest; `Code.ImageUri` may carry a
  tag. Check both.
- A multi tag digest is one image. It matches if any of its tags or its digest is
  referenced. Report it as one row listing every tag.
- References to other registries, Regions, or repositories are ignored for this
  repository but counted in the inventory summary.

Source coverage per Region, with the bounded ECS task definition scan:

| Source | Calls | Full coverage | `Partial` coverage |
|---|---|---|---|
| ECS running tasks | `ListClusters`, per cluster `ListTasks desiredStatus=RUNNING`, `DescribeTasks` in batches of 100 | every running task described | never partial; if a cluster call fails, record it in Not Assessed |
| ECS services | per cluster `ListServices`, `DescribeServices` in batches of 10 | every service's current and deploying task definitions | same |
| ECS task definitions | `ListTaskDefinitions status=ACTIVE sort=DESC`, all pages | if 200 or fewer ARNs, describe every one | if more than 200, describe the latest ACTIVE revision per family (`ListTaskDefinitionFamilies status=ACTIVE`, then `DescribeTaskDefinition <family>`) plus every task definition referenced by a running task or service, and record `Partial` |
| Batch job definitions | `DescribeJobDefinitions status=ACTIVE`, all pages | every ACTIVE job definition | n/a |
| Lambda | `ListFunctions`, all pages; `GetFunction` for each `PackageType=Image` | every image function | `GetFunction` denied: `AccessDenied` for the source |
| App Runner | `ListServices`, `DescribeService` per service | every service, any status | n/a |
| EKS | `ListClusters` | presence only | always "pod references not checked" when at least one cluster exists |
| CloudTrail | see section 6 | optional | `NotChecked` is not a finding |

`Partial` on the ECS task definition source makes every expiring image without a
confirmed reference `Expiring-Unknown`, with the reason "ECS task definition
scan bounded at 200 ARNs". Never claim full coverage after a bounded scan.

## 6. Optional CloudTrail pull probe (evidence tier (c))

In use evidence is ranked, strongest first:

- (a) `lastRecordedPullTime` present on the image (`DescribeImages`). ECR
  maintains it from real pulls and refreshes it at least once every 24 hours,
  so a pull in the last day may not show yet. Authoritative when present.
- (b) a reference by tag or digest in an ECS running task, ECS service or ACTIVE
  task definition, Batch ACTIVE job definition, Lambda image function URI, or
  App Runner service (section 5). Confirmed.
- (c) a CloudTrail `BatchGetImage` or `GetDownloadUrlForLayer` event on the
  digest or tag. Circumstantial, and the only tier that is filtered.

Purpose of tier (c): find direct pulls (EC2 hosts, CI runners, developer
laptops) that no task or function definition records. A qualifying pull makes
the image `Expiring-InUse`. Absence of events is not evidence of non use.

- Call `LookupEvents` with `LookupAttributes=[{AttributeKey: EventName,
  AttributeValue: BatchGetImage}]` and again with `GetDownloadUrlForLayer`,
  `StartTime` = now minus 30 days (or the window the user set), paginate
  with `NextToken`. `LookupEvents` covers the last 90 days of management
  events and is rate limited, so cap the probe at 20 pages per event name per
  Region. Call it a third time with `PutImage` for the same window so the
  pushing principal of each expiring digest is known.
- Parse `CloudTrailEvent` and match `requestParameters.repositoryName` and
  `requestParameters.imageIds[].imageTag` or `imageDigest` against the
  expiring set. Keep `eventTime` and `userIdentity` (`arn`, `principalId`,
  `sessionContext.sessionIssuer.arn`) for every matched event.
- **Push correlation rule.** Before any matched event counts, drop:
  1. every `BatchGetImage`, `GetDownloadUrlForLayer`, `PutImage`,
     `InitiateLayerUpload`, `CompleteLayerUpload` or
     `BatchCheckLayerAvailability` event whose `eventTime` is within 60
     seconds of that image's `imagePushedAt`; the push workflow reads the
     manifest and checks layers, and these events are the push, not a pull;
  2. every event whose `userIdentity` matches the principal that performed the
     push. Take that principal from the `PutImage` event for the same digest
     when one was found; otherwise take it from the events inside the 60
     second window. Compare on `sessionContext.sessionIssuer.arn` (the role)
     when present, else on `arn`.
  Count the dropped events per image and in total; the total is reported in
  check U8. An image is `Expiring-InUse` on tier (c) only when at least one
  event remains more than 60 seconds after `imagePushedAt`. The evidence string
  names the event, its time, the principal, and the gap from push, for example
  `tier (c) CloudTrail BatchGetImage 2026-10-25 14:02 UTC by role
  batch-worker-instance-role, 4 days after push`. When every matched event was
  dropped, the evidence string is `push correlated events only (n excluded),
  no tier (a) or (b) evidence`.
- Also look up `EventName=PolicyExecutionEvent` when the user asks why an image
  disappeared; those events list the images ECR expired.
- The agent guardrail has been observed cancelling the whole `cloudtrail`
  namespace in other skills. A cancellation sets the source to `ToolingFailure`,
  which does not change any verdict for this optional source and is listed
  under Not Assessed.

Observed 2026-10-27 on a 26 image fixture: every image had a `BatchGetImage`
event 1 to 2 seconds after its `imagePushedAt` from the pushing principal, and
`lastRecordedPullTime` was set on exactly one image. Without the rule above
every expiring image would be reported in use.

## 7. Source status enum

| Status | Meaning | Effect on verdicts | Effect on rating |
|---|---|---|---|
| `OK` | Every call for the source succeeded and all pages were read | References found are in use evidence; none found means none in that source | none |
| `Partial` | The source was read within a documented bound | Found references count; unreferenced expiring images become `Expiring-Unknown` | at most `Attention` unless an `Expiring-InUse` exists |
| `AccessDenied` | IAM denied a required call | Unreferenced expiring images become `Expiring-Unknown` (in use sources only) | at most `Attention` unless an `Expiring-InUse` exists |
| `ToolingFailure` | Guardrail cancellation, throttling after retries, server error | Same as `AccessDenied` | same |
| `NotChecked` | Source deliberately skipped (CloudTrail probe not requested, Region out of scope) | No effect for optional sources; for required sources treat as `ToolingFailure` | none for optional sources |

For the CloudTrail source, `OK` means the events were read and the push
correlation rule (section 6) was applied. Only events that survive it are
evidence.

For the expiring set itself: `AUTHORITATIVE` when it came from
`GetLifecyclePolicyPreview`, `SIMULATED` when it came from the semantics
procedure. A `SIMULATED` set caps the repository rating at `Attention` unless an
`Expiring-InUse` verdict exists, in which case the rating is `AtRisk` and the
report says the set must be confirmed with a preview.

## 8. Unverified facts

Each row names a claim the skill relies on that could not be confirmed from the
public documentation on 2026-10-26, or that was confirmed only indirectly. The
README repeats these as open questions for SME review.

| Claim | Where used | What to confirm | Source to check |
|---|---|---|---|
| Preview results are retained briefly and then return `EXPIRED` | section 3, step 4 | the retention period | ECR User Guide lifecycle policy preview page (did not render during authoring), or a live test |
| `BatchGetImage` and `GetDownloadUrlForLayer` pulls appear in `LookupEvents` as management events for ordinary pulls | section 6 | that pulls by EC2 hosts and CI appear with `requestParameters.imageIds`. Confirmed 2026-10-27 only for the push side: every push produced a `BatchGetImage` event 1 to 2 seconds later from the pushing principal, which is why the push correlation rule exists | https://docs.aws.amazon.com/AmazonECR/latest/userguide/logging-using-cloudtrail.html shows a `BatchGetImage` event example; confirm for consumer pulls in the target account |
| 60 seconds is a wide enough push correlation window | section 6 | observed gap was 1 to 2 seconds (up to 4 in one run); a slow multi layer push could exceed 60 seconds between `imagePushedAt` and the last layer event, though `imagePushedAt` is set when the manifest is put, which is the end of the push | live test transcripts 2026-10-27; SME judgement |
| The agent guardrail classifies `StartLifecyclePolicyPreview` as mutative in every Agent Space | section 3, step 2 | whether the platform can allowlist it | observed in gap transcripts on 2026-10-21; service reference marks the action `IsWrite: true` |
| `ListTaskDefinitions status=ACTIVE` with 200 ARNs is a reasonable bound | section 5 | tool call budget in the Agent Space | SME judgement |
| Batch job definition image fields cover every job type | section 1 | `ecsProperties` and `eksProperties` shapes | https://docs.aws.amazon.com/batch/latest/APIReference/API_JobDefinition.html |
| ECR rejects a policy whose `tagStatus: any` rule does not carry the highest `rulePriority` number | semantics step 1, check P2 | whether `PutLifecyclePolicy` returns `InvalidParameterException` or accepts the policy and reorders or ignores the rule | https://docs.aws.amazon.com/AmazonECR/latest/userguide/lifecycle_policy_parameters.html states the requirement only; confirm with a `PutLifecyclePolicy` attempt in a sandbox |
| `lastRecordedPullTime` is refreshed at least once every 24 hours and may lag | semantics, verdict rules | confirmed from `ImageDetail` doc; the skill therefore treats any pull inside the window as recent | https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_ImageDetail.html |

## 9. Documentation URLs

- AIDevOpsAgentAccessPolicy: https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html
- StartLifecyclePolicyPreview: https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_StartLifecyclePolicyPreview.html
- GetLifecyclePolicyPreview: https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_GetLifecyclePolicyPreview.html
- LifecyclePolicyPreviewResult: https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_LifecyclePolicyPreviewResult.html
- DescribeImages and ImageDetail: https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_DescribeImages.html and https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_ImageDetail.html
- ECR actions and access levels: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonelasticcontainerregistry.html
- ECR CloudTrail logging: https://docs.aws.amazon.com/AmazonECR/latest/userguide/logging-using-cloudtrail.html
- CloudTrail LookupEvents: https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html
- ECS DescribeTasks and Container: https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DescribeTasks.html and https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_Container.html
- ECS ListTaskDefinitions: https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ListTaskDefinitions.html
- Batch DescribeJobDefinitions: https://docs.aws.amazon.com/batch/latest/APIReference/API_DescribeJobDefinitions.html
- Lambda GetFunction and FunctionCodeLocation: https://docs.aws.amazon.com/lambda/latest/api/API_GetFunction.html and https://docs.aws.amazon.com/lambda/latest/api/API_FunctionCodeLocation.html
- App Runner DescribeService and ImageRepository: https://docs.aws.amazon.com/apprunner/latest/api/API_DescribeService.html and https://docs.aws.amazon.com/apprunner/latest/api/API_ImageRepository.html

## 10. Known quirks

Behaviours observed or documented that change how the skill calls or reads these
APIs. Each is already encoded in the execution flow and the verdict model; this
table is the lookup form.

| Quirk | Effect on the skill |
|---|---|
| One preview at a time per repository; a second start returns `LifecyclePolicyPreviewInProgressException` | Wait and poll; never retry the start call in a loop |
| Preview results are kept for a limited time and then report `EXPIRED` | Read all pages as soon as `COMPLETE`; restart once if `EXPIRED` |
| `StartLifecyclePolicyPreview` is a write access level action in IAM terms | The agent guardrail may cancel it; approval is safe because it changes nothing |
| `lastRecordedPullTime` is refreshed at least once every 24 hours | A pull in the last day may not show yet; any value inside the window counts as recent, and absence is never proof of non use |
| Images never pulled have no `lastRecordedPullTime` field | Missing field means "no recorded pull", not "unused" |
| `tagPrefixList` and `tagPatternList` entries are ANDed across the list | A two entry list protects only images carrying both tags; suggest one rule per family |
| `tagStatus: any` must carry the highest `rulePriority` number | Catch all is always evaluated last and claims only what higher rules left |
| A higher priority rule's candidates are claimed even when that rule does not expire them | This is why a 14 day `rc-` rule stops the catch all from touching `rc-` images |
| Multi tag digests match through any tag and are expired once | One row per digest |
| Manifest list children are not expired while the list exists | Remove them from a simulated set and say so |
| `archive` action and `imageStatus ARCHIVED` exist | Archive is treated as removal for verdicts and shown in the Action column |
| ECR acts within 24 hours of an image meeting the criteria | A HIGH or CRITICAL finding is urgent |
| Lifecycle actions appear in CloudTrail as `PolicyExecutionEvent`, previews as `DryRunEvent` | Use `LookupEvents` on these names for "why did my image disappear" |
| `batch:DescribeJobDefinitions` and `lambda:GetFunction` are not in the managed policy | Expect `AccessDenied` until the delta policy is attached; report Unknown, not Unused |
| The guardrail has cancelled the whole `cloudtrail` namespace in other skills | The pull probe is optional; a cancellation is listed under Not Assessed and changes no verdict |
| An image push emits `BatchGetImage` (and layer events) 1 to 2 seconds after `imagePushedAt`, from the pushing principal (observed 2026-10-27 on 26 of 26 images) | The push correlation rule drops these events; they are counted in U8 and never make an image `Expiring-InUse` |
