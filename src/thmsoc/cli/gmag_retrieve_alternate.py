# src/thmsoc/cli/gmag_retrieve_alternate.py
import argparse
from thmsoc.gmag_retrieve_alternate import run_gmag_retrieve_alternate
from thmsoc.arguments import add_trange_arguments, check_trange_arguments

"""
run_gmag_retrieve_alternate(
    station_code:str | list[str], 
    start_date: str, 
    end_date: str,
    mirror_dir:str | Path | None = None,
    issue_list_fp: str | Path | None = None)
"""

def main() -> int:
    # Initialize argument parser
    p = argparse.ArgumentParser()
    
    # Specify date range arguments
    add_trange_arguments(p)
    # start_date, end_date, days

    # Specify station code arguments
    p.add_argument("-c","--station_codes", help="Stations to process, as THEMIS station code alias", nargs='*', choices=['snkq','lrv'], type=str.lower, default=['snkq','lrv'])
    
    # Specify MYSQL query filepath:
    p.add_argument("-m", "--mirror_dir", help="Directory for mirroring raw data", required=False, type = str)
    
    # Specify failed retrieval list filepath:
    p.add_argument("-i", "--issue_list_fp", help="Filepath which will contain list of stations, dates, and issues where retrieval failed.", required=False, type = str, default="")
    # max_num_retries

    # Parse arguments
    args = p.parse_args()
    
    # Check arguments
    check_trange_arguments(args)

    exit_status = 0
    # Run the variometer retrieval script:
    exit_status = run_gmag_retrieve_alternate(
        station_code=args.station_codes,
        start_date=args.start_date,
        end_date=args.end_date,
        mirror_dir=args.mirror_dir,
        issue_list_fp=args.issue_list_fp
    )
    return exit_status

if __name__ == "__main__":
    raise SystemExit(main())