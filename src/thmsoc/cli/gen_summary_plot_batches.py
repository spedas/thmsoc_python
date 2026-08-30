
# src/thmsoc/cli/gen_summary_plot_batches.py
import argparse
import sys
#from thmsoc.dates import parse_date
#from thmsoc.logging_config import setup_logging
from thmsoc.gen_summary_plot_batches import DEFAULT_PLOT_DIR, make_plot_batches
from thmsoc.arguments import add_trange_arguments, check_trange_arguments
from thmsoc.arguments import add_summary_plot_arguments, expand_summary_plot_arguments
from thmsoc.arguments import add_probe_arguments, expand_probe_arguments

def build_parser() -> argparse.ArgumentParser:
    """Build and return the command-line argument parser."""
    p = argparse.ArgumentParser(
        description="Create IDL batch files for processing THEMIS summary plots."
    )

    # Specify date range arguments
    add_trange_arguments(p)

    # Specify L2 data type arguments
    add_summary_plot_arguments(p)

    # Specify probe arguments
    add_probe_arguments(p, required=False, default=["all"])

    # Specify days per batch argument
    p.add_argument("-b", "--batch_days", help="Days per batch to process", type=int, default=1)

    # Specify output directory
    p.add_argument("-o", "--output_directory", help="Directory where master list and batch files will be written", required=True)

    # Specify plot output directory
    p.add_argument(
        "--plot_dir",
        help="Parent directory where summary plots will be written",
        default=DEFAULT_PLOT_DIR,
    )

    # Install plots directly in the database
    p.add_argument(
        "-i",
        "--install",
        help="Add /direct_to_dbase to thm_over_shell calls",
        action="store_true",
    )

    return p


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    args = build_parser().parse_args()

    # Check arguments
    check_trange_arguments(args)

    # Expand L2 types in case 'all' was specified
    summary_plot_types = expand_summary_plot_arguments(args)

    # Expand probes in case 'all' was specified
    probes = expand_probe_arguments(args)

    # Run the report
    make_plot_batches(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        days_per_batch=args.batch_days,
        summary_plot_types=summary_plot_types,
        probes=probes,
        output_directory=args.output_directory,
        plot_dir=args.plot_dir,
        install=args.install,
    )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
