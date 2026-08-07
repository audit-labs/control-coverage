"""Scope — which controls are in play, and which are excluded with justification.

Not every control applies to every organization. ISO 27001 formalizes this as the
**Statement of Applicability (SoA)**: for each Annex A control, a decision to apply
it or not, and the reason. This module reads a small YAML scope file expressing
exactly that, so coverage is computed over *in-scope* controls and exclusions are
recorded rather than silently counted as gaps::

    subject: Acme Production
    frameworks: [SOC2, ISO]
    exclusions:
      - {control: ISO:A.5.7, reason: "No formal threat-intel program; risk accepted 2026-Q1."}
      - {control: ISO:A.7.1, reason: "Fully cloud-hosted; no physical premises in scope."}
    exclude_families:
      - {framework: SOC2, family: Privacy, reason: "Privacy category not in the SOC 2 audit scope."}
    owners:
      SOC2:CC6.1: platform-team

``exclude_families`` removes a whole category at once — a SOC 2 Trust Services
category, an ISO Annex A theme, a NIST family — which is how audit scope is actually
decided (a SOC 2 report covers Security and maybe Availability, rarely Privacy).

Every exclusion, per-control or per-family, must carry a reason — an exclusion without
justification is the single most common SoA audit finding, so we reject it rather than
accept it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Scope:
    """A parsed scope / Statement of Applicability."""

    subject: str = ""
    frameworks: list[str] = field(default_factory=list)
    # control code -> justification for excluding it
    exclusions: dict[str, str] = field(default_factory=dict)
    # (framework, family) -> justification for excluding a whole family/category
    family_exclusions: dict[tuple[str, str], str] = field(default_factory=dict)
    # control code -> owning team/person (optional metadata)
    owners: dict[str, str] = field(default_factory=dict)

    def excluded(self, code: str) -> bool:
        return code in self.exclusions

    def reason(self, code: str) -> str:
        return self.exclusions.get(code, "")

    def family_excluded(self, framework: str, family: str) -> bool:
        return (framework, family) in self.family_exclusions

    def family_reason(self, framework: str, family: str) -> str:
        return self.family_exclusions.get((framework, family), "")

    def owner(self, code: str) -> str:
        return self.owners.get(code, "")


def empty() -> Scope:
    """A scope that excludes nothing — every catalog control is in scope."""
    return Scope()


def load(path: str | Path) -> Scope:
    """Load a scope file, validating that every exclusion carries a reason."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    exclusions: dict[str, str] = {}
    for i, item in enumerate(raw.get("exclusions", [])):
        if not isinstance(item, dict) or "control" not in item:
            raise ValueError(f"exclusion #{i + 1} must be a mapping with a 'control' key")
        code = str(item["control"]).strip()
        reason = str(item.get("reason", "")).strip()
        if not reason:
            raise ValueError(f"exclusion for '{code}' needs a non-empty 'reason'")
        exclusions[code] = reason

    family_exclusions: dict[tuple[str, str], str] = {}
    for i, item in enumerate(raw.get("exclude_families", [])):
        if not isinstance(item, dict) or "framework" not in item or "family" not in item:
            raise ValueError(
                f"exclude_families #{i + 1} must be a mapping with 'framework' and 'family' keys"
            )
        framework = str(item["framework"]).strip()
        family = str(item["family"]).strip()
        reason = str(item.get("reason", "")).strip()
        if not reason:
            raise ValueError(f"family exclusion for '{framework}:{family}' needs a non-empty 'reason'")
        family_exclusions[(framework, family)] = reason

    owners = {str(k): str(v) for k, v in (raw.get("owners") or {}).items()}
    frameworks = [str(f) for f in (raw.get("frameworks") or [])]

    return Scope(
        subject=str(raw.get("subject", "")),
        frameworks=frameworks,
        exclusions=exclusions,
        family_exclusions=family_exclusions,
        owners=owners,
    )
