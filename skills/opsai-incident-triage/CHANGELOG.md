# Changelog

## [1.0.0] - 2026-11-17
- Initial release in this repository.
- Triages live model-call failures (errors, throttling, latency) and rules whether the fault is the provider, infrastructure or app.
- Renamed from the earlier incident triage skill. `Remediation owner` now names an owner track from `references/related-skills.md` instead of a skill.
- Works on its own: sibling skills are optional, with a fallback check per area in `references/related-skills.md`.
