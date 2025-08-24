import jdatetime
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # Python 3.9+

def jalali_to_gregorian(jalali_date: str, time_str: str) -> datetime:
    """
    Convert Jalali date (YYYY/MM/DD) + time (HH:MM) → Python datetime in UTC
    """
    year, month, day = map(int, jalali_date.split("/"))
    hour, minute = map(int, time_str.split(":"))
    jdt = jdatetime.datetime(year, month, day, hour, minute)
    gdt = jdt.togregorian()
    tehran_time = gdt.replace(tzinfo=ZoneInfo("Asia/Tehran"))
    return tehran_time.astimezone(timezone.utc)

a = jalali_to_gregorian("1404/06/31", "12:00")
print(a)