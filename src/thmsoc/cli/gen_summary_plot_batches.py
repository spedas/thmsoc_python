
# src/thmsoc/cli/gen_summary_plot_batches.py
import argparse
#from thmsoc.dates import parse_date
#from thmsoc.logging_config import setup_logging
from thmsoc.gen_summary_plot_batches import make_plot_batches
from thmsoc.arguments import add_trange_arguments, check_trange_arguments
from thmsoc.arguments import add_summary_plot_arguments, expand_summary_plot_arguments
from thmsoc.arguments import add_probe_arguments, expand_probe_arguments

def main() -> int:
    # Initialize argument parser
    p = argparse.ArgumentParser()

    # Specify date range arguments
    add_trange_arguments(p)

    # Specify L2 data type arguments
    add_summary_plot_arguments(p)

    # Specify days per batch argument
    p.add_argument("-b", "--batch_days", help="Days per batch to process", type=int, default=1)

    # Specify output directory
    p.add_argument("-o", "--output_directory", help="Directory where master list and batch files will be written", required=True)

    # Parse arguments
    args = p.parse_args()

    # Check arguments
    check_trange_arguments(args)

    # Expand L2 types in case 'all' was specified
    summary_plot_types = expand_summary_plot_arguments(args)

    # Run the report
    make_plot_batches(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        days_per_batch=args.batch_days,
        summary_plot_types=summary_plot_types,
        output_directory=args.output_directory
    )

    return 0

if __name__ == "__main__":
    import sys
    sys.argv=["gen_summary_plot_batches","-s","2026-04-14","-d","14","-b","7","--summary_plot_types","all", "--output_directory","/tmp/gen_summary_plot_batches"]
    raise SystemExit(main())