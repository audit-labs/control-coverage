"""Markdown renderer — the coverage matrix and blind-spot list, auditor-facing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import __version__
from ..coverage import (
    ASSERTED,
    FAILING,
    OUT_OF_SCOPE,
    STATE_ORDER,
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
_STATE_MARK = {
    SUPPORTED: "✓",
    FAILING: "✗",
    ASSERTED: "◐",
    UNADDRESSED: "○",
    OUT_OF_SCOPE: "—",
}


def _evidence_note(result) -> str:
    """A short 'checked by' cell: rule ids or the exclusion reason."""
    if result.state == OUT_OF_SCOPE:
        return f"_excluded: {result.exclusion_reason}_"
    if not result.observations:
        return ""
    rules = sorted({o.rule_id for o in result.observations if o.rule_id})
    return ", ".join(f"`{r}`" for r in rules)


def _framework_section(fc: FrameworkCoverage) -> list[str]:
    cat = fc.catalog
    counts = fc.counts
    out: list[str] = []
    out.append(f"## {cat.name}")
    out.append("")
    suffix = "" if cat.complete else " _(partial catalog — coverage is of the shipped subset)_"
    out.append(
        f"**Coverage {fc.coverage_pct}%** ({fc.addressed}/{fc.in_scope} in-scope "
        f"controls addressed) · **assured {fc.assured_pct}%** "
        f"({fc.supported} supported){suffix}"
    )
    out.append("")
    out.append(
        "| " + " · ".join(
            f"{_STATE_MARK[s]} {counts[s]} {_STATE_LABEL[s]}"
            for s in STATE_ORDER
            if counts[s]
        ) + " |"
    )
    out.append("|" + "---|")
    out.append("")
    out.append("| Control | Status | Description | Checked by |")
    out.append("| --- | --- | --- | --- |")
    for r in fc.results:
        mark = _STATE_MARK[r.state]
        label = _STATE_LABEL[r.state]
        out.append(
            f"| **{r.control.id}** | {mark} {label} | {r.control.title} | {_evidence_note(r)} |"
        )
    out.append("")
    return out


def _blind_spots(report: CoverageReport) -> list[str]:
    out: list[str] = ["## Blind spots", ""]
    total = sum(len(fc.blind_spots) for fc in report.frameworks)
    if total == 0:
        out.append("_No in-scope control is left unaddressed by the corpus._")
        out.append("")
        return out
    out.append(
        f"{total} in-scope control(s) are **unaddressed** — no finding in the corpus "
        "maps to them. These are the framework requirements the evidence does not "
        "look at yet."
    )
    out.append("")
    for fc in report.frameworks:
        spots = fc.blind_spots
        if not spots:
            continue
        out.append(f"### {fc.catalog.name} ({len(spots)})")
        out.append("")
        for r in spots:
            fam = f" · _{r.control.family}_" if r.control.family else ""
            out.append(f"- **{r.control.id}** — {r.control.title}{fam}")
        out.append("")
    return out


def render(report: CoverageReport) -> str:
    out: list[str] = []
    title = report.subject or "Evidence corpus"
    out.append(f"# Control Coverage — {title}")
    out.append("")
    out.append(f"- **Generated:** {report.generated_at}")
    out.append(f"- **Tool:** control-coverage {__version__}")
    out.append(f"- **Corpus:** {report.source_count} evidence source(s)")
    frameworks = ", ".join(
        f"{fc.catalog.framework} {fc.catalog.version} (`sha256:{fc.catalog.sha256[:12]}`)"
        for fc in report.frameworks
    )
    out.append(f"- **Frameworks:** {frameworks}")
    out.append("")
    out.append(
        "> Coverage measures how much of a framework the evidence corpus addresses — "
        "not whether the organization is compliant. An unaddressed control is a gap "
        "in *evidence*, which may reflect a real gap in *controls* or simply a signal "
        "not yet collected. The final judgment belongs to the organization and its auditor."
    )
    out.append("")

    # Headline table across frameworks.
    out.append("## Summary")
    out.append("")
    out.append("| Framework | In scope | Addressed | Supported | Failing | Blind spots | Coverage | Assured |")
    out.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for fc in report.frameworks:
        c = fc.counts
        out.append(
            f"| {fc.catalog.name} | {fc.in_scope} | {fc.addressed} | {fc.supported} "
            f"| {c[FAILING]} | {len(fc.blind_spots)} | {fc.coverage_pct}% | {fc.assured_pct}% |"
        )
    out.append("")

    out.extend(_blind_spots(report))

    for fc in report.frameworks:
        out.extend(_framework_section(fc))

    if report.orphan_codes:
        out.append("## Unmatched control codes")
        out.append("")
        out.append(
            "The corpus cites these control codes, but no loaded catalog defines them. "
            "They are typos, renamed controls, or controls outside the bundled catalogs:"
        )
        out.append("")
        for code in report.orphan_codes:
            out.append(f"- `{code}`")
        out.append("")

    return "\n".join(out).rstrip() + "\n"
