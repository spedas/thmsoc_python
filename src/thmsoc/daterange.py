from datetime import date, timedelta, datetime

def args_to_startend(start_date=None, end_date=None, days=None)->tuple[date, date]:
    if (start_date is not None) and (end_date is not None):
        # start date and end date provided; value of days is ignored
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif (start_date is not None) and (days is not None):
        # start date and duration provided
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = start + timedelta(days=days-1)
    elif (end_date is not None) and (days is not None):
        # end date and duration provided
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        start = end - timedelta(days=days-1)
    else:
        raise ValueError("Must supply at least two of start_date, end_date, or days")
    return (start,end)

def simple_daterange(start: date, end: date):
    if end < start:
        raise ValueError("End date must be greater than start date")
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)

def batch_daterange(start:date, end:date, days_per_batch:int=1):
    if end < start:
        raise ValueError("End date must be greater than start date")
    current = start
    while current <= end:
        batch_date = current
        nbatch=1
        return_list = []
        while (batch_date <= end) and (nbatch <= days_per_batch):
            return_list.append(batch_date)
            nbatch +=1
            batch_date += timedelta(days=1)
        yield return_list
        current += timedelta(days=days_per_batch)

def datelist_to_string(datelist:list[date])->list[str]:
    str_list = [date.strftime("%Y-%m-%d") for date in datelist]
    return str_list
