from datetime import date, datetime, timedelta, timezone
from typing import Optional, Union
from dcicutils.datetime_utils import parse_datetime_string as dcicutils_parse_datetime_string


def convert_uptime_to_datetime(uptime: str, relative_to: datetime = None) -> Optional[datetime]:
    """
    Converts the given duration string which (happens to be) from the Portal health endpoint
    into its equivalent datetime. Format of the given upatime looks something like this:

      1 week, 2 days, 3 hours, 4 minutes, 5.67 seconds

    If the given uptime is not parsable then returns None, otherwise returns the datetime corresponding
    to this uptime, relative to now, by default, or to the relative_to datetime argument if given.
    We THINK it's right to interpret the given uptime relative to UTC (TODO).
    """
    def normalize_spaces(s: str) -> str:
        return " ".join(s.split())

    if not uptime:
        return None
    try:
        minutes_per_hour = 60
        minutes_per_day = minutes_per_hour * 24
        minutes_per_week = minutes_per_day * 7
        minutes = 0
        seconds = 0
        uptime = normalize_spaces(uptime)
        for item in uptime.split(","):
            item = item.strip()
            if item:
                item = item.split(" ")
                if len(item) == 2:
                    unit = item[1].lower()
                    value = float(item[0])
                    if unit.startswith("week"):
                        minutes += minutes_per_week * value
                    elif unit.startswith("day"):
                        minutes += minutes_per_day * value
                    elif unit.startswith("hour"):
                        minutes += minutes_per_hour * value
                    elif unit.startswith("minute"):
                        minutes += value
                    elif unit.startswith("second"):
                        seconds += value
        t = relative_to if relative_to else datetime.now(timezone.utc)
        return t + timedelta(minutes=-minutes, seconds=-seconds)
    except Exception:
        pass
    return None


def format_duration(seconds: Union[int, float, timedelta], verbose: bool = False) -> str:
    if verbose is True:
        return format_duration_verbose(seconds)
    if isinstance(seconds, timedelta):
        seconds = seconds.total_seconds()
    days = (duration := timedelta(seconds=seconds)).days
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}-{hours:02}:{minutes:02}:{seconds:02}"
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def format_duration_verbose(seconds: Union[int, float, timedelta]) -> str:
    if isinstance(seconds, timedelta):
        seconds = seconds.total_seconds()
    seconds_actual = seconds
    seconds = round(max(seconds, 0))
    durations = [("year", 31536000), ("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1)]
    parts = []
    for name, duration in durations:
        if (seconds == 0) or (seconds >= duration):
            count = seconds // duration
            seconds %= duration
            if count != 1:
                name += "s"
            parts.append(f"{count} {name}")
    if len(parts) == 0:
        return f"{seconds_actual:.1f} seconds"
    elif len(parts) == 1:
        return f"{seconds_actual:.1f} seconds"
    return " ".join(parts[:-1]) + " " + parts[-1]


def parse_datetime_string(value: str) -> Optional[datetime]:
    if isinstance(value, str) and (len(value) == 8) and value.isdigit():
        # Very special case to accept for example "20241206" to mean "2024-12-06".
        value = f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    elif isinstance(value, datetime):
        return value
    elif isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return dcicutils_parse_datetime_string(value)
