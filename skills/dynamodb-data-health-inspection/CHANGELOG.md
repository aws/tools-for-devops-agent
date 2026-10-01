# Changelog

## 1.3.0

### Measured outcome: the targeted fabrications were fixed, the aggregate rate was not

Re-running the same 40-case blinded ground-truth eval across three skill versions, with the
control arm unchanged as a constant:

| | 1.1.0 | 1.3.0 (facts file) | 1.3.0 (+ no-live-table carve-out) |
|---|---|---|---|
| Harmful claim | 8 (21.6%) | 8 (21.6%) | **8 (21.6%)** |
| Root cause correct | 89.2% | 91.9% | 89.2% |
| *Control arm, unchanged* | *8* | *9* | *8* |

**Four of the five originally-targeted fabrications are fixed** and stay fixed - the 400 KB
write semantics (two cases), GSI propagation, and GSI backfill throughput. The fifth, a TTL
capacity claim, persists.

**The aggregate rate did not move.** The harmful *set rotates* between runs: different cases are
flagged each time, and some of the new ones are facts this file explicitly covers with a
"Do not say" warning. The control arm moved 8 to 9 to 8 across identical inputs, which puts
run-to-run noise at about one case, so the flat 8 is indistinguishable from a small change
either way at n=40.

**Interpretation, stated plainly:** the facts file reliably corrects the specific fabrication it
is pointed at, but it does not raise baseline instruction-following. The agent still contradicts
facts that are present in the reference, and which facts it contradicts varies per run. This is
a property of instruction adherence, not of the facts themselves - so the file is retained
because its content is correct and independently verifiable, not because it demonstrably lowers
the rate.

The residual rate is largely shared with the no-skill arm and is a property of the base agent.
Anyone relying on a DynamoDB diagnosis from this or any skill should expect roughly one
mechanism claim in five to need checking against the documentation.


Addresses the fabrication rate the ground-truth eval measured. The `1.2.0` eval reported a 20%
harmful-claim rate in **both** arms, which was initially dismissed as base-agent behaviour.
Investigating it found a real defect in this skill.

**Diagnosis.** Five of the harmful claims in the with-skill arm were DynamoDB mechanism facts
inside this skill's own four dimensions - 400 KB write semantics, GSI propagation, TTL capacity
consumption, GSI backfill throughput. In every one the finding itself was scored *correct*: the
skill reached the right conclusion and then invented the mechanism around it.

The cause was structural. The skill's facts were **stranded inside conditional finding
templates**. TTL-06 correctly stated that TTL deletions consume no write capacity, but TTL-06
only fires when TTL is `DISABLED` - so on a TTL *backlog* case that text was never in play and
the agent asserted the opposite. IX-05 correctly stated that GSIs have their own provisioned
capacity, but it only fires on missing autoscaling. Compounding it, every anti-fabrication rule
governed *findings* only; nothing governed the explanatory prose where the fabrications lived.

**Changes.**

- Added `references/dynamodb-facts.md`, loaded unconditionally: the load-bearing mechanics for
  all four dimensions, each cited to AWS documentation, each paired with the specific false
  version observed in validation so the trap is recognisable rather than abstract. Covers
  400 KB write rejection semantics, LSI size accounting, GSI asynchronous propagation and
  capacity ownership, GSI backfill throughput, TTL capacity and window, item collections, and
  restore-with-index-override.
- Added a **"Do not fabricate mechanism"** rule to Critical Rules, extending the evidence
  discipline from findings to the explanation around them, with an explicit instruction to say
  "not certain" and name the settling check rather than invent a timing figure or error
  behaviour.
- Cross-referenced the facts file from the four finding templates that previously stranded
  these facts (IS-01, TTL-05, IX-05, IX-06), and corrected their inline wording.
- Four regression tests, one per fabrication class.

**Correction to the previously reported number.** Hand-verifying all 16 harmful flags against
AWS documentation found the judge had made scoring errors in **both** directions - it marked a
control answer harmful for stating that LSI entries count toward the 400 KB limit, which the
documentation confirms they do, and similarly for saying a restore can exclude an LSI, which
`LocalSecondaryIndexOverride` supports. The verified with-skill rate is **7 of 40 (17.5%)**, not
20%: five mechanism fabrications addressed here, two dimension-bias cases already fixed in
1.2.0, and one SDK claim outside this skill's dimensions.

**SKILL.md size.** Adding the rule pushed the body over the 5,000-token guidance, so the
Scan-sample reasoning was moved into `references/sampling-protocol.md` where it belongs, leaving
in SKILL.md only the four rules that bind the report itself. Audit back to 100/100.

## 1.2.0

Adds a guard found by a blinded ground-truth eval: 40 real sev1-2 support cases, diagnosed
from the case narrative alone, scored against the documented root cause and solution by a
judge that could not tell which answer came from which arm.

**The finding was negative and worth acting on.** With no live table to inspect, applying
this skill *reduced* root-cause accuracy from 97.5% (no skill) to 90.0%, and remediation
match from 97.5% to 92.5%. Harmful-claim rate was unchanged at 20% in both arms. Two
mechanisms, both traced to specific cases:

- **Dimension bias.** The skill pushed a pagination-behaviour case toward "hot partition"
  because hot keys are one of its four dimensions, explicitly rejecting the reporter's
  correct 1 MB response-limit explanation to do so.
- **Over-skepticism.** The skill's evidence discipline, meant to stop the agent
  over-claiming, instead overruled a reporter who had already measured the answer - it
  asserted that provisioning GSI write capacity for a backfill was not possible, which is
  both wrong and exactly what the documented remediation did.

Root cause of both: the skill's method is collect-then-threshold, and it was applying its
framing even when there was nothing to collect. SKILL.md now instructs it to decline the
inspection when there is no live table, reason from symptoms without its thresholds or rule
IDs, and never cite a rule ID for a finding it did not derive from collected data.

This does not change behaviour where the skill is designed to operate. The AgentSpace A/B
on live infrastructure, run the same day, showed the opposite result: on a live table with
a real TTL fault, the no-skill arm's *primary* diagnosis was wrong ("not enough time has
passed") with the true cause ranked fourth, while the skill arm identified TTL-01 from a
measured-zero-versus-NoData distinction and gated sampling - consistently across 3/3 runs.

## 1.1.0

Recalibrated against 11,677 real Amazon DynamoDB support cases. The four dimensions
and the rule taxonomy held up; the weighting and two gating conditions did not.

- **HK-02 no longer requires the key-range throttle metric.** It gated a confirmed hot
  partition on `*KeyRangeThroughputThrottleEvents > 0`, but across ~1,275 real
  hot-partition cases throttling was the presenting symptom in 93.6% while the key-range
  metric was cited in only 12.2% and Contributor Insights in 63.5%. The rule now accepts
  either the key-range metric (strong evidence) or generic throttle events plus
  Contributor Insights concentration (corroborating), and states which it had.
- **Reordered hot-key remediation to match how real cases resolve** - retry with
  backoff (53.4% of cases) and capacity headroom (42.8%) before write sharding (37.8%),
  while labelling the first two as mitigations and sharding as the cure so operators do
  not stop at step 2 and meet the same ceiling at the next peak.
- **TTL-05 now explains asynchronous deletion.** Deletion delay is the single most
  common TTL complaint in the data (21.2% of 520 TTL cases), with root causes recorded as
  "asynchronous ttl processing" and "backend capacity limitations". The skill never said
  that TTL throughput is bounded by background capacity and cannot be accelerated by the
  customer. It now leads with the fix that is actually in the operator's control - filter
  expired items out of read paths - and warns against a scan-and-delete job.
- **IX-01 recalibrated.** A genuinely unused index is the *rarest* index problem in the
  data (~3% of index cases), yet it was the rule that produced a false High-severity
  finding during agent testing. It now phrases the action as "confirm with the owning
  application, then delete", never "delete this index".
- **IX-08 promoted.** Item collection limits are the *most* common index problem (~28%
  of index cases, ~10x the unused-index rate). The skill now estimates collection size
  whenever LSIs exist and prioritises this above projection and utilization findings.
- **Added IX-10, write amplification.** ~101 cases arrive as "unexpected WCU
  consumption" with no throttling - a question the per-index rules did not answer. Fires
  when summed GSI write capacity is >= 1.5x the base table's, and explains the
  write-multiplication arithmetic plus sparse indexes as a remedy.

Measured scope: the four dimensions match 18.3% of the corpus (2,133 cases). Hot keys
are the most severe dimension (46% at sev1-2). The largest untouched families are
correctly out of scope per the skill's own boundaries - quotas 35.9%, latency 34.9%,
configuration 21.5%, authorization 14.0%.

## 1.0.5

Corrections from driving the real AWS DevOps Agent over its API against the live
validation table - skill uploaded to an Agent Space, prompted naturally without naming it,
trajectory inspected via ListJournalRecords across several rounds.

- **Fixed a design flaw in Phase B.** The protocol asked the agent to compute per-item
  statistics over 1,000 items, a ~1 MB payload per page. The agent has no code execution
  and must aggregate in its own context; the platform summarizer produced sub-batch counts
  disagreeing by 3x and the agent correctly refused to publish numbers it could not trust.
  Phase B is now two passes: a projected pass (keys + TTL attribute only) small enough to
  total reliably at n=1,000, and a separate full-item pass at n=100-200 for item size.
  Re-tested: the agent then produced correct quantified TTL percentages.
- **Fixed a false "unused index" finding.** IX-01 recommends deleting a customer's index
  and requires 30 days of metric coverage, but on a 4-hour-old table the agent read
  "consumed read over the last 30 days: 0" and fired it at High severity - conflating the
  width of the queried window with the amount of data in it. `metric_coverage_days` is now
  defined as `min(datapoints at a daily period, table age from CreationDateTime)`, with an
  explicit guard routing to IX-02 below 30 days.
- **Made Phase A collection scope-aware.** Two successive instructions to always collect
  all six Phase A steps were both declined on targeted prompts; measurement showed a
  *full review* prompt already produces complete collection (8 GetInsightRuleReport calls
  across table and GSI). Scoping work to the question is correct behavior, so the skill
  now defines two modes: targeted questions collect for the dimension asked and must list
  what was not assessed without rendering a dimensions matrix; full reviews collect
  everything and honor the Final Delivery Contract. The invariant holds in both - never
  imply a dimension was assessed when it was not, and never conflate "not determinable"
  (asked, unavailable) with "not collected" (chose not to look).
- Fixed the unknown-mean RCU upper bound, which halved the correct figure and
  under-predicted a measured 450 RCU as 256. A full 1 MB eventually-consistent page is
  128 RCU, with no further 0.5 factor.
- Reframed `minimal-exposure` as "run the projected pass only", since projection is now
  the default for the TTL/key pass rather than an exposure-only option.
- Added the 80-character limit on structured choice options, with exact short forms. The
  agent lost a turn to a validation error twice, both times by interpolating the table
  name into an option description.
- Findings must cite the exact rule ID. The agent had labelled a malformed-timestamp
  finding "TTL-01 style" when TTL-01 is a materially different diagnosis (TTL deleted
  nothing) from TTL-04 (timestamps malformed).

Verified working in the same rounds: unprompted activation, the consent gate blocking
before any data-plane read, stale-metadata detection, and the measured-zero-versus-missing-
data distinction, which the agent surfaced verbatim as "0 (measured zero, not missing data)".

## 1.0.1

Corrections from live validation against a seeded DynamoDB table, run under the
least-privilege role the bundled CloudFormation template provisions.

- Fixed: a stale `ItemCount` of 0 (DynamoDB refreshes it only every ~6 hours) caused
  sampling to be skipped on tables that actually hold data. Emptiness must now be
  corroborated by `TableSizeBytes` and consumed write capacity before Phase B is
  skipped.
- Fixed: no rule covered Contributor Insights being enabled but returning zero
  contributors, so the hot-key dimension could render as assessed-and-healthy when
  nothing had been measured. Added HK-06 and a `NoData` status that forces the
  dimension to "not determinable".
- Documented the real Contributor Insights rule-name convention (`PKC`/`SKC`/`PKT`/
  `SKT`, four rules per target, `<table>-<index>` for GSIs) so contributors can be
  attributed to traffic versus throttling instead of guessed at.
- Documented the 1 MB `Scan` page cap, which binds before `Limit` once items exceed
  ~4 KB and makes the realized sample smaller than planned.
- Strengthened the sampling-bias warning with a measured case: where 40 % of items
  shared one partition key, a bounded sample measured its share at 0.3 %. A low
  sampled share is therefore not evidence of even distribution.
- Fixed: IX-04 (over-broad GSI projection) silently did not fire when
  `amplification_ratio` was null from stale `TableSizeBytes`, so a full projection on
  a large table went unreported. It now degrades to a Low finding that states why the
  ratio is unavailable. Added a general consistency rule: a threshold that cannot be
  evaluated is never a passing threshold.
- Recorded validated accuracy of the cost estimate (1.00x) and the item-size
  approximation (0.2 % drift against billed capacity).

Rule discrimination verified against the live table: with Contributor Insights
showing 16.7x traffic concentration but no key-range throttle events, HK-02
(confirmed hot partition) correctly stayed suppressed and HK-03 (concentration
without throttling) fired instead.

## 1.0.0

- Initial version
- Four diagnostic dimensions: hot key detection, item size analysis, TTL
  effectiveness evaluation, and GSI/LSI utilization assessment
- Two-phase execution: Phase A (control plane, CloudWatch, Contributor Insights) at
  zero data-plane cost, then Phase B bounded sampling behind an explicit consent gate
- Read-only throughout; sampling capped at 1,000 items by default (10,000 absolute),
  ≤ 4 Scan segments, eventually-consistent reads, with abort on cost overshoot or
  throttling
- Sampling refused by default against tables that are already throttling
- Value redaction: item byte sizes, attribute names, and TTL timestamps only;
  partition keys rendered as digests
- `minimal-exposure` projection mode for tables holding regulated or personal data
- 25 finding rules with verbatim templates and a confidence-downgrade rule for small
  samples
