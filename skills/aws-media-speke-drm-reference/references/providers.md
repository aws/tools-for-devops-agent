# Qualified SPEKE DRM providers

Independent reference. **Dated: 2026-06.** SPEKE v1/v2 support and pricing change -- confirm current support
and pricing **directly with the vendor**. **Specific dollar figures are intentionally omitted** because they
go stale quickly; only the *pricing model* category is listed. Verify the qualified-partner list against the
current AWS SPEKE partner documentation.

| Provider | SPEKE v1 | SPEKE v2 | Integration model | Pricing model |
|---|---|---|---|---|
| Axinom | Yes | Yes | SPEKE gateway | quote-based |
| BuyDRM (KeyOS) | Yes | Yes | API Gateway HTTP proxy | license-pool tiers |
| CastLabs (DRMtoday) | Yes | Yes | CloudFormation Lambda adapter | subscription + per-request tiers |
| EZDRM | Yes | Yes | direct SPEKE endpoint | subscription + license bundle |
| Inisoft | Yes | Yes | -- | quote-based |
| DoveRunner (PallyCon) | Yes | Yes | direct KMS URL | subscription (MAU / MAL tiers) |
| Insys Cloud DRM | Yes | Yes | -- | quote-based |
| Intertrust | Yes | Yes | -- | quote-based |
| Irdeto Control | Yes | Yes | AWS Marketplace | enterprise |
| JW Player | Yes | Yes | -- | bundled with platform |
| Kaltura | Yes | No | -- | bundled with platform |
| NAGRA | Yes | Yes | -- | enterprise |
| NEXTSCAPE | Yes | Yes | -- | quote-based |
| SeaChange | Yes | No | -- | quote-based |
| Verimatrix | Yes | Yes | -- | quote-based |
| Viaccess-Orca | Yes | No | -- | enterprise |
| WebStream | Yes | Yes | -- | quote-based |

## Selection guidance
- **Need SPEKE v2 / multi-key:** confirm the provider's v2 column above (Kaltura, SeaChange, and Viaccess-Orca
  are v1-only in this snapshot -- re-verify).
- **Want minimal integration:** a *direct SPEKE endpoint* or *direct KMS URL* is the least plumbing; a
  *gateway* or *Lambda adapter* model adds an indirection you operate.
- **Procurement style:** *subscription* models give predictable monthly cost; *quote-based* and *enterprise*
  suit large/SLA-driven deployments. Get current numbers from the vendor -- do not quote figures from memory.

> Currency note: this list and the support flags reflect a 2026-06 snapshot. The authoritative, current list of
> qualified SPEKE partners and their v1/v2 support is the AWS SPEKE partner documentation.
