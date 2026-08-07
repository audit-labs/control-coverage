"""Renderers for a coverage report: Markdown, HTML, JSON, and a Statement of Applicability."""

from __future__ import annotations

from ..coverage import CoverageReport
from . import html, json, markdown, soa

_RENDERERS = {
    "md": markdown.render,
    "markdown": markdown.render,
    "html": html.render,
    "json": json.render,
    "soa": soa.render,
}

# File extension per format (soa is Markdown by default).
EXTENSIONS = {"md": "md", "markdown": "md", "html": "html", "json": "json", "soa": "md"}


def render(report: CoverageReport, fmt: str) -> str:
    try:
        return _RENDERERS[fmt](report)
    except KeyError:
        raise ValueError(
            f"unknown format '{fmt}'. Choose from: {', '.join(sorted(_RENDERERS))}"
        ) from None
