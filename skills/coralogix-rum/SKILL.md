---
name: coralogix-rum
description: Use when the user asks to "query RUM", "cx_rum", "real user monitoring", "frontend errors", "browser errors", "mobile app crashes", "Web Vitals", "slow page load", "LCP", "CLS", "browser network failures", "user clicks", "session replay", "RUM SDK", "install RUM", "source maps for RUM", or wants to query Coralogix RUM telemetry using query_dataprime with `source rum.events`, DataPrime, and flat `$d.*` fields (field catalog is in Key Fields below), or needs official RUM SDK docs (read_rum_sdk_docs).
metadata:
  author: "coralogix"
  version: "1.0.0"
  tier: "partner-managed"
aws-devops-agent-skills:
  agent-types: "CHAT,INCIDENT_TRIAGE,INCIDENT_RCA,INCIDENT_MITIGATION"
---

# Coralogix RUM (`rum.events`)

## What is RUM?

**RUM (Real User Monitoring)** is **client-side telemetry** from **real users** in production—primarily **web browsers** and **mobile apps** (iOS, Android, React Native, Flutter, etc.). It captures what happens on the client, for example:

| Area | Examples |
|------|----------|
| **Reliability** | JavaScript errors, unhandled exceptions, crashes, ANRs (mobile) |
| **Performance** | Web Vitals (LCP, CLS, FID, INP, …), load time (LT), long tasks |
| **Network** | Failed or slow XHR/Fetch, HTTP status codes from the user’s perspective |
| **Behavior** | Clicks, inputs, scrolls, page views, sessions |
| **Resources** | Scripts, images, CSS, fonts loading slowly or failing |

In Coralogix, RUM is stored in its own **`rum.events`** dataset. You query it with **`query_dataprime`** and **`source rum.events`**, and read structured fields flat under **`$d.*`**. Unlike ordinary logs, RUM reflects **user-visible** experience on the device. Do **not** query `source logs` or filter by `$l.subsystemname` for RUM — the `rum.events` dataset has no subsystem label. **Never fall back to `source logs` or `cx_rum`** — if `source rum.events` returns no rows for the time range, report that no RUM data was found (optionally suggest widening the range); do not re-query logs.

**Workflow and DataPrime basics** (DataPrime commands, tool order, `$d` / `$l` / `$m`, severity): **`coralogix-dataprime`** — `skill://coralogix-dataprime/SKILL.md`;

**Discovering RUM field paths**: most fields are listed in **Key Fields** below. `search_for_fields` does **not** work for RUM — it supports only logs and spans. For a field that is not listed:
- **You have a literal value** (e.g. an app name or label value the user quoted) — run `source rum.events | wildfind '<literal>'`, then read the matching `$d.*` keypath off a returned record and use that path in the real query.
- **You only have a concept** (no example value) — sample with `source rum.events | limit 10` and inspect a record for the right keypath.

Use `distinct $d.<path>` only *after* the path is known, to enumerate its values — it cannot discover a path you do not already have.

## Official RUM SDK docs (`read_rum_sdk_docs`)

Use the MCP tool **`read_rum_sdk_docs`** for the authoritative Coralogix RUM SDK setup and API reference — **before** searching the codebase or guessing integration steps.

**Use it first** to get authoritative answers for any of:

- Installing or configuring Coralogix RUM SDKs (Browser, React Native, Flutter, Android, iOS)
- Adding RUM / real user monitoring / browser or mobile tracking
- Session recording or replay
- Source maps for minified stack traces (`@coralogix/rum-cli`) or de-obfuscating errors
- RUM SDK configuration, API, or initialization

Pass **`topic`** as documented in the tool (e.g. `BROWSER_SDK`, `SOURCE_MAPS`, `REACT_NATIVE_SDK`, `FLUTTER_SDK`, `ANDROID_SDK`, `IOS_SDK`).

---

## Querying RUM (`rum.events`)

Same model as in **What is RUM?** above: query **`source rum.events`** and read the payload flat under **`$d.*`**.

### Event Types
Filter by `$d.event_context.type`:
- `error` - Errors, unhandled exceptions, crashes (from any SDK framework — browser, mobile, etc.)
- `resources` - Resource loading (scripts, images, CSS, fonts)
- `network-request` - XHR/Fetch requests
- `user-interaction` - Clicks, inputs, scrolls
- `web-vitals` - Web Vitals (LT, LCP, FID, CLS, FCP)
- `longtask` - Long tasks blocking the main thread
- `life-cycle` - Page lifecycle events (load, unload, visibility)
- `dom` - DOM mutations and changes
- `log` - Console logs captured by the SDK
- `custom-measurement` - Custom metrics sent by the app
- `mobile-vitals` - Mobile-specific performance metrics

### Errors / Issues
RUM errors can come from three event types: errors (`event_context.type == 'error'`), network requests with bad status codes (`event_context.type == 'network-request'`), and custom event errors.
The common identifiers for ALL RUM errors are:
- `event_context.severity == 5` — indicates an error regardless of event type
- `rum_template_id` — error fingerprint that groups similar error events into distinct issues

**Always filter errors by severity**: `$d.event_context.severity:num == 5`
**Always group errors by issue**: `groupby $d.rum_template_id` — this already groups by application, error message, network details, etc.
**Always filter out null template IDs**: Add `$d.rum_template_id != null` to the filter when grouping by `rum_template_id`.
**Use `any_value()` for descriptive fields**: Since `rum_template_id` uniquely identifies an issue, use `any_value()` to extract app name, event type, error message, etc.
**Always include application name**: `any_value($d.version_metadata.app_name) as app_name` or `any_value($d.labels.mfeApp) as app_name` (whichever is available). Do NOT use `$l.applicationname` for RUM application name.
**Filter by application**: Use `$d.version_metadata.app_name == 'my-app'` or `$d.labels.mfeApp == 'my-app'` — NOT `$l.applicationname`.

Error details depend on the event type:
- For errors (all SDK frameworks): see `error_context.error_message`, `error_context.error_type`, `error_context.is_crash`, `error_context.original_stacktrace`
- For network request errors (`event_context.type == 'network-request'`): see `network_request_context.fragments`, `network_request_context.method`, `network_request_context.status_code`, `network_request_context.host`, `network_request_context.url`. Compose error description as "<method> <fragments> (status <status_code>)"
- For custom log errors (`event_context.type == 'custom-log'`): see `custom_log_context.message`

### Composing Error Descriptions
When querying errors, groupby `$d.rum_template_id` and **always include all of these fields** in your aggregation:
- `any_value($d.version_metadata.app_name) as app_name`
- `any_value($d.event_context.type) as event_type`
- `any_value($d.error_context.error_message) as error_message`
- `any_value($d.network_request_context.method) as method`
- `any_value($d.network_request_context.fragments) as url_fragments`
- `any_value($d.network_request_context.status_code) as status_code`
- `any_value($d.custom_log_context.message) as custom_log_message`
- `distinct_count($d.session_context.user_id) as affected_users`

Fields not relevant to a given error type will be empty/null — that is expected. This way every row has a meaningful description:
- For `error` type rows: use `error_message`
- For `network-request` type rows: present as "<method> <url_fragments> (status <status_code>)"
- For `custom-log` type rows: use `custom_log_message`

### User Interaction Querying
When asked about user interactions (clicks, inputs, etc.) on a page:
- **NEVER return raw interaction events** — always aggregate and group the results.
- **Always group by `interaction_context.target_element_inner_text`** — this is the button/link text the user sees (e.g. "Show more", "Profiles", "Save").
- **Always filter out empty/null inner text**: `$d.interaction_context.target_element_inner_text != null && $d.interaction_context.target_element_inner_text != ''`
- Do NOT group by `target_element` (HTML tag like DIV, SPAN) or `target_selector` — these are not meaningful to users.
- Do NOT use fields like `user_interaction_context` — the correct prefix is `interaction_context`.
- Example: `source rum.events | filter $d.event_context.type == 'user-interaction' && $d.page_context.page_fragments ~ 'my-page' && $d.interaction_context.target_element_inner_text != null && $d.interaction_context.target_element_inner_text != '' | groupby $d.interaction_context.target_element_inner_text aggregate count() as click_count, distinct_count($d.session_context.user_id) as unique_users | orderby click_count desc`

### Key Fields (all under `$d.*`)

**Event Context** (`event_context.*`):
- `type`, `severity` (5 = error, applies to all event types), `source`

**Error Context** (`error_context.*`) — for errors from all SDK frameworks (browser, mobile, etc.):
- `error_message`, `error_type`, `is_crash`, `original_stacktrace`, `threads`

**Error Grouping**:
- `rum_template_id` - Error fingerprint that groups similar error events into distinct issues. Always use `groupby $d.rum_template_id` when querying RUM errors.
- `fingerPrint` - Additional fingerprint field

**Session Context** (`session_context.*`):
- `user_id`, `user_email`, `user_name`, `user_metadata`, `session_id`, `session_creation_date`
- `browser`, `browserVersion`, `os`, `osVersion`, `device`, `user_agent`, `ip`
- `ip_geoip.country_name`, `ip_geoip.city_name`, `ip_geoip.continent_name`, `ip_geoip.is_local`
- `hasRecording`, `hasScreenshot`, `hasError`, `onlyWithErrorMode`

**Version & Environment**:
- `version_metadata.app_name`, `version_metadata.app_version`
- `platform`, `environment`

**Page Context** (`page_context.*`):
- `page_url`, `page_fragments` (always use this for groupby), `referrer`, `page_url_blueprint`

**Network Request Context** (`network_request_context.*`):
- `url`, `url_blueprint`, `fragments`, `host`, `schema`, `status_code`, `status_text`, `method`, `duration`, `response_content_length`, `source`

**Resource Context** (`resource_context.*`):
- `initiatorType`, `fragments`, `name` (resource URL), `duration`, `responseStatus`, `transferSize`, `decodedBodySize`, `contentType`, `contentEncoding`, `deliveryType`, `nextHopProtocol`, `fetchStart`

**Web Vitals Context** (`web_vitals_context.*`):
- `name`, `value`, `rating`, `id`
- Possible `name` values: `LT` (Load Time — full page load duration, use this for page loading time queries), `LCP` (Largest Contentful Paint), `FID` (First Input Delay), `CLS` (Cumulative Layout Shift), `FCP` (First Contentful Paint), `INP` (Interaction to Next Paint), `TTFB` (Time to First Byte), `TBT` (Total Blocking Time)
- `domComplete`, `domInteractive`, `domContentLoadedEventStart`, `domContentLoadedEventEnd`, `loadEventStart`, `loadEventEnd`
- `attribution.element`, `attribution.eventTarget`, `attribution.largestShiftTarget`, `attribution.interactionTarget`
- **Querying web vitals**: Use `percentile(0.75, ...)` for p75 values (NOT avg, which is skewed by outliers). Use `$d.web_vitals_context.value` (without `:num` cast). **Only query the specific vitals the user asks about** — e.g., for "loading times" query only `LT`, for "LCP" query only `LCP`. Do NOT include all vitals unless the user explicitly asks for a full web vitals overview. When querying a single vital, filter directly: `$d.web_vitals_context.name == 'LT'`. When querying multiple vitals in one query, use conditional `if()` inside percentile: `percentile(0.75, if($d.web_vitals_context.name == 'LT', $d.web_vitals_context.value)) as LT_p75`. **Use a wide time range** (at least 7 days) for page performance queries unless the user specifies otherwise — short ranges produce unreliable percentiles because low-traffic pages have too few data points and single outliers dominate the result.

**Interaction Context** (`interaction_context.*`):
- `event_name`, `target_element`, `target_element_inner_text`, `target_element_type`, `element_id`, `element_classes`

**Log Context** (`log_context.*`):
- `message`

**Long Task Context** (`longtask_context.*`):
- `id`, `name`, `duration`

**Custom Measurement Context** (`custom_measurement_context.*`):
- `name`, `value`

**Mobile Device Context** (`device_context.*`):
- `device`, `device_name`/`deviceName`, `os`, `osVersion`, `emulator`

**Mobile SDK** (`mobile_sdk.*`):
- `framework`, `sdk_version`

**Mobile View Context** (`view_context.*`):
- `view`, `view_activity`, `view_fragment`

**Mobile Vitals Context** (`mobile_vitals_context.*`):
- `cpu.cpu_usage`, `cpu.total_cpu_time`, `cpu.main_thread_cpu_time`
- `memory.memory_utilization`, `memory.heap_max`, `memory.heap_used`, `memory.heap_utilization`
- `fps`, `cold`, `warm`, `slow_frozen.slow_frames`, `slow_frozen.frozen_frames`, `anr`

**Browser SDK**: `browser_sdk.version`

**Labels**: `labels.*` (custom labels, e.g. `labels.mfeApp`, `labels.mfeVersion`)

**Tracing**: `traceId`, `spanId`

**Screenshot**: `screenshot_context.id`, `screenshotId`

### Common Query Patterns
- Errors with error_context: `source rum.events | filter $d.event_context.severity:num == 5 && $d.rum_template_id != null | groupby $d.rum_template_id aggregate count() as error_count, any_value($d.version_metadata.app_name) as app_name, any_value($d.event_context.type) as event_type, any_value($d.error_context.error_message) as error_message | orderby error_count desc`
- Network request errors: `source rum.events | filter $d.event_context.severity:num == 5 && $d.event_context.type == 'network-request' | groupby $d.rum_template_id aggregate count() as error_count, any_value($d.version_metadata.app_name) as app_name, any_value($d.network_request_context.method) as method, any_value($d.network_request_context.fragments) as fragments, any_value($d.network_request_context.status_code) as status_code | orderby error_count desc`
- All RUM errors (when querying across types, split into separate queries per event type for meaningful error descriptions, or use any_value() for type-specific fields)
- Affected users by error: `source rum.events | filter $d.event_context.severity:num == 5 && $d.rum_template_id != null | groupby $d.rum_template_id aggregate distinct_count($d.session_context.user_id) as affected_users`
- Slow loading pages (loading time only — use LT): `source rum.events | filter $d.event_context.type == 'web-vitals' && $d.web_vitals_context.name == 'LT' | groupby $d.page_context.page_fragments aggregate distinct_count($d.session_context.user_id:string) as users, count() as page_views, percentile(0.75, $d.web_vitals_context.value) as LT_p75_ms | orderby users desc`
- User interactions on a page: `source rum.events | filter $d.event_context.type == 'user-interaction' && $d.page_context.page_fragments ~ '/some/page' && $d.interaction_context.target_element_inner_text != null && $d.interaction_context.target_element_inner_text != '' | groupby $d.interaction_context.target_element_inner_text aggregate count() as click_count, distinct_count($d.session_context.user_id) as unique_users | orderby click_count desc`
- Web Vitals p75: `source rum.events | filter $d.event_context.type == 'web-vitals' | groupby $d.web_vitals_context.name aggregate percentile(0.75, $d.web_vitals_context.value) as p75`

## Related

- **DataPrime basics** — `skill://coralogix-dataprime/SKILL.md`
- **DataPrime (pipelines + command catalog tools)** — `skill://coralogix-dataprime/SKILL.md`
- **Coralogix logs (`query_dataprime`)** — `skill://coralogix-logs/SKILL.md`
