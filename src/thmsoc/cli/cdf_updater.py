# src/thmsoc/cli/cdf_updater.py
import sys
import argparse
from thmsoc.cdf_updater import cdf_updater
from typing import TextIO

def build_parser() -> argparse.ArgumentParser:
    # Initialize argument parser
    p = argparse.ArgumentParser()
    # Output CDFs:
    p.add_argument("-f", "--outputcdf_fp", help="Output CDF filepath(s)", nargs='*', required=False, type=str, default=None)
    # Output CDF list:
    p.add_argument("-l", "--outputcdflist_fp", help="List containing output CDF filepath(s)", required=False, type=str, default=None)
    # mastercdf:
    p.add_argument("-m", "--mastercdf_fp", help="Mastercdf CDF filepath", required=False, type=str, default=None)
    # Updates:
    p.add_argument("-u", "--updates", help="Updates dictionary", required=True, type=str)
    # Num parallel jobs
    p.add_argument("-n", "--num_parallel_jobs", help="Total number of jobs to run in parallel, minimum 1", required=False, type=int, default = 1)
    return p

def main() -> int: 
    if not isinstance(sys.stdout,TextIO):
        sys.stdout.reconfigure(line_buffering=True)
    else:
        raise AssertionError("stdout must not be TextIO (requires reconfigure attribute)")
    
    # Parse arguments
    args = build_parser().parse_args()
    
    cdf_updater(
        outputcdf_fp=args.outputcdf_fp, 
        outputcdflist_fp=args.outputcdflist_fp,
        mastercdf_fp=args.mastercdf_fp, 
        updates=args.updates,
        num_parallel_jobs=args.num_parallel_jobs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())