"""Command-line interface for the web traffic report."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
import time

from thmsoc.web_traffic_report import write_report

DEFAULT_LOG = Path("/var/log/httpd/ssl_access_log")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize Apache access log requests from the previous local minute."
    )
    parser.add_argument(
        "-s", "--status", choices=("successful", "unsuccessful", "all"), default="all",
        help="filter by HTTP status: successful = 200, unsuccessful = 4xx or 5xx (default: all)",
    )
    parser.add_argument(
        "--log", type=Path, default=DEFAULT_LOG, metavar="FILE",
        help=f"Apache access log to read (default: {DEFAULT_LOG})",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    previous = datetime.fromtimestamp(time.time() - 60)
    month = MONTHS[previous.month - 1]
    minute = f"{previous.day:02d}/{month}/{previous:%Y:%H:%M}"
    try:
        with args.log.open(encoding="utf-8", errors="replace") as lines:
            write_report(lines, sys.stdout, minute, args.status)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
