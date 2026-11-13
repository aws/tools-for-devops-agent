# Report format

Output is a diagnosis, never an action.

## AI-generated banner (mandatory, first line of every report)

Every report begins with this banner, verbatim, before any other content:

```
> AI-generated diagnosis - read-only. Findings are evidence-based but may be incomplete;
> validate before acting. Every "Fix" is a command or console step for a human operator to
> run; this skill does not execute it.
```

## Structure

```
# Bedrock Knowledge Base Diagnosis
Knowledge base: <name> (<kb-id>)   Region: <region>
Symptom (as reported): <quote>
Data sources: <n>   Vector store: <type>

## Verdict
<Root cause at layer X> | <No single root cause - see findings>

## Pipeline walk (in order; stops at first fault)
- Source:        <Ruled out | Root cause | Inspect | Not checked> - <one-line evidence>
- Ingestion:     <...>
- Embedding:     <...>
- Vector store:  <...>
- Query:         <...>

## Findings
| # | Layer | Finding | Verdict | Severity | Evidence (API . field = value) | Fix |
|---|-------|---------|---------|----------|--------------------------------|-----|

## Fix (operator runs)
<command or console step per finding, e.g.
 aws bedrock-agent start-ingestion-job --knowledge-base-id <kb-id> --data-source-id <ds-id>>

## Inspect (data-plane checks for the operator)
<exact checks the API could not perform>

## Not checked
<denied calls / unsupported stores / scope limits, each with reason>

## Handoffs
<aiml-access-diagnostics | bedrock-operation-review | service-quota-check, with the context passed>
```

Rules:
- Cite evidence as `API . field = value` and cite job IDs for ingestion claims.
- Mask before writing any text, including interim summaries, CloudTrail timelines, and any
  delegated sub-agent output: account IDs in ARNs, plus source IPs and principal/session names
  taken from CloudTrail. Mask before the text is emitted, never as a raw value followed by
  "masked".
- Nothing - no interim output, timeline, or sub-agent text - may appear before the
  AI-generated banner above.
- Never include document or chunk content.
- State the region used and why (named vs current).
- Every "Fix" is a command/console step for the operator - the skill never executes it.
