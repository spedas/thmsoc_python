from datetime import date, timedelta, datetime

def args_to_startend(start_date=None, end_date=None, days=None)->tuple[date, date]:
    if days is None:
        # Must have start date and end date
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif end_date is None:
        # Must have start date and duration
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = start + timedelta(days=days-1)
    elif start_date is None:
        # Must have end date and duration
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        start = end - timedelta(days=days-1)
    else:
        raise ValueError("Must supply at least two of start_date, end_date, or days")
    return (start,end)

def daterange(start: date, end: date):
    if end < start:
        raise ValueError("End date must be greater than start date")
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
