"""HTML renderer — a self-contained, printable coverage report.

No external assets: all CSS is inlined so the file can be attached to an audit
workpaper and opened anywhere, including offline.
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from .. import __version__
from ..coverage import (
    ASSERTED,
    FAILING,
    OUT_OF_SCOPE,
    SUPPORTED,
    UNADDRESSED,
)

if TYPE_CHECKING:
    from ..coverage import CoverageReport, FrameworkCoverage

_STATE_LABEL = {
    SUPPORTED: "supported",
    FAILING: "failing",
    ASSERTED: "asserted",
    UNADDRESSED: "unaddressed",
    OUT_OF_SCOPE: "out of scope",
}
_STATE_CLASS = {
    SUPPORTED: "supported",
    FAILING: "failing",
    ASSERTED: "asserted",
    UNADDRESSED: "unaddressed",
    OUT_OF_SCOPE: "oos",
}

CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  margin: 0; padding: 2rem; line-height: 1.5; color: #1a1a1a; background: #fff; }
main { max-width: 64rem; margin: 0 auto; }
h1 { margin: 0 0 .25rem; font-size: 1.6rem; }
h2 { margin: 2rem 0 .75rem; font-size: 1.25rem; border-bottom: 2px solid #e5e5e5; padding-bottom: .25rem; }
h3 { margin: 1.4rem 0 .5rem; font-size: 1.02rem; }
.meta { color: #555; font-size: .9rem; margin: 0 0 1rem; }
.meta code { background: #f2f2f2; padding: .05rem .3rem; border-radius: 3px; }
.note { background: #f7f7f9; border-left: 3px solid #b9b9c6; padding: .6rem .9rem;
  font-size: .9rem; color: #444; border-radius: 0 4px 4px 0; }
table { border-collapse: collapse; width: 100%; font-size: .85rem; margin: .5rem 0; }
th, td { border: 1px solid #e0e0e0; padding: .35rem .5rem; text-align: left; vertical-align: top; }
th { background: #f5f5f7; }
td.num, th.num { text-align: right; }
.badge { display: inline-block; font-weight: 700; font-size: .72rem; letter-spacing: .02em;
  padding: .12rem .5rem; border-radius: 999px; white-space: nowrap; }
.badge.supported { background: #e5f6ea; color: #1a7f37; }
.badge.failing { background: #fdeaea; color: #c1272d; }
.badge.asserted { background: #fff4e0; color: #a8620a; }
.badge.unaddressed { background: #eceaf6; color: #5b4bb0; }
.badge.oos { background: #eee; color: #666; }
.bar { display: flex; height: 1.1rem; border-radius: 4px; overflow: hidden; margin: .4rem 0 .2rem;
  border: 1px solid #ddd; }
.bar > span { display: block; }
.bar .supported { background: #35b866; }
.bar .failing { background: #e2565b; }
.bar .asserted { background: #eaa53c; }
.bar .unaddressed { background: #8877d8; }
.bar .oos { background: #cfcfcf; }
.headline { font-size: 1.5rem; font-weight: 700; }
.headline small { font-size: .85rem; font-weight: 500; color: #666; }
.legend { font-size: .78rem; color: #666; display: flex; flex-wrap: wrap; gap: .8rem; margin: .2rem 0 1rem; }
.legend i { display: inline-block; width: .8rem; height: .8rem; border-radius: 2px; vertical-align: -1px; margin-right: .25rem; }
footer { margin-top: 3rem; font-size: .8rem; color: #888; border-top: 1px solid #eee; padding-top: .75rem; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e6e6; background: #16171a; }
  h2 { border-color: #333; }
  .meta { color: #aaa; } .meta code { background: #26272b; }
  .note { background: #1e1f24; border-color: #444; color: #bbb; }
  th, td { border-color: #333; } th { background: #202126; }
  .headline small, .legend { color: #999; }
  .badge.supported { background: #12321d; color: #4ac36a; }
  .badge.failing { background: #3a1416; color: #ff6b70; }
  .badge.asserted { background: #33260f; color: #e6a94e; }
  .badge.unaddressed { background: #211d3a; color: #9d8ef0; }
  .badge.oos { background: #26272b; color: #999; }
  .bar { border-color: #333; }
  footer { border-color: #2a2b30; }
}
"""

_LEGEND_COLORS = {
    SUPPORTED: "#35b866",
    FAILING: "#e2565b",
    ASSERTED: "#eaa53c",
    UNADDRESSED: "#8877d8",
    OUT_OF_SCOPE: "#cfcfcf",
}


def _badge(state: str) -> str:
    return f'<span class="badge {_STATE_CLASS[state]}">{_STATE_LABEL[state]}</span>'


def _bar(fc: FrameworkCoverage) -> str:
    counts = fc.counts
    total = sum(counts.values()) or 1
    segments = []
    for state in [SUPPORTED, FAILING, ASSERTED, UNADDRESSED, OUT_OF_SCOPE]:
        n = counts[state]
        if not n:
            continue
        pct = 100 * n / total
        segments.append(
            f'<span class="{_STATE_CLASS[state]}" style="width:{pct:.2f}%" '
            f'title="{n} {_STATE_LABEL[state]}"></span>'
        )
    return '<div class="bar">' + "".join(segments) + "</div>"


def _legend() -> str:
    items = []
    for state in [SUPPORTED, FAILING, ASSERTED, UNADDRESSED, OUT_OF_SCOPE]:
        items.append(
            f'<span><i style="background:{_LEGEND_COLORS[state]}"></i>{_STATE_LABEL[state]}</span>'
        )
    return '<div class="legend">' + "".join(items) + "</div>"


def _checked_by(result) -> str:
    if result.state == OUT_OF_SCOPE:
        return f"<em>excluded: {escape(result.exclusion_reason)}</em>"
    rules = sorted({o.rule_id for o in result.observations if o.rule_id})
    return ", ".join(f"<code>{escape(r)}</code>" for r in rules)


def _framework_section(fc: FrameworkCoverage) -> str:
    cat = fc.catalog
    partial = "" if cat.complete else (
        ' <small>(partial catalog — coverage is of the shipped subset)</small>'
    )
    rows = []
    for r in fc.results:
        rows.append(
            "<tr>"
            f"<td><strong>{escape(r.control.id)}</strong></td>"
            f"<td>{_badge(r.state)}</td>"
            f"<td>{escape(r.control.title)}</td>"
            f"<td>{_checked_by(r)}</td>"
            "</tr>"
        )
    return (
        f"<h2>{escape(cat.name)}{partial}</h2>"
        f'<p class="headline">{fc.coverage_pct}% <small>coverage · {fc.addressed}/{fc.in_scope} '
        f"in-scope controls addressed · {fc.assured_pct}% assured</small></p>"
        f"{_bar(fc)}{_legend()}"
        "<table><thead><tr><th>Control</th><th>Status</th><th>Description</th>"
        "<th>Checked by</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _summary_table(report: CoverageReport) -> str:
    rows = []
    for fc in report.frameworks:
        c = fc.counts
        rows.append(
            "<tr>"
            f"<td>{escape(fc.catalog.name)}</td>"
            f'<td class="num">{fc.in_scope}</td>'
            f'<td class="num">{fc.addressed}</td>'
            f'<td class="num">{fc.supported}</td>'
            f'<td class="num">{c[FAILING]}</td>'
            f'<td class="num">{len(fc.blind_spots)}</td>'
            f'<td class="num">{fc.coverage_pct}%</td>'
            f'<td class="num">{fc.assured_pct}%</td>'
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Framework</th><th class='num'>In scope</th>"
        "<th class='num'>Addressed</th><th class='num'>Supported</th>"
        "<th class='num'>Failing</th><th class='num'>Blind spots</th>"
        "<th class='num'>Coverage</th><th class='num'>Assured</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _blind_spots(report: CoverageReport) -> str:
    total = sum(len(fc.blind_spots) for fc in report.frameworks)
    if total == 0:
        return "<h2>Blind spots</h2><p>No in-scope control is left unaddressed by the corpus.</p>"
    parts = [
        "<h2>Blind spots</h2>",
        (
            f"<p>{total} in-scope control(s) are <strong>unaddressed</strong> — no finding "
            "in the corpus maps to them.</p>"
        ),
    ]
    for fc in report.frameworks:
        spots = fc.blind_spots
        if not spots:
            continue
        parts.append(f"<h3>{escape(fc.catalog.name)} ({len(spots)})</h3><ul>")
        for r in spots:
            fam = f" <em>· {escape(r.control.family)}</em>" if r.control.family else ""
            parts.append(
                f"<li><strong>{escape(r.control.id)}</strong> — {escape(r.control.title)}{fam}</li>"
            )
        parts.append("</ul>")
    return "".join(parts)


def render(report: CoverageReport) -> str:
    title = report.subject or "Evidence corpus"
    frameworks = ", ".join(
        f"{fc.catalog.framework} {fc.catalog.version} "
        f"(sha256:{fc.catalog.sha256[:12]})"
        for fc in report.frameworks
    )
    body = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Control Coverage — {escape(title)}</title>",
        f"<style>{CSS}</style></head><body><main>",
        f"<h1>Control Coverage — {escape(title)}</h1>",
        (
            f'<p class="meta">Generated {escape(report.generated_at)} · '
            f"Tool control-coverage {escape(__version__)} · "
            f"{report.source_count} evidence source(s) · frameworks: {escape(frameworks)}</p>"
        ),
        (
            '<p class="note">Coverage measures how much of a framework the evidence corpus '
            "addresses — not whether the organization is compliant. An unaddressed control is "
            "a gap in <em>evidence</em>, which may reflect a real control gap or simply a signal "
            "not yet collected. The final judgment belongs to the organization and its auditor.</p>"
        ),
        "<h2>Summary</h2>",
        _summary_table(report),
        _blind_spots(report),
    ]
    for fc in report.frameworks:
        body.append(_framework_section(fc))

    if report.orphan_codes:
        codes = "".join(f"<li><code>{escape(c)}</code></li>" for c in report.orphan_codes)
        body.append(
            "<h2>Unmatched control codes</h2><p>The corpus cites these codes, but no loaded "
            f"catalog defines them (typos, renamed, or out-of-catalog):</p><ul>{codes}</ul>"
        )

    body.append(
        "<footer>Generated by control-coverage · Audit Labs. Evidence, not a verdict.</footer>"
    )
    body.append("</main></body></html>")
    return "".join(body)
