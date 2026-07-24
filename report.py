#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPORT_DIR = Path.home() / ".opencode" / "opencode-dispatch-reports"


def format_integer(value: object) -> str:
    try:
        return f"{int(float(value or 0)):,}"
    except (TypeError, ValueError):
        return "0"


def format_percent(value: object) -> str:
    try:
        return f"{float(value or 0):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def format_duration(milliseconds: object) -> str:
    try:
        value = max(0.0, float(milliseconds or 0))
    except (TypeError, ValueError):
        value = 0.0
    if value < 1_000:
        return f"{round(value)} ms"
    seconds = value / 1_000
    if seconds < 60:
        digits = 1 if seconds < 10 else 0
        return f"{seconds:.{digits}f} s"
    minutes, remaining_seconds = divmod(round(seconds), 60)
    if minutes < 60:
        return f"{minutes} min {remaining_seconds}s"
    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours} h {remaining_minutes} min"


def resolve_report_path(args: argparse.Namespace) -> Path:
    if args.session:
        matches = sorted(
            REPORT_DIR.glob(f"*/{args.session}.json"),
            reverse=True,
        )
        if matches:
            return matches[0]
        raise FileNotFoundError(f"session not found: {args.session}")
    if args.active:
        return REPORT_DIR / "active.json"
    return REPORT_DIR / "latest.json"


def compact_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    root = report.get("rootSession", {})
    models = report.get("models", [])
    fallbacks = report.get("fallbacks", [])
    orchestration = report.get("orchestration", {})
    orchestration_summary = orchestration.get("summary", {})
    latest_run = orchestration.get("latest") or {}
    total_tokens = (summary.get("totalTokens") or {}).get("total")
    lines = [
        "### OpenCode Dispatch telemetry",
        (
            f"- Time: {format_duration(root.get('wallClockMs'))} wall clock; "
            f"{format_duration(summary.get('aggregateModelMs'))} aggregated "
            "across models."
        ),
        (
            f"- Tokens: {format_integer(total_tokens)} "
            f"({summary.get('messagesWithTokenUsage', 0)}/"
            f"{summary.get('assistantMessages', 0)} assistant responses "
            "reported usage)."
        ),
        (
            f"- Fallback: {'yes' if summary.get('fallbackUsed') else 'no'}; "
            f"{summary.get('fallbackCount', 0)} event(s)."
        ),
        (
            f"- Sessions: {summary.get('sessions', 0)}, including "
            f"{summary.get('subagentSessions', 0)} subagent session(s)."
        ),
        (
            "- Orchestration: "
            f"{format_percent(orchestration_summary.get('compliancePct', 100))} "
            f"compliance; current category "
            f"{latest_run.get('category', 'not reported')}; gate "
            f"{'approved' if latest_run.get('gateApproved') else 'pending'}; "
            f"{orchestration_summary.get('remediations', 0)} remediation(s)."
        ),
    ]
    if models:
        lines.append("- Model distribution:")
        for model in models:
            lines.append(
                f"  - {model.get('name') or model.get('key')}: "
                f"{format_percent(model.get('tokenSharePct'))} of tokens, "
                f"{format_percent(model.get('requestSharePct'))} of responses, "
                f"{format_duration(model.get('durationMs'))}; fallback "
                f"out/in {model.get('fallbackFromCount', 0)}/"
                f"{model.get('fallbackToCount', 0)}."
            )
    if fallbacks:
        lines.append("- Fallback routes:")
        for item in fallbacks:
            lines.append(
                f"  - {item.get('from') or '?'} -> "
                f"{item.get('to') or 'none'} ({item.get('reason')}, HTTP "
                f"{item.get('status') or '-'})."
            )
    if report.get("final"):
        lines.append("- Final report generated after the session became idle.")
    else:
        lines.append(
            "- This snapshot does not include tokens from the response still "
            "being generated."
        )
    return "\n".join(lines) + "\n"


def list_reports() -> int:
    files = sorted(REPORT_DIR.glob("*/*.json"), reverse=True)
    if not files:
        print("No reports found.")
        return 1
    for file in files[:50]:
        try:
            report = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        root = report.get("rootSession", {})
        summary = report.get("summary", {})
        orchestration = report.get("orchestration") or {}
        compliance = (orchestration.get("summary") or {}).get(
            "compliancePct",
            100,
        )
        total_tokens = (summary.get("totalTokens") or {}).get("total")
        print(
            f"{file.stem}\t{root.get('endedAt', '')}\t"
            f"{summary.get('modelsUsed', 0)} models\t"
            f"{format_integer(total_tokens)} tokens\t"
            f"{summary.get('fallbackCount', 0)} fallbacks\t"
            f"{format_percent(compliance)} gate"
        )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read OpenCode Dispatch telemetry reports",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--active",
        action="store_true",
        help="read the active session snapshot",
    )
    source.add_argument(
        "--latest",
        action="store_true",
        help="read the latest final report",
    )
    source.add_argument("--session", help="read a report by session ID")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="print a compact Markdown summary",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print JSON instead of Markdown",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list recent reports",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list:
        return list_reports()
    try:
        json_path = resolve_report_path(args)
        report = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        print(
            f"OpenCode Dispatch: {error}. Complete an OpenCode response first.",
            file=sys.stderr,
        )
        return 1
    except (OSError, json.JSONDecodeError) as error:
        print(f"OpenCode Dispatch: invalid report: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.compact:
        print(compact_report(report), end="")
        return 0
    markdown_path = json_path.with_suffix(".md")
    if json_path.name == "active.json":
        markdown_path = REPORT_DIR / "active.md"
    elif json_path.name == "latest.json":
        markdown_path = REPORT_DIR / "latest.md"
    if markdown_path.exists():
        print(markdown_path.read_text(encoding="utf-8"), end="")
    else:
        print(compact_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
