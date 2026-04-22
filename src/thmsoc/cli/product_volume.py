# src/thmsoc/cli/product_volume.py
import argparse
#from thmsoc.dates import parse_date
#from thmsoc.logging_config import setup_logging
from thmsoc.product_volume import run_product_volume

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("start_date")
    p.add_argument("end_date")
    p.add_argument("-v", "--verbose", action="store_true")
    return p

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    #setup_logging(verbose=args.verbose)

    #start = parse_date(args.start_date)
    #end = parse_date(args.end_date)
    run_product_volume(args.start_date, args.end_date)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())