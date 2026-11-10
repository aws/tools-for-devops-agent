# Framing and Attribution — Emissions as Context

Read this file in full before interpreting any emissions or water figure (Step 5), and again
before Step 8 and before writing report Sections 1 and 3. It holds the rules that decide what
the report may say about emissions and what it may attribute to the customer.

## Core Framing Rule — Read This First

**Emissions and water data are context. Resource intensity KPIs are the assessment.**

A reported MTCO2e figure is a **confounded** measurement, not a scorecard. It is the product
of what the customer provisions and a set of factors that move independently of anything the
customer does:

| Confounder | Moves the number without any customer action |
|------------|----------------------------------------------|
| Methodology revision | AWS restates all history under the current model version. The figure changes; the workload did not. |
| Grid carbon intensity | The Region's grid mix varies seasonally and yearly. |
| AWS renewable energy procurement | Lands in Scope 2 MBM, so LBM and MBM can move in opposite directions. |
| Data center efficiency and hardware refresh | PUE improvements and newer hardware change the emissions per unit of usage. |
| Allocation share shift | Emissions are allocated by *proportional* usage, so the customer's share moves when **other** customers' usage moves. |
| Reporting lag and thresholds | Carbon for month M publishes by the 21st of month M+1; values below 0.5 g CO2e are absent, not zero. |

Because these move at the same time as the customer's own changes, **a period-over-period
change in reported emissions cannot be attributed to a customer action without first ruling
them out** (Step 8). That is a statement about attribution, not about magnitude: customer
decisions can and do move the reported figure substantially — provisioning determines how much
AWS infrastructure gets allocated to the account in the first place, and Region choice is an
explicit Pillar best practice (SUS01-BP01). The problem is that the emissions figure alone
cannot tell you *which* cause was responsible.

Resource intensity KPIs have no such confounders: they measure what the customer provisioned
and used, directly. That is why they are the assessment and emissions are the context.

**Water withdrawal is allocated by the same top-down method and carries the same
confounders** — treat it identically to carbon throughout.

Note what this does **not** mean. It does not mean efficiency work is futile or that the
customer's slice is too small to matter. The division of responsibility is that AWS owns the
*efficiency of the infrastructure* (PUE, renewable supply, hardware) while the customer owns
*how much of it they consume* — and that second quantity is what every recommendation in this
skill targets. Never tell a customer their rightsizing or decommissioning work is immaterial
to their footprint; embodied hardware carbon in particular scales with what they provision.

You MUST NOT claim causality between a customer action and a change in reported
emissions. Specifically:

| Never say | Say instead |
|-----------|-------------|
| "Your optimization reduced emissions by X MTCO2e" | "Reported emissions fell X MTCO2e over this period. Grid intensity and AWS infrastructure changes also moved in this window, so this figure cannot be attributed to the architecture change. The resource intensity KPI fell Y%, which *is* attributable." |
| "Emissions increased, so the workload regressed" | "Reported emissions increased. Check the methodology version and grid intensity first — see Step 8 before treating this as a regression." |
| "This change will save X MTCO2e" | "This change reduces provisioned vCPU-hours by X%, which reduces the resource footprint the emissions model allocates to you." |
| "Moving to Graviton will cut your emissions by 60%" | "AWS states that Graviton-based EC2 instances use up to 60% less energy than comparable EC2 instances for the same performance. This review does not estimate the effect on your reported emissions. The migration moves X vCPU-hours/month to Graviton, which you can track through compute intensity." |

Resource intensity KPIs *are* attributable to customer action, because they measure
what the customer provisions and consumes. Lead with them.

## Step 8: Explain Emissions Changes Before Attributing Them

If reported emissions changed period-over-period, work through these causes **in this
order** before considering an architecture change as the explanation:

0. **Is the comparison even valid?** Only when the data came from a CSV (Step 5.0). An
   incomplete latest period, two different `model_version` values, or a period length
   mismatch will each manufacture an apparent change out of nothing. If any of these applies,
   there is no change to explain — report the coverage and stop here.
1. **Methodology version change** — a revision can move reported figures substantially with
   zero change in usage. History is restated under the current model, so all months in a
   response share one `ModelVersion` and you **cannot** detect a revision by comparing
   periods. Instead compare it against the version behind any figure the customer published
   previously; if it differs, their earlier number was restated — the change is in the
   instrument, not the workload. Say so and stop here. Carbon and water version
   independently, so check the relevant one.
2. **Grid carbon intensity** — the Region's grid mix changes seasonally and yearly.
   Emissions can rise while usage falls, or fall with no customer action.
3. **AWS-side infrastructure changes** — hardware refresh, PUE improvements, and
   renewable energy procurement all move the number without customer action.
4. **Allocation share shift** — CCFT allocates a share of AWS infrastructure emissions
   based on proportional usage. Your share can change because *other* customers' usage
   changed.
5. **Scope composition** — check whether the change is in Scope 1, 2, or 3, and in LBM vs
   MBM. Scope 2 MBM is where AWS renewable purchases land, so LBM and MBM often move in
   opposite directions and a customer reading the wrong series draws the wrong conclusion.
6. **Actual usage change** — after ruling out 1–5, correlate against the resource intensity
   KPIs from Step 6. This is a legitimate and often substantial cause, not a leftover:
   provisioned capacity drives the allocation, and embodied hardware carbon (frequently the
   largest scope) scales with it. If the KPIs moved in the same direction and the confounders
   above are ruled out, say the usage change is the **most likely** explanation — while still
   not asserting a precise causal split, because the confounders were ruled out, not measured.

The ordering exists because the confounders are invisible in the figure itself, so they must be
eliminated first. It does **not** rank them by size, and reaching step 6 is a normal outcome.

A storage reduction that does not show up as an emissions reduction is the **expected**
result, not an anomaly. Say so directly — customers who have done real optimization work and
see no movement in reported emissions need this explained, not hedged. Equally, do not talk a
customer out of efficiency work on the grounds that emissions are mostly not their doing:
the reason to rightsize is that it reduces the resources allocated to them, which is both
real and the thing they control.
