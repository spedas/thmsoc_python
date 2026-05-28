
# src/thmsoc/cli/gmag_retrieve_usgs_variometer.py
import argparse
#from thmsoc.dates import parse_date
#from thmsoc.logging_config import setup_logging
from thmsoc.gmag_retrieve_usgs_variometer import retrieve_files
from thmsoc.arguments import add_trange_arguments, check_trange_arguments
from thmsoc.arguments import add_station_arguments

def main() -> int:
    # Initialize argument parser
    p = argparse.ArgumentParser()
    
    # Specify date range arguments
    add_trange_arguments(p)
    # Specify station code arguments
    add_station_arguments(p)
    # Specify sample rate argument
    p.add_argument("-h", "--sampling_rate", help="Set sampling rate, in Hz",required=True, type=int, default=1)
    p.add_argument("-m", "--fp_db_update", help="MYSQL query filepath",required=True)
    # Specify output directory
    p.add_argument("-o", "--output_directory", help="Directory where retrieved files will be saved",required=True)

    # Parse arguments
    args = p.parse_args()

    # Check arguments
    check_trange_arguments(args)

    # Run the report
    retrieve_files(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        station_list=args.station_codes,
        sampling_rate=args.sampling_rate,
        fp_db_update=args.fp_db_update,
        output_directory=args.output_directory
    )

    return 0

if __name__ == "__main__":
    import sys
    sys.argv=["gmag_retrieve_usgs_variometer","-s","2025-11-17","-d","3","-c","['anmo','s61a']","-h","10"]
    raise SystemExit(main())