# Changelog

## [1.0.0] - 2026-11-03
### Added
- Initial public release: two-direction BGP prefix coverage assessment for
  redundant Direct Connect VIFs, tiered redundant-set resolution (memory →
  resiliency groups → inference → confirmation), partial-supernet residual
  reporting, device-diversity and resiliency-group pairing findings.
- `enable_tools` frontmatter registering the three `dx-resilience-mcp` tools
  (prefixed with the MCP server's registered name).
- Guidance on ListVirtualInterfaceRoutes convergence lag (eventually-consistent,
  non-deterministic per VIF, observed 1–14 min) and full pagination of large
  tables.
### Validated
- 12-scenario live BGP test suite in a DX lab: coverage classes, aggregate
  tiling, residuals incl. nested /21-vs-/22, empty VIF, default route,
  TE-not-a-gap, and pagination to 478 routes/VIF. Deterministic coverage cases
  are committed in the MCP server's `tests/`; functional evals are produced via
  the skill-evaluation tool.
