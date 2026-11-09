# Set up LaunchDarkly

You connect by signing in to LaunchDarkly and approving access. DevOps Agent then acts as the member who signed in, with that member's role, so choose that member before you connect.

## Prerequisites

- **A LaunchDarkly account on the commercial instance** (`app.launchdarkly.com`). The connector uses the LaunchDarkly hosted MCP server, which isn't available on the EU (`app.eu.launchdarkly.com`) or federal (`app.launchdarkly.us`) instances. There's no region or site to pick.
- **No LaunchDarkly account yet?** Subscribe through [LaunchDarkly on AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-ges3lgpueswn2):
  1. Open the listing and choose **View purchase options**.
  2. Review the offer and choose **Subscribe**.
  3. Choose **Set up your account** and finish creating your LaunchDarkly account.

  Billing goes through your AWS account. For custom pricing or a private offer, email [aws-alliance@launchdarkly.com](mailto:aws-alliance@launchdarkly.com).
- **A LaunchDarkly member to sign in as**, with a role from [Choose the member's role](#choose-the-members-role). If you can, use a member set aside for DevOps Agent: removing the member who signed in from your LaunchDarkly account ends the connection.

## Choose the member's role

The agent can do only what the member who signed in can do, and changes to that member's role apply right away.

| What the agent should do | Role |
| --- | --- |
| Investigate only: read flags, AgentControl configs, their change history and releases | **Reader** |
| Investigate, then turn off a risky flag or revert an AgentControl config | **Writer** or the **LaunchDarkly Developer** preset role |

**Writer** can change any flag and AgentControl config in any project. If your plan includes custom roles, you can give the member a narrower custom role instead:

- `viewProject` on the projects the agent should see, such as `proj/*`
- `updateOn` (turn a flag on or off) on flags in the environments where the agent may roll back, such as `proj/*:env/production:flag/*`
- `updateAIConfigTargeting` (change which variation an AgentControl config serves) on AgentControl configs in those environments, such as `proj/*:env/production:aiconfig/*`

Other people write some of the data the agent reads, such as flag descriptions and logs, and that data could contain instructions aimed at the agent. Give the member only the access the agent needs.

## Sign in and approve access

When you connect, LaunchDarkly asks you to sign in and shows the permissions DevOps Agent requests. Sign in as the member you chose, then approve.

The connection stays signed in for 90 days. After that, LaunchDarkly asks you to sign in and approve again.

To end the connection from LaunchDarkly, open **Organization settings** > **Authorization** > **OAuth applications**, open the overflow menu next to the app, and choose **Revoke application**.

## Troubleshooting

**Access denied (403) after you approve.** The member who signed in doesn't have enough access to the project or environment. Check the member's role against [Choose the member's role](#choose-the-members-role), then connect again.

## Learn more

- [LaunchDarkly hosted MCP server](https://launchdarkly.com/docs/home/getting-started/mcp-hosted)
- [OAuth applications](https://launchdarkly.com/docs/home/infrastructure/oauth)
- [Role actions](https://launchdarkly.com/docs/home/account/role-actions)
