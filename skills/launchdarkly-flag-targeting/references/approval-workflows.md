# Approval Workflows

Some LaunchDarkly environments require approval before changes take effect. This is an Enterprise feature configured per environment. When this happens, mutation tools like `toggle-flag`, `update-rollout`, `update-targeting-rules`, `update-individual-targets`, and `copy-flag-config` return `requiresApproval: true` instead of making the change directly.

## Detecting Approval Requirements

Any mutation tool response may include these fields when a change is blocked:

- `requiresApproval: true`: the change was blocked and needs approval
- `approvalUrl`: a URL where the approval can be reviewed (if available)
- `message`: a human-readable explanation
- `instructions`: the semantic patch instructions that were attempted (use these to create an approval request)

## Creating an Approval Request

When a change is blocked, use `create-approval-request` to submit the change for review:

1. Use the **same instructions** returned in the blocked response's `instructions` field
2. Provide a clear `description` explaining what the change does and why
3. Optionally notify specific team members (`notifyMemberIds`) or teams (`notifyTeamKeys`)

### Example: Toggle flag with approval

If `toggle-flag` returns `requiresApproval: true`:

```
Tool: create-approval-request
Input:
  projectKey: "my-project"
  flagKey: "new-checkout"
  env: "production"
  instructions: [{"kind": "turnFlagOn"}]
  description: "Enable new checkout flow in production after successful staging test"
```

### Example: Rollout with approval

If `update-rollout` returns `requiresApproval: true` with instructions:

```
Tool: create-approval-request
Input:
  projectKey: "my-project"
  flagKey: "new-checkout"
  env: "production"
  instructions: [{"kind": "updateFallthroughVariationOrRollout", "rolloutWeights": {"var-id-1": 25000, "var-id-2": 75000}}]
  description: "Roll out new checkout to 25% of users in production"
```

### Example: Targeting rule with approval

If `update-targeting-rules` returns `requiresApproval: true`:

```
Tool: create-approval-request
Input:
  projectKey: "my-project"
  flagKey: "new-checkout"
  env: "production"
  instructions: [{"kind": "addRule", "clauses": [{"contextKind": "user", "attribute": "email", "op": "endsWith", "values": ["@company.com"]}], "variationId": "<variation-id>", "description": "Internal users"}]
  description: "Add targeting rule for internal users in production"
```

## Checking Approval Status

Use `list-approval-requests` to see pending requests for a flag:

```
Tool: list-approval-requests
Input:
  projectKey: "my-project"
  flagKey: "new-checkout"
  env: "production"
```

The response shows:
- `status`: pending, completed, or failed
- `reviewStatus`: pending, approved, or declined
- `reviews`: list of reviewer actions with status and comments
- `description`: what the change does
- `instructionCount`: number of instructions in the request

## Applying Approved Requests

Once a reviewer approves the request (`reviewStatus` is `"approved"`), use `apply-approval-request`:

```
Tool: apply-approval-request
Input:
  projectKey: "my-project"
  id: "<approval-request-id>"
  comment: "Applying approved production rollout"
```

After applying, verify the change with `get-flag`.

**Important:** The agent can apply already-approved requests but must NEVER approve requests itself. Approval is a human decision.

## What the Agent Should NOT Do

- **Do NOT auto-approve**: The purpose of approvals is human oversight. Never try to approve a request.
- **Do NOT retry the direct change**: If a change was blocked, retrying the same mutation will also be blocked. Use the approval workflow.
- **Do NOT skip informing the user**: Always tell the user that approval is required and what the next steps are.
- **Do NOT bypass approval**: Never use workarounds or alternative API calls to skip the approval process.

## Typical Flow

1. User asks for a targeting change (e.g., "turn on the flag in production")
2. Agent attempts the change using the mutation tool
3. Tool returns `requiresApproval: true` with `instructions`
4. Agent informs the user and offers to create an approval request
5. If the user agrees, agent creates the request with `create-approval-request`
6. Agent shares the approval request details (ID, approval URL if available)
7. A human reviewer approves or declines the request (outside the agent)
8. If approved, the user or agent can apply it with `apply-approval-request`
9. Agent verifies the change with `get-flag`
