# Network Log Analyzer

This skill teaches AWS DevOps Agent to troubleshoot connectivity from **VPC Flow Logs** and
**packet captures**. It answers questions like "is this REJECT a security group or a network
ACL?", "why does this TCP handshake never complete?" and "are these retransmissions real loss
or a capture artifact?". Every finding is labelled with its evidence and can be reproduced.

## ⚠️ Important Notice

This skill is sample code, not intended for production use without additional review and
testing. Users should validate in a non-production environment first. It is read-only: it
queries and interprets evidence, and takes no action on your network configuration.

## Purpose

Flow logs and packet captures answer different questions, and both are easy to misread:

- A flow log REJECT doesn't tell you whether the security group or the network ACL dropped the
  traffic. Pairing both directions on the same ENI sometimes can, because SGs are stateful and
  NACLs are stateless. Some traffic, such as Amazon DNS and instance metadata, is never logged
  at all.
- In a capture, "ACKed unseen segment" usually means the capture missed packets, not the
  network. Oversized segments on a host capture are offload artifacts, not MTU problems. And
  the meaning of every flag depends on where the capture was taken.

The skill supplies the decision rules, the scoped queries, and the evidence-collection
commands, so the agent reaches a consistent, evidence-backed root cause.

## Key Capabilities

- Attribute flow log rejects to a network ACL vs a security group, or say clearly when the logs
  can't tell
- Analyze TCP handshakes from flow log `tcp-flags`: unanswered SYN vs refused vs completed
- Query flow logs with time-boxed CloudWatch Logs Insights and Athena queries, including custom
  formats
- Interpret tshark and tcpdump text output with Wireshark's own `tcp.analysis.*` definitions
  and precedence
- Locate the capture point from handshake timing, and separate capture artifacts from network
  faults
- Diagnose path MTU black holes, idle-timeout resets (NLB and connection tracking), DNS
  packets that go unanswered in a capture, and NAT/EKS original source IPs. Name-resolution
  failures (NXDOMAIN, SERVFAIL, wrong answers) are left to the `aws-vpc-dns-investigation`
  skill.
- Guide the user to export a small, header-only evidence set when the data isn't directly
  queryable

## Prerequisites

- **Flow logs (Path A):** VPC Flow Logs delivered to CloudWatch Logs or S3. For S3, an Athena
  table helps (DDL in the Athena docs). The agent needs read access to `ec2:Describe*`,
  `logs:StartQuery`, `logs:GetQueryResults` and `logs:FilterLogEvents` on the flow log group,
  and Athena/S3 read access if you use Athena.
- **For handshake analysis**, a custom flow log format that includes `tcp-flags`,
  `flow-direction`, and `pkt-srcaddr`/`pkt-dstaddr` (the recommended format is in
  `references/vpc-flow-logs.md`).
- **Packet captures (Path B):** Wireshark/tshark (or tcpdump) on the machine that has the
  capture file, so you can convert it to text. Chat can't accept `.pcap`/`.pcapng` files.

## Limitations

- The agent can't read binary captures. Its packet-level view is only as good as the tshark
  output you provide.
- Chat attachments are limited to 3.75 MB per file and must fit in the model's context. Large
  raw exports must be narrowed; see `references/preparing-evidence.md`.
- Attachments are visible to everyone in the Agent Space. Export headers only, never payloads.
- Flow logs are aggregated per interval and omit some traffic types, so absence of a record
  isn't proof that traffic didn't happen.
- The skill recommends fixes and read-only validation commands. It never applies changes.

## Agent Types

- **Chat tasks**: conversational troubleshooting with queried or uploaded evidence
- **Incident RCA**: investigations where connectivity, rejects, or packet loss may be the cause

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html)
in your Agent Space, go to Settings → Add Skill → Import from repository, and point to the
`skills/network-log-analyzer` directory.

**Option B: Upload as a zip file**

1. Zip the directory, including only allowed extensions:

   ```bash
   cd skills
   zip -r network-log-analyzer.zip network-log-analyzer/ -i '*.md' '*.json' -x '*/README.md' '*/CHANGELOG.md' '*/evals/*' '*/.skilleval.yaml'
   ```

2. In the AWS DevOps Agent web app, go to the **Skills** page.
3. Click **Add skill** → **Upload skill**, and drop in the zip file.
4. Select the agent types **Chat tasks** and **Incident RCA**, then click **Upload**.

**Option C: Upload via the Asset API**

Assign the skill to the `CHAT` and `INCIDENT_RCA` agent types. See
[Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

## How to Use This Skill

### Chat

- "Flow logs show REJECT for 10.0.1.5 to 10.0.2.9 on port 5432 in vpc-0abc. Is it the security group or the NACL?"
- "Ping from my bastion to the app server works one way but not the other."
- "Connections through our NLB reset after a few minutes of idle time."
- "Here is tshark output from a capture on the client (attached). Why does the TLS connection hang?"
- "Which instance behind the NAT gateway is generating this traffic?"

### Investigation

- "The payment service started timing out to the database at 14:05 UTC."
- "Large file uploads over the Site-to-Site VPN hang, but small requests work."
- "Intermittent packet loss between two EC2 instances since this morning's deployment."

## Learn More

- [VPC Flow Logs records](https://docs.aws.amazon.com/vpc/latest/userguide/flow-log-records.html)
- [Wireshark User's Guide: TCP Analysis](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvTCPAnalysis.html)
- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
