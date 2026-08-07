"""Coverage trend — how control coverage moved between two corpora.

`audit-report` diffs two evidence *packages*; this diffs two whole *corpora* at
the framework-coverage level. Evaluate an earlier corpus and a current one with
the same catalogs and scope, then compare each control's assurance state to see
what improved, what regressed, and how the coverage percentage moved.

States are ranked ``supported > failing > asserted > unaddressed`` — going from
"no data" to "failing data" still counts as more assurance, because you now have
evidence. Two transitions are called out specially because they move the coverage
numerator: **gained** (a blind spot became addressed) and **lost** (an addressed
control became a blind spot).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .coverage import (
    ASSERTED,
    FAILING,
    OUT_OF_SCOPE,
    SUPPORTED,
    UNADDRESSED,
    CoverageReport,
)

# Assurance rank; higher is more assured. out_of_scope is handled separately.
_RANK = {SUPPORTED: 3, FAILING: 2, ASSERTED: 1, UNADDRESSED: 0}
_ADDRESSED = {SUPPORTED, FAILING, ASSERTED}

REGRESSED = "regressed"
IMPROVED = "improved"
GAINED = "gained"
LOST = "lost"
RESCOPED = "rescoped"
UNCHANGED = "unchanged"

# Order categories appear in a report (most urgent first).
CATEGORY_ORDER = [REGRESSED, LOST, GAINED, IMPROVED, RESCOPED, UNCHANGED]
# Categories that count as a regression for the CI gate.
_REGRESSION = {REGRESSED, LOST}


def _categorize(old: str, new: str) -> str:
    if old == new:
        return UNCHANGED
    if OUT_OF_SCOPE in (old, new):
        return RESCOPED
    if old == UNADDRESSED and new in _ADDRESSED:
        return GAINED
    if old in _ADDRESSED and new == UNADDRESSED:
        return LOST
    return IMPROVED if _RANK[new] > _RANK[old] else REGRESSED


@dataclass
class ControlDelta:
    """How one control's assurance state changed between the two corpora."""

    framework: str
    id: str
    title: str
    old_state: str
    new_state: str
    category: str


@dataclass
class FrameworkTrend:
    """Coverage movement for one framework."""

    framework: str
    name: str
    deltas: list[ControlDelta]
    old_coverage_pct: float
    new_coverage_pct: float

    def by_category(self, category: str) -> list[ControlDelta]:
        return [d for d in self.deltas if d.category == category]

    @property
    def counts(self) -> dict[str, int]:
        counts = {c: 0 for c in CATEGORY_ORDER}
        for d in self.deltas:
            counts[d.category] += 1
        return counts

    @property
    def coverage_delta(self) -> float:
        return round(self.new_coverage_pct - self.old_coverage_pct, 1)

    @property
    def regressions(self) -> int:
        return sum(1 for d in self.deltas if d.category in _REGRESSION)


@dataclass
class TrendReport:
    subject: str
    generated_at: str
    frameworks: list[FrameworkTrend] = field(default_factory=list)

    @property
    def total_regressions(self) -> int:
        return sum(fc.regressions for fc in self.frameworks)


def compare(baseline: CoverageReport, current: CoverageReport) -> TrendReport:
    """Diff two coverage reports evaluated with the same catalogs and scope."""
    old_by_fw = {fc.catalog.framework: fc for fc in baseline.frameworks}

    frameworks: list[FrameworkTrend] = []
    for cur in current.frameworks:
        base = old_by_fw.get(cur.catalog.framework)
        if base is None:
            continue  # framework only appears in the current run
        old_state = {r.control.id: r.state for r in base.results}
        deltas: list[ControlDelta] = []
        for r in cur.results:
            prev = old_state.get(r.control.id, UNADDRESSED)
            deltas.append(
                ControlDelta(
                    framework=cur.catalog.framework,
                    id=r.control.id,
                    title=r.control.title,
                    old_state=prev,
                    new_state=r.state,
                    category=_categorize(prev, r.state),
                )
            )
        frameworks.append(
            FrameworkTrend(
                framework=cur.catalog.framework,
                name=cur.catalog.name,
                deltas=deltas,
                old_coverage_pct=base.coverage_pct,
                new_coverage_pct=cur.coverage_pct,
            )
        )

    return TrendReport(
        subject=current.subject,
        generated_at=current.generated_at,
        frameworks=frameworks,
    )


# --- renderers -------------------------------------------------------------

_ARROW = {
    REGRESSED: "▼",
    LOST: "▼",
    GAINED: "▲",
    IMPROVED: "▲",
    RESCOPED: "◆",
    UNCHANGED: "·",
}


def to_dict(report: TrendReport) -> dict:
    return {
        "subject": report.subject,
        "generated_at": report.generated_at,
        "total_regressions": report.total_regressions,
        "frameworks": [
            {
                "framework": fc.framework,
                "name": fc.name,
                "old_coverage_pct": fc.old_coverage_pct,
                "new_coverage_pct": fc.new_coverage_pct,
                "coverage_delta": fc.coverage_delta,
                "counts": fc.counts,
                "changes": [
                    {
                        "id": d.id,
                        "title": d.title,
                        "old_state": d.old_state,
                        "new_state": d.new_state,
                        "category": d.category,
                    }
                    for d in fc.deltas
                    if d.category != UNCHANGED
                ],
            }
            for fc in report.frameworks
        ],
    }


def render_json(report: TrendReport) -> str:
    import json

    return json.dumps(to_dict(report), indent=2, sort_keys=False) + "\n"


def render_markdown(report: TrendReport) -> str:
    out: list[str] = []
    out.append(f"# Coverage Trend — {report.subject or 'Evidence corpus'}")
    out.append("")
    out.append(f"- **Generated:** {report.generated_at}")
    out.append(f"- **Regressions:** {report.total_regressions}")
    out.append("")

    out.append("| Framework | Coverage (was → now) | Δ | Regressed | Lost | Gained | Improved |")
    out.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for fc in report.frameworks:
        c = fc.counts
        sign = "+" if fc.coverage_delta >= 0 else ""
        out.append(
            f"| {fc.name} | {fc.old_coverage_pct}% → {fc.new_coverage_pct}% "
            f"| {sign}{fc.coverage_delta} | {c[REGRESSED]} | {c[LOST]} | {c[GAINED]} | {c[IMPROVED]} |"
        )
    out.append("")

    for fc in report.frameworks:
        changes = [d for d in fc.deltas if d.category != UNCHANGED]
        if not changes:
            continue
        out.append(f"## {fc.name}")
        out.append("")
        out.append("| Control | Change | Was → Now | Description |")
        out.append("| --- | --- | --- | --- |")
        ordered = sorted(changes, key=lambda d: CATEGORY_ORDER.index(d.category))
        for d in ordered:
            arrow = _ARROW[d.category]
            out.append(
                f"| **{d.id}** | {arrow} {d.category} | {d.old_state} → {d.new_state} | {d.title} |"
            )
        out.append("")

    if all(all(x.category == UNCHANGED for x in fc.deltas) for fc in report.frameworks):
        out.append("_No control changed state between the two corpora._")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# Category badge colours, layered onto the shared coverage CSS.
_TREND_CSS = """
.badge.improved { background: #e5f6ea; color: #1a7f37; }
.badge.gained { background: #e3eefb; color: #1667a8; }
.badge.regressed { background: #fdeaea; color: #c1272d; }
.badge.lost { background: #fbe7d8; color: #a8480a; }
.badge.rescoped { background: #eee; color: #666; }
.delta-up { color: #1a7f37; font-weight: 700; }
.delta-down { color: #c1272d; font-weight: 700; }
@media (prefers-color-scheme: dark) {
  .badge.improved { background: #12321d; color: #4ac36a; }
  .badge.gained { background: #12263a; color: #5aa6e6; }
  .badge.regressed { background: #3a1416; color: #ff6b70; }
  .badge.lost { background: #33220f; color: #e0913c; }
  .badge.rescoped { background: #26272b; color: #999; }
}
"""


def render_html(report: TrendReport) -> str:
    from html import escape

    from .reporters.html import CSS

    def badge(category: str) -> str:
        return f'<span class="badge {category}">{_ARROW[category]} {category}</span>'

    def delta(value: float) -> str:
        cls = "delta-up" if value >= 0 else "delta-down"
        sign = "+" if value >= 0 else ""
        return f'<span class="{cls}">{sign}{value}</span>'

    title = report.subject or "Evidence corpus"
    body = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Coverage Trend — {escape(title)}</title>",
        f"<style>{CSS}{_TREND_CSS}</style></head><body><main>",
        f"<h1>Coverage Trend — {escape(title)}</h1>",
        (
            f'<p class="meta">Generated {escape(report.generated_at)} · '
            f"{report.total_regressions} regression(s)</p>"
        ),
        "<h2>Summary</h2>",
        (
            "<table><thead><tr><th>Framework</th><th>Coverage (was → now)</th>"
            "<th class='num'>Δ</th><th class='num'>Regressed</th><th class='num'>Lost</th>"
            "<th class='num'>Gained</th><th class='num'>Improved</th></tr></thead><tbody>"
        ),
    ]
    for fc in report.frameworks:
        c = fc.counts
        body.append(
            "<tr>"
            f"<td>{escape(fc.name)}</td>"
            f"<td>{fc.old_coverage_pct}% → {fc.new_coverage_pct}%</td>"
            f'<td class="num">{delta(fc.coverage_delta)}</td>'
            f'<td class="num">{c[REGRESSED]}</td><td class="num">{c[LOST]}</td>'
            f'<td class="num">{c[GAINED]}</td><td class="num">{c[IMPROVED]}</td>'
            "</tr>"
        )
    body.append("</tbody></table>")

    for fc in report.frameworks:
        changes = sorted(
            (d for d in fc.deltas if d.category != UNCHANGED),
            key=lambda d: CATEGORY_ORDER.index(d.category),
        )
        if not changes:
            continue
        body.append(f"<h2>{escape(fc.name)}</h2>")
        body.append(
            "<table><thead><tr><th>Control</th><th>Change</th><th>Was → Now</th>"
            "<th>Description</th></tr></thead><tbody>"
        )
        for d in changes:
            body.append(
                "<tr>"
                f"<td><strong>{escape(d.id)}</strong></td>"
                f"<td>{badge(d.category)}</td>"
                f"<td>{d.old_state} → {d.new_state}</td>"
                f"<td>{escape(d.title)}</td>"
                "</tr>"
            )
        body.append("</tbody></table>")

    if not any(any(x.category != UNCHANGED for x in fc.deltas) for fc in report.frameworks):
        body.append("<p>No control changed state between the two corpora.</p>")

    body.append(
        "<footer>Generated by control-coverage · Audit Labs. Evidence, not a verdict.</footer>"
    )
    body.append("</main></body></html>")
    return "".join(body)
