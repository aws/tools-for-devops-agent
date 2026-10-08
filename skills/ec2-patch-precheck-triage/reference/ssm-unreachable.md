# SSM-unreachable instances (no remote path)

**Signatures:** `PingStatus: ConnectionLost` or `Inactive`; a patch command never starts / times out
with no plugin output; a maintenance window skips/fails offline targets; hybrid (`mi-`) instances with
a stale `LastPingDateTime` (weeks/months); compliance shows perpetual non-compliance because the
instance is never scanned.

**Hard constraint:** SSM is the ONLY channel Patch Manager uses AND the only remote path in. If SSM
is not Online there is **no Run Command and no Session Manager** — triage is **control-plane only**
(EC2 state, IAM, network) plus **customer escalation** to restore the in-guest agent.

## Enumerate & classify
```bash
aws ssm describe-instance-information --region <region> \
  --query "InstanceInformationList[?PingStatus!='Online'].{Id:InstanceId,Type:ResourceType,Ping:PingStatus,LastPing:LastPingDateTime,Agent:AgentVersion,Platform:PlatformName}" --output table
```
- **Class A — EC2 lost connectivity:** agent stopped/old, instance stopped/impaired, IAM profile
  missing/changed, VPC endpoint/NAT/SG blocked 443 to `ssm`/`ssmmessages`/`ec2messages`, subnet isolated.
- **Class B — hybrid `mi-` ghost:** decommissioned host never deregistered / expired activation — lingers
  forever and inflates the non-compliant count.

## The one control-plane-fixable cause: IAM instance profile
```bash
aws ec2 describe-instances --instance-ids <id> --region <region> \
  --query "Reservations[].Instances[].{State:State.Name,Profile:IamInstanceProfile.Arn,Subnet:SubnetId}" --output table
aws iam list-attached-role-policies --role-name <role> --query "AttachedPolicies[].PolicyName" --output text
```
If the profile is missing or lacks `AmazonSSMManagedInstanceCore` (i.e. `ssm:UpdateInstanceInformation`,
`ssmmessages:*`, `ec2messages:*`) → report/attach it; this can restore connectivity without in-guest access.
If the profile is present and correct → the cause is in-guest/network → customer must restore the agent.

## Actions
1. **Document** InstanceId, region, PingStatus, LastPing, AgentVersion, platform, EC2 State, subnet, profile ARN; escalate to the owner (agent must come back online on their side).
2. **Fix the instance profile** if that's the cause (only remotely-fixable one).
3. **Exclude** the instance from the current patch run so it's tracked as *excluded*, not a hard failure. **Do NOT deregister** hybrid ghosts — flag for customer review.

## Verify
Once the owner restores the agent: `describe-instance-information` shows `PingStatus=Online`, then
re-include. If a CloudWatch Logs group is configured for the agent, search it by instance id for the
disconnect cause (you can't reach the instance directly).
