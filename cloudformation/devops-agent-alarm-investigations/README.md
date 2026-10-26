# DevOps Agent alarm investigations

Forwards Amazon CloudWatch alarms to an AWS DevOps Agent generic webhook, so each alarm
opens an investigation. One stack serves a list of alarms through a single webhook
connection.

No Lambda and no code: an Amazon EventBridge rule scoped to the alarm ARNs matches
`CloudWatch Alarm State Change` with `state.value = ALARM`, an input transformer builds
the incident payload, and an EventBridge API destination POSTs it. The API key lives in an
EventBridge connection, which sends it as `Authorization: Bearer <key>`. An IAM role grants
the rule `events:InvokeApiDestination` on that one destination.

The investigation title is the alarm name and its description is the alarm ARN.

Every alarm in a stack opens its investigation at the stack's `Priority`. To use several
priorities, deploy one stack per priority and list each alarm in the stack that matches
it. Moving an alarm to another priority means moving its ARN between those lists.

## Before you deploy

Create the webhook in the console first. Its API key is shown only once:

1. Create the Agent Space.
2. In the Agent Space, open **Capabilities**, and in the **Agent Space Webhook** table choose
   **Add webhook** with authentication type **API key**. Copy the URL and the key.
3. Deploy this stack with that URL, that key, and the alarm ARNs.

Lost the key? Rotate the webhook from the Capabilities tab; rotation keeps the URL and
issues a new key. Then update every stack that uses the webhook with the new
`WebhookApiKey`.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WebhookUrl` | *(required)* | HTTPS URL of the generic webhook. |
| `WebhookApiKey` | *(required)* | The API key exactly as the console shows it at webhook creation. The template adds the `Bearer ` prefix, and strips one if it was pasted in. `NoEcho`, so it is masked in stack events and `describe-stacks`. |
| `AlarmArns` | *(required)* | Comma-separated ARNs of the alarms to forward. |
| `Priority` | `HIGH` | Investigation priority for every alarm in the stack: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` or `MINIMAL`. |
| `InvocationRateLimitPerSecond` | `300` | Cap on webhook invocations per second. 300 is the default per-destination quota; raise that quota first to go higher. |
| `DevOpsAgentAlarmIntegrationTag` | *(stack name)* | Value of the `DevOpsAgent` tag on the rule and role. Identification and cost allocation only; does not affect routing. |

## Deploy

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-alarm-investigations/devops-agent-alarm-investigations.yaml \
  --stack-name devops-agent-alarm-investigations-high \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      WebhookUrl="https://<your-webhook-url>" \
      WebhookApiKey="<your-webhook-api-key>" \
      Priority="HIGH" \
      AlarmArns="arn:aws:cloudwatch:<region>:<account>:alarm:<alarm-a>,arn:aws:cloudwatch:<region>:<account>:alarm:<alarm-b>"
```

To add or remove an alarm, run the same command with the new full list. On an update,
`deploy` keeps the existing value of every parameter you leave out, so `AlarmArns` is the
only override you need. Repeat with another stack name and `Priority` for each priority you
use.

## Notes

- **Repeat alarms join earlier investigations.** DevOps Agent correlates incidents. When
  an alarm ARN already appears in an earlier incident, the new event is attached to that
  incident as `LINKED` instead of opening a new investigation, even if the earlier one is
  closed. Related alarms that fire together, such as alarms with similar names a second
  apart, can also arrive `LINKED` to the first one.
- **How many alarms fit.** The ARNs are written into the rule's event pattern, and the
  event pattern quota is 2,048 characters (adjustable in Service Quotas). That fits about
  20 alarms with names up to 45 characters. Beyond that, raise the quota or deploy a
  second stack for the next group.
- **Cross-Region and cross-account alarms.** Deploy this stack in the DevOps Agent's
  account and Region, and list each alarm's real (possibly remote) ARN in `AlarmArns`.
  Remote alarms reach it via ordinary
  [bus-to-bus forwarding](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-cross-account.html):
  a rule in the alarm's own Region/account targeting the agent Region's default bus, with
  an IAM role that allows `events:PutEvents` on that bus, plus, for cross-account only, a
  resource policy on the agent bus allowing `PutEvents` from the source account. The forwarded event still carries the alarm ARN in `resources`, so this
  stack's rule matches it.
- **Region availability.** API destinations to public HTTPS endpoints are not available in
  every Region. Check
  [API destinations as targets](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-api-destinations.html#eb-api-destination-regions).
- **Deduplication.** `incidentId` is the EventBridge event id, constant across retries, so
  redeliveries reuse it instead of opening duplicates.
- **Special characters in alarm names.** The alarm name and ARN are inserted as standalone
  input-transformer values, which EventBridge quotes and escapes, so a `"` or `\` in an
  alarm name still produces valid JSON.
- **Delivery.** Up to 32 retry attempts over 8 hours; API destinations require a response
  within 5 seconds. Retries stop once an event is older than 8 hours.
- **Monitoring.** There is no log group. The rule publishes `InvocationAttempts`,
  `SuccessfulInvocationAttempts`, `RetryInvocationAttempts` and `FailedInvocations` in
  `AWS/Events` by `RuleName`. `FailedInvocations` counts events only after retries run out,
  so alarm on `RetryInvocationAttempts` to catch a wrong key early, and treat missing data
  as not breaching. Add a dead-letter queue to the target to inspect events that never
  landed.
- **Keeping the key in your own secret.** Store the API key as the console shows it in a
  Secrets Manager secret, replace `ApiKeyValue` with
  `'Bearer {{resolve:secretsmanager:MyWebhookSecret}}'`, and drop the `WebhookApiKey`
  parameter. The secret must hold the key only, without a `Bearer ` prefix.
  CloudFormation does not re-read a changed secret on its own, so after rotating, pin the
  new version by changing the reference to `MyWebhookSecret:SecretString:::<version-id>`,
  and update the stack.
- **Authentication.** The template uses the webhook's API key (bearer token)
  authentication. EventBridge connections cannot compute the per-request HMAC signature.
