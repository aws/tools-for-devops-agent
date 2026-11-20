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

- **On-demand**: conversational troubleshooting with queried or uploaded evidence
- **Incident RCA**: investigations where connectivity, rejects, or packet loss may be the cause

## Uploading to AWS DevOps Agent

Set up flow log delivery and read access in [Prerequisites](#prerequisites) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

Target **On-demand** for troubleshooting with evidence you query or upload, and **Incident RCA** for investigations where connectivity, rejects, or packet loss may be the cause. **Generic** would also load it for triage, mitigation, and evaluation agents, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `network-log-analyzer`, or filter by AWS service **Amazon VPC**.
4. Choose **Details** and check that the agent types are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to add your own queries to `references/flow-log-queries.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/network-log-analyzer/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f network-log-analyzer.zip
   zip -r network-log-analyzer.zip network-log-analyzer/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l network-log-analyzer.zip | tail -1   # expect 7 files
   ```

2. Check that the zip has this structure:

   ```text
   network-log-analyzer.zip
   └── network-log-analyzer/
       ├── SKILL.md                          # required: frontmatter with name and description
       └── references/
           ├── flow-log-queries.md
           ├── packet-capture-analysis.md
           ├── preparing-evidence.md
           ├── troubleshooting-playbooks.md
           ├── vpc-flow-logs.md
           └── wireshark-analysis.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `network-log-analyzer.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

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
