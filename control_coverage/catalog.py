"""Framework catalogs — the complete list of controls a framework defines.

This is the piece the rest of the audit-labs ecosystem does not have. Tools like
audit-report are *evidence-first*: they start from what you collected and map each
finding onto whatever controls it touches. That can never tell you what you are
**not** looking at, because it has no list of everything a framework requires.

A catalog is that list — the denominator. Loading ``soc2`` gives every Trust
Services Criterion; loading ``iso`` gives all 93 Annex A controls. Coverage is
then simply: of these, how many does the evidence corpus actually address?

Control codes are written ``FRAMEWORK:ID`` (for example ``SOC2:CC6.1``,
``ISO:A.5.17``), matching the codes audit-report rulesets cite.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_CATALOG_DIR = Path(__file__).resolve().parent / "catalogs"

# User-facing framework name -> catalog file stem. Aliases keep the CLI forgiving.
_ALIASES = {
    "soc2": "soc2",
    "soc 2": "soc2",
    "iso": "iso27001",
    "iso27001": "iso27001",
    "iso 27001": "iso27001",
    "nist": "nist80053",
    "nist80053": "nist80053",
    "800-53": "nist80053",
}


@dataclass(frozen=True)
class Control:
    """One control in a framework catalog."""

    framework: str
    id: str
    title: str
    family: str = ""

    @property
    def code(self) -> str:
        """The full ``FRAMEWORK:ID`` code used to join against evidence."""
        return f"{self.framework}:{self.id}"


@dataclass
class Catalog:
    """A framework's complete (or explicitly partial) set of controls."""

    framework: str
    name: str
    version: str
    coverage: str  # "complete" or "partial"
    source: str
    controls: list[Control]

    @property
    def complete(self) -> bool:
        return self.coverage == "complete"

    def codes(self) -> set[str]:
        return {c.code for c in self.controls}


def available() -> list[str]:
    """Framework short codes with a bundled catalog (e.g. ``["ISO", "NIST", "SOC2"]``)."""
    return sorted(load(p.stem).framework for p in _CATALOG_DIR.glob("*.yaml"))


def _resolve(name: str) -> Path:
    stem = _ALIASES.get(name.strip().lower(), name.strip().lower())
    path = _CATALOG_DIR / f"{stem}.yaml"
    if not path.exists():
        known = ", ".join(sorted(p.stem for p in _CATALOG_DIR.glob("*.yaml")))
        raise ValueError(f"unknown framework '{name}'. Bundled catalogs: {known}")
    return path


def load(name: str) -> Catalog:
    """Load a bundled catalog by framework name, short code, or alias."""
    path = _resolve(name)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    framework = raw["framework"]
    controls = [
        Control(
            framework=framework,
            id=str(c["id"]),
            title=str(c["title"]),
            family=str(c.get("family", "")),
        )
        for c in raw.get("controls", [])
    ]
    return Catalog(
        framework=framework,
        name=raw.get("name", framework),
        version=str(raw.get("version", "")),
        coverage=raw.get("coverage", "partial"),
        source=raw.get("source", ""),
        controls=controls,
    )


def load_frameworks(names: list[str]) -> list[Catalog]:
    """Load several catalogs, de-duplicated by framework, in a stable order."""
    seen: dict[str, Catalog] = {}
    for name in names:
        cat = load(name)
        seen[cat.framework] = cat
    return [seen[k] for k in sorted(seen)]
