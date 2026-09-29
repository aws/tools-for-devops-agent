# Changelog

## 1.0.0

- Initial version
- Ranks the top 5 AWS services by support case count (per account) over a configurable window (default: trailing 12 months)
- Surfaces critical (error/red) Trusted Advisor recommendations per account
- Cross-references support-case volume against critical Trusted Advisor findings in the same account
- Designed to pair with the Optira support-case insights MCP server (`get_support_insights`, `get_trusted_advisor_recommendations`) and the `support-and-ta-report` custom agent
