# Changelog

## 1.0.0
- Initial release. Read-only, advisory architectural anti-pattern catalog.
  Consumes the DevOps Agent Topology graph and Proactive Incident Prevention
  output (does not re-implement them) and classifies findings against a named
  catalog (SPOF, synchronous coupling, missing bulkheads, cascade paths, retry
  storms, shared-fate deployment), returning a severity-ranked architectural-debt
  report. Remediation is proposed, never executed.
