from datetime import date, datetime
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo("America/Mexico_City")


def datetime_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def business_today() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()


def business_local_date(value: datetime | None) -> date | None:
    """Calendar day in Mexico City for ticket/report grouping."""
    if value is None:
        return None
    if value.tzinfo is None:
        localized = value.replace(tzinfo=BUSINESS_TIMEZONE)
    else:
        localized = value.astimezone(BUSINESS_TIMEZONE)
    return localized.date()
