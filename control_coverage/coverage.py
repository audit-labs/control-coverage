"""Compute control coverage: join an evidence corpus onto framework catalogs.

For every control in a catalog we assign one **assurance state**:

* ``supported``   — in scope, at least one mapped finding passes and none fail.
* ``failing``     — in scope, at least one mapped finding fails.
* ``asserted``    — in scope, findings map here but their data was absent
                    (``not_applicable``): evidence was attempted, not obtained.
* ``unaddressed`` — in scope, *no* finding maps here at all. The blind spot.
* ``out_of_scope``— excluded by the scope file, with a recorded justification.

When several findings touch one control the worst wins: a single failure makes the
control ``failing`` regardless of how many others pass. Coverage is then a headline
number the evidence-first tools cannot produce — of everything a framework
requires, how much the corpus even looks at, and how much it supports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import Catalog, Control
from .corpus import FAIL, PASS, Observation

SUPPORTED = "supported"
FAILING = "failing"
ASSERTED = "asserted"
UNADDRESSED = "unaddressed"
OUT_OF_SCOPE = "out_of_scope"

# Order states appear in reports and roll up in summaries (most urgent first).
STATE_ORDER = [FAILING, UNADDRESSED, ASSERTED, SUPPORTED, OUT_OF_SCOPE]

# States that count as the control being "addressed" by the corpus at all.
_ADDRESSED = {SUPPORTED, FAILING, ASSERTED}


@dataclass
class ControlResult:
    """One control's assurance state and the evidence behind it."""

    control: Control
    state: str
    observations: list[Observation] = field(default_factory=list)
    owner: str = ""
    exclusion_reason: str = ""

    @property
    def addressed(self) -> bool:
        return self.state in _ADDRESSED


def _state_for(observations: list[Observation]) -> str:
    """Worst-wins resolution of a control's state from its observations."""
    if not observations:
        return UNADDRESSED
    statuses = {o.status for o in observations}
    if FAIL in statuses:
        return FAILING
    if PASS in statuses:
        return SUPPORTED
    return ASSERTED  # only not_applicable observations remain


@dataclass
class FrameworkCoverage:
    """Coverage of one framework catalog by the corpus."""

    catalog: Catalog
    results: list[ControlResult]

    def by_state(self, state: str) -> list[ControlResult]:
        return [r for r in self.results if r.state == state]

    @property
    def counts(self) -> dict[str, int]:
        counts = {s: 0 for s in STATE_ORDER}
        for r in self.results:
            counts[r.state] += 1
        return counts

    @property
    def in_scope(self) -> int:
        return sum(1 for r in self.results if r.state != OUT_OF_SCOPE)

    @property
    def addressed(self) -> int:
        return sum(1 for r in self.results if r.addressed)

    @property
    def supported(self) -> int:
        return sum(1 for r in self.results if r.state == SUPPORTED)

    @property
    def coverage_pct(self) -> float:
        """Share of in-scope controls the corpus touches at all (0–100)."""
        return round(100 * self.addressed / self.in_scope, 1) if self.in_scope else 0.0

    @property
    def assured_pct(self) -> float:
        """Share of in-scope controls that are supported and not failing (0–100)."""
        return round(100 * self.supported / self.in_scope, 1) if self.in_scope else 0.0

    @property
    def blind_spots(self) -> list[ControlResult]:
        """In-scope controls no finding touches — the headline gap list."""
        return self.by_state(UNADDRESSED)


@dataclass
class CoverageReport:
    """Coverage across every requested framework, plus corpus-wide diagnostics."""

    subject: str
    generated_at: str
    frameworks: list[FrameworkCoverage]
    # Control codes cited by the corpus that no loaded catalog defines. These are
    # typos, renamed controls, or controls outside the bundled catalogs — either
    # way, evidence pointing at nothing is worth surfacing.
    orphan_codes: list[str] = field(default_factory=list)
    source_count: int = 0


def _observations_by_control(observations: list[Observation]) -> dict[str, list[Observation]]:
    grouped: dict[str, list[Observation]] = {}
    for obs in observations:
        grouped.setdefault(obs.control, []).append(obs)
    return grouped


def evaluate(
    catalogs: list[Catalog],
    observations: list[Observation],
    scope=None,
    subject: str = "",
    generated_at: str = "",
) -> CoverageReport:
    """Produce a :class:`CoverageReport` from catalogs, a corpus, and a scope."""
    grouped = _observations_by_control(observations)
    catalog_codes: set[str] = set()
    loaded_frameworks = {cat.framework for cat in catalogs}

    frameworks: list[FrameworkCoverage] = []
    for cat in catalogs:
        catalog_codes |= cat.codes()
        results: list[ControlResult] = []
        for control in cat.controls:
            code = control.code
            obs = grouped.get(code, [])
            owner = scope.owner(code) if scope else ""
            if scope and scope.excluded(code):
                results.append(
                    ControlResult(control, OUT_OF_SCOPE, obs, owner, scope.reason(code))
                )
            elif scope and scope.family_excluded(cat.framework, control.family):
                reason = scope.family_reason(cat.framework, control.family)
                results.append(ControlResult(control, OUT_OF_SCOPE, obs, owner, reason))
            else:
                results.append(ControlResult(control, _state_for(obs), obs, owner))
        frameworks.append(FrameworkCoverage(cat, results))

    # A code is an orphan only when its framework *is* loaded but the catalog
    # does not define it — a typo or a renamed control. Codes for frameworks we
    # did not load this run are simply out of scope, not orphans.
    cited = {o.control for o in observations}
    orphans = sorted(
        code
        for code in cited
        if code.split(":", 1)[0] in loaded_frameworks and code not in catalog_codes
    )
    sources = {o.source for o in observations}

    return CoverageReport(
        subject=subject,
        generated_at=generated_at,
        frameworks=frameworks,
        orphan_codes=orphans,
        source_count=len(sources),
    )
