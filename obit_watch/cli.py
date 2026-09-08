"""CLI entry for obit-watch."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from .sources import run_all_sources


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="obit_watch",
        description=(
            "Check free public obituary/funeral/death-notice sources "
            "for Northern Indiana (stdlib only; no paid APIs)."
        ),
    )
    p.add_argument(
        "--name",
        action="append",
        default=[],
        dest="names",
        help="Primary name to search (repeatable)",
    )
    p.add_argument(
        "--name-variant",
        action="append",
        default=[],
        dest="variants",
        help="Alternate name spelling/form (repeatable)",
    )
    p.add_argument(
        "--town",
        action="append",
        default=[],
        dest="towns",
        help="Town to include in location context (repeatable)",
    )
    p.add_argument(
        "--county",
        action="append",
        default=[],
        dest="counties",
        help="County to include in location context (repeatable)",
    )
    p.add_argument(
        "--state",
        default="IN",
        help="US state abbreviation (default: IN)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP timeout seconds (default: 15)",
    )
    p.add_argument(
        "--extra-url",
        action="append",
        default=[],
        dest="extra_urls",
        help="Extra URL to scan for name variants (repeatable)",
    )
    p.add_argument(
        "--format",
        choices=("json", "md"),
        default="json",
        dest="fmt",
        help="Output format (default: json)",
    )
    return p


def summarize(sources: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"hits": 0, "misses": 0, "errors": 0, "blocked": 0}
    for s in sources:
        st = s.get("status")
        if st == "hit":
            counts["hits"] += 1
        elif st == "miss":
            counts["misses"] += 1
        elif st == "blocked":
            counts["blocked"] += 1
        else:
            counts["errors"] += 1
    return counts


def exit_code(summary: Dict[str, int], n_sources: int) -> int:
    if summary["hits"] > 0:
        return 0
    if n_sources == 0:
        return 2
    runnable_ok = summary["misses"]
    if runnable_ok > 0 and summary["hits"] == 0:
        return 1
    # every source error/blocked (or zero misses and zero hits)
    if summary["misses"] == 0 and summary["hits"] == 0:
        return 2
    return 1


def to_markdown(payload: Dict[str, Any]) -> str:
    q = payload["query"]
    lines = [
        "# obit-watch report",
        "",
        f"- **Checked at:** {payload['checked_at']}",
        f"- **Names:** {', '.join(q['names']) or '(none)'}",
        f"- **Towns:** {', '.join(q['towns']) or '(none)'}",
        f"- **Counties:** {', '.join(q['counties']) or '(none)'}",
        f"- **State:** {q['state']}",
        "",
        "## Summary",
        "",
        f"- hits: {payload['summary']['hits']}",
        f"- misses: {payload['summary']['misses']}",
        f"- errors: {payload['summary']['errors']}",
        f"- blocked: {payload['summary']['blocked']}",
        "",
        "## Sources",
        "",
    ]
    for s in payload["sources"]:
        lines.append(f"### {s['name']} (`{s['id']}`)")
        lines.append(f"- status: **{s['status']}**")
        lines.append(f"- url: {s['url']}")
        lines.append(f"- http_code: {s.get('http_code')}")
        if s.get("excerpt"):
            lines.append(f"- excerpt: {s['excerpt']}")
        if s.get("reason"):
            lines.append(f"- reason: {s['reason']}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    names: List[str] = list(args.names or [])
    variants: List[str] = list(args.variants or [])
    if not names and not variants:
        parser.error("at least one --name or --name-variant is required")

    # Combine for query display: primary names first, then variants not already listed
    display_names = []
    seen = set()
    for n in names + variants:
        k = n.strip().lower()
        if n.strip() and k not in seen:
            seen.add(k)
            display_names.append(n.strip())

    sources = run_all_sources(
        names=names,
        variants=variants,
        towns=list(args.towns or []),
        counties=list(args.counties or []),
        state=(args.state or "IN").strip() or "IN",
        timeout=float(args.timeout),
        extra_urls=list(args.extra_urls or []),
    )
    summary = summarize(sources)
    payload: Dict[str, Any] = {
        "query": {
            "names": display_names,
            "towns": list(args.towns or []),
            "counties": list(args.counties or []),
            "state": (args.state or "IN").strip() or "IN",
        },
        "checked_at": _utc_now(),
        "sources": sources,
        "summary": summary,
    }

    if args.fmt == "md":
        sys.stdout.write(to_markdown(payload))
        if not to_markdown(payload).endswith("\n"):
            sys.stdout.write("\n")
    else:
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
        sys.stdout.write("\n")

    return exit_code(summary, len(sources))


if __name__ == "__main__":
    raise SystemExit(main())
