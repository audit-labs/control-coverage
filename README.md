# control-coverage

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()

Control-first coverage and blind-spot analysis over an evidence corpus.

The rest of the Audit Labs toolchain is **evidence-first**: [audit-tools](https://github.com/audit-labs/audit-tools)
collects raw signals, [audit-report](https://github.com/audit-labs/audit-report)
maps each finding onto the controls it touches, and [evidence-seal](https://github.com/audit-labs/evidence-seal)
proves the package is authentic. That answers *"what did I collect, and what does it
map to?"* — but it can never tell you what you are **not** looking at, because it has
no list of everything a framework requires.

`control-coverage` supplies that missing list — the **denominator**. It starts from
the *complete* catalog of a framework's controls and scores your evidence against it,
so it can report two numbers nothing else in the pipeline can:

- **Coverage %** — of everything the framework requires, how much the evidence corpus
  addresses at all.
- **Blind spots** — the in-scope controls that *no* finding touches. These are the
  gaps an auditor finds for you if you don't find them first.

It also produces a **Statement of Applicability** — the ISO 27001 artifact that lists
every Annex A control, whether it applies, and why — derived from your evidence
instead of hand-maintained.

> Like every Audit Labs tool, this produces *evidence*, not a verdict. An unaddressed
> control is a gap in *evidence*, which may reflect a real gap in *controls* or simply
> a signal not yet collected. The final judgment belongs to the organization and its
> auditor.

## Install

```bash
git clone https://github.com/audit-labs/control-coverage
cd control-coverage
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Pure standard library plus PyYAML — no other dependencies.

## Usage

The input is one or more JSON reports from `audit-report` (its `--format json`
output). A corpus is typically one report per platform and date — AWS, GitHub,
GitLab — which `control-coverage` folds into a single per-framework picture.

```bash
# Coverage across every framework the corpus cites, Markdown to stdout
control-coverage aws.json github.json

# Just the blind spots — the controls nothing evidences yet
control-coverage aws.json github.json --framework SOC2 --blind-spots

# A whole directory of reports, all formats into ./out/
control-coverage ./reports/ --format md,html,json,soa --out out/

# Gate CI: exit non-zero if any framework's coverage is under 60%
control-coverage ./reports/ --fail-under 60
```

### Trend — how coverage moved

Point `--baseline` at an earlier corpus (a file or a directory) to see what changed:
controls that improved, regressed, and — the two that move the coverage number —
were *gained* (a blind spot became addressed) or *lost* (an addressed control became
a blind spot).

```bash
control-coverage ./reports/2026-02/ --baseline ./reports/2026-01/ --framework SOC2

# Gate CI: fail the build if any control regressed or lost coverage
control-coverage ./reports/2026-02/ --baseline ./reports/2026-01/ --fail-on-regression
```

Trend mode outputs Markdown, HTML, or JSON (`--format md,html,json`).

### Crosswalk — evidence leverage and the minimal set

One check is rarely worth one control: enforced 2FA is evidence for SOC 2 CC6.1,
ISO A.5.17, and NIST IA-2 at once. `--crosswalk` shows that leverage per check and
computes the **minimal evidence set** — the fewest checks that still touch every
addressed control, which is what you want when scoping a walkthrough or a sample.

```bash
control-coverage ./reports/ --framework SOC2,ISO,NIST --crosswalk
```

Crosswalk mode outputs Markdown, HTML, or JSON (`--format md,html,json`).

### Scope and the Statement of Applicability

Not every control applies to every organization. A **scope file** records which
controls are excluded and — required, never optional — *why*:

```yaml
# soa.yaml
subject: Acme Production
frameworks: [SOC2, ISO]
exclusions:
  - control: ISO:A.7.1
    reason: "Fully cloud-hosted; no physical premises are in scope for the ISMS."
  - control: ISO:A.5.7
    reason: "No formal threat-intelligence program; risk accepted by the CISO for 2026."
owners:
  SOC2:CC6.1: platform-team
```

```bash
# Coverage over in-scope controls, plus a ready-to-file SoA
control-coverage ./reports/ --scope soa.yaml --format md,soa --out out/
```

Excluded controls are recorded with their justification rather than counted as gaps.
An exclusion with no reason is rejected — an unjustified exclusion is the single most
common SoA audit finding.

## Assurance states

Every in-scope control lands in exactly one state:

| State | Meaning |
| --- | --- |
| **supported** | At least one mapped finding passes, and none fail. |
| **failing** | At least one mapped finding fails. The worst observation wins. |
| **asserted** | Findings map here, but their data was absent — evidence attempted, not obtained. |
| **unaddressed** | No finding maps here at all. **The blind spot.** |
| **out of scope** | Excluded by the scope file, with a recorded justification. |

`coverage %` is the share of in-scope controls in any of the first three states;
`assured %` is the share that are `supported`.

## Bundled catalogs

| Framework | Code | Catalog |
| --- | --- | --- |
| SOC 2 (Trust Services Criteria) | `SOC2` | Complete — all five categories (Common Criteria + Availability, Confidentiality, Processing Integrity, Privacy), 61 controls |
| ISO/IEC 27001:2022 Annex A | `ISO` | Complete — all 93 controls |
| NIST SP 800-53 Rev. 5 | `NIST` | Moderate baseline — 177 base controls across 18 families |

Most SOC 2 reports scope only some categories (Security is near-universal; Privacy and
Processing Integrity often are not). Use `exclude_families` in the scope file to drop a
whole category — or an ISO theme, or a NIST family — from the denominator in one line:

```yaml
exclude_families:
  - {framework: SOC2, family: Privacy, reason: "Privacy category not in the SOC 2 audit scope."}
  - {framework: SOC2, family: Processing Integrity, reason: "PI category not in the SOC 2 audit scope."}
```

Control codes are written `FRAMEWORK:ID` (`SOC2:CC6.1`, `ISO:A.5.17`), matching the
codes `audit-report` rulesets already cite. A partial catalog is reported honestly as
coverage of the shipped subset, never as the whole standard.

If the corpus cites a code whose framework is loaded but the catalog does not define
it — a typo or a renamed control — it is surfaced as an **unmatched control code**
rather than silently ignored.

## How it fits the pipeline

```
audit-tools ──► CSV package ──► evidence-seal (seal + verify)
                     │
                     ▼
               audit-report ──► per-package report (--format json)
                                        │
                                        ▼  one or more reports = a corpus
                               control-coverage ──► coverage %, blind spots, SoA,
                                                    trend over time, evidence crosswalk
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
