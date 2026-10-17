# aws-waf-log-investigation

An [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/) skill that teaches
it how to investigate AWS WAF logs and metrics. It covers six kinds of question:

- false positives;
- injection attacks;
- bypasses in allowed traffic;
- whether a Count rule can be switched to Block;
- DDoS events;
- who a client IP is.

> **Sample code, not for production use without your own review and testing.** Validate it in a
> non-production environment first. The skill tells DevOps Agent how to analyse data and to propose
> rule changes as plans. It never changes your WebACL itself, and you should review any change it
> proposes before applying it.

## Why

DevOps Agent can already read WAF configuration, CloudWatch metrics and WAF logs, and its queries
are usually correct. What it lacks is WAF judgment.

We ran it without this skill against a CloudFront WebACL that had received labelled test traffic: a
false-positive user, an injection scan, a scraper fleet and XSS probes against a Count-mode rule.

What it got right:
- Every count matched the test design: 132 blocks, 130 from the scan, 160 XSS matches from 4 IPs.
- It identified Route 53 health checks from their labels.

What it got wrong:
- It filed the blocked legitimate user under the attack.
- It missed the scraper fleet, because it only read blocked and counted records.
- It said nothing reached the origin, when 30 probes from the attacking IPs had been allowed.
- It based a Count-to-Block recommendation on the attack window alone.

[Why WAF Analyst?](https://github.com/aws-samples/sample-building-a-conversational-ai-agent-for-aws-waf-analysis-with-agentcore/blob/main/docs/why-waf-agent.md) has the full comparison. The skill adds the
missing method, and it works the same on Athena and CloudWatch Logs.

## Before you install

1. **WAF logging is on.** Without logs, only the metric parts of the skill apply.
2. **Logs in S3 need an Athena table that already exists.** DevOps Agent can't create one: its
   session policy blocks `glue:CreateTable`, whatever the role allows. AWS documents how to
   create a WAF log table with partition projection. Logs in CloudWatch Logs need no table.
3. **Logs in S3 also need a workgroup with Athena managed query results**, in the log bucket's
   Region. DevOps Agent's session policy has no `s3:PutObject`. With a normal workgroup, every
   query fails with "Access denied when writing output", whichever result bucket you pick.

   ```bash
   aws athena create-work-group --region <log-bucket-region> --name devops-agent \
     --configuration '{"ManagedQueryResultsConfiguration":{"Enabled":true}}'
   ```

   Don't convert `primary` without checking first. Clients that pass their own output location or
   use result reuse fail on a managed workgroup.
4. **The Agent Space role can run queries.** The default `AIDevOpsAgentAccessPolicy` doesn't grant
   `athena:StartQueryExecution`, `athena:GetQueryResults`, or object reads on your log bucket.
   Add something like this:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["athena:StartQueryExecution", "athena:StopQueryExecution",
                    "athena:GetQueryExecution", "athena:BatchGetQueryExecution",
                    "athena:GetQueryResults", "athena:GetQueryResultsStream"],
         "Resource": "arn:aws:athena:<region>:<account-id>:workgroup/devops-agent"
       },
       {
         "Effect": "Allow",
         "Action": ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
         "Resource": ["arn:aws:s3:::<waf-log-bucket>", "arn:aws:s3:::<waf-log-bucket>/*"]
       }
     ]
   }
   ```

   If the log bucket uses a KMS key, also allow `kms:Decrypt` on that key. Don't add
   `s3:PutObject` or Glue write actions, because the session policy removes them anyway.

## Install

**From GitHub.** Your Agent Space needs a GitHub connection, and any account will do for a public
repository. In the DevOps Agent web app:

1. Open Knowledge, then Skills.
2. Choose Add skill, then Import from repository.
3. Paste this URL:

   ```
   https://github.com/aws/tools-for-devops-agent/tree/main/skills/aws-waf-log-investigation
   ```

4. Choose **Generic** as the agent type. Investigations run their queries in sub-agents, and
   Generic makes the skill available to all of them.

With the CLI:

```bash
aws devops-agent create-asset --agent-space-id <agent-space-id> --asset-type skill \
  --metadata '{"agent_types":["GENERIC"]}' \
  --content '{"sourceUrl":{"url":"https://github.com/aws/tools-for-devops-agent/tree/main/skills/aws-waf-log-investigation"}}'
```

An imported skill doesn't follow the repository on its own. Choose **Sync** on the skill, or run
`update-asset` with the same `sourceUrl`, to pull changes.

**As a zip file.** Zip this directory with `SKILL.md` at the root of the archive. Then upload it
under Knowledge, Skills, Add skill, Upload skill.

**Facts about your environment** go in the Agent Space instructions, not in the skill. That means
which WebACLs matter, the Athena database and table for each one, the workgroup name, and your time
zone. Instructions apply to every session, while a skill loads only when it matches the task.

## What to expect

- Answers say how sure they are. "WAF-side likely false-positive candidate, needs business
  confirmation" and "possible bypass lead" are as far as WAF evidence goes.
- Rule changes come as plans. Each one has a backup, the LockToken, the full rule list and a
  rollback, and a person applies it.
- A failed query is reported as failed, never as "no traffic".

We haven't measured the effect of this skill yet. To check it in your own account, ask the same
question about the same window with and without the skill. Then compare both answers with what
you know happened.

## Where the method comes from

The skill restates methods implemented and tested in [WAF Analyst](https://github.com/aws-samples/sample-building-a-conversational-ai-agent-for-aws-waf-analysis-with-agentcore), a conversational WAF
analysis agent. Where that agent had a known defect, the skill gives the corrected method. Paths
below are in that repository.

| Reference | Source in WAF Analyst |
|---|---|
| `SKILL.md`, `log-data-facts.md`, `metric-facts.md`, `query-environment.md` | `tools/waf_query.py`, `tools/waf_athena.py`, `tools/waf_metrics.py`, `tools/static_assets.py`, the system prompt in `agent.py` |
| `false-positive.md` | `tools/waf_block_fp.py`, `tools/waf_challenge_check.py` |
| `injection.md` | `tools/waf_injection.py`, `tools/waf_aggregate.py` |
| `bypass.md` | `tools/waf_bypass.py`, `tools/ja4.py`, `token_reuse_ips` in `tools/waf_logs.py` |
| `count-to-block.md` | `tools/waf_count_eval.py` |
| `ddos.md` | `tools/waf_overview.py`, the DDoS sections of the system prompt |
| `ip-profile.md` | `analyze_ip` in `tools/waf_logs.py` |

If a change to one of those files changes the method, the matching reference changes with it.
