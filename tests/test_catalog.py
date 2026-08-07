"""Tests for loading framework catalogs."""

import pytest

from control_coverage import catalog


def test_soc2_is_complete_common_criteria():
    cat = catalog.load("soc2")
    assert cat.framework == "SOC2"
    assert cat.complete
    ids = {c.id for c in cat.controls}
    # A representative spread across every Common Criteria group.
    for cc in ["CC1.1", "CC5.3", "CC6.8", "CC7.5", "CC8.1", "CC9.2"]:
        assert cc in ids


def test_soc2_has_all_five_tsc_categories():
    cat = catalog.load("soc2")
    families = {c.family for c in cat.controls}
    assert {"Availability", "Confidentiality", "Processing Integrity", "Privacy"} <= families
    ids = {c.id for c in cat.controls}
    for cid in ["C1.1", "PI1.5", "P6.7", "P8.1"]:
        assert cid in ids
    assert len(cat.controls) == 61


def test_iso_has_all_93_annex_a_controls():
    cat = catalog.load("iso")
    assert cat.framework == "ISO"
    assert cat.complete
    assert len(cat.controls) == 93


def test_nist_is_the_moderate_baseline():
    cat = catalog.load("nist")
    assert cat.complete  # complete relative to the moderate baseline
    assert "Moderate" in cat.name
    assert len(cat.controls) > 150
    ids = {c.id for c in cat.controls}
    # A spread across families the ecosystem's rulesets cite and beyond.
    for cid in ["AC-6", "AU-2", "CM-6", "IA-2", "SC-7", "SI-2", "SR-3"]:
        assert cid in ids


def test_control_code_joins_framework_and_id():
    cat = catalog.load("soc2")
    ctrl = next(c for c in cat.controls if c.id == "CC6.1")
    assert ctrl.code == "SOC2:CC6.1"


def test_titles_with_commas_survive_parsing():
    cat = catalog.load("soc2")
    ctrl = next(c for c in cat.controls if c.id == "CC1.3")
    assert "reporting lines" in ctrl.title  # flow-scalar comma bug regression


def test_aliases_resolve():
    assert catalog.load("iso 27001").framework == "ISO"
    assert catalog.load("800-53").framework == "NIST"


def test_unknown_framework_raises():
    with pytest.raises(ValueError, match="unknown framework"):
        catalog.load("hipaa")


def test_load_frameworks_dedupes_and_sorts():
    cats = catalog.load_frameworks(["NIST", "SOC2", "soc 2"])
    assert [c.framework for c in cats] == ["NIST", "SOC2"]


def test_available_lists_bundled():
    assert set(catalog.available()) == {"SOC2", "ISO", "NIST"}
