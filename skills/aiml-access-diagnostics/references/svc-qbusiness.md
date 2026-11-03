# Service Specifics - Amazon Q Business

Load only when the failing call is a Q Business operation.

Q Business is the service where **IAM is necessary but not sufficient**. Unlike every
other service in this skill, Q Business has a second authorization layer that runs AFTER
IAM succeeds: the user must be assigned to the application in IAM Identity Center AND hold
an active subscription. A caller with correct IAM permissions will still get denied if
either of these layers is missing - and the error message does not distinguish which layer
rejected the request.

This makes Q Business the hardest service to diagnose in the AI/ML family. The caller sees
`AccessDeniedException`, checks their IAM policy (correct), checks their role assumption
(correct), and concludes the system is broken. The actual problem is one of two
non-IAM authorization gates that IAM policy analysis cannot see.

## Applicable hops

| Call | Hop 1 | Hop 2 | Hop 3 | Hop 4 | Hop 5 | Hop 6 |
|---|---|---|---|---|---|---|
| `ChatSync`, `Chat` (end-user conversation) | ✓ | n/a | n/a | n/a | ✓ (app resource policy, if cross-account) | ✓ |
| `CreateApplication`, `UpdateApplication` (admin) | ✓ | n/a | n/a | n/a | n/a | ✓ |
| `CreateRetriever`, `CreateDataSource` (data connector setup) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `StartDataSourceSyncJob` (indexing) | ✓ | n/a | n/a | ✓ (service role reaches data source) | ✓ | ✓ |

Conversation APIs (`Chat`, `ChatSync`) are single-hop from IAM's perspective - no role is
passed. But they have a non-IAM gate (Identity Center assignment + subscription) that must
pass AFTER hop 1 succeeds.

Data connector operations pass a service role that needs access to the data source (S3,
Confluence, SharePoint, etc.). This is the only Q Business path that has the full 6-hop
chain.

## Actions and resource ARNs

| Operation | IAM action | Resource ARN shape |
|---|---|---|
| Chat (streaming) | `qbusiness:Chat` | `arn:aws:qbusiness:<region>:<account>:application/<appId>` |
| Chat (synchronous) | `qbusiness:ChatSync` | same |
| List conversations | `qbusiness:ListConversations` | same |
| Create application | `qbusiness:CreateApplication` | `*` |
| Create retriever | `qbusiness:CreateRetriever` | `arn:aws:qbusiness:<region>:<account>:application/<appId>` |
| Create data source | `qbusiness:CreateDataSource` | `arn:aws:qbusiness:<region>:<account>:application/<appId>/index/<indexId>` |
| Start data sync | `qbusiness:StartDataSourceSyncJob` | `arn:aws:qbusiness:<region>:<account>:application/<appId>/index/<indexId>/data-source/<dsId>` |

**ARN depth increases with specificity.** Application-level actions target the app ARN.
Index actions add `/index/<id>`. Data source actions add `/data-source/<id>`. A wildcard
at the application level does NOT cascade to child resources unless the Resource is
`arn:aws:qbusiness:<region>:<account>:application/<appId>/*`.

## The four failure modes for Chat/conversation APIs

All four produce `AccessDeniedException` or a 403. The caller cannot distinguish them
without checking different systems for each.

| # | Layer | What is missing | Where to check | Who needs the fix |
|---|---|---|---|---|
| 1 | IAM (hop 1) | Caller lacks `qbusiness:ChatSync` on the application ARN | IAM policy | Caller's identity policy |
| 2 | Identity Center | User is not assigned to the Q Business application | IAM Identity Center console | Admin assigns user to app |
| 3 | Subscription | User is assigned but has no active subscription (or subscription expired) | Q Business console > User subscriptions | Admin provisions subscription |
| 4 | SCP (hop 6) | Organization SCP denies `qbusiness:*` | Organization policies | Org admin |

**Mode 2 is invisible to IAM analysis.** No amount of policy inspection will find this.
The Identity Center assignment is a separate authorization plane. `SimulatePrincipalPolicy`
will report `allowed` for `qbusiness:ChatSync` - and the actual call still fails.

**Mode 3 is invisible to both IAM and Identity Center.** The user can be assigned AND have
correct IAM AND Identity Center shows them as active - but if their Q Business subscription
has not been provisioned (or has been cancelled), conversations fail. Subscription status
is visible only in the Q Business console under "Manage user access."

**These layers are evaluated in order.** IAM first, then Identity Center assignment, then
subscription. If IAM denies, you never reach the Identity Center check. But a passing IAM
evaluation does NOT mean the request will succeed - two more gates remain.

## The three failure modes for data connector operations

| # | Hop | What is missing | When it surfaces | Who needs the fix |
|---|---|---|---|---|
| 5 | 2 | Caller lacks `iam:PassRole` for the data source service role | Immediately | Caller's identity policy |
| 6 | 3 | Service role trust policy omits `qbusiness.amazonaws.com` | Immediately | Service role trust policy |
| 7 | 4 | Service role cannot reach the data source (S3 bucket, Confluence API, SharePoint) | **During sync** - data source sync status `FAILED` | Service role's permissions |

**Mode 7 is the Textract pattern**: submission succeeds, execution fails minutes later.
Check `ListDataSourceSyncJobs` for the sync status and error message.

## Non-denial causes and the closed vocabulary

Q Business has causes that are **not an IAM authorization denial**. The Identity-Center
region-mismatch and web-experience auth-mode cases are configuration/validation failures,
not an authorization decision in the six-hop chain. Assigning `DENIED_BY` to a validation
error asserts a denial that did not happen.

Distinguish these from the two genuine non-IAM **gates** — Identity Center assignment and
subscription provisioning (modes 2 and 3). Those DO return a 403/`AccessDeniedException`:
a denial genuinely occurred, just at a layer IAM policy analysis cannot see, so they are
reported as service-specific denials exactly as Bedrock model-access is. The validation
causes below are different and take the non-denial root-cause form:

      **Root cause:** 🚫 Not an access denial — <one-line statement>

See `finding-logic.md` "Root cause selection", case 3b. Every hop keeps its own
evidence-based verdict; emit the non-denial form only from evidence actually read.

## Non-IAM cause 1 - Identity Center region integration

All Amazon Q Business components of a given application (retriever, index, chat experience)
must be in the **same region as each other** (confirmed: "All Amazon Q Business components
of a given application must be created in the same Region"). The IAM Identity Center
instance, however, does **not** have to be co-located: Q Business supports a **cross-region
integration** with an org-level Identity Center instance in any commercial region where
Identity Center is available, even one Q Business itself isn't in. (Cross-region is NOT
supported for *account-level* Identity Center instances — org-level only.)

So "IDC is in a different region from the application" is only a real failure for an
account-level instance, or when the components themselves are split across regions. Do not
report a cross-region org-level IDC setup as the cause — it is a supported configuration
(with a documented latency caveat).

**Finding body**
- verdict: none — configuration/validation, not a hop verdict. See "Non-denial causes".
- root-cause line (only when it genuinely applies — account-level IDC in a different region,
  or Q Business components split across regions): "**Root cause:** 🚫 Not an access denial —
  `[account-level Identity Center instance in [idcRegion], application in [appRegion] | Q Business components split across [regions]]`"
- body: "Amazon Q Business requires all of an application's components to be in one region,
  and for an *account-level* Identity Center instance, co-location with the application.
  `[state which rule is violated]`. Note: a cross-region integration with an *org-level*
  Identity Center instance is supported and is not a failure."

## Non-IAM cause 2 - Web experience URL authentication mode mismatch

Q Business supports two authentication modes: IAM Identity Center and IAM Federation.
The required IAM actions differ between them. A policy written for IAM Identity Center
mode will fail against an IAM Federation application and vice versa.

**IAM Identity Center mode**: Users authenticate via Identity Center. The web experience
handles auth automatically. IAM policies on the admin side manage application creation
and data source setup. End users do not need IAM policies at all - they are authorized
via Identity Center assignments.

**IAM Federation mode**: Users authenticate via IAM/STS. The caller needs explicit IAM
permissions for `qbusiness:Chat*` and additional actions. The IAM role for the web
experience requires specific permissions including `user-subscriptions:CreateClaim`.

**Finding body**
- verdict: `DENIED_BY` (service-specific)
- body: "The application uses `[IAM Federation]` mode but the caller's permissions are
  configured for `[Identity Center]` mode. In IAM Federation mode, the caller needs
  explicit `qbusiness:Chat*` IAM permissions and the web experience IAM role needs
  `user-subscriptions:CreateClaim`."

## Non-IAM cause 3 - Subscription tier insufficient for feature

Q Business has subscription tiers (`Q_LITE` and `Q_BUSINESS` — the console labels them
Amazon Q Business Lite, $3/user/mo, and Pro, $20/user/mo). Pro-only features include
Amazon Q Apps, custom and managed plugins for third-party apps, Q in QuickSight (Reader
Pro), image responses, and longer (~seven-page vs ~one-page) responses. A Lite user
attempting a Pro-only feature gets a 403 that looks like a permissions error but is
actually a licensing constraint. (Confirmed: AWS Q Business pricing + Key Concepts docs.)

## Service role requirements (data connectors)

### Trust policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "qbusiness.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "<accountId>"
        },
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:qbusiness:<region>:<accountId>:application/<appId>"
        }
      }
    }
  ]
}
```

### Permissions vary by data source type

Each data source connector (S3, Confluence, SharePoint, ServiceNow, Salesforce, etc.)
requires different permissions on the service role. The Q Business console generates
these automatically during data source creation. For CloudFormation/CDK deployments,
consult the Q Business data source connector documentation for the specific service.

**S3 data source example:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::<bucket>",
        "arn:aws:s3:::<bucket>/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["kms:Decrypt"],
      "Resource": "arn:aws:kms:<region>:<account>:key/<keyId>",
      "Condition": {
        "StringLike": {
          "kms:ViaService": "s3.*.amazonaws.com"
        }
      }
    }
  ]
}
```

## Hop 2 - PassRole specifics

```json
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::<account>:role/<qbusinessServiceRole>",
  "Condition": {
    "StringEquals": {
      "iam:PassedToService": "qbusiness.amazonaws.com"
    }
  }
}
```

## Diagnostic sequence

### For Chat/conversation failures:

1. **Check IAM first** (hop 1). Does the caller have `qbusiness:ChatSync` on the
   application ARN? If no: fix. If yes: IAM is not the problem - continue.
2. **Check authentication mode.** Is this Identity Center mode or IAM Federation mode?
   The fix path diverges completely here.
3. **For Identity Center mode:** Is the user assigned to the application? Check in Q
   Business console > Manage user access. If not assigned: that is the cause.
4. **Is subscription provisioned?** Same console section shows subscription status. If
   "No subscription" or "Cancelled": that is the cause.
5. **SCP?** If all above pass, check for `qbusiness:*` denials in SCPs.

### For data connector failures:

1. **Did CreateDataSource/StartDataSourceSyncJob succeed?** If no: check
   `iam:PassRole` (hop 2) and trust policy (hop 3).
2. **For sync failures:** Check `ListDataSourceSyncJobs` error message. It usually
   names the failing resource (S3 bucket, Confluence URL, etc.).
3. **Is the data source cross-account?** Both the role's identity policy AND the
   resource policy must allow.
4. **Is KMS involved?** The service role needs `kms:Decrypt` if the data source is
   encrypted.

### Key rule: SimulatePrincipalPolicy is unreliable for Q Business Chat.

A simulation showing `allowed` only proves IAM is not the problem. Two additional
authorization layers (Identity Center assignment and subscription provisioning) exist
outside IAM and cannot be simulated. Do not report "permissions are correct" based on
simulation alone - acknowledge the layers you cannot check and recommend verifying
Identity Center and subscription status manually.

In IAM Federation mode the web-experience role additionally needs
`user-subscriptions:CreateClaim` (with the `user-subscriptions:CreateForSelf=true` and
`aws:CalledViaLast=qbusiness.amazonaws.com` conditions), plus the `qbusiness:Chat*`,
`qbusiness:ListMessages`, and `qbusiness:GetWebExperience` actions. (Confirmed: AWS docs,
"IAM role for an Amazon Q Business web experience using IAM Federation".)

## Runtime permission reality and condition-key matching

Coverage is bounded by what the DevOps Agent role can read. This diagnosis uses `qbusiness:GetApplication`/`GetIndex`/`GetDataSource`/`GetRetriever`/`GetPlugin`/`GetWebExperience` and `qbusiness:List*`, plus the shared `iam:GetRole`/`GetRolePolicy`, `s3:GetBucketPolicy`, `kms:GetKeyPolicy`, the `sso:List*`/`Describe*` and `identitystore:List*`/`Describe*` reads used to check the Identity Center assignment gate, and `organizations:*`. Confirmed by reading `AIDevOpsAgentAccessPolicy` (v12, 2026-11-02): those `qbusiness:Get*` actions and `qbusiness:List*` are granted to the agent role (Q Business exposes `Get*`, not `Describe*`), as are the `sso:*` and `identitystore:*` reads. Subscription status - the second non-IAM gate - is not visible through any granted API (it lives in the Q Business console), so mark it `CANNOT_DETERMINE` rather than inferring it. If any other read is refused at runtime, mark the affected hop `CANNOT_DETERMINE` naming the operation.

Match condition keys (`aws:SourceAccount`/`aws:SourceArn` on the data-source service-role trust policy, and `iam:PassedToService` on the PassRole grant) case-insensitively - IAM evaluates them case-insensitively and tooling stores them in varying case, so a case-sensitive string match can miss a policy that is actually present.

## References

- Set up required permissions (admin IAM, IDC perms, subscription APIs): https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/setting-up.html
- IAM Identity Center user/subscription model + trusted identity propagation: https://aws.amazon.com/blogs/machine-learning/configuring-amazon-q-business-with-aws-iam-identity-center-trusted-identity-propagation/
- Subscription tiers (Q_LITE / Q_BUSINESS): https://docs.aws.amazon.com/powershell/v5/reference/items/New-QBUSSubscription.html
- Identity Center authentication requirement (connectors): https://aws.amazon.com/blogs/machine-learning/index-your-atlassian-confluence-cloud-contents-using-the-amazon-q-confluence-cloud-connector-for-amazon-q-business/
