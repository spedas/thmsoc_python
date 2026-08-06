# src/thmsoc/cli/product_volume.py
import argparse
#from thmsoc.dates import parse_date
#from thmsoc.logging_config import setup_logging
from thmsoc.product_volume import run_product_volume
from thmsoc.arguments import add_trange_arguments, check_trange_arguments

def build_parser() -> argparse.ArgumentParser:
    """Build and return the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Create a report of product data volume over a time range."
    )

    # Specify date range arguments
    add_trange_arguments(parser)

    return parser


def main() -> int:
    p = build_parser()

    # Parse arguments
    args = p.parse_args()

    # Check arguments
    check_trange_arguments(args)

    # Run the report
    run_product_volume(args.start_date, args.end_date, args.days)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
