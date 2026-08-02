"""Command-line interface for the IP ownership report."""

import argparse
import sys
from pathlib import Path

from thmsoc.ip_owner_report import LookupError, read_addresses, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Group IPv4 request addresses by RDAP owner and routed origin ASN."
    )
    parser.add_argument("--cache", type=Path, default=Path(".ip-owner-cache.json"),
                        help="persistent lookup cache (default: .ip-owner-cache.json)")
    parser.add_argument("--refresh", action="store_true", help="ignore cached lookups")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument("--strict-lookups", action="store_true",
                        help="stop instead of reporting UNKNOWN when an external lookup fails")
    parser.add_argument("--ca-bundle", type=Path,
                        help="PEM CA bundle for HTTPS certificate verification")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        write_report(read_addresses(sys.stdin), sys.stdout, args.cache, refresh=args.refresh,
                     timeout=args.timeout, strict_lookups=args.strict_lookups,
                     ca_bundle=args.ca_bundle)
    except (ValueError, LookupError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
