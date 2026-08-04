"""Command-line interface for the IP rDNS report."""

import argparse
from contextlib import nullcontext
from pathlib import Path
import sys

from thmsoc.ip_rdns_report import read_sources, write_report


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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        source = args.input.open(encoding="utf-8") if args.input else nullcontext(sys.stdin)
        with source as lines:
            source_counts = read_sources(lines)
        write_report(source_counts, sys.stdout, args.cache, refresh=args.refresh)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
