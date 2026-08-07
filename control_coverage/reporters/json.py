"""JSON renderer — the coverage result as a machine-readable document.

Stable key order so two runs diff cleanly. Suitable for dashboards, ticketing,
or gating a pipeline on the coverage percentage.
"""

from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING

from .. import __version__

if TYPE_CHECKING:
    from ..coverage import CoverageReport


def to_dict(report: CoverageReport) -> dict:
    return {
        "subject": report.subject,
        "generated_at": report.generated_at,
        "source_count": report.source_count,
        "tool": {"name": "control-coverage", "version": __version__},
        "frameworks": [
            {
                "framework": fc.catalog.framework,
                "name": fc.catalog.name,
                "version": fc.catalog.version,
                "sha256": fc.catalog.sha256,
                "catalog_coverage": fc.catalog.coverage,
                "in_scope": fc.in_scope,
                "addressed": fc.addressed,
                "supported": fc.supported,
                "coverage_pct": fc.coverage_pct,
                "assured_pct": fc.assured_pct,
                "counts": fc.counts,
                "controls": [
                    {
                        "id": r.control.id,
                        "code": r.control.code,
                        "title": r.control.title,
                        "family": r.control.family,
                        "state": r.state,
                        "owner": r.owner,
                        "exclusion_reason": r.exclusion_reason,
                        "checked_by": sorted({o.rule_id for o in r.observations if o.rule_id}),
                        "sources": sorted({o.source for o in r.observations}),
                    }
                    for r in fc.results
                ],
            }
            for fc in report.frameworks
        ],
        "orphan_codes": report.orphan_codes,
    }


def render(report: CoverageReport) -> str:
    return _json.dumps(to_dict(report), indent=2, sort_keys=False) + "\n"
