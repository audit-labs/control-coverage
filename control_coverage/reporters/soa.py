"""Statement of Applicability renderer.

ISO 27001 requires a Statement of Applicability (SoA): for every Annex A control,
whether it applies, why, and its implementation status. This renders exactly that
from the coverage result — applicability comes from the scope file, and the
implementation status is derived from the evidence corpus rather than asserted by
hand, so the SoA stays honest to what the evidence actually shows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..coverage import ASSERTED, FAILING, OUT_OF_SCOPE, SUPPORTED, UNADDRESSED

if TYPE_CHECKING:
    from ..coverage import CoverageReport

# How each assurance state reads as an implementation status in an SoA.
_IMPL_STATUS = {
    SUPPORTED: "Implemented — supporting evidence collected",
    FAILING: "Deficient — evidence shows a non-supporting state",
    ASSERTED: "Claimed — mapped, but evidence not yet obtained",
    UNADDRESSED: "Not evidenced — no evidence collected yet",
    OUT_OF_SCOPE: "Excluded",
}


def _justification(result) -> str:
    if result.state == OUT_OF_SCOPE:
        return result.exclusion_reason
    rules = sorted({o.rule_id for o in result.observations if o.rule_id})
    sources = sorted({o.source for o in result.observations})
    if rules:
        return f"Evidenced by {', '.join(rules)} in {', '.join(sources)}."
    return "No control in the evidence corpus addresses this yet."


def render(report: CoverageReport) -> str:
    out: list[str] = []
    subject = report.subject or "the organization"
    out.append(f"# Statement of Applicability — {report.subject or 'Untitled'}")
    out.append("")
    out.append(f"- **Generated:** {report.generated_at}")
    out.append(f"- **Derived from:** {report.source_count} evidence source(s)")
    out.append("")
    out.append(
        f"This Statement of Applicability records, for each control in scope for "
        f"{subject}, whether it applies and its implementation status. Applicability "
        "decisions come from the documented scope; implementation status is derived "
        "from collected evidence, not asserted."
    )
    out.append("")

    for fc in report.frameworks:
        out.append(f"## {fc.catalog.name}")
        out.append("")
        out.append("| Control | Description | Applicable | Status | Justification | Owner |")
        out.append("| --- | --- | --- | --- | --- | --- |")
        for r in fc.results:
            applicable = "No" if r.state == OUT_OF_SCOPE else "Yes"
            out.append(
                f"| **{r.control.id}** | {r.control.title} | {applicable} "
                f"| {_IMPL_STATUS[r.state]} | {_justification(r)} | {r.owner} |"
            )
        out.append("")

    return "\n".join(out).rstrip() + "\n"
