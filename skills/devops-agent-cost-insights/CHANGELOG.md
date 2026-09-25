# Changelog

## 1.0.0

- Initial version
- Methodology skill for AWS DevOps Agent cost reporting: defines how figures are gathered and computed, and leaves presentation to the consuming agent (chat answer or custom agent dashboard)
- Reporting window fixed once at Step 1 and reused for every source, so two runs over the same period agree
- Logs Insights attribution from `DescribeQueries` as the sole source of query count, identity, `bytesScanned`, and cost, paginated to exhaustion with `maxResults: 1000` and a coverage check against the window start
- Athena attribution by joining `StartQueryExecution` CloudTrail events (for the initiating role) to `ListQueryExecutions` / `BatchGetQueryExecution` (for exact `DataScannedInBytes`), with the 10 MB per-query minimum applied
- Direct usage labelled space-scoped and downstream/tool usage role-scoped; the two are never combined into one total
- Per-GB and per-TB rates resolved from the AWS Pricing API each run; a denied or empty lookup yields `not priced: rate unavailable` rather than `$0.00`
- Tool usage classified from journal records across AWS, Azure, third-party MCP, and platform tools
- Unavailable data always reported as unavailable with a reason
- Evaluation suite under `evals/` covering structure, functional, and best-practice checks
