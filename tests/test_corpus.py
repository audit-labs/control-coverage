"""Tests for loading an evidence corpus from audit-report JSON."""

from pathlib import Path

import pytest

from control_coverage import corpus

FIXTURES = Path(__file__).parent / "fixtures"
GITHUB = FIXTURES / "github_audit_acme_2026-01-01.json"
AWS = FIXTURES / "aws_audit_acme_2026-01-01.json"


def test_one_observation_per_finding_control_pair():
    obs = corpus.load_report(GITHUB)
    # 4 findings with 3+3+3+3 controls = 12 observations.
    assert len(obs) == 12


def test_observation_carries_provenance():
    obs = corpus.load_report(GITHUB)
    o = next(o for o in obs if o.control == "SOC2:CC6.3")
    assert o.status == corpus.FAIL
    assert o.rule_id == "github.org.default-permission"
    assert o.source == "github_audit_acme_2026-01-01"


def test_load_corpus_flattens_multiple_reports():
    obs = corpus.load_corpus([GITHUB, AWS])
    sources = {o.source for o in obs}
    assert sources == {"github_audit_acme_2026-01-01", "aws_audit_acme_2026-01-01"}


def test_directory_is_expanded_to_json_files():
    obs = corpus.load_corpus([FIXTURES])
    assert len(obs) > 0
    assert any(o.source.startswith("aws_") for o in obs)


def test_empty_directory_raises(tmp_path):
    with pytest.raises(ValueError, match="no audit-report JSON"):
        corpus.load_corpus([tmp_path])
