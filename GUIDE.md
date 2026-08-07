# Using control-coverage

A practical, task-oriented guide. For the conceptual overview see the
[README](README.md); this walks through actually running the tool.

## The one thing to understand first

Every other Audit Labs tool is **evidence-first**: it starts from what you collected
and tells you what it maps to. `control-coverage` is **control-first**: it starts
from the *complete* list of a framework's controls and tells you how much of it your
evidence addresses — and, more usefully, what it *doesn't*.

So the input is your evidence, and the output is measured against a fixed yardstick
(the framework catalog) you didn't have to write.

## 1. Get the input: audit-report JSON

The corpus is one or more JSON reports from `audit-report`. Produce them with its
`--format json` flag, one per platform:

```bash
audit-report ./output/aws_audit_prod_2026-02-01     --format json --out reports/
audit-report ./output/github_audit_prod_2026-02-01  --format json --out reports/
```

You now have `reports/*.json`. That directory *is* a corpus — coverage aggregates
every report in it into one per-framework picture, so AWS, GitHub, and GitLab
evidence all count toward the same SOC 2 number.

> No audit-report packages yet? Any JSON with the same shape works — a list of
> `findings`, each with `controls: ["SOC2:CC6.1", ...]` and a `status` of `pass`,
> `fail`, or `not_applicable`.

## 2. Install

```bash
git clone https://github.com/audit-labs/control-coverage
cd control-coverage
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## 3. The four things you'll actually do

### A. "How covered am I, and what am I missing?"

```bash
control-coverage reports/
```

Prints a Markdown report: a per-framework summary table, then the **blind spots**
(in-scope controls no finding touches), then the full matrix. Frameworks are inferred
from the codes your corpus cites.

Want just the gap list, nothing else?

```bash
control-coverage reports/ --framework SOC2 --blind-spots
```

Want files to hand off? Write all formats to a directory:

```bash
control-coverage reports/ --format md,html,json --out coverage-out/
```

- **md** — human-readable, good for a PR comment or a wiki paste.
- **html** — self-contained, printable, has coverage bars. Attach to a workpaper.
- **json** — for dashboards or further scripting.

### B. "Produce a Statement of Applicability"

First write a scope file. It selects frameworks and records exclusions — each with a
mandatory reason (an unjustified exclusion is rejected):

```yaml
# soa.yaml
subject: Acme Production
frameworks: [SOC2, ISO]
exclusions:
  - control: ISO:A.7.1
    reason: "Fully cloud-hosted; no physical premises are in scope for the ISMS."
  - control: ISO:A.5.7
    reason: "No formal threat-intelligence program; risk accepted by the CISO for 2026."
exclude_families:
  - {framework: SOC2, family: Privacy, reason: "Privacy category not in the SOC 2 audit scope."}
owners:
  SOC2:CC6.1: platform-team
```

`exclusions` drops one control; `exclude_families` drops a whole category, ISO theme,
or NIST family at once (how audit scope is really decided). Both require a reason.

Then generate coverage over the in-scope controls, plus the SoA itself:

```bash
control-coverage reports/ --scope soa.yaml --format md,soa --out coverage-out/
```

`coverage-out/soa.md` lists every control, whether it applies, its implementation
status (derived from your evidence, not asserted by hand), and the justification.
Excluded controls are recorded, not counted as gaps.

### C. "What changed since last time?"

Keep last month's reports around. Point `--baseline` at them:

```bash
control-coverage reports/2026-02/ --baseline reports/2026-01/ --framework SOC2
```

You get a movement report:

- **improved** — a control got more assurance (e.g. failing → supported).
- **regressed** — a control lost assurance (e.g. supported → failing).
- **gained** — a blind spot became addressed (coverage went up).
- **lost** — an addressed control became a blind spot (coverage went down).

`--baseline` accepts a single file or a directory.

### D. "Which evidence is doing the most work?"

```bash
control-coverage reports/ --framework SOC2,ISO,NIST --crosswalk
```

Two things come out:

- **Evidence leverage** — each check and the controls it supports, across all three
  frameworks. You'll see that one 2FA check earns SOC 2 CC6.1 + ISO A.5.17 + NIST IA-2.
- **Minimal evidence set** — the fewest checks that still cover every addressed
  control. This is your walkthrough/sampling short-list: pull these and you've touched
  everything the full corpus touches.

## 4. Reading the numbers

Every in-scope control is in exactly one state:

| State | What it means | Counts toward… |
| --- | --- | --- |
| **supported** | Something passes here, nothing fails | coverage **and** assured |
| **failing** | Something fails here (worst wins) | coverage |
| **asserted** | Mapped, but the data was absent | coverage |
| **unaddressed** | Nothing maps here — a blind spot | neither |
| **out of scope** | Excluded in the scope file, with a reason | neither (removed from the denominator) |

- **Coverage %** = supported + failing + asserted, over in-scope controls. *"How much
  of the framework am I even looking at?"*
- **Assured %** = supported only, over in-scope controls. *"How much do I have good
  evidence for?"*

A low coverage number on a fresh corpus is expected — the framework is large and your
automated checks touch a slice of it. The value is knowing *exactly which* slice, and
watching coverage climb (via `--baseline`) as you add evidence.

## 5. Wire it into CI

Two independent gates, both exit non-zero to fail a build:

```bash
# Fail if any framework's coverage drops below a floor
control-coverage reports/ --scope soa.yaml --fail-under 60

# Fail if anything regressed or lost coverage versus the last run
control-coverage reports/ --baseline last-run/ --fail-on-regression
```

See [`examples/github-actions-coverage.yml`](examples/github-actions-coverage.yml) for
a scheduled workflow that runs both and uploads the reports as artifacts.

## 6. Frameworks and codes

| Framework | Pass as | Catalog |
| --- | --- | --- |
| SOC 2 Trust Services Criteria | `SOC2` | All five categories, 61 controls |
| ISO/IEC 27001:2022 Annex A | `ISO` (or `iso27001`) | All 93 Annex A controls |
| NIST SP 800-53 Rev. 5 | `NIST` (or `800-53`) | Moderate baseline, 177 base controls |

Control codes are `FRAMEWORK:ID` — `SOC2:CC6.1`, `ISO:A.5.17`, `NIST:IA-2` — the same
codes `audit-report` rulesets already emit, so the two tools line up with no
translation. If your corpus cites a code whose framework is loaded but the catalog
doesn't define it (a typo or a renamed control), it's reported under **Unmatched
control codes** rather than silently dropped.

## Gotchas

- **`--crosswalk` and `--baseline` can't be combined** — they're different analyses.
- **Trend and crosswalk emit `md`, `html`, and `json`** (not `soa`). Coverage emits all four.
- **SOC 2 defaults to all five categories (61 controls).** Most reports scope only some.
  Drop the ones you're not audited on with `exclude_families` (see §2) so coverage
  reflects your real perimeter — e.g. exclude `Privacy` and `Processing Integrity`.
- **NIST coverage looks low** because the moderate baseline is large (177 controls) and
  most are organizational/physical/personnel controls no automated scanner evidences.
  That's the point — those are your blind spots. Use a scope file to exclude the ones
  handled by policy rather than tooling, so the number reflects your real perimeter.
- **An unaddressed control is a gap in *evidence*, not proof of a gap in *controls*.**
  It may just mean the signal isn't collected yet. The tool produces evidence, never a
  verdict.
