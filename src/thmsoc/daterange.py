from datetime import date, timedelta

def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
