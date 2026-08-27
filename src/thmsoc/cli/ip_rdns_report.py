"""Command-line interface for the IP rDNS report."""

import argparse
from contextlib import nullcontext
from pathlib import Path
import sys

from thmsoc.ip_rdns_report import read_sources, write_report


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate IPv4 addresses and hostnames by rDNS base domain."
    )
    parser.add_argument("-i", "--input", type=Path, metavar="FILE",
                        help="read input from FILE instead of standard input")
    parser.add_argument("--cache", type=Path, default=Path(".ip-rdns-cache.json"),
                        help="persistent rDNS cache (default: .ip-rdns-cache.json)")
    parser.add_argument("--refresh", action="store_true",
                        help="ignore cached rDNS lookups")
    parser.add_argument("--domain-level", choices=("second", "top"), default="second",
                        help="domain level used for aggregation (default: second)")
    parser.add_argument("--max-hostnames", type=nonnegative_int, default=10,
                        help="maximum hostnames listed per row (default: 10)")
    return parser


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    args = build_parser().parse_args()
    try:
        source = args.input.open(encoding="utf-8") if args.input else nullcontext(sys.stdin)
        with source as lines:
            source_counts = read_sources(lines)
        write_report(source_counts, sys.stdout, args.cache, refresh=args.refresh,
                     domain_level=args.domain_level, max_hostnames=args.max_hostnames)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
