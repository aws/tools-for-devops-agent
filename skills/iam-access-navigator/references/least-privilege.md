# Least-privilege synthesis

Propose the smallest IAM policy that covers what a role actually did. This is the
capability where a wrong step silently removes permissions a workload needs, so
the coverage rules here are not optional.

## Procedure
1. **Current grant:** union of Allow actions across the role's managed and inline
   policies (lowercased for comparison; preserve `*`).
2. **Observed usage:** analyze CloudTrail for the role over a lookback window
   (default 90 days). `LookupEvents` returns **management events only** — see
   Nuance 4 before treating any granted action as unused.
3. **Build** the least-privilege policy from observed usage.
4. **Diff** current vs proposed; compute reduction.
5. **Validate** the result (see `policy-validation.md`) — always.

## Nuance 1 — session name vs role name (the false-zero trap)
CloudTrail `LookupEvents` has **no role-name lookup attribute**. Its `Username`
attribute resolves to the **session name** for assumed-role activity (the
`RoleSessionName`, or a service-generated name for AWS-service callers), *not*
the role name. Valid lookup attribute keys are only: EventId, EventName,
ReadOnly, Username, ResourceType, ResourceName, EventSource, AccessKeyId. And
`AccessKeyId` does not help — each assumed-role session gets fresh STS creds.

So filtering server-side by `Username = <role name>` returns a **systemic false
"0 events"** for every role. Instead:
- Query the window **unfiltered** (paginate the whole thing).
- Match **client-side** on `userIdentity.arn`, accepting both:
  - direct: arn ends with `role/<role_name>`
  - assumed: arn contains `role/<role_name>/` (the trailing `/` before the
    session name)
- The boundary after `<role_name>` prevents a prefix name (`app-role`) from
  absorbing `app-role-v2`'s events.
- Skip `GetCallerIdentity`, `AssumeRole`, `GetSessionToken` — credential-check
  noise, not real usage.
- Cross-check against IAM `RoleLastUsed`, which is a separate, always-accurate
  last-used timestamp.

Cap pagination (e.g. 50/page × 20 pages = 1000 events); if you hit the cap, mark
the result **truncated** and say so.

## Nuance 2 — unused → empty, but only when you are sure
- CloudTrail scan **succeeded**, zero matching events → least-privilege policy is
  an empty statement list, 100% reduction. Say the role **appears unused** and
  recommend deactivate→monitor→remove, not a bare delete.
- CloudTrail lookup **failed** (unavailable: AccessDenied, throttle, no trail,
  error) → **refuse to propose a policy**. Return the coverage failure and
  explain: a policy built on "no data" would strip permissions the role needs.
  This is the most dangerous silent failure the skill can make; do not make it.

Distinguish the two states explicitly in your coverage report: `empty`
(succeeded, zero) vs `unavailable` (failed). "Appears unused" also requires that
Nuance 4 does not apply.

## Nuance 4 — management events only (the data-plane blind spot)
CloudTrail event history and `LookupEvents` contain **management events only**.
Data events — S3 object-level calls such as `GetObject`, `PutObject`,
`DeleteObject` — are never in event history, and a trail records them only if
data-event logging was explicitly turned on (it is off by default). So zero
S3 object activity in `LookupEvents` means **"not observable"**, not "unused".
The same applies to any other action CloudTrail logs only as a data event
(for example `lambda:InvokeFunction`, DynamoDB item reads/writes).

Before building the policy, check the current grant for S3 object actions:
`s3:GetObject*`, `s3:PutObject*`, `s3:DeleteObject*`, `s3:RestoreObject`,
`s3:AbortMultipartUpload`, `s3:ListMultipartUploadParts`, and any wildcard that
covers them (`s3:*`, `s3:Get*`, `s3:Put*`, `s3:Delete*`, `*`). If any are
granted **and you have no data-event source** for the window (you queried only
`LookupEvents`, which is the default), then:
- **Do not drop them.** Carry every granted S3 object action into the proposed
  policy unchanged, with its current resources, and label it "kept — usage not
  observable from management events" in the summary table, never as a key or
  comment inside the policy JSON (IAM policies have no comment field; the policy
  must stay valid, apply-ready JSON).
- **Do not add to them.** Keep exactly what is granted; skip the optional
  headroom below for S3, since there is no observed usage to size it from.
- **Do not call the role unused.** If the role's only observed activity is zero
  and it holds S3 object actions, say its management-plane activity is zero but
  its S3 object usage is unknown, and do not recommend deactivate → remove on
  that basis.
- **Warn** in the policy summary and the coverage report: name the actions you
  kept unverified, and say that confirming them needs S3 data events (a trail or
  CloudTrail Lake event data store with S3 data events enabled) or S3 server
  access logs, which this skill does not read.
- If the role's grants are **all** data-plane actions, refuse to propose a
  reduced policy: there is nothing you can observe to reduce it from.

Report the S3 data-plane source as `unavailable` in the coverage contract
whenever this nuance applies — never as `empty`.

## Nuance 3 — valid IAM actions, not raw event names
Map `eventSource` + `eventName` → `service:Action`. Service =
`eventSource` minus `.amazonaws.com`.

**Lambda date-suffix quirk:** some Lambda event names carry an 8-digit
API-version date suffix (Lambda's stable `2015-03-31` API → `20150331`), e.g.
`ListFunctions20150331` → `lambda:ListFunctions`, `GetFunction20150331` →
`lambda:GetFunction`. Strip a trailing 8-all-digit run **only when service ==
lambda**. Do **not** strip trailing digits globally — you would corrupt action
names that legitimately end in digits. The mapping is still imperfect (event
names are not always the IAM verb), which is exactly why Capability 6 validation
is mandatory.

## Building the policy
- Group used actions by service; one statement per service, `Sid` =
  `<Service>Access`.
- Optional headroom (default on, except where Nuance 4 applies): add safe companion actions —
  s3:{ListBucket,GetBucketLocation}, logs:{CreateLogGroup,CreateLogStream,
  PutLogEvents}, sts:{GetCallerIdentity}, ec2:{DescribeRegions}.
- Resource scoping: collect observed resource ARNs per action from event
  `Resources`; if any were seen, scope to them (cap the list); else `"*"`.

## Reduction metrics and warnings
- reduction % = removed ÷ current × 100. Risk of the change: > 70% HIGH,
  > 40% MEDIUM, else LOW.
- Warn if lookback < 30 days ("may miss monthly batch jobs").
- Warn if reduction > 80% ("double-check no seasonal workloads were missed").
- Explain *what* was removed and *why* in words, not just the diff.

## Account ID
Resolve with `sts:GetCallerIdentity` — no IAM permission required, callable by
any principal. Cache it for the session.
