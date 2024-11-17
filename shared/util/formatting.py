from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def format_timedelta(start_time: datetime, end_time: datetime, *, precision: int = 3, exclude_zeros: bool = False):
    if int((end_time - start_time).total_seconds()) == 0:
        return "0s"

    delta = relativedelta(end_time, start_time)

    # Some mild rounding
    if delta.seconds % 60 == 59:
        delta += timedelta(seconds=1)
    elif delta.seconds % 60 == 1:
        delta += timedelta(seconds=-1)

    times = [
        (delta.years, "y"),
        (delta.months, "mo"),
        (delta.days, "d"),
        (delta.hours, "h"),
        (delta.minutes, "m"),
        (delta.seconds, "s"),
    ]
    precision = min(max(precision, 1), len(times))
    i = 0
    while times[i][0] == 0:
        i += 1
    times = times[i : precision + i]

    if exclude_zeros:
        times = [time for time in times if time[0] != 0]

    return ", ".join([f"{time[0]}{time[1]}" for time in times])
