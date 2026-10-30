---
name: coralogix-infrastructure
description: 'Find and inspect infrastructure resources: monitored resource types, resource inventory, health history, raw source data, and configuration changes. Load when the user asks to "show resource types", "list infrastructure resources", "what resources of this kind are monitored", "is this resource healthy", "resource health history", "when did this resource go critical", "get raw resource data", "what changed on this host", "which resources changed configuration", "infrastructure inventory", "find resources by name", "filter resources by service or environment", or wants to explore infrastructure resources and their data.'
metadata:
  author: "coralogix"
  version: "1.0.0"
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "CHAT,INCIDENT_TRIAGE,INCIDENT_RCA,INCIDENT_MITIGATION"
---

# Infrastructure Resources Skill

Find infrastructure resources and inspect them: what exists, whether it is healthy, what its source
document holds, and what changed in its configuration.

## Tools

| Tool                                  | Use it to                                                      |
|---------------------------------------|----------------------------------------------------------------|
| `describe_infrastructure`             | Find the resource types, then the attributes one can filter on |
| `list_infrastructure_resources`       | Find resources and their `resource_id`                         |
| `get_infrastructure_resource_details` | Inspect named resources, one aspect per call                   |

All three are read-only. This skill covers the order to call them in and the rules that span them.

## Workflow

Four steps, because each one gives the next the input it needs.

```python
# 1. What is monitored? Types are per account, so never guess.
describe_infrastructure(aspect="types")

# 2. What can I filter that type on, and with which values?
describe_infrastructure(aspect="attributes", category="Hosts", resource_type="EC2_Instances")

# 3. Which resources match? This is where resource_id comes from.
list_infrastructure_resources(
    category="Hosts",
    resource_type="EC2_Instances",
    resource_filter={"match": {"field": "Health", "values": ["Critical"]}},
)

# 4. What is going on with them?
get_infrastructure_resource_details(
    resource_ids=["1001234:host_id=i-abc123"],
    aspect="health_history",
)
```

`describe_infrastructure` answers one aspect per call:

- `types` lists every category and type in the account. It takes no `category` or `resource_type`.
- `attributes` needs a `category`, a `resource_type`, or both. Scope it to the type you are about
  to list: accepted values can differ by type, and a type-level call returns that type's values.

Pass categories and types exactly as `types` lists them.

Skip step 1 when the category and type are already known from earlier in the conversation. Skip
step 2 only when `attributes` already returned the attribute and its values for this type.

## Filtering

A `resource_filter` is a tree. Every node is one of two shapes:

```text
{"match": {"field": "<attribute>", "values": ["<value>", ...]}}
{"bool":  {"op": "AND" | "OR", "operands": [<node>, ...]}}
```

A `match` names one attribute. A `bool` holds more nodes, so the tree nests.

So `OS=linux AND (Health=Critical OR Region=eu-west-1)` is:

```text
{"bool": {"op": "AND", "operands": [
  {"match": {"field": "OS", "values": ["linux"]}},
  {"bool": {"op": "OR", "operands": [
    {"match": {"field": "Health", "values": ["Critical"]}},
    {"match": {"field": "Region", "values": ["eu-west-1"]}}
  ]}}
]}}
```

- **Values inside one `match` are alternatives (OR).** `"field": "Region", "values": ["eu-west-1", "us-east-1"]`
  matches a resource in either region.
- **To require two wildcard patterns on one attribute, use one `match` per pattern under an `AND`.**
  A name containing both `checkout` and `prod` is `Name=*checkout*` AND `Name=*prod*`. Never do this
  with exact values: `Region=eu-west-1` AND `Region=us-east-1` matches nothing.
- **`Category` and `Type` are not attributes.** They have their own arguments, and a `match` on
  them is rejected.
- **A `*` works only where `describe_infrastructure` reports `wildcard: true`.**
- **An exact value is case-sensitive, a wildcard one is not.** `OS=linux` matches and `OS=Linux`
  does not, but `Name=*checkout*` and `Name=*Checkout*` are the same query. For free text, take the
  spelling from a row's `columns` or use a wildcard.
- **An attribute from a category-only `attributes` call may not apply to the type you then
  pick.** Each attribute carries `types`. One that does not apply returns 0 rows, which reads the
  same as no matches.
- **0 rows is an answer.** A valid attribute that is simply unpopulated matches nothing. Do not
  retry or reword. A wrong attribute name or an out-of-set value is rejected outright, and the
  error says what is accepted.

## Paging

`total_count` on the first call answers "how many". Do not page to count, and do not page to find
one resource. Filter for it instead.

Page only when the user needs the rows themselves, such as an inventory or "list all...". Then:

- `limit` is 1 to 100 rows and defaults to 100.
- The next window starts at `start_row + returned_count`, with the same `limit`, filter, category
  and type.
- Stop when `start_row + returned_count >= total_count`.

**If the first call's `total_count` is more than 500, do not page through it.** Narrow the filter,
or answer with the count and the first window and say which filter would narrow it.

**The window cannot reach past row 10,000.** `total_count` still reports the true size.

## Aspects

One aspect per call. Each one takes different arguments and answers differently:

| `aspect`         | Ids per call | Time arguments                                           | Which ids come back             |
|------------------|--------------|----------------------------------------------------------|---------------------------------|
| `health_history` | 100          | None                                                     | Every valid id                  |
| `raw_data`       | 5            | `timestamp` optional: newest version at or before it     | Every id, until 30K chars       |
| `config_summary` | 100          | `from_time` required, `to_time` optional (default now)   | Only resources that changed     |
| `config_diff`    | 100          | `from_time` required, `to_time` optional (default now)   | Every valid id, changed or not  |

Passing an argument an aspect does not take is rejected.

- `health_history` gives one sample per day, oldest first. Statuses are `Healthy`, `Critical`
  and `Unmonitored`.
- `raw_data` gives the source document. Ask for a few resources at a time. Most documents
  are 2K to 10K chars of free-form payload. One past 10K chars comes back cut to a string, with
  `truncated: true`. The whole answer stops near 30K chars: the ids left out are reported through
  `omitted_because: "result_size_limit"`, so ask for those again. Narrow with
  `list_infrastructure_resources` and `health_history` first, then come here for the handful you
  actually need to read. A wide sweep belongs on those two, not here.
- `config_summary` says which resources changed, and how often. A resource that did not change
  is absent, so a short answer means the rest were unchanged. Use it to pick who to look at.
- `config_diff` says what changed, field by field. Run it after the summary, on the resources
  the summary named.

### Reading `config_diff`

Every valid requested resource gets a row. Read its `outcome` before its `changes`:

| `outcome`               | Meaning                                                                                                                |
|-------------------------|------------------------------------------------------------------------------------------------------------------------|
| `changed`               | Both versions exist and differ                                                                                         |
| `unchanged`             | Nothing differs, or there were no events in the window                                                                 |
| `created`               | The resource first appeared inside the window, so there is nothing to compare against                                  |
| `priorStateUnavailable` | It changed, but the previous version is more than 14 days older than `from_time`. Move `from_time` earlier to reach it |
| `comparisonUnavailable` | Versions exist on both sides but one will not decode                                                                   |

Inside `changes`, a `null` on one side means the field was added or removed. It is a value, not a
missing one.

## Key Principles

- **Pass `resource_id` verbatim.** Ids embed `:`, `|` and `=`. URL encoding is handled for you.
- **Infra health is its own concept.** `Healthy`, `Critical` and `Unmonitored` are computed by the
  infrastructure domain and are not Service Catalog health. Correlate them with telemetry signals.
  Do not treat them as interchangeable.

## Related Skills

To look up the same resource using another skill, search for its display name or its `Service`
value. Do not use the `resource_id`: it exists only in the infrastructure tools, so logs and
metrics will not match it.

- Load the `coralogix-metrics-query` skill to match health against CPU and memory for the resource.
