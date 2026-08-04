"""Command-line interface for the IP ownership report."""

import argparse
from contextlib import nullcontext
import sys
from pathlib import Path

from thmsoc.ip_owner_report import LookupError, read_addresses, write_report


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Group IPv4 request addresses by RDAP owner and routed origin ASN."
    )
    parser.add_argument("-i", "--input", type=Path, metavar="FILE",
                        help="read input from FILE instead of standard input")
    parser.add_argument("--hostnames", choices=("ignore", "resolve", "error"),
                        default="ignore",
                        help="how to handle hostnames (default: ignore)")
    parser.add_argument("--cache", type=Path, default=Path(".ip-owner-cache.json"),
                        help="persistent lookup cache (default: .ip-owner-cache.json)")
    parser.add_argument("--refresh", action="store_true", help="ignore cached lookups")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=nonnegative_int, default=8,
                        help="retries for rate limits and transient failures (default: 8)")
    parser.add_argument("--request-delay", type=nonnegative_float, default=0.25,
                        help="minimum seconds between requests to one host (default: 0.25)")
    parser.add_argument("--strict-lookups", action="store_true",
                        help="stop instead of reporting UNKNOWN when an external lookup fails")
    parser.add_argument("--ca-bundle", type=Path,
                        help="PEM CA bundle for HTTPS certificate verification")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        source = args.input.open(encoding="utf-8") if args.input else nullcontext(sys.stdin)
        with source as lines:
            address_counts = read_addresses(lines, args.hostnames)
        write_report(address_counts, sys.stdout, args.cache, refresh=args.refresh,
                     timeout=args.timeout, strict_lookups=args.strict_lookups,
                     ca_bundle=args.ca_bundle, retries=args.retries,
                     request_delay=args.request_delay)
    except (ValueError, LookupError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
