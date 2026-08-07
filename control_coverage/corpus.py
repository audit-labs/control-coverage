"""Load an evidence corpus from audit-report JSON reports.

audit-report emits one JSON document per evidence package. Each finding carries
the controls it maps to and a status::

    {"findings": [
        {"id": "github.org.require-2fa", "status": "pass", "severity": "high",
         "controls": ["SOC2:CC6.1", "ISO:A.5.17", "NIST:IA-2"], ...},
        ...
    ]}

A **corpus** is any number of these reports — typically one per platform and date
(AWS, GitHub, GitLab…) — flattened into a list of :class:`Observation`, one per
(finding, control) pair. Coverage is then computed by joining observations onto a
framework catalog.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Statuses as emitted by audit-report's engine.
PASS = "pass"
FAIL = "fail"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class Observation:
    """One finding's bearing on one control, with provenance."""

    control: str  # "FRAMEWORK:ID"
    status: str  # pass | fail | not_applicable
    rule_id: str
    title: str
    severity: str
    source: str  # report file / package name the finding came from


def _iter_report(doc: dict, source: str):
    for f in doc.get("findings", []):
        status = f.get("status", NOT_APPLICABLE)
        rule_id = f.get("id", "")
        title = f.get("title", "")
        severity = f.get("severity", "medium")
        for control in f.get("controls", []):
            yield Observation(
                control=control,
                status=status,
                rule_id=rule_id,
                title=title,
                severity=severity,
                source=source,
            )


def load_report(path: str | Path) -> list[Observation]:
    """Load observations from a single audit-report JSON file."""
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    # Prefer the package name audit-report records; fall back to the file name.
    source = doc.get("source_package") or p.name
    return list(_iter_report(doc, source))


def _expand(paths: list[str | Path]) -> list[Path]:
    """Resolve inputs: JSON files pass through; directories contribute their *.json."""
    resolved: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            resolved.extend(sorted(p.glob("*.json")))
        else:
            resolved.append(p)
    return resolved


def load_corpus(paths: list[str | Path]) -> list[Observation]:
    """Load and flatten observations from files and/or directories of reports."""
    files = _expand(paths)
    if not files:
        raise ValueError("no audit-report JSON files found in the given paths")
    observations: list[Observation] = []
    for f in files:
        observations.extend(load_report(f))
    return observations
