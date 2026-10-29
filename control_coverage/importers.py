"""Convert published framework content into catalog YAML.

Supported inputs:

* an OSCAL catalog (JSON), with nested control enhancements;
* an OSCAL profile (JSON) applied to its OSCAL catalog, keeping only the
  controls the profile includes (for example a NIST 800-53 baseline);
* a CISO Assistant framework library (YAML): assessable requirement nodes
  become controls, their parent node becomes the family.

Each result records where it came from (`source`, `imported_from`, `version`)
and the `license` the content is used under, so the provenance travels with
the catalog. Converting the same input twice yields the same YAML.
"""

from __future__ import annotations

import json
import re

import yaml


def _code(raw: str) -> str:
    code = re.sub(r"[^A-Za-z0-9]+", "", str(raw or "")).upper()
    if not code:
        raise ValueError("framework code is required")
    return code


def _oscal_controls(controls: list[dict], family: str, out: list[dict], keep: set[str] | None) -> None:
    for c in controls or []:
        if keep is None or c.get("id") in keep:
            out.append({"id": str(c["id"]).upper(), "title": str(c.get("title", "")).strip(), "family": family})
        _oscal_controls(c.get("controls") or [], family, out, keep)


def from_oscal_catalog(doc: dict, framework: str, license_text: str, imported_from: str = "", keep: set[str] | None = None) -> dict:
    cat = doc.get("catalog") if isinstance(doc, dict) else None
    if not isinstance(cat, dict):
        raise ValueError("not an OSCAL catalog (no 'catalog' object)")  # noqa: TRY004
    meta = cat.get("metadata") or {}
    controls: list[dict] = []
    for group in cat.get("groups") or []:
        _oscal_controls(group.get("controls") or [], str(group.get("title") or group.get("id") or ""), controls, keep)
    _oscal_controls(cat.get("controls") or [], "", controls, keep)
    if not controls:
        raise ValueError("the OSCAL catalog has no controls")
    return {
        "framework": _code(framework),
        "name": str(meta.get("title") or framework),
        "version": str(meta.get("version") or ""),
        "coverage": "complete" if keep is None else "partial",
        "source": f"OSCAL catalog {cat.get('uuid', '')}".strip(),
        "license": license_text,
        "imported_from": imported_from,
        "controls": controls,
    }


def from_oscal_profile(profile_doc: dict, catalog_doc: dict, framework: str, license_text: str, imported_from: str = "") -> dict:
    prof = profile_doc.get("profile") if isinstance(profile_doc, dict) else None
    if not isinstance(prof, dict):
        raise ValueError("not an OSCAL profile (no 'profile' object)")  # noqa: TRY004
    keep: set[str] = set()
    for imp in prof.get("imports") or []:
        for inc in imp.get("include-controls") or []:
            keep.update(inc.get("with-ids") or [])
    if not keep:
        raise ValueError("the OSCAL profile selects no controls with 'include-controls'/'with-ids'")
    data = from_oscal_catalog(catalog_doc, framework, license_text, imported_from, keep)
    pmeta = prof.get("metadata") or {}
    data["name"] = str(pmeta.get("title") or data["name"])
    data["version"] = str(pmeta.get("version") or data["version"])
    data["source"] = f"OSCAL profile {prof.get('uuid', '')} over {data['source']}".strip()
    data["coverage"] = "complete"  # complete for the profile's baseline
    return data


def from_ciso_assistant(doc: dict, framework: str | None, license_text: str = "", imported_from: str = "") -> dict:
    if not isinstance(doc, dict):
        raise ValueError("not a CISO Assistant library")  # noqa: TRY004
    fw = ((doc.get("objects") or {}).get("framework")) or {}
    nodes = fw.get("requirement_nodes") or []
    if not nodes:
        raise ValueError("the library has no framework requirement_nodes")
    by_urn = {n.get("urn"): n for n in nodes}
    controls = []
    for n in nodes:
        if not n.get("assessable") or not n.get("ref_id"):
            continue
        parent = by_urn.get(n.get("parent_urn")) or {}
        controls.append(
            {
                "id": str(n["ref_id"]),
                "title": str(n.get("name") or n.get("description") or "").strip()[:200],
                "family": str(parent.get("name") or parent.get("ref_id") or ""),
            }
        )
    if not controls:
        raise ValueError("the library has no assessable requirements with a ref_id")
    return {
        "framework": _code(framework or fw.get("ref_id") or doc.get("ref_id") or ""),
        "name": str(fw.get("name") or doc.get("name") or ""),
        "version": str(doc.get("version") or ""),
        "coverage": "complete",
        "source": f"CISO Assistant library {doc.get('urn', '')} ({doc.get('provider') or doc.get('packager') or 'unknown provider'})",
        "license": license_text or str(doc.get("copyright") or ""),
        "imported_from": imported_from,
        "controls": controls,
    }


def to_yaml(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def load_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc
