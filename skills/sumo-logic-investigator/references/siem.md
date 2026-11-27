# Cloud SIEM reference

Load this when the question is security-related — insights, signals, entities, detection
rules, or threat investigation.

## Workflow

1. **Insights first** — `getInsights` with entity/severity filters. Do not start from logs;
   an insight already correlates the signals for you.
2. **Read the rules** — `getRules` to see what is actually being monitored. A gap in
   coverage is itself an answer.
3. **Correlate with logs** — use the 3-step log search workflow in SKILL.md for supporting
   evidence, scoped to the entities the insight names.
4. **Act** — update insight status/assignee, or propose a new detection rule.

## Insight query DSL

Filters are joined with `+` (not `AND`). Substitute real dates from context, never a
literal copied from this file.

```
status:"new"
severity:>7
entity.ip:"10.0.1.5"
entity.username:"jdoe"
timestamp:><today>T00:00:00+00:00
tag:"MITRE_ATT&CK"
assignee:"unassigned"
```

Combined: `q=severity:>7+status:"new"+timestamp:><today>T00:00:00+00:00`

Other useful fields: `confidence`, `triageVerdict`, `resolution`, `ruleId`,
`involvedEntities.value`, `readableId`. Range syntax is `field:low..high`; substring match
is `field:contains("...")`; set membership is `field:in("a", "b")`.

## Creating detection rules

Rule creation mutates the customer's tenant and will prompt for permission. Before calling
`createTemplatedMatchRule` or `createThresholdRule`:

- **Always set `enabled: false`** and tell the user to review it in the UI before enabling.
  A live rule that misfires pages someone.
- Also set `isPrototype: true` unless the user asked for a production rule — prototype rules
  generate signals without contributing to insights.
- Write a `descriptionExpression` that states what the rule detects and why it matters.
  This is the text an on-call engineer sees at 3am.
- Pick entity selectors that match the record fields (`_ip`, `_hostname`, `_username`,
  `_mac`) — a selector pointing at a field the stream does not carry yields signals with no
  entity, which never roll up into an insight.
- Set `score` 1-10 proportionate to real severity. Inflated scores dilute insight ranking.
- Threshold rules need `windowSize` and `limit`; confirm both with the user rather than
  guessing a rate.

Show the user the full rule payload and get confirmation before creating it.
