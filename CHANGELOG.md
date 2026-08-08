# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-07

First stable release. The bundled catalogs, the coverage / Statement of
Applicability / JSON output schemas, and the `--fail-under` gate are committed
under semantic versioning. Reads
[audit-report](https://github.com/audit-labs/audit-report)'s v1 JSON contract.

## [0.1.0] - 2026-08-06

### Added

- Control-first coverage and blind-spot analysis over a corpus of audit-report
  JSON, producing a true coverage percentage and an unaddressed-control (blind-spot)
  list from the framework's full control catalog.
- Bundled catalogs: SOC 2 (61 controls across all five Trust Services categories),
  ISO 27001:2022 Annex A (93), NIST SP 800-53 Moderate baseline (177).
- Statement of Applicability generation from a scope file (exclusions + reasons),
  with `exclude_families` to drop a whole category/theme/family from the denominator.
- Trend mode (`--baseline`) and crosswalk mode (`--crosswalk`, greedy minimal
  evidence set); md/html/json output.
- `--fail-under N` coverage gate for CI.
- PyPI trusted-publishing release workflow.

[1.0.0]: https://github.com/audit-labs/control-coverage/releases/tag/v1.0.0
[0.1.0]: https://github.com/audit-labs/control-coverage/releases/tag/v0.1.0
