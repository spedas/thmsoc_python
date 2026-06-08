
# src/thmsoc/cli/gmag_retrieve_usgs_variometer.py
import argparse
from thmsoc.gmag_retrieve_usgs_variometer import run_gmag_retrieve_usgs_variometer
from thmsoc.arguments import add_trange_arguments, check_trange_arguments
from thmsoc.arguments import add_station_arguments, expand_station_arguments

def main() -> int:
    # Initialize argument parser
    p = argparse.ArgumentParser()
    
    # Specify date range arguments
    add_trange_arguments(p)
    # start_date, end_date, days

    # Specify station code arguments
    add_station_arguments(p)
    # station_list

    # Specify sample rate argument:
    p.add_argument("-f", "--sampling_rate", help="Set sampling rate, in Hz", required=False, type=str, default='1')
    # sampling_rate
    
    # Specify MYSQL query filepath:
    p.add_argument("-m", "--db_update_fp_str", help="MYSQL query filepath", required=False, type = str, default="")
    # fp_db_update

    # Specify file output directory:
    p.add_argument("-o", "--output_p_str", help="Directory where retrieved files will be saved", required=False, type = str, default="")

    # Specify failed retrieval list filepath:
    p.add_argument("-i", "--issue_list_fp_str", help="Filepath which will contain list of stations, dates, and issues where retrieval failed.", required=False, type = str, default="")
    # max_num_retries

    # Specify number of retries:
    p.add_argument("-r", "--retries", help="Number of retries to make if initial segment retrieval attempt fails.", required=False, type=int, default=0)
    # max_num_retries

    # Parse arguments
    args = p.parse_args()
    
    # Check arguments
    check_trange_arguments(args)

    # Expand station codes:
    station_codes = expand_station_arguments(args)
    

    exit_status = 0
    # Run the variometer retrieval script:
    exit_status = run_gmag_retrieve_usgs_variometer(
        station_list=station_codes,
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        output_p_str=args.output_p_str,
        issue_list_fp_str=args.issue_list_fp_str,
        db_update_fp_str=args.db_update_fp_str,
        sampling_rate=args.sampling_rate,
        max_num_retries=args.retries
    )
    return exit_status

if __name__ == "__main__":
    import sys
    #sys.argv=["gmag_retrieve_usgs_variometer","-s","2025-11-17","-d","3","-c","anmo","s61a","-f","10","-r","2"]
    #sys.argv=["gmag_retrieve_usgs_variometer","-s","2025-11-17","-d","3","-c","anmo","s61a","-f","1","-r","2"]
    #sys.argv=["gmag_retrieve_usgs_variometer","-s","2026-03-03","-d","3","-c","bouv","-f","1","-r","2"]
    sys.argv=["gmag_retrieve_usgs_variometer","-s","2026-06-01","-d","1","-f","1","-r","2"]
    #sys.argv=["gmag_retrieve_usgs_variometer","-s","2026-06-01","-d","1","-f","10","-r","2"]
    #sys.argv=["gmag_retrieve_usgs_variometer","-s","2026-06-01","-d","1","-c","X48A","-f","10","-r","2"]
    raise SystemExit(main())