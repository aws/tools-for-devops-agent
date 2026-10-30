# Hypothesis guide

A hypothesis is a testable guess: *if we change this, that measurable thing will
move, and here's why.* Most users freeze when asked for one. Don't ask cold —
generate candidates from the feature they picked, show the shape, and let them
edit.

## The shape

> Changing **[what you'll change]** will **[increase / decrease]**
> **[the metric]** for **[which users]**, because **[the reason]**.

A good one names four things:
1. **The change** — the treatment vs. the control (what the flag switches).
2. **The metric** — the single number you expect to move (the primary metric).
3. **The direction** — up or down (and ideally a rough size, e.g. "~3%").
4. **The reason** — the mechanism you believe in. This is what makes it a
   hypothesis and not a wish.

## Turning a fuzzy goal into a hypothesis

| User says… | Reframe toward… |
|------------|-----------------|
| "I want more sales." | "Which step loses people? Test a change there; metric = checkout completion or add-to-cart rate." |
| "The new page feels better." | "Better how — faster, clearer, more clicks? Pick the one number that captures it." |
| "People don't sign up." | "Test a change to the signup flow; metric = signup completion rate for new visitors." |
| "The app is slow." | "Test the optimization behind a flag; metric = p95 latency or load time (numeric, lower is better)." |

## Worked examples by product type

**E-commerce**
> Showing the redesigned checkout will increase **checkout completion** for
> logged-in shoppers, because it removes two form steps.
> Primary metric: `checkout-completed` (conversion).

**SaaS onboarding**
> Adding an interactive product tour will increase **activation** (first key
> action within 24h) for new signups, because it shortens time-to-value.
> Primary metric: `activated` (conversion).

**Content / media**
> Surfacing personalized recommendations will increase **articles read per
> session**, because readers find relevant content faster.
> Primary metric: `article-opened` (numeric count per session).

**Performance**
> Enabling the new image pipeline will decrease **p95 page load time** without
> hurting engagement, because images are served pre-optimized.
> Primary metric: `page-load-ms` (numeric, lower is better).
> Guardrail: `bounce-rate` (should not increase).

**Pricing / growth**
> Showing the annual plan first will increase **annual-plan conversion** for
> visitors to the pricing page, because it anchors on the better-value option.
> Primary metric: `annual-plan-selected` (conversion).

## Sizing (keep it light for a first experiment)

You don't need a power calculation to start. Nudge toward:
- A **clear primary metric** with a direction.
- A **realistic effect** ("a few percent," not "double").
- A **decision rule**: "if completion is up with high confidence after ~2 weeks,
  ship it." LaunchDarkly's stats engine handles significance; the user just
  needs to let it run long enough.

## Anti-patterns to redirect

- **No metric** ("see if people like it") → pin it to one measurable number.
- **Two changes at once** ("new checkout *and* new colors") → split into two
  experiments so the result is attributable.
- **Vanity metric** ("page views") → prefer a metric tied to the actual goal
  (completion, activation, revenue).
- **No reason** → ask "why do you think it'll help?"; the reason shapes what to
  measure.
