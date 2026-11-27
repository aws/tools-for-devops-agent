# Managed node not online or unreachable: checklist

Use this when a node has no invocation under tag targeting, shows `Undeliverable`,
`DeliveryTimedOut` or `Delayed`, or is not `Online` in `ssm:DescribeInstanceInformation`.
All checks are read-only. Report each item as passed, failed or not observable.

## 1. Is it a managed node at all?

- `ssm:DescribeInstanceInformation` (filter `InstanceIds`): absent = never registered (or
  deregistered); `PingStatus` `ConnectionLost` = registered, not checking in; also
  `LastPingDateTime`, `AgentVersion`, `PlatformName`.
- A node with `ConnectionLost` can still have an open channel and receive commands for a
  while, so ping status alone does not prove a command could not reach it.

## 2. Identity

- `ec2:DescribeInstances`: `IamInstanceProfile`. None attached: the node is managed only if
  Default Host Management Configuration is on for the account and Region. That setting is
  not readable with the default policy (`ssm:GetServiceSetting` is not in it): report it
  as not observable.
- With a profile: `iam:GetInstanceProfile`, then `iam:ListAttachedRolePolicies` and
  `iam:GetRolePolicy` on its role. The AWS-managed core policy
  (`AmazonSSMManagedInstanceCore`) cannot be read by the agent; it grants, among others,
  `ssm:UpdateInstanceInformation`, `ssm:ListInstanceAssociations`, `ssm:GetDocument`,
  `ssmmessages:CreateControlChannel`, `ssmmessages:CreateDataChannel`,
  `ssmmessages:OpenControlChannel`, `ssmmessages:OpenDataChannel`, and
  `ec2messages:GetMessages`, `ec2messages:AcknowledgeMessage`, `ec2messages:SendReply`.
  A custom policy without these actions breaks registration.
- The role's trust policy must allow `ec2.amazonaws.com`.
- `MetadataOptions`: `HttpEndpoint` `disabled` means the agent cannot get credentials at
  all. `HttpPutResponseHopLimit` 1 can break agents running in containers.

## 3. Network path to the Systems Manager endpoints

The agent needs HTTPS (443) to `ssm`, `ssmmessages` and `ec2messages` in the node's Region
(and `s3`, `logs`, `kms` if those features are used).

- Route table of the node's subnet (`ec2:DescribeRouteTables`): a route to an internet
  gateway (with a public address) or a NAT gateway, or none.
- With no route out: interface endpoints (`ec2:DescribeVpcEndpoints`) for each of the
  three services in the node's VPC, `State` `available`, in the node's subnet or
  Availability Zone, `PrivateDnsEnabled` true (or the node is configured for the endpoint
  names). Private DNS needs the VPC's `enableDnsSupport` and `enableDnsHostnames`
  (`ec2:DescribeVpcAttribute`). Check CloudTrail `ModifyVpcEndpoint` for a recent change.
- Endpoint security groups: inbound 443 from the node or its subnet.
- Node security group: outbound 443 to the endpoints or to the internet.
- Network ACLs of the node and endpoint subnets: 443 out and ephemeral ports back.
- DHCP options set (`ec2:DescribeDhcpOptions`): `AmazonProvidedDNS`, or a resolver that can
  resolve the endpoint names.
- Endpoint policies that deny the node's role.

For a deeper DNS investigation of the VPC, a VPC DNS skill may apply if one is loaded.

## 4. Not observable from outside the node

Agent service state, the agent log, proxy settings, the local resolver and hosts file,
clock skew and disk space. Ask the operator to run, on the node (Linux, agent 3.1.501.0 or
later):

```
sudo ssm-cli get-diagnostics --output table
sudo systemctl status amazon-ssm-agent
sudo tail -n 100 /var/log/amazon/ssm/amazon-ssm-agent.log
```

On Windows: `& "C:\Program Files\Amazon\SSM\ssm-cli.exe" get-diagnostics --output table`
and the log under `C:\ProgramData\Amazon\SSM\Logs\`.

A node that is offline cannot receive a command, so these are for the operator to run
locally (Session Manager will not work either), never a step for the agent.

If the customer already ran the AWS-provided managed-node troubleshooting runbook, read
that execution's step outputs with `ssm:DescribeAutomationStepExecutions`. Do not start it.

## 5. Fix, as a recommendation

- No profile: attach an instance profile whose role has the core permissions (or turn on
  Default Host Management Configuration), and enable the metadata endpoint if disabled.
- Network: the specific route, endpoint, private DNS, security group or ACL change. SSM
  needs no inbound rule on the node. Never propose a public IP, an internet gateway route
  for a private subnet, or an inbound rule. Endpoint security group: 443 from the node's
  security group.
- Then the operator re-sends the command to those nodes. Never "reinstall the agent" or
  "reboot" unless the in-guest diagnostics point to it.
