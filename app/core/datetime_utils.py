from datetime import datetime


def datetime_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
