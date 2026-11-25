# Breakdown keys

Key names differ between datasets. Always pick from what `get_keys` returns for the dataset, and copy the name exactly. These are the names most often seen for each dimension, so you know what to look for.

Fields whose names start with `$` are resource attributes Bronto adds, such as `$hostname` and `$service`. Filter and group on them by name, in double quotes: `"$hostname"`.

| Dimension | Common key names | What a concentration here usually means |
| --- | --- | --- |
| Version or deployment | `version`, `app_version`, `service.version`, `deployment.version`, `release`, `git_sha`, `commit`, `image`, `container.image.tag` | A bad deploy. Check whether the errors begin when the new version first appears. |
| Host, pod or instance | `$hostname`, `host`, `hostname`, `host.name`, `instance_id`, `k8s.pod.name`, `pod`, `container.id`, `container_name` | A bad host: a full disk, memory pressure, a noisy neighbour, or a node that missed a config change. |
| Endpoint or operation | `path`, `route`, `http.route`, `url.path`, `endpoint`, `operation`, `method`, `http.method`, `rpc.method` | A code path or input that fails. Group by method and path together when both exist. |
| Customer, tenant or account | `customer_id`, `tenant_id`, `tenant`, `account_id`, `org_id`, `organization` | One customer's data, configuration or traffic triggers the error. |
| User | `user_id`, `user.id`, `username`, `principal` | A single client retrying, or one user's bad data. |
| Client IP or source | `client_ip`, `remote_addr`, `source_address`, `x_forwarded_for`, `user_agent`, `client`, `@origin` | One client or integration sending bad requests, or a bot. `@origin` is the address that sent the event to Bronto, not the request's client. |
| Region, zone or location | `region`, `cloud.region`, `availability_zone`, `cloud.availability_zone`, `zone`, `datacenter`, `geo.country` | An outage in one zone or region, or a regional dependency. |
| Downstream dependency | `peer.service`, `upstream`, `upstream_host`, `db.name`, `db.system`, `server.address`, `net.peer.name`, `queue`, `topic` | A failing or slow dependency. The errors usually name it too. |

## Keys to skip

- Keys with only one value in `get_key_values`.
- Timestamps, durations and byte counts. Use them as `AVG` or `P95` metrics, not as groups.
- Request IDs, trace IDs, span IDs, session IDs and other values unique to each event. Grouping by them returns one event per group.
- Keys the error filter already fixes. If the filter is `status = 503`, grouping by `status` returns one group.

## Reading a breakdown

A worked example, with errors on checkout-api starting at 14:05 UTC:

| `version` | Errors | Share of errors | Share of all events |
| --- | --- | --- | --- |
| 4.12.0 | 4,810 | 96% | 31% |
| 4.11.3 | 190 | 4% | 69% |

Version 4.12.0 handles a third of the traffic but produces nearly all of the errors, and its first events arrive in the 14:05 bucket: a strong lead. Verify it in step 6 of the skill. Compare it with a breakdown by `$hostname` that shows errors spread across eight hosts in proportion to their traffic: that rules out a single bad host, and is worth reporting as such.
