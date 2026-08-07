"""Tests for the command-line interface."""

from pathlib import Path

import pytest

from control_coverage import cli

FIXTURES = Path(__file__).parent / "fixtures"
GITHUB = str(FIXTURES / "github_audit_acme_2026-01-01.json")
AWS = str(FIXTURES / "aws_audit_acme_2026-01-01.json")
SCOPE = str(FIXTURES / "scope.yaml")


def test_stdout_markdown_default(capsys):
    rc = cli.main([GITHUB, AWS, "--framework", "SOC2"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "# Control Coverage" in out
    assert "Coverage" in out


def test_frameworks_inferred_from_corpus(capsys):
    cli.main([GITHUB, "--format", "json"])
    out = capsys.readouterr().out
    # github fixture cites SOC2, ISO, NIST codes -> all three inferred.
    for fw in ("SOC2", "ISO", "NIST"):
        assert f'"framework": "{fw}"' in out


def test_scope_file_supplies_frameworks_and_subject(capsys):
    cli.main([GITHUB, AWS, "--scope", SCOPE, "--format", "json"])
    out = capsys.readouterr().out
    assert '"subject": "Acme Production"' in out
    assert '"framework": "NIST"' not in out  # scope lists only SOC2, ISO


def test_blind_spots_mode(capsys):
    rc = cli.main([GITHUB, "--framework", "SOC2", "--blind-spots"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "unaddressed" in out
    assert "SOC2:CC1.1" in out


def test_fail_under_gate_trips(capsys):
    rc = cli.main([GITHUB, "--framework", "SOC2", "--fail-under", "90"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "coverage gate" in err


def test_fail_under_gate_passes(capsys):
    rc = cli.main([GITHUB, "--framework", "SOC2", "--fail-under", "1"])
    assert rc == 0


def test_out_dir_writes_files(tmp_path, capsys):
    rc = cli.main(
        [GITHUB, "--scope", SCOPE, "--format", "md,html,json,soa", "--out", str(tmp_path)]
    )
    assert rc == 0
    written = {p.name for p in tmp_path.iterdir()}
    assert "soa.md" in written
    assert any(n.endswith(".html") for n in written)
    assert any(n.endswith(".json") for n in written)


def test_missing_reports_errors():
    with pytest.raises(SystemExit):
        cli.main([str(FIXTURES / "nope.json"), "--framework", "SOC2"])


BASELINE = str(FIXTURES / "baseline_github.json")


def test_trend_mode_markdown(capsys):
    rc = cli.main([GITHUB, AWS, "--framework", "SOC2", "--baseline", BASELINE])
    out = capsys.readouterr().out
    assert rc == 0
    assert "# Coverage Trend" in out


def test_trend_html_output(tmp_path):
    cli.main([GITHUB, AWS, "--framework", "SOC2", "--baseline", BASELINE,
              "--format", "html,json", "--out", str(tmp_path)])
    names = {p.name for p in tmp_path.iterdir()}
    assert "trend.html" in names and "trend.json" in names


def test_crosswalk_mode(capsys):
    rc = cli.main([GITHUB, AWS, "--framework", "SOC2,ISO", "--crosswalk"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Minimal evidence set" in out


def test_crosswalk_and_baseline_conflict():
    with pytest.raises(SystemExit, match="cannot be combined"):
        cli.main([GITHUB, "--crosswalk", "--baseline", BASELINE])


def test_trend_rejects_soa_format():
    with pytest.raises(SystemExit, match="trend mode supports"):
        cli.main([GITHUB, "--framework", "SOC2", "--baseline", BASELINE, "--format", "soa"])


def test_family_exclusion_via_cli(tmp_path, capsys):
    scope_file = tmp_path / "scope.yaml"
    scope_file.write_text(
        "frameworks: [SOC2]\n"
        "exclude_families:\n"
        "  - {framework: SOC2, family: Privacy, reason: 'Not in scope.'}\n"
    )
    cli.main([GITHUB, "--scope", str(scope_file), "--format", "json"])
    out = capsys.readouterr().out
    assert '"state": "out_of_scope"' in out
