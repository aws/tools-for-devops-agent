# Changelog

## 1.0.0

- Initial version
- System prompt with Goal/Approach/Constraints/Output structure
- Uses the `support-and-ta` skill for domain knowledge and report structure
- Calls the Optira MCP tools `get_support_insights` and `get_trusted_advisor_recommendations` (registered server `optirainsight-lambda-mcp`); artifact and recommendation creation use the built-in custom agent output capabilities
- Default reporting window: trailing 12 months
- Produces a tiered Improvements list (HIGHEST/HIGH/MEDIUM) and refreshes a single "Daily Support & Trusted Advisor Report" artifact per run
