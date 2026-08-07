# Control catalogs — provenance and rationale

`control-coverage` measures how much of a framework an evidence corpus addresses.
The **denominator** is a framework catalog: the complete list of controls the
framework defines. This document records where those catalogs come from, how they
are versioned, and the limits of what they claim.

## What these catalogs are — and are not

- They enumerate control **identifiers** (e.g. `SOC2:CC6.1`, `ISO:A.5.17`,
  `NIST:AC-2`) plus a short title used as a display label.
- They are **not** the normative control text. For authoritative wording, consult
  the source standard.
- Mapping a control to an evidence signal is the **maintainers' interpretation**.
  It is not reviewed or endorsed by the AICPA, ISO/IEC, or NIST.
- Coverage is a measure of **evidence**, not of compliance. A control counted as
  "addressed" means the corpus contains a signal relevant to it — not that the
  control operates effectively. That judgment belongs to the organization and its
  auditor.

## Sources and revisions

| Framework | Catalog file | Revision used | Scope |
|---|---|---|---|
| SOC 2 | `catalogs/soc2.yaml` | Trust Services Criteria 2017 (2022 revised points of focus) | All five categories: Security (Common Criteria), Availability, Confidentiality, Processing Integrity, Privacy |
| ISO/IEC 27001 | `catalogs/iso27001.yaml` | 27001:2022 Annex A | All 93 Annex A controls, four themes |
| NIST SP 800-53 | `catalogs/nist80053.yaml` | Rev. 5 / SP 800-53B **Moderate** baseline | 177 base controls (see below) |

### How the NIST count is 177

The NIST catalog is the base controls selected in the **SP 800-53B Moderate**
impact baseline, across the 18 baseline-applicable families. Control
**enhancements** (e.g. `AC-2(1)`) are not enumerated — coverage is measured at the
base-control level. The Program Management (PM) family is organization-wide and
not baseline-allocated; the Privacy (PT) family is selected via the separate
privacy baseline. That selection is 177 base controls.

## Versioning and traceability

- Each catalog carries a `version` field, and every report stamps the catalog
  `version` **and a SHA-256 of the catalog file** into its output (`tool` and
  `frameworks[].sha256` in JSON; the header line in Markdown/HTML).
- This lets an auditor tie any coverage result back to the exact denominator that
  produced it, and re-perform against it.
- Change the control set or a title and the SHA-256 changes; bump `version` on any
  substantive change.

## Authorship and review

- **Author:** the audit-labs maintainer.
- **Review status:** maintainer self-review. These catalogs have **not** been
  through independent professional review; treat them accordingly and validate
  against the source standards before relying on them in an engagement.
- **Effective date:** 2026-08.

## Copyright

- **SOC 2 / Trust Services Criteria** — copyright AICPA. Only identifiers are
  reproduced; titles are our own short-form paraphrases, not the criteria text.
- **ISO/IEC 27001:2022** — copyright ISO/IEC. Only Annex A identifiers and short
  titles are reproduced; normative text and guidance are not.
- **NIST SP 800-53** — U.S. Government work in the public domain.
