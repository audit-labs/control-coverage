"""Tests for the evidence crosswalk and minimal-evidence set."""

import json
from pathlib import Path

from control_coverage import catalog, corpus, crosswalk
from control_coverage.coverage import evaluate

FIXTURES = Path(__file__).parent / "fixtures"
GITHUB = FIXTURES / "github_audit_acme_2026-01-01.json"
AWS = FIXTURES / "aws_audit_acme_2026-01-01.json"


def _crosswalk(frameworks):
    obs = corpus.load_corpus([GITHUB, AWS])
    cats = catalog.load_frameworks(frameworks)
    return crosswalk.build(evaluate(cats, obs))


def test_item_spans_multiple_frameworks():
    xw = _crosswalk(["SOC2", "ISO", "NIST"])
    twofa = next(i for i in xw.items if i.rule_id == "github.org.require-2fa")
    # 2FA maps to SOC2:CC6.1, ISO:A.5.17, NIST:IA-2.
    assert set(twofa.frameworks) == {"SOC2", "ISO", "NIST"}
    assert "SOC2:CC6.1" in twofa.controls


def test_items_sorted_by_leverage():
    xw = _crosswalk(["SOC2", "ISO", "NIST"])
    counts = [i.count for i in xw.items]
    assert counts == sorted(counts, reverse=True)


def test_minimal_cover_reaches_full_universe():
    xw = _crosswalk(["SOC2", "ISO", "NIST"])
    assert xw.cover  # non-empty
    assert xw.cover[-1].cumulative == xw.universe_size
    assert xw.cover[-1].cumulative_pct == 100.0


def test_cover_is_monotonic_and_no_wasted_picks():
    xw = _crosswalk(["SOC2"])
    cumulative = [s.cumulative for s in xw.cover]
    assert cumulative == sorted(cumulative)
    assert all(s.new_controls > 0 for s in xw.cover)  # greedy never picks a no-op


def test_markdown_has_both_sections():
    md = crosswalk.render_markdown(_crosswalk(["SOC2", "ISO"]))
    assert "## Minimal evidence set" in md
    assert "## Evidence leverage" in md
    assert "github.org.require-2fa" in md


def test_json_structure():
    doc = json.loads(crosswalk.render_json(_crosswalk(["SOC2", "ISO"])))
    assert doc["universe_size"] > 0
    assert "minimal_evidence_set" in doc
    assert all("controls" in e for e in doc["evidence"])


def test_html_is_self_contained():
    html = crosswalk.render_html(_crosswalk(["SOC2", "ISO", "NIST"]))
    assert html.startswith("<!doctype html>")
    assert "<style>" in html
    assert "http://" not in html and "https://" not in html
    assert "github.org.require-2fa" in html
