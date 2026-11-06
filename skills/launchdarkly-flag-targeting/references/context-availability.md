# Targeting context availability

Which **context kinds** and **attributes** a flag can actually target depends on
where the flag is evaluated. A targeting rule, individual target, or percentage
rollout that names a context kind or attribute the evaluation doesn't carry
**silently never matches** — the context falls through to the default rule (or the
off variation). This reference explains how to pick a context that will actually
fire, and how to determine it deterministically from your own code rather than
guessing.

Read this whenever a flag plan involves a **targeting rule**, an
**individual/expiring target**, a **percentage rollout**, or **self-targeting** —
i.e. any time you pick a `contextKind` or attribute.

## TL;DR

- **Target only kinds present on the surface where the flag is read.** A flag read
  in a browser (client-side SDK) can only match kinds your app actually puts in the
  client context; a flag read on the server can match whatever the server builds.
  A rule on a kind that isn't in the evaluation context never matches.
- **A context's key is not an attribute.** Individual targets match the context
  **key**; everything else (email, plan, country, …) is an **attribute** and must
  be a targeting **rule**. Targeting an email as if it were a key is the single most
  common mistake — see [Key vs attribute](#key-vs-attribute).
- **Percentage rollouts bucket by one context kind.** A ramp needs that kind
  present in the evaluation context, or it can't bucket — see
  [Rollout bucketing](#rollout-bucketing).
- **Availability is conditional, not global.** The same app can carry different
  kinds/attributes in different code paths (authenticated vs anonymous, request
  handler vs background job). Decide per surface, not once for the whole app.

## Match the kind to the surface where the flag is read

The context passed to an SDK's `variation` call is assembled by *your* code, and it
differs by where that code runs:

- **Server-side evaluation.** The server builds the context from whatever it has in
  scope — often a user/account plus request-scoped data. Kinds and attributes are
  whatever your server-side context builder puts in.
- **Client-side / browser evaluation.** The browser only sees the context your app
  ships to it (typically at page load, then updated via an identify call). This is
  usually a **strict subset** of what the server has: request-scoped or
  server-only kinds are not present, and an anonymous / pre-auth page (login,
  signup) may carry *no* user/account context at all.
- **Mobile evaluation.** Similar to client-side: the app controls the context and
  it reflects the signed-in (or anonymous) state on the device.

Implications:

- A flag read in **both** server and client code should target only kinds present
  in **both** contexts.
- A client-side flag evaluated on an **anonymous / pre-auth** page cannot match a
  user- or account-scoped rule — plan the fallthrough / off variation for the case
  where nothing matches.
- Client SDKs can add attributes at runtime (via an identify call) only to a kind
  the shipped context already has; they generally can't conjure a brand-new kind on
  a page that never carried it. Don't plan a rule on a kind the surface never sees.

## Key vs attribute

Every context has exactly one **key** (its stable identifier) plus any number of
**attributes**.

- **Individual / expiring targets match the key.** "Target this specific user" means
  their context **key**, not their email or name.
- **Everything else is a rule on an attribute.** To target by email, plan, country,
  version, etc., write a targeting **rule** with a clause on that attribute
  (`contextKind` + `attribute` + `op` + `values`).

The classic trap: a context keyed by an opaque user ID, where email is an
*attribute*. Adding the email as an individual **target** matches nothing (the key
is the ID, not the email); email targeting must be a **rule** on the email
attribute. Confirm your context's key from the code that builds it before choosing
between an individual target and a rule.

## Rollout bucketing

A percentage rollout (and a guarded/progressive ramp) hashes a context to place it
in a bucket, using **one** context kind — the rollout's `bucketBy` / rollout
context kind (defaults to the flag's default kind). That kind must be present in the
evaluation context for the ramp to work.

- If a flag is only ever evaluated in a context that **lacks** the bucketing kind
  (e.g. a background job with no user context when the ramp buckets by user), the
  ramp can't place it — the context falls through instead of ramping.
- Choose a bucketing kind that is present everywhere the flag is read, and stable
  per subject so a given subject stays in the same bucket as the percentage grows.

## Set `contextKind` explicitly

A rule clause with no explicit `contextKind` defaults to the SDK's default kind
(historically `user`). If your app targets a different kind, always set
`contextKind` explicitly so a rule doesn't silently land on the wrong kind and fail
to match.

## Determine availability deterministically from your code

Don't guess which kinds/attributes exist — read the code that builds the context:

1. **Find where the context is constructed.** Search for the SDK context builder in
   your codebase — e.g. `LDContext`, `newContext` / `ContextBuilder` (Go),
   `LDContext.builder` (Java), `Context.builder` / `LDContext` (JS/React),
   `Context.create` (Python), or the object literal passed to `variation` /
   `useLDClient` / `identify`. That call site is the source of truth for the kinds
   and attributes available at that evaluation.
2. **Compare the surfaces.** If the flag is read on more than one surface
   (server + client, authenticated + anonymous), read each surface's context
   construction and target only what they share.
3. **Confirm the key.** Read what value is used as the context `key` so you know
   whether a subject is targetable as an individual target (by key) or only via a
   rule (by attribute).
4. **Cross-check a neighbor.** Inspect an existing flag's rules (their `contextKind`
   / `attribute`) to confirm the convention already in use, and a rollout's
   bucketing kind to confirm what ramps bucket by.

## Common mistakes

- Targeting a client-side flag by a server-only or request-scoped kind — it never
  fires in the browser.
- Writing a user/account rule on a flag evaluated on an anonymous / pre-auth page,
  where no such context exists.
- Adding an email (or any attribute) as an **individual target** when the context
  key is an opaque ID — email must be a **rule** on the email attribute.
- Planning a percentage rollout bucketed by a kind that isn't present where the flag
  is read — the ramp can't bucket.
- Omitting `contextKind` on a clause and silently targeting the default kind.
- Assuming a kind/attribute is global — availability is conditional per code path;
  decide per surface.

## See also

- [Targeting Patterns](targeting-patterns.md): rule construction, individual
  targeting, percentage rollouts, and cross-environment copying.
- [Safety Checklist](safety-checklist.md): pre-change verification and approvals.
