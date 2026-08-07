"""Tests for scope / Statement of Applicability parsing."""

from pathlib import Path

import pytest

from control_coverage import scope

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_exclusions_and_owners():
    scp = scope.load(FIXTURES / "scope.yaml")
    assert scp.subject == "Acme Production"
    assert scp.frameworks == ["SOC2", "ISO"]
    assert scp.excluded("ISO:A.7.1")
    assert "cloud-hosted" in scp.reason("ISO:A.7.1")
    assert scp.owner("SOC2:CC6.1") == "platform-team"


def test_exclusion_without_reason_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("exclusions:\n  - control: ISO:A.5.7\n")
    with pytest.raises(ValueError, match="needs a non-empty 'reason'"):
        scope.load(bad)


def test_exclusion_missing_control_key_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("exclusions:\n  - reason: no control key\n")
    with pytest.raises(ValueError, match="must be a mapping with a 'control' key"):
        scope.load(bad)


def test_family_exclusion_parses(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text(
        "exclude_families:\n"
        "  - {framework: SOC2, family: Privacy, reason: 'Not in the audit scope.'}\n"
    )
    scp = scope.load(f)
    assert scp.family_excluded("SOC2", "Privacy")
    assert "audit scope" in scp.family_reason("SOC2", "Privacy")
    assert not scp.family_excluded("SOC2", "Availability")


def test_family_exclusion_needs_reason(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text("exclude_families:\n  - {framework: SOC2, family: Privacy}\n")
    with pytest.raises(ValueError, match="needs a non-empty 'reason'"):
        scope.load(f)


def test_family_exclusion_needs_framework_and_family(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text("exclude_families:\n  - {family: Privacy, reason: x}\n")
    with pytest.raises(ValueError, match="'framework' and 'family'"):
        scope.load(f)


def test_empty_scope_excludes_nothing():
    scp = scope.empty()
    assert not scp.excluded("ISO:A.7.1")
    assert not scp.family_excluded("SOC2", "Privacy")
    assert scp.frameworks == []
