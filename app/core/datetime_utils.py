from datetime import date, datetime
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo("America/Santiago")


def business_now() -> datetime:
    """Hora actual en Chile; naive para columnas DATETIME en MySQL."""
    return datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None)


def datetime_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    localized = value
    if localized.tzinfo is None:
        localized = localized.replace(tzinfo=BUSINESS_TIMEZONE)
    return localized.isoformat()


def business_today() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()


def business_local_date(value: datetime | None) -> date | None:
    """Día calendario en Chile para tickets e informes."""
    if value is None:
        return None
    if value.tzinfo is None:
        localized = value.replace(tzinfo=BUSINESS_TIMEZONE)
    else:
        localized = value.astimezone(BUSINESS_TIMEZONE)
    return localized.date()
