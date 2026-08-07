"""Tests for coverage trend (diffing two corpora)."""

from pathlib import Path

from control_coverage import catalog, corpus, trend
from control_coverage.coverage import evaluate

FIXTURES = Path(__file__).parent / "fixtures"
GITHUB = FIXTURES / "github_audit_acme_2026-01-01.json"
AWS = FIXTURES / "aws_audit_acme_2026-01-01.json"
BASELINE = FIXTURES / "baseline_github.json"


def _cov(paths):
    obs = corpus.load_corpus(paths)
    cats = catalog.load_frameworks(["SOC2"])
    return evaluate(cats, obs)


def _compare():
    return trend.compare(_cov([BASELINE]), _cov([GITHUB, AWS]))


def _delta(fc, control_id):
    return next(d for d in fc.deltas if d.id == control_id)


def test_categories_reflect_state_movement():
    fc = _compare().frameworks[0]
    assert _delta(fc, "CC6.1").category == trend.IMPROVED  # failing -> supported
    assert _delta(fc, "CC6.3").category == trend.UNCHANGED  # failing -> failing
    assert _delta(fc, "CC6.6").category == trend.GAINED  # unaddressed -> failing
    assert _delta(fc, "CC7.2").category == trend.GAINED  # unaddressed -> supported
    assert _delta(fc, "CC9.2").category == trend.LOST  # supported -> unaddressed


def test_counts_and_coverage_delta():
    fc = _compare().frameworks[0]
    c = fc.counts
    assert c[trend.IMPROVED] == 1
    assert c[trend.GAINED] == 3  # CC6.6, CC7.2, CC8.1
    assert c[trend.LOST] == 1
    assert c[trend.REGRESSED] == 0
    assert fc.coverage_delta == round(fc.new_coverage_pct - fc.old_coverage_pct, 1)
    assert fc.new_coverage_pct > fc.old_coverage_pct


def test_regressions_count_lost_and_regressed():
    report = _compare()
    assert report.total_regressions == 1  # the single LOST control


def test_markdown_lists_changes_only():
    md = trend.render_markdown(_compare())
    assert "# Coverage Trend" in md
    assert "CC9.2" in md  # a lost control appears
    assert "CC1.1" not in md  # an unchanged blind spot does not


def test_json_omits_unchanged():
    import json

    doc = json.loads(trend.render_json(_compare()))
    changes = doc["frameworks"][0]["changes"]
    ids = {c["id"] for c in changes}
    assert "CC9.2" in ids
    assert "CC1.1" not in ids


def test_html_is_self_contained():
    html = trend.render_html(_compare())
    assert html.startswith("<!doctype html>")
    assert "<style>" in html
    assert "http://" not in html and "https://" not in html
    assert "CC9.2" in html  # a changed control shows up
