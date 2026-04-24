import argparse


def add_trange_arguments(p:argparse.ArgumentParser) -> None:
    p.add_argument("-s", "--start_date", help="start date (YYYY-MM-DD)", default=None)
    p.add_argument("-e","--end_date", help="end date (YYYY-MM-DD)", default=None)
    p.add_argument("-d","--days", help="Duration (days)", type=int, default=None)

def check_trange_arguments(args:argparse.Namespace) -> bool:
    # check argument count
    count=0
    if args.start_date is not None:
        count+=1
    if args.end_date is not None:
        count+=1
    if args.days is not None:
        count +=1
    if count < 2:
        raise ValueError("At least two of start_date, end_date, or days must be specified")
    if args.days is not None and args.days < 1:
        raise ValueError("days must be positive")
    return True