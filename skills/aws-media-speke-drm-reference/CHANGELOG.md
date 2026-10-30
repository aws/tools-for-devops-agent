# Changelog

## 1.0.0 (2026-10-27)

- Initial contribution to aws/tools-for-devops-agent: SPEKE / DRM Reference for AWS Elemental Media Services.
- Covers SPEKE v1 and v2, CPIX authoring, multi-key presets and the key rotation versus multi-key trade-off, DRM system IDs, commonEncryptionScheme selection, player CENC/CBCS compatibility, provider selection and a layer by layer DRM troubleshooting runbook.
- Knowledge-only; the optional diagnostics in the troubleshooting runbook use read-only permissions granted separately (EnableMediaSpekeDrmDiagnostics in the shared IAM template, default off).
- Shaped to the DevOps Agent skill-eval best practices: reference links carry load conditions, the DRM system ID, trade-off and SPEKE v1 vs v2 tables moved to references/lookup-tables.md, and a self-check runs before answering.
