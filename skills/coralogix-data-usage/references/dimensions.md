# Labels And Dimensions

### Mandatory breakdown dimensions

For usage metrics that support breakdowns, the LLM should expect these core dimensions:

- `pillar`
- `entity_type`
- `priority`
- `measurement_type`
- `feature_group_id`
- `feature_id`

### Optional user-provided dimensions

- `application_name`
- `subsystem_name`

### Optional system-derived dimensions

- `tco_policy_id`
- `tco_policy_name`
- `severity`
- `evaluator_name`
- `evaluator_version`
- `data_set`
- `data_space`
- `cx_source`
- other system labels depending on the data type and exporter path

### Exporter normalization behavior

The metrics exporter normalizes some optional labels for dashboard stability:

- missing `application_name` may be exported as `cx_null`
- missing `subsystem_name` may be exported as `cx_null`
- missing `severity` may be exported as `cx_null`

For blocked processed-data traffic, the exporter may also derive:

- `blocking_reason_name`
- `blocking_reason_type`

These are helpful when a user asks why traffic was blocked or which policy caused blocked usage.

### Label availability rule

Not every label exists on every metric or every record.

The LLM must:

- treat the mandatory dimensions above as the main grouping dimensions for usage breakdowns
- only use optional dimensions when they are actually present
- treat `cx_null` as "label not set" rather than as a meaningful customer value
- avoid assuming that all entity types support all priorities

## Business Semantics Of Key Dimensions

### Pillar

The high-level product/data domain, for example:

- `logs`
- `spans`
- `binary`
- `metrics`

### Entity Type

A subtype within a pillar, for example:

- `logs`
- `browser_logs`
- `spans`
- `session_recordings`

This is more specific than pillar and is often the right level for customer attribution.

### Priority

Traffic priority, such as:

- `high`
- `medium`
- `low`
- `blocked`

Not every entity type has every priority combination.

### Measurement Type

The raw measurement family, such as:

- processed bytes
- tokens
- egress bytes
- samples
- events

### Feature

`feature_id` and `feature_group_id` identify the product capability or business area responsible for the usage. These are important for questions like:

- which feature caused the most usage
- how much usage belongs to logs vs AI vs metrics

