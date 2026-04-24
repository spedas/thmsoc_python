# src/thmsoc/cli/product_volume.py
import argparse
#from thmsoc.dates import parse_date
#from thmsoc.logging_config import setup_logging
from thmsoc.product_volume import run_product_volume
from thmsoc.arguments import add_trange_arguments, check_trange_arguments

def main() -> int:
    # Initialize argument parser
    p = argparse.ArgumentParser()

    # Specify date range arguments
    add_trange_arguments(p)

    # Parse arguments
    args = p.parse_args()

    # Check arguments
    check_trange_arguments(args)

    # Run the report
    run_product_volume(args.start_date, args.end_date, args.days)

    return 0

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Using default time range 2026-04-14 (single day)")
        sys.argv=["product_volume","-s","2026-04-14","-d","1"]
    raise SystemExit(main())