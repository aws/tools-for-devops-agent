# Relationship search: `span(...)`, `log(...)`, and `THEN`

Load this file when a `query-sessions` question depends on how events relate to each other: "did A happen and then B?", "did A happen but never B?", "which sessions had both A and B?", "either A or B?".

Plain filters such as `visited-url=*/pricing* visited-url=*/checkout*` only check that a session matched each filter, in any order and not necessarily on the same event. Relationship search wraps each event in its own block and joins the blocks with `AND`, `OR`, or `THEN`. Never tell the user that event order or absence cannot be checked; use this syntax instead.

## Blocks

| Block | Matches |
|---|---|
| `span(A)` | at least one span matching `A` in the session |
| `no_span(A)` | no span in the session matches `A` |
| `log(A)` | at least one log matching `A`, recorded during the session |
| `no_log(A)` | no log matches `A` during the session |

Relationship search is available in `query-sessions` only. Don't use `span(...)` chains or `THEN` in `query-traces`.

In Session Replay search, every page view, click, network request, `track` call, and flag evaluation is stored as a span, so `span(...)` covers frontend events as well as backend spans. Log blocks only join logs recorded with the session's `secure_session_id`. Frontend console logs carry it. Backend logs carry it only when the SDK propagated the session to that request.

## Operators between blocks

All three operators join blocks. Pick the one that matches the question:

| Query | Meaning |
|---|---|
| `span(A) span(B)` or `span(A) AND span(B)` | Both happened, in any order. The two blocks may match the same event. |
| `span(A) OR span(B)` | Either happened. |
| `span(A) THEN span(B)` | `A` happened, and strictly later `B` happened. Chains can be longer: `span(A) THEN span(B) THEN span(C)`. |
| `span(A) THEN no_span(B)` | Drop-off: `A` happened and `B` never happened after the first `A`. |
| `span(A) no_span(B)` | `A` happened and `B` never happened anywhere, before or after. |

Span and log blocks are interchangeable, so they mix freely: `span(A) THEN log(B)`, `span(A) OR log(B)`, `log(A) THEN no_log(B)`.

Precedence, tightest first: `THEN`, then `AND` / whitespace, then `OR`. `country=US span(A) THEN span(B) has_rage_clicks=true` parses as `country=US AND (span(A) THEN span(B)) AND has_rage_clicks=true`. Use parentheses to group `OR` alternatives.

### Where to put `OR`

Prefer `OR` **inside** a single block when the alternatives are the same kind of event. It scans once instead of joining twice:

```
span(span_name="click" event.text=("Pay Now" OR "Complete Order")) THEN span(has_errors=true OR http.status_code>=500)
```

Use `OR` **between** blocks when the alternatives are different kinds of events, such as a span versus a log, or two different sequences:

```
span(http.url=*/api/pay* http.status_code>=500) OR log(level=error message=*payment*)
(span(view_name="/signup") THEN span(has_errors=true)) OR (span(view_name="/login") THEN span(has_errors=true))
```

## Two scopes: session keys vs. span keys

Everything outside a block filters the whole session. Everything inside a block filters one event. The keys are different. A session key written inside `span(...)` still parses, but it silently matches nothing, so convert it first:

| Session key (outside blocks only) | Inside `span(...)` |
|---|---|
| `visited-url=*/checkout*` | `view_name="/checkout"` (web path or mobile screen name) or `url.full=*/checkout*` |
| `clickTextContent="Pay Now"` | `span_name="click" event.text="Pay Now"` |
| `clickSelector=...` | `span_name="click"` with `event.id`, `event.classname`, or `event.xpath` |
| `clickTarget=BUTTON` | `span_name="click" event.tag="BUTTON"` |
| `event="order_completed"` (custom track event) | `span_name="track" key="order_completed"` |
| `has_errors=true` | `has_errors=true` (an error on that event) |

Session keys with no span equivalent (`country`, `browser_name`, `os_name`, `identifier`, `email`, `length`, `active_length`, `has_rage_clicks`, `first_time`, `viewed_by_me`, `environment`, ...) stay outside the blocks: `country=US span(A) THEN span(B)`.

### Canonical span recipes

- Page or screen view: `span(view_name="/checkout")`. `view_name` holds the path only; to match a host or query string, use `span(span_name="page_view" url.full=*...*)`.
- Click: `span(span_name="click" event.text="Pay Now")`. Add `url.full=*/checkout*` inside the same block to pin the page.
- Network request: `span(http.method=POST http.url=*/api/checkout* http.status_code>=500)`. `duration>3s` also works.
- Custom `track` event: `span(span_name="track" key="order_completed")`. Don't use `event.name`, which is the mobile screen name.
- Error: `span(has_errors=true)` or `span(service_name="payment-service" has_errors=true)`.
- Flag evaluation: `span(feature_flag.key="new-checkout" feature_flag.result.value="true")`. Values are JSON-encoded, so match a string variation with an unquoted wildcard: `feature_flag.result.value=*treatment*`.

Inside `log(...)`, use log keys: `level`, `message`, `source`, `service_name`, or any log attribute. A bare word searches the message: `log(timeout)`.

The normal filter grammar applies inside a block: `=`, `!=`, `<`, `>`, `EXISTS`, value groups like `(500 OR 502)`, and unquoted wildcards. A `*` inside quotes is a literal asterisk. Duration suffixes need whole integers (`1500ms`, not `1.5s`).

## Examples

```
# Visited /pricing, then /checkout
span(view_name="/pricing") THEN span(view_name="/checkout")

# Clicked "Pay Now", then the app logged a payment error
span(span_name="click" event.text="Pay Now") THEN log(level=error message=*payment*)

# Checkout funnel drop-off: clicked "Pay Now" and never completed the order
span(view_name="/checkout") THEN span(span_name="click" event.text="Pay Now") THEN no_span(span_name="track" key="order_completed")

# Visited /pricing and never clicked "Contact Sales" anywhere in the session
span(view_name="/pricing") no_span(span_name="click" event.text="Contact Sales")

# Both happened, in any order
span(feature_flag.key="new-editor" feature_flag.result.value="true") span(service_name="document-service" duration>5s)

# US mobile users who either cancelled or hit a failing delete-account request
os_name=(iOS OR Android) country=US (span(span_name="click" event.text="Cancel Subscription") OR span(http.method=DELETE http.url=*/api/account*))

# Clicked "Save" twice (THEN guarantees two distinct events)
span(span_name="click" event.text="Save") THEN span(span_name="click" event.text="Save")
```

## Rules the parser enforces

- `THEN` only joins blocks, never plain filters. Write `country=US span(A)`, not `country=US THEN span(A)`.
- A `THEN` chain must start with `span(...)` or `log(...)`. For "B never happened, and A did", write `span(A) no_span(B)`.
- `THEN no_span(...)` / `THEN no_log(...)` may only be the last step. "A, then C, with no B in between" is not expressible.
- `NOT` cannot precede a block or a chain. Use `no_span(...)` / `no_log(...)` instead. `span(NOT x)` means "some event that isn't x", which almost every session has.
- Blocks cannot be nested, and a parenthesized group cannot follow `THEN`. Expand `span(A) THEN (span(B) OR span(C))` into `(span(A) THEN span(B)) OR (span(A) THEN span(C))`, or merge `B` and `C` into one block with a value group.
- `OR` between a block and a plain session filter is rejected. `country=US span(A) OR span(B)` is also rejected, because it parses as `(country=US AND span(A)) OR span(B)`. Wrap the alternatives: `country=US (span(A) OR span(B))`.

## Not supported

Don't invent syntax for these. Rewrite to the closest supported form and tell the user what was dropped:

- **Time bounds** ("B within 10 seconds of A"): there is no `WITHIN`. `THEN` means "later, with no upper bound".
- **Counts** ("clicked Retry at least 3 times"): there is no count operator. Chain `THEN` once per occurrence for small numbers.
- **Ordering across sessions**: every block is scoped to one session.

## Interpreting results

- `THEN` anchors on the earliest match of each step. A session that did `A`, then `B`, then `A` again with no `B` afterwards is not a `span(A) THEN no_span(B)` drop-off, because `B` followed the first `A`.
- `THEN` needs strictly increasing timestamps. Two events written with the same timestamp, such as a page view and a flag evaluation that fires on load, never satisfy `THEN` in either order.
- Every block is limited to the query's time range. A `B` that happened just outside the window is invisible, so near-the-edge drop-offs can be false positives.
- Exact matches are case- and whitespace-sensitive. When the user's wording is approximate, use a case-insensitive regex: `event.text=/pay now/i`.
- Span-based blocks need the SDK's tracing instrumentation. If a project has session keys like `clickTextContent` but `span(span_name="click" ...)` returns nothing, the project may be on an older SDK or have tracing off. Say so rather than reporting zero matches as a finding.
