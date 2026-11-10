"""Command-line interface for the web traffic report."""

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import time

from thmsoc.web_traffic_report import RegexFilters, write_report

DEFAULT_LOG = Path("/var/log/httpd/ssl_access_log")
SAVE_FIELDS = ("matches", "ips", "user_agents", "urls", "referer")


def positive_minutes(value: str) -> int:
    minutes = int(value)
    if minutes < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return minutes


def iso_timestamp(value: str) -> float:
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        timestamp = datetime.fromisoformat(normalized).timestamp()
        datetime.fromtimestamp(timestamp, timezone.utc)
        return timestamp
    except (ValueError, OverflowError, OSError) as exc:
        raise argparse.ArgumentTypeError("expected an ISO 8601 date or timestamp") from exc


def regex_pattern(value: str) -> re.Pattern[str]:
    try:
        return re.compile(value)
    except (re.error, OverflowError) as exc:
        raise argparse.ArgumentTypeError(f"invalid regular expression: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize Apache access log requests (default: entire file)."
    )
    parser.add_argument(
        "-s", "--status", choices=("successful", "unsuccessful", "all"), default="all",
        help="filter by HTTP status: successful = 200, unsuccessful = 4xx or 5xx (default: all)",
    )
    parser.add_argument(
        "--log", type=Path, default=DEFAULT_LOG, metavar="FILE",
        help=f"Apache access log to read (default: {DEFAULT_LOG})",
    )
    parser.add_argument(
        "--ip", action="append", default=[], metavar="PATTERN",
        help="source IP substring or quoted shell glob; repeat to require every pattern",
    )
    for field, label in (
        ("url", "request URL"), ("user_agent", "user agent"), ("referer", "referer"),
    ):
        parser.add_argument(
            f"--{field}", action="append", type=regex_pattern, metavar="REGEX",
            help=f"require a regex match anywhere in the {label}; repeatable",
        )
        parser.add_argument(
            f"--not_{field}", action="append", type=regex_pattern, metavar="REGEX",
            help=f"exclude requests with a regex match anywhere in the {label}; repeatable",
        )
    parser.add_argument(
        "--latest", type=positive_minutes, metavar="N",
        help="include the last N complete minutes, excluding the current minute",
    )
    parser.add_argument(
        "--start_time", type=iso_timestamp, metavar="TIME",
        help="inclusive ISO 8601 start time; local time if no offset is given",
    )
    parser.add_argument(
        "--end_time", type=iso_timestamp, metavar="TIME",
        help="exclusive ISO 8601 end time; local time if no offset is given",
    )
    for field in SAVE_FIELDS:
        label = "referer strings" if field == "referer" else field.replace("_", " ")
        help_text = (
            "save original matching log lines"
            if field == "matches"
            else f"save distinct {label} with counts; preview the top 25"
        )
        parser.add_argument(f"--save_{field}", type=Path, metavar="FILE", help=help_text)
    return parser


def validate_output_paths(source: Path, destinations: list[Path]) -> None:
    """Reject aliased paths before opening any output for writing."""
    paths = [source, *destinations]
    for index, path in enumerate(paths):
        for other in paths[:index]:
            if path.resolve() == other.resolve() or (
                path.exists() and other.exists() and path.samefile(other)
            ):
                raise ValueError(f"input and output files must be distinct: {path} and {other}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    has_start = args.start_time is not None
    has_end = args.end_time is not None
    time_range = None
    if args.latest is not None:
        if has_start or has_end:
            parser.error("--latest cannot be combined with --start_time or --end_time")
        end = int(time.time() // 60) * 60
        start = end - args.latest * 60
        try:
            datetime.fromtimestamp(start, timezone.utc)
        except (ValueError, OverflowError, OSError):
            parser.error("--latest is too large")
        time_range = (start, end)
    elif has_start or has_end:
        if not (has_start and has_end):
            parser.error("--start_time and --end_time must be supplied together")
        if args.start_time >= args.end_time:
            parser.error("--start_time must be earlier than --end_time")
        time_range = (args.start_time, args.end_time)
    try:
        paths = {
            f"save_{field}": path for field in SAVE_FIELDS
            if (path := getattr(args, f"save_{field}")) is not None
        }
        validate_output_paths(args.log, list(paths.values()))
        with ExitStack() as stack:
            lines = stack.enter_context(args.log.open(
                encoding="utf-8", errors="surrogateescape", newline="",
            ))
            destinations = {
                name: stack.enter_context(path.open(
                    "w", encoding="utf-8", errors="surrogateescape", newline="",
                ))
                for name, path in paths.items()
            }
            write_report(
                lines, sys.stdout, args.status, time_range=time_range,
                ip_filters=tuple(args.ip),
                url_filters=RegexFilters(tuple(args.url or ()), tuple(args.not_url or ())),
                user_agent_filters=RegexFilters(
                    tuple(args.user_agent or ()), tuple(args.not_user_agent or ()),
                ),
                referer_filters=RegexFilters(
                    tuple(args.referer or ()), tuple(args.not_referer or ()),
                ),
                **destinations,
            )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
