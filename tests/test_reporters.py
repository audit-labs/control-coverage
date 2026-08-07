"""Tests for the Markdown, HTML, JSON, and SoA renderers."""

import json as _json
from pathlib import Path

from control_coverage import catalog, corpus, reporters, scope
from control_coverage.coverage import evaluate

FIXTURES = Path(__file__).parent / "fixtures"


def _report():
    obs = corpus.load_corpus([FIXTURES / "github_audit_acme_2026-01-01.json"])
    cats = catalog.load_frameworks(["SOC2"])
    scp = scope.load(FIXTURES / "scope.yaml")
    return evaluate(cats, obs, scope=scp, subject="Acme", generated_at="2026-01-01")


def test_markdown_has_summary_and_blind_spots():
    md = reporters.render(_report(), "md")
    assert "# Control Coverage — Acme" in md
    assert "## Summary" in md
    assert "## Blind spots" in md
    assert "CC1.1" in md  # a blind spot is listed


def test_json_is_valid_and_structured():
    doc = _json.loads(reporters.render(_report(), "json"))
    assert doc["subject"] == "Acme"
    soc2 = doc["frameworks"][0]
    assert soc2["framework"] == "SOC2"
    assert soc2["coverage_pct"] >= 0
    states = {c["state"] for c in soc2["controls"]}
    assert "unaddressed" in states


def test_json_stamps_tool_and_catalog_provenance():
    from control_coverage import __version__

    doc = _json.loads(reporters.render(_report(), "json"))
    assert doc["tool"] == {"name": "control-coverage", "version": __version__}
    soc2 = doc["frameworks"][0]
    assert len(soc2["sha256"]) == 64  # full SHA-256 hex digest of the catalog file


def test_html_is_self_contained():
    html = reporters.render(_report(), "html")
    assert html.startswith("<!doctype html>")
    assert "<style>" in html
    assert "http://" not in html and "https://" not in html  # no external assets


def test_soa_lists_applicability_and_status():
    soa = reporters.render(_report(), "soa")
    assert "Statement of Applicability" in soa
    assert "Applicable" in soa
    assert "Implemented" in soa or "Not evidenced" in soa


def test_unknown_format_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown format"):
        reporters.render(_report(), "pdf")
