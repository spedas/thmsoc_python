# src/thmsoc/cli/cdf_updater.py
import argparse
from thmsoc.cdf_updater import cdf_updater
def main() -> int:
    # Initialize argument parser
    p = argparse.ArgumentParser()

    # Output CDFs:
    p.add_argument("-f", "--outputcdf_fp", help="Output CDF filepath(s)", nargs='*', required=False, type=str, default=None)

    # mastercdf:
    p.add_argument("-m", "--mastercdf_fp", help="Mastercdf CDF filepath", required=False, type=str, default=None)

    # Updates:
    p.add_argument("-u", "--updates", help="Updates dictionary", required=True, type=str)

    # Num parallel jobs
    p.add_argument("-n", "--num_parallel_jobs", help="Total number of jobs to run in parallel, minimum 1", required=False, type=int, default = 1)
    
    # Parse arguments
    args = p.parse_args()
    
    exit_status = 0
    exit_status = cdf_updater(
        outputcdf_fp=args.outputcdf_fp, 
        mastercdf_fp=args.mastercdf_fp, 
        updates=args.updates,
        num_parallel_jobs=args.num_parallel_jobs)
    return exit_status
if __name__ == "__main__":
    raise SystemExit(main())