# Discovery guide — inferring the product and recent features

The goal of Step 1–2 is a fast, accurate read of *what this app is* and *what
the team has been building*, not a full audit. Spend a handful of tool calls,
then confirm with the user.

## Infer the product

Read these first — they give the most signal per byte:

| File | What it tells you |
|------|-------------------|
| `README*`, `docs/` index | The product in the team's own words. |
| `package.json` / `pyproject.toml` / `go.mod` / `Gemfile` / `pom.xml` / `*.csproj` | Name, description, and the dependency list (framework, payment, auth, analytics libs). |
| Top-level dirs | `app/`, `pages/`, `routes/`, `controllers/`, `cmd/`, `services/` → the major surfaces. |
| Entrypoint | `src/index.*`, `main.*`, `app.*`, `server.*` → app type (web/API/CLI/mobile). |

Framework → product-type hints:
- `next`, `react`, `vue`, `svelte`, `@angular/core` → web frontend / full-stack app.
- `express`, `fastify`, `nestjs`, `flask`, `django`, `fastapi`, `gin`, `rails` → backend/API.
- `react-native`, `expo`, `flutter` → mobile.
- `stripe`, `braintree`, `shopify` → commerce / revenue surface (strong experiment target).
- `segment`, `amplitude`, `posthog`, `mixpanel`, `launchdarkly` → analytics already present (reusable events).

Name the major user-facing surfaces you can see — checkout, onboarding/signup,
search, feed, pricing, settings. These are where experiments live.

## Surface recent features

Recent work is the best experiment candidate — the team already cares, and the
code is fresh.

- `git log --oneline -n 30` — scan commit subjects for feature words ("add",
  "new", "redesign", "revamp", "v2", feature names).
- `git log --since="8 weeks ago" --name-only --pretty=format:"%s"` — which files
  changed for recent features; cluster by directory to spot the feature area.
- Look for feature flags already in the diff (`variation(`, `boolVariation`,
  `useFlags`, `ldClient`) — a recently-added flag with no experiment is an ideal
  candidate.

## Detect the LaunchDarkly SDK

Grep the manifest/imports to find which SDK the code uses:

- `launchdarkly-node-server-sdk`, `@launchdarkly/node-server-sdk` → Node server
- `launchdarkly-js-client-sdk`, `launchdarkly-react-client-sdk` → browser/React
- `launchdarkly-python-server-sdk` → Python
- `launchdarkly-go-server-sdk` / `gopkg.in/launchdarkly/...` → Go
- none found → the user hasn't installed an SDK yet; the flag/metric delegate
  skills handle SDK setup.

## Confirm before building

End discovery with one or two sentences and a yes/no:

> "This looks like a **Next.js e-commerce storefront**. Recent commits are about
> a **redesigned checkout** and a **recommendation widget**, and you're already
> using the LaunchDarkly React SDK. Want to experiment on one of those?"

A wrong guess here is cheap to fix now and expensive to fix after you've drafted
the wrong experiment.
