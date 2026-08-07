"""Crosswalk — which controls each piece of evidence supports, across frameworks.

One check is rarely worth one control. Enforced 2FA is evidence for SOC 2 CC6.1,
ISO A.5.17, and NIST IA-2 at once. This module inverts the coverage result to show
that leverage: for every check (rule) in the corpus, the set of controls it
addresses and the frameworks it spans.

It then answers a practical question auditors and evidence-owners both ask — *what
is the smallest set of checks that still covers everything?* — with a greedy
set-cover over the addressed controls. The result is an ordered "minimal evidence
set": collect these few checks and you have touched every control the full corpus
touches, which is what you want when scoping a walkthrough or a sample.

"Addressed" here matches the coverage engine: a control any finding maps to,
whatever the finding's outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .coverage import CoverageReport


@dataclass
class EvidenceItem:
    """One check and the controls it supports across frameworks."""

    rule_id: str
    title: str
    controls: list[str]  # full FRAMEWORK:ID codes, sorted
    frameworks: list[str]  # framework short codes it spans, sorted

    @property
    def count(self) -> int:
        return len(self.controls)


@dataclass
class CoverStep:
    """One pick in the greedy minimal-evidence set."""

    rule_id: str
    new_controls: int  # controls this pick added that were not yet covered
    cumulative: int
    cumulative_pct: float


@dataclass
class Crosswalk:
    subject: str
    generated_at: str
    items: list[EvidenceItem] = field(default_factory=list)
    cover: list[CoverStep] = field(default_factory=list)
    universe_size: int = 0

    @property
    def multi_framework(self) -> list[EvidenceItem]:
        """Checks that earn coverage in more than one framework at once."""
        return [i for i in self.items if len(i.frameworks) > 1]


def build(report: CoverageReport) -> Crosswalk:
    """Invert a coverage report into a crosswalk and a minimal evidence set."""
    rule_controls: dict[str, set[str]] = {}
    rule_title: dict[str, str] = {}
    rule_frameworks: dict[str, set[str]] = {}
    universe: set[str] = set()

    for fc in report.frameworks:
        for r in fc.results:
            if not r.addressed:
                continue
            code = r.control.code
            universe.add(code)
            for obs in r.observations:
                if not obs.rule_id:
                    continue
                rule_controls.setdefault(obs.rule_id, set()).add(code)
                rule_title.setdefault(obs.rule_id, obs.title)
                rule_frameworks.setdefault(obs.rule_id, set()).add(fc.catalog.framework)

    items = [
        EvidenceItem(
            rule_id=rid,
            title=rule_title.get(rid, ""),
            controls=sorted(codes),
            frameworks=sorted(rule_frameworks.get(rid, set())),
        )
        for rid, codes in rule_controls.items()
    ]
    # Most leverage first; rule id breaks ties for stable output.
    items.sort(key=lambda i: (-i.count, i.rule_id))

    cover = _greedy_cover(rule_controls, universe)
    return Crosswalk(
        subject=report.subject,
        generated_at=report.generated_at,
        items=items,
        cover=cover,
        universe_size=len(universe),
    )


def _greedy_cover(rule_controls: dict[str, set[str]], universe: set[str]) -> list[CoverStep]:
    remaining = set(universe)
    pool = {rid: set(codes) for rid, codes in rule_controls.items()}
    total = len(universe) or 1
    steps: list[CoverStep] = []

    while remaining:
        best_rule, best_gain = None, 0
        for rid in sorted(pool):
            gain = len(pool[rid] & remaining)
            if gain > best_gain:
                best_rule, best_gain = rid, gain
        if not best_rule:  # nothing left can cover the remainder
            break
        remaining -= pool[best_rule]
        del pool[best_rule]
        cumulative = len(universe) - len(remaining)
        steps.append(
            CoverStep(
                rule_id=best_rule,
                new_controls=best_gain,
                cumulative=cumulative,
                cumulative_pct=round(100 * cumulative / total, 1),
            )
        )
    return steps


# --- renderers -------------------------------------------------------------


def to_dict(xw: Crosswalk) -> dict:
    return {
        "subject": xw.subject,
        "generated_at": xw.generated_at,
        "universe_size": xw.universe_size,
        "minimal_evidence_set": [
            {
                "rule_id": s.rule_id,
                "new_controls": s.new_controls,
                "cumulative": s.cumulative,
                "cumulative_pct": s.cumulative_pct,
            }
            for s in xw.cover
        ],
        "evidence": [
            {
                "rule_id": i.rule_id,
                "title": i.title,
                "frameworks": i.frameworks,
                "controls": i.controls,
                "count": i.count,
            }
            for i in xw.items
        ],
    }


def render_json(xw: Crosswalk) -> str:
    import json

    return json.dumps(to_dict(xw), indent=2, sort_keys=False) + "\n"


def render_markdown(xw: Crosswalk) -> str:
    out: list[str] = []
    out.append(f"# Evidence Crosswalk — {xw.subject or 'Evidence corpus'}")
    out.append("")
    out.append(f"- **Generated:** {xw.generated_at}")
    out.append(f"- **Addressed controls:** {xw.universe_size}")
    out.append(f"- **Checks in corpus:** {len(xw.items)}")
    out.append(f"- **Checks spanning multiple frameworks:** {len(xw.multi_framework)}")
    out.append("")

    out.append("## Minimal evidence set")
    out.append("")
    if xw.cover:
        out.append(
            f"The {len(xw.cover)} check(s) below cover all {xw.universe_size} addressed "
            "controls — the smallest set that touches everything the full corpus does."
        )
        out.append("")
        out.append("| # | Check | New controls | Cumulative | % of addressed |")
        out.append("| ---: | --- | ---: | ---: | ---: |")
        for n, s in enumerate(xw.cover, 1):
            out.append(
                f"| {n} | `{s.rule_id}` | +{s.new_controls} | {s.cumulative} | {s.cumulative_pct}% |"
            )
    else:
        out.append("_No addressed controls to cover._")
    out.append("")

    out.append("## Evidence leverage")
    out.append("")
    out.append("Each check and the controls it supports, most leverage first.")
    out.append("")
    out.append("| Check | Frameworks | # | Controls |")
    out.append("| --- | --- | ---: | --- |")
    for i in xw.items:
        codes = ", ".join(f"`{c}`" for c in i.controls)
        fws = ", ".join(i.frameworks)
        out.append(f"| `{i.rule_id}` | {fws} | {i.count} | {codes} |")
    out.append("")

    return "\n".join(out).rstrip() + "\n"


_XW_CSS = """
.fw { display: inline-block; font-size: .7rem; font-weight: 700; letter-spacing: .02em;
  padding: .08rem .4rem; border-radius: 4px; margin-right: .25rem; background: #eef; color: #33488c; }
.track { position: relative; background: #eee; border-radius: 4px; height: 1rem; min-width: 5rem; }
.track > span { position: absolute; left: 0; top: 0; bottom: 0; background: #35b866; border-radius: 4px; }
.codes code { font-size: .78rem; }
@media (prefers-color-scheme: dark) {
  .fw { background: #22243a; color: #9fb0f0; }
  .track { background: #26272b; }
}
"""


def render_html(xw: Crosswalk) -> str:
    from html import escape

    from .reporters.html import CSS

    title = xw.subject or "Evidence corpus"
    body = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Evidence Crosswalk — {escape(title)}</title>",
        f"<style>{CSS}{_XW_CSS}</style></head><body><main>",
        f"<h1>Evidence Crosswalk — {escape(title)}</h1>",
        (
            f'<p class="meta">Generated {escape(xw.generated_at)} · '
            f"{xw.universe_size} addressed control(s) · {len(xw.items)} check(s) · "
            f"{len(xw.multi_framework)} spanning multiple frameworks</p>"
        ),
        "<h2>Minimal evidence set</h2>",
    ]
    if xw.cover:
        body.append(
            f"<p>The {len(xw.cover)} check(s) below cover all {xw.universe_size} addressed "
            "controls — the smallest set that touches everything the full corpus does.</p>"
        )
        body.append(
            "<table><thead><tr><th class='num'>#</th><th>Check</th>"
            "<th class='num'>New</th><th class='num'>Cumulative</th>"
            "<th>% of addressed</th></tr></thead><tbody>"
        )
        for n, s in enumerate(xw.cover, 1):
            body.append(
                "<tr>"
                f'<td class="num">{n}</td>'
                f"<td><code>{escape(s.rule_id)}</code></td>"
                f'<td class="num">+{s.new_controls}</td>'
                f'<td class="num">{s.cumulative}</td>'
                f'<td><div class="track" title="{s.cumulative_pct}%">'
                f'<span style="width:{s.cumulative_pct:.1f}%"></span></div> {s.cumulative_pct}%</td>'
                "</tr>"
            )
        body.append("</tbody></table>")
    else:
        body.append("<p>No addressed controls to cover.</p>")

    body.append("<h2>Evidence leverage</h2>")
    body.append("<p>Each check and the controls it supports, most leverage first.</p>")
    body.append(
        "<table><thead><tr><th>Check</th><th>Frameworks</th><th class='num'>#</th>"
        "<th>Controls</th></tr></thead><tbody>"
    )
    for i in xw.items:
        fws = "".join(f'<span class="fw">{escape(f)}</span>' for f in i.frameworks)
        codes = ", ".join(f"<code>{escape(c)}</code>" for c in i.controls)
        body.append(
            "<tr>"
            f"<td><code>{escape(i.rule_id)}</code></td>"
            f"<td>{fws}</td>"
            f'<td class="num">{i.count}</td>'
            f'<td class="codes">{codes}</td>'
            "</tr>"
        )
    body.append("</tbody></table>")
    body.append(
        "<footer>Generated by control-coverage · Audit Labs. Evidence, not a verdict.</footer>"
    )
    body.append("</main></body></html>")
    return "".join(body)
