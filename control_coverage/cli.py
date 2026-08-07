"""Command-line entry point for control-coverage."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, catalog, corpus, reporters, scope
from .coverage import evaluate


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="control-coverage",
        description=(
            "Score an evidence corpus against complete framework catalogs: what "
            "share of each framework does the evidence address, and which controls "
            "are blind spots no finding touches?"
        ),
    )
    parser.add_argument(
        "reports",
        nargs="+",
        help="audit-report JSON files, and/or directories containing them",
    )
    parser.add_argument(
        "--framework",
        help=(
            "comma-separated frameworks to evaluate (e.g. SOC2,ISO,NIST). "
            "Default: every framework the corpus cites, or the scope file's list."
        ),
    )
    parser.add_argument(
        "--scope",
        help="path to a scope / Statement of Applicability YAML (marks exclusions)",
    )
    parser.add_argument(
        "--subject",
        help="name for the subject of this corpus (overrides the scope file)",
    )
    parser.add_argument(
        "--format",
        default="md",
        help="comma-separated output formats: md, html, json, soa (default: md)",
    )
    parser.add_argument(
        "--out",
        help="directory to write reports into (default: print the first format to stdout)",
    )
    parser.add_argument(
        "--blind-spots",
        action="store_true",
        help="print only the unaddressed in-scope controls, then exit",
    )
    parser.add_argument(
        "--baseline",
        metavar="PATH",
        help=(
            "trend mode: an earlier corpus (file or directory) to compare against. "
            "Reports how coverage moved — what improved, regressed, was gained or lost."
        ),
    )
    parser.add_argument(
        "--crosswalk",
        action="store_true",
        help=(
            "crosswalk mode: show which controls each piece of evidence supports "
            "across frameworks, and the minimal evidence set that covers them all"
        ),
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        metavar="PCT",
        help="exit non-zero if any framework's coverage %% is below PCT (CI gate)",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="in trend mode, exit non-zero if any control regressed or lost coverage",
    )
    parser.add_argument("--version", action="version", version=f"control-coverage {__version__}")
    return parser.parse_args(argv)


def _select_frameworks(args, observations, scp) -> list[str]:
    """Decide which framework catalogs to load, in priority order."""
    if args.framework:
        return [f.strip() for f in args.framework.split(",") if f.strip()]
    if scp.frameworks:
        return scp.frameworks
    # Infer from the corpus: every framework prefix the observations cite.
    cited = sorted({o.control.split(":", 1)[0] for o in observations if ":" in o.control})
    if not cited:
        raise SystemExit(
            "error: could not infer frameworks from the corpus. Pass --framework."
        )
    return cited


def _print_blind_spots(report) -> None:
    total = 0
    for fc in report.frameworks:
        spots = fc.blind_spots
        if not spots:
            continue
        print(f"{fc.catalog.name} — {len(spots)} unaddressed:")
        for r in spots:
            print(f"  {r.control.code}  {r.control.title}")
        total += len(spots)
    print(f"\n{total} in-scope control(s) unaddressed across {len(report.frameworks)} framework(s).")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _build_report(paths, args, scp, names, subject):
    """Load a corpus from *paths* and evaluate it into a CoverageReport."""
    try:
        observations = corpus.load_corpus(paths)
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise SystemExit(f"error: {exc}") from None
    catalogs = catalog.load_frameworks(names)
    return evaluate(catalogs, observations, scope=scp, subject=subject, generated_at=_now())


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if args.crosswalk and args.baseline:
        raise SystemExit("error: --crosswalk and --baseline cannot be combined")

    try:
        observations = corpus.load_corpus(args.reports)
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise SystemExit(f"error: {exc}") from None

    scp = scope.load(args.scope) if args.scope else scope.empty()

    try:
        names = _select_frameworks(args, observations, scp)
        catalogs = catalog.load_frameworks(names)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from None

    subject = args.subject or scp.subject
    report = evaluate(catalogs, observations, scope=scp, subject=subject, generated_at=_now())

    if args.baseline:
        return _trend_mode(args, scp, names, subject, report)

    if args.crosswalk:
        return _crosswalk_mode(args, report)

    if args.blind_spots:
        _print_blind_spots(report)
        return _exit_code(report, args.fail_under)

    formats = [f.strip() for f in args.format.split(",") if f.strip()]
    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = _slug(subject) or "coverage"
        for fmt in formats:
            ext = reporters.EXTENSIONS.get(fmt, fmt)
            name = "soa" if fmt == "soa" else "coverage"
            path = out_dir / f"{name}.{ext}" if fmt == "soa" else out_dir / f"{stem}.{ext}"
            path.write_text(reporters.render(report, fmt), encoding="utf-8")
            print(f"wrote {path}")
    else:
        # Print the first requested format to stdout.
        print(reporters.render(report, formats[0]), end="")

    return _exit_code(report, args.fail_under)


def _trend_mode(args, scp, names, subject, current) -> int:
    from . import trend

    baseline = _build_report([args.baseline], args, scp, names, subject)
    tr = trend.compare(baseline, current)

    formats = [f.strip() for f in args.format.split(",") if f.strip()]
    renderers = {
        "md": trend.render_markdown,
        "html": trend.render_html,
        "json": trend.render_json,
    }
    unknown = [f for f in formats if f not in renderers]
    if unknown:
        raise SystemExit(f"error: trend mode supports md, html, and json, not: {', '.join(unknown)}")

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for fmt in formats:
            path = out_dir / f"trend.{fmt}"
            path.write_text(renderers[fmt](tr), encoding="utf-8")
            print(f"wrote {path}")
    else:
        print(renderers[formats[0]](tr), end="")

    if args.fail_on_regression and tr.total_regressions:
        print(
            f"trend gate: {tr.total_regressions} control(s) regressed or lost coverage",
            file=sys.stderr,
        )
        return 1
    return 0


def _crosswalk_mode(args, report) -> int:
    from . import crosswalk

    xw = crosswalk.build(report)
    formats = [f.strip() for f in args.format.split(",") if f.strip()]
    renderers = {
        "md": crosswalk.render_markdown,
        "html": crosswalk.render_html,
        "json": crosswalk.render_json,
    }
    unknown = [f for f in formats if f not in renderers]
    if unknown:
        raise SystemExit(
            f"error: crosswalk mode supports md, html, and json, not: {', '.join(unknown)}"
        )

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for fmt in formats:
            path = out_dir / f"crosswalk.{fmt}"
            path.write_text(renderers[fmt](xw), encoding="utf-8")
            print(f"wrote {path}")
    else:
        print(renderers[formats[0]](xw), end="")
    return 0


def _exit_code(report, fail_under: float | None) -> int:
    if fail_under is None:
        return 0
    below = [fc for fc in report.frameworks if fc.coverage_pct < fail_under]
    if below:
        for fc in below:
            print(
                f"coverage gate: {fc.catalog.framework} at {fc.coverage_pct}% "
                f"is below {fail_under}%",
                file=sys.stderr,
            )
        return 1
    return 0


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


if __name__ == "__main__":
    raise SystemExit(main())
