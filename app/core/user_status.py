"""IDs de la tabla statuses usados en users (Abierto / Cerrado)."""

STATUS_ABIERTO_ID = 2
STATUS_CERRADO_ID = 1


def status_id_from_active(active: bool) -> int:
    return STATUS_ABIERTO_ID if active else STATUS_CERRADO_ID


def active_from_status_id(status_id: int | None) -> bool:
    if status_id is None:
        return True
    return status_id != STATUS_CERRADO_ID
