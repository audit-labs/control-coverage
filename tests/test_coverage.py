"""Tests for the coverage engine — the heart of the tool."""

from pathlib import Path

from control_coverage import catalog, corpus, scope
from control_coverage.coverage import (
    ASSERTED,
    FAILING,
    OUT_OF_SCOPE,
    SUPPORTED,
    UNADDRESSED,
    evaluate,
)

FIXTURES = Path(__file__).parent / "fixtures"
GITHUB = FIXTURES / "github_audit_acme_2026-01-01.json"
AWS = FIXTURES / "aws_audit_acme_2026-01-01.json"


def _state(fc, control_id):
    return next(r.state for r in fc.results if r.control.id == control_id)


def _report(frameworks, scp=None):
    obs = corpus.load_corpus([GITHUB, AWS])
    cats = catalog.load_frameworks(frameworks)
    return evaluate(cats, obs, scope=scp)


def test_worst_wins_and_blind_spots_for_soc2():
    fc = _report(["SOC2"]).frameworks[0]
    assert _state(fc, "CC6.1") == SUPPORTED  # two passes across github + aws
    assert _state(fc, "CC6.3") == FAILING  # one fail
    assert _state(fc, "CC6.6") == FAILING
    assert _state(fc, "CC8.1") == ASSERTED  # only not_applicable observations
    assert _state(fc, "CC1.1") == UNADDRESSED  # nothing maps here


def test_soc2_rollup_numbers():
    fc = _report(["SOC2"]).frameworks[0]
    assert fc.in_scope == 61  # full five-category Trust Services Criteria
    assert fc.supported == 3
    assert fc.counts[FAILING] == 2
    assert fc.counts[ASSERTED] == 1
    assert fc.addressed == 6
    assert len(fc.blind_spots) == 55
    assert fc.coverage_pct == 9.8  # 6 / 61
    assert fc.assured_pct == 4.9  # 3 / 61


def test_scope_marks_controls_out_of_scope_with_reason():
    scp = scope.load(FIXTURES / "scope.yaml")
    fc = next(f for f in _report(["ISO"], scp).frameworks if f.catalog.framework == "ISO")
    assert _state(fc, "A.7.1") == OUT_OF_SCOPE
    assert _state(fc, "A.5.7") == OUT_OF_SCOPE
    assert fc.in_scope == 91  # 93 Annex A controls minus 2 exclusions
    excluded = next(r for r in fc.results if r.control.id == "A.7.1")
    assert "cloud-hosted" in excluded.exclusion_reason


def test_orphan_only_flags_loaded_frameworks():
    # CC6.99 is a SOC2 typo; NIST codes are cited but NIST is not loaded here.
    report = _report(["SOC2", "ISO"])
    assert "SOC2:CC6.99" in report.orphan_codes
    assert not any(c.startswith("NIST:") for c in report.orphan_codes)


def test_family_exclusion_marks_whole_category_out_of_scope():
    from control_coverage.scope import Scope

    scp = Scope(family_exclusions={("SOC2", "Privacy"): "Not in the SOC 2 audit scope."})
    fc = _report(["SOC2"], scp).frameworks[0]
    privacy = [r for r in fc.results if r.control.family == "Privacy"]
    assert privacy  # the catalog has Privacy controls
    assert all(r.state == OUT_OF_SCOPE for r in privacy)
    assert all("audit scope" in r.exclusion_reason for r in privacy)
    # Security (Common Criteria) controls remain in scope.
    cc61 = next(r for r in fc.results if r.control.id == "CC6.1")
    assert cc61.state != OUT_OF_SCOPE


def test_owner_is_attached_from_scope():
    scp = scope.load(FIXTURES / "scope.yaml")
    fc = _report(["SOC2"], scp).frameworks[0]
    owner = next(r.owner for r in fc.results if r.control.id == "CC6.1")
    assert owner == "platform-team"


def test_source_count_reflects_distinct_packages():
    report = _report(["SOC2"])
    assert report.source_count == 2
