"""Catalog importers (OSCAL catalog/profile, CISO Assistant), provenance, and typed mappings."""

import json

import pytest
import yaml

from control_coverage import catalog, coverage, importers
from control_coverage.corpus import Observation, load_report

OSCAL = {
    "catalog": {
        "uuid": "c-1",
        "metadata": {"title": "Mini 800-53", "version": "5.1.1"},
        "groups": [
            {"id": "ac", "title": "Access Control", "controls": [
                {"id": "ac-1", "title": "Policy and Procedures"},
                {"id": "ac-2", "title": "Account Management", "controls": [{"id": "ac-2.1", "title": "Automated Account Management"}]},
            ]},
            {"id": "au", "title": "Audit and Accountability", "controls": [{"id": "au-2", "title": "Event Logging"}]},
        ],
    }
}
PROFILE = {"profile": {"uuid": "p-1", "metadata": {"title": "Mini Low Baseline", "version": "1"}, "imports": [{"href": "#c-1", "include-controls": [{"with-ids": ["ac-2", "au-2"]}]}]}}
CISO = {
    "urn": "urn:intuitem:risk:library:dora",
    "ref_id": "DORA",
    "name": "DORA",
    "version": 2,
    "provider": "EU",
    "copyright": "EU public domain",
    "objects": {"framework": {"ref_id": "DORA", "name": "Digital Operational Resilience Act", "requirement_nodes": [
        {"urn": "u:ch2", "ref_id": "Chapter II", "name": "ICT risk management", "assessable": False},
        {"urn": "u:a5", "parent_urn": "u:ch2", "ref_id": "Art.5", "name": "Governance and organisation", "assessable": True},
        {"urn": "u:a9", "parent_urn": "u:ch2", "ref_id": "Art.9", "name": "Protection and prevention", "assessable": True},
    ]}},
}


def _write(tmp_path, data):
    path = tmp_path / f"{data['framework'].lower()}.yaml"
    path.write_text(importers.to_yaml(data))
    return path


def test_oscal_catalog_with_enhancements_and_provenance(tmp_path):
    data = importers.from_oscal_catalog(OSCAL, "nist", "Public domain (US government work)", "nist-mini.json")
    assert [c["id"] for c in data["controls"]] == ["AC-1", "AC-2", "AC-2.1", "AU-2"]
    cat = catalog.load_file(_write(tmp_path, data))
    assert cat.framework == "NIST" and cat.version == "5.1.1" and cat.license.startswith("Public domain")
    assert cat.imported_from == "nist-mini.json"
    assert importers.to_yaml(importers.from_oscal_catalog(OSCAL, "nist", "Public domain (US government work)", "nist-mini.json")) == importers.to_yaml(data)


def test_oscal_profile_selects_baseline():
    data = importers.from_oscal_profile(PROFILE, OSCAL, "NISTLOW", "Public domain")
    assert [c["id"] for c in data["controls"]] == ["AC-2", "AU-2"]
    assert data["name"] == "Mini Low Baseline" and "profile p-1" in data["source"]


def test_ciso_assistant_library():
    data = importers.from_ciso_assistant(CISO, None)
    assert data["framework"] == "DORA" and data["license"] == "EU public domain"
    assert data["controls"] == [
        {"id": "Art.5", "title": "Governance and organisation", "family": "ICT risk management"},
        {"id": "Art.9", "title": "Protection and prevention", "family": "ICT risk management"},
    ]
    with pytest.raises(ValueError):
        importers.from_ciso_assistant({"objects": {}}, "X")


def _obs(status, relationship="full"):
    return Observation("TEST:C1", status, "r", "t", "high", "s", relationship=relationship)


def test_partial_mappings_give_partially_supported():
    cat = catalog.Catalog("TEST", "Test", "1", "complete", "", [catalog.Control("TEST", "C1", "One")])
    state = lambda obs: coverage.evaluate([cat], obs).frameworks[0].results[0].state
    assert state([_obs("pass", "partial")]) == coverage.PARTIALLY_SUPPORTED
    assert state([_obs("pass", "intersects"), _obs("pass", "subset")]) == coverage.PARTIALLY_SUPPORTED
    assert state([_obs("pass", "partial"), _obs("pass", "full")]) == coverage.SUPPORTED
    assert state([_obs("pass", "equal"), _obs("fail", "partial")]) == coverage.FAILING
    report = coverage.evaluate([cat], [_obs("pass", "partial")])
    assert report.frameworks[0].addressed == 1 and report.frameworks[0].supported == 0


def test_report_json_carries_mappings(tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"findings": [{"id": "x", "status": "pass", "controls": ["SOC2:CC6.1", "ISO:A.5.17"],
                                              "control_mappings": {"ISO:A.5.17": {"relationship": "partial", "rationale": "covers MFA only"}}}]}))
    obs = {o.control: o for o in load_report(path)}
    assert obs["SOC2:CC6.1"].relationship == "full"
    assert (obs["ISO:A.5.17"].relationship, obs["ISO:A.5.17"].mapping) == ("partial", "covers MFA only")


def test_bundled_catalogs_still_load():
    assert yaml.safe_load(importers.to_yaml({"a": 1})) == {"a": 1}
    assert catalog.load("soc2").license == ""
