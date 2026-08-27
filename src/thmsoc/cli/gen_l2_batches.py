
# src/thmsoc/cli/generate_reprocess_l2_batches.py
import argparse
import sys
#from thmsoc.dates import parse_date
#from thmsoc.logging_config import setup_logging
from thmsoc import make_l2_batches
from thmsoc.arguments import add_trange_arguments, check_trange_arguments
from thmsoc.arguments import add_l2_arguments, expand_l2_arguments
from thmsoc.arguments import add_probe_arguments, expand_probe_arguments

def build_parser() -> argparse.ArgumentParser:
    """Build and return the command-line argument parser."""
    p = argparse.ArgumentParser(
        description="Create IDL batch files for processing THEMIS L2 products."
    )

    # Specify date range arguments
    add_trange_arguments(p)

    # Specify L2 data type arguments
    add_l2_arguments(p)

    # Specify probe arguments
    add_probe_arguments(p)

    # Specify days per batch argument
    p.add_argument("-b", "--batch_days", help="Days per batch to process", type=int, default=1)

    # Specify output directory
    p.add_argument("-o", "--output_directory", help="Directory where master list and batch files will be written", required=True)

    return p


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    args = build_parser().parse_args()

    # Check arguments
    check_trange_arguments(args)

    # Expand L2 types in case 'all' was specified
    l2_types = expand_l2_arguments(args)

    # Expand probes in case 'all' was specified
    probes = expand_probe_arguments(args)

    # Run the report
    make_l2_batches(start_date=args.start_date, end_date=args.end_date, days=args.days, days_per_batch=args.batch_days, l2_types=l2_types, probes=probes, output_directory=args.output_directory)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
